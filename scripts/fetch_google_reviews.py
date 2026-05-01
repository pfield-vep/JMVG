"""
scripts/fetch_google_reviews.py
===============================
Fetches Google Maps reviews for all JM Valley Group stores via the
Google Places API (Legacy) and stores them in the store_reviews table.

The Google Places API returns up to 5 most recent reviews per call.
Run this daily to accumulate a growing review history over time — each
new call captures any reviews posted since the last run.

Usage
-----
  py scripts/fetch_google_reviews.py --discover   # find Google Place IDs (run once)
  py scripts/fetch_google_reviews.py --fetch      # pull latest reviews (run daily)
  py scripts/fetch_google_reviews.py --update     # alias for --fetch

API Key Setup
-------------
Add your Google Places API key to .streamlit/secrets.toml:

    [google]
    places_api_key = "AIzaSy..."

Or set environment variable:  GOOGLE_PLACES_API_KEY=AIzaSy...

The key needs the "Places API" enabled in Google Cloud Console.
Free tier: 5,000 Place Details calls/month (~$0 for our 29 stores running daily).
"""

import os, sys, time, json, hashlib
from datetime import date, datetime
from urllib.request import urlopen
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PLACES_BASE = "https://maps.googleapis.com/maps/api/place"


# ── API Key ───────────────────────────────────────────────────────────────────

def get_api_key():
    """Try .streamlit/secrets.toml → environment variable."""
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(secrets_path, "rb") as f:
            cfg = tomllib.load(f)
        key = (cfg.get("google", {}).get("places_api_key") or
               cfg.get("GOOGLE_PLACES_API_KEY") or "")
        if key:
            return key.strip()
    return os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()


# ── DB connection (same pattern as all other scripts) ─────────────────────────

def get_conn():
    import psycopg2

    env_host = os.environ.get("SUPABASE_HOST")
    if env_host:
        try:
            conn = psycopg2.connect(
                host=env_host,
                port=int(os.environ.get("SUPABASE_PORT", "5432")),
                dbname=os.environ.get("SUPABASE_DBNAME", "postgres"),
                user=os.environ.get("SUPABASE_USER"),
                password=os.environ.get("SUPABASE_PASSWORD"),
                sslmode="require",
            )
            print("Connected to Supabase via environment variables")
            return conn, "postgres"
        except Exception as e:
            print(f"⚠️  Supabase (env) failed: {e}")

    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(secrets_path, "rb") as f:
            cfg = tomllib.load(f)
        if "supabase" in cfg:
            try:
                s = cfg["supabase"]
                conn = psycopg2.connect(
                    host=s["host"], port=int(s["port"]),
                    dbname=s["dbname"], user=s["user"],
                    password=s["password"], sslmode="require"
                )
                print("Connected to Supabase / Postgres")
                return conn, "postgres"
            except Exception as e:
                print(f"⚠️  Supabase failed ({e}), falling back to SQLite…")

    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"


# ══════════════════════════════════════════════════════════════════════════════
# TABLE DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

CREATE_REVIEWS_PG = """
CREATE TABLE IF NOT EXISTS store_reviews (
    id                SERIAL  PRIMARY KEY,
    store_id          TEXT    NOT NULL,
    review_id         TEXT    NOT NULL UNIQUE,   -- sha1 hash of store+reviewer+time
    platform          TEXT    NOT NULL DEFAULT 'google',
    reviewer_name     TEXT,
    rating            INTEGER NOT NULL,           -- 1–5 stars
    review_text       TEXT,
    review_date       DATE,                       -- from Unix timestamp in API
    fetched_at        TIMESTAMP DEFAULT NOW(),
    -- Phase 2: LLM topic classification (populated by classify_reviews.py)
    topic_speed       INTEGER,    -- 1 if review mentions wait time / speed
    topic_accuracy    INTEGER,    -- 1 if mentions order accuracy / wrong order
    topic_staff       INTEGER,    -- 1 if mentions staff attitude / friendliness
    topic_food        INTEGER,    -- 1 if mentions food quality / freshness
    topic_cleanliness INTEGER,    -- 1 if mentions cleanliness / store condition
    topic_online      INTEGER,    -- 1 if mentions app / online ordering / delivery
    sentiment         TEXT,       -- 'positive', 'negative', 'neutral'
    classified_at     TIMESTAMP
)"""

CREATE_REVIEWS_SQLITE = CREATE_REVIEWS_PG.replace(
    "SERIAL  PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT"
).replace("DEFAULT NOW()", "DEFAULT CURRENT_TIMESTAMP")

# Columns to add to the existing stores table
STORES_NEW_COLS = [
    ("google_place_id",       "TEXT"),      # Google Maps Place ID (e.g. ChIJ...)
    ("google_rating",         "REAL"),      # current overall star rating
    ("google_review_count",   "INTEGER"),   # total reviews on Google Maps
    ("google_rating_updated", "TEXT"),      # ISO date of last rating refresh
]


def create_tables(conn, dialect):
    """Create store_reviews and patch stores table with google_* columns."""
    cur = conn.cursor()

    # store_reviews
    cur.execute(CREATE_REVIEWS_PG if dialect == "postgres" else CREATE_REVIEWS_SQLITE)

    # Add google_* columns to stores (idempotent)
    for col, dtype in STORES_NEW_COLS:
        if dialect == "postgres":
            cur.execute(f"ALTER TABLE stores ADD COLUMN IF NOT EXISTS {col} {dtype}")
        else:
            try:
                cur.execute(f"ALTER TABLE stores ADD COLUMN {col} {dtype}")
            except Exception:
                conn.rollback()

    conn.commit()
    print("store_reviews table ready + stores.google_* columns ensured")


# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE PLACES API HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def places_get(endpoint, params):
    """GET https://maps.googleapis.com/maps/api/place/<endpoint>/json?..."""
    url = f"{PLACES_BASE}/{endpoint}/json?{urlencode(params)}"
    with urlopen(url, timeout=15) as resp:
        return json.loads(resp.read())


def discover_place_id(store_id, address, api_key):
    """
    Use Places Text Search to find the Google Place ID for one store.
    Query format: "Jersey Mike's <address>" — very reliable for chain locations.
    Returns place_id string, or None if not found.
    """
    query = f"Jersey Mike's Subs {address}" if address else f"Jersey Mike's store {store_id}"
    try:
        data = places_get("textsearch", {
            "query": query,
            "key":   api_key,
            "type":  "restaurant",
        })
        results = data.get("results", [])
        if not results:
            print(f"  {store_id}: no results for '{query}'")
            return None
        place  = results[0]
        pid    = place.get("place_id")
        name   = place.get("name", "")
        addr   = place.get("formatted_address", "")
        print(f"  {store_id}: '{name}' at {addr} → {pid}")
        return pid
    except Exception as e:
        print(f"  {store_id}: Text Search error — {e}")
        return None


def fetch_place_detail(place_id, api_key):
    """
    Fetch Place Details: name, rating, user_ratings_total, reviews (up to 5).
    Returns the 'result' dict from the API, or None on error.
    """
    try:
        data = places_get("details", {
            "place_id":     place_id,
            "fields":       "name,rating,user_ratings_total,reviews",
            "key":          api_key,
            "language":     "en",
            "reviews_sort": "newest",
        })
        status = data.get("status")
        if status != "OK":
            print(f"  ⚠️  Places Details status: {status}")
            return None
        return data.get("result", {})
    except Exception as e:
        print(f"  ⚠️  Places Details error: {e}")
        return None


def make_review_id(store_id, reviewer, ts):
    """
    Generate a stable 16-char unique ID for a review.
    Google's legacy API doesn't expose a native review ID, so we hash
    (store_id, reviewer_name, unix_timestamp) which is effectively unique.
    """
    raw = f"{store_id}|{reviewer}|{ts}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


# ══════════════════════════════════════════════════════════════════════════════
# UPSERT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def upsert_review(cur, dialect, store_id, rev):
    """
    Insert one review into store_reviews.  Skips silently if review_id
    already exists (ON CONFLICT DO NOTHING / INSERT OR IGNORE).
    Returns 1 if inserted, 0 if skipped.
    """
    p  = "%s" if dialect == "postgres" else "?"
    ts = rev.get("time", 0)
    reviewer  = rev.get("author_name", "")
    rid       = make_review_id(store_id, reviewer, ts)
    rating    = rev.get("rating", 0)
    text      = rev.get("text", "")
    rev_date  = date.fromtimestamp(ts).isoformat() if ts else None

    if dialect == "postgres":
        sql = (
            f"INSERT INTO store_reviews "
            f"    (store_id, review_id, platform, reviewer_name, rating, review_text, review_date) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p}) "
            f"ON CONFLICT (review_id) DO NOTHING"
        )
    else:
        sql = (
            f"INSERT OR IGNORE INTO store_reviews "
            f"    (store_id, review_id, platform, reviewer_name, rating, review_text, review_date) "
            f"VALUES ({p},{p},{p},{p},{p},{p},{p})"
        )
    cur.execute(sql, (store_id, rid, "google", reviewer, rating, text, rev_date))
    return cur.rowcount


def update_store_meta(cur, dialect, store_id, rating, review_count):
    """Refresh the google_rating + google_review_count snapshot on the store row."""
    p = "%s" if dialect == "postgres" else "?"
    today = date.today().isoformat()
    cur.execute(
        f"UPDATE stores SET "
        f"  google_rating={p}, "
        f"  google_review_count={p}, "
        f"  google_rating_updated={p} "
        f"WHERE store_id={p}",
        (rating, review_count, today, store_id)
    )


# ══════════════════════════════════════════════════════════════════════════════
# DISCOVER  (run once — maps store addresses → google_place_id)
# ══════════════════════════════════════════════════════════════════════════════

def discover_all_place_ids():
    """
    For every store without a google_place_id, call the Places Text Search
    API to find one and save it.  Safe to re-run — skips stores already mapped.
    """
    api_key = get_api_key()
    if not api_key:
        print("❌  No Google Places API key found.")
        print("    Add to .streamlit/secrets.toml:  [google] / places_api_key = 'AIza...'")
        return

    conn, dialect = get_conn()
    create_tables(conn, dialect)
    cur = conn.cursor()

    # Load stores that still need a place_id
    try:
        cur.execute("""
            SELECT store_id, address
            FROM   stores
            WHERE  (google_place_id IS NULL OR google_place_id = '')
            ORDER  BY store_id
        """)
        stores = cur.fetchall()
    except Exception as e:
        print(f"❌  Could not query stores: {e}")
        conn.close()
        return

    if not stores:
        print("✓  All stores already have a Google Place ID.")
        conn.close()
        return

    print(f"Discovering Place IDs for {len(stores)} stores…")
    p = "%s" if dialect == "postgres" else "?"
    found = 0

    for store_id, address in stores:
        if not address:
            print(f"  {store_id}: no address in DB — skipping (add address via update_stores.py first)")
            continue
        pid = discover_place_id(store_id, address, api_key)
        if pid:
            cur.execute(
                f"UPDATE stores SET google_place_id = {p} WHERE store_id = {p}",
                (pid, store_id)
            )
            conn.commit()
            found += 1
        time.sleep(0.35)   # stay well within the free quota

    conn.close()
    print(f"\nDone — {found}/{len(stores)} stores now have a Google Place ID.")
    if found < len(stores):
        print("  Stores with no address will need their google_place_id set manually.")
        print("  UPDATE stores SET google_place_id='ChIJ...' WHERE store_id='XXXXX';")


# ══════════════════════════════════════════════════════════════════════════════
# FETCH  (run daily to accumulate reviews)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_all_reviews(log=None):
    """
    For every store with a google_place_id, fetch the 5 most recent reviews
    and upsert them into store_reviews.  Fully idempotent — duplicates skipped.

    `log` is an optional callable(str) for streaming output to a UI logger.
    Falls back to print() if None.
    """
    def out(msg):
        if log:
            log(msg)
        else:
            print(msg)

    api_key = get_api_key()
    if not api_key:
        out("❌  No Google Places API key found.")
        out("    Add to .streamlit/secrets.toml:  [google] / places_api_key = 'AIza...'")
        return 0, 0

    conn, dialect = get_conn()
    create_tables(conn, dialect)
    cur = conn.cursor()

    # Stores with a known Place ID
    cur.execute("""
        SELECT store_id, google_place_id
        FROM   stores
        WHERE  google_place_id IS NOT NULL AND google_place_id != ''
        ORDER  BY store_id
    """)
    stores = cur.fetchall()

    if not stores:
        out("No stores have a Google Place ID yet — run --discover first.")
        conn.close()
        return 0, 0

    out(f"Fetching reviews for {len(stores)} stores…")
    total_new   = 0
    total_stores = 0

    for store_id, place_id in stores:
        result = fetch_place_detail(place_id, api_key)
        if result is None:
            out(f"  {store_id}: ⚠️  no data returned")
            time.sleep(0.5)
            continue

        rating       = result.get("rating")
        review_count = result.get("user_ratings_total")
        reviews      = result.get("reviews") or []

        # Update the star-rating snapshot on the store row
        if rating is not None:
            update_store_meta(cur, dialect, store_id, rating, review_count)

        new_count = sum(upsert_review(cur, dialect, store_id, r) for r in reviews)
        total_new   += new_count
        total_stores += 1

        stars = f"★{rating:.1f}" if rating else "★?"
        total_str = f"{review_count:,}" if review_count else "?"
        out(f"  {store_id}: {stars}  {total_str} total on Google  +{new_count} new in DB")

        conn.commit()
        time.sleep(0.3)

    conn.close()
    out(f"\nDone — {total_new} new reviews stored across {total_stores} stores.")
    return total_new, total_stores


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY STATS  (used by Update Data page status display)
# ══════════════════════════════════════════════════════════════════════════════

def get_review_stats(conn, dialect):
    """
    Returns dict with:
      total_reviews, latest_review_date, stores_with_reviews,
      stores_with_place_id, avg_rating
    """
    cur = conn.cursor()
    stats = {
        "total_reviews":       0,
        "latest_review_date":  None,
        "stores_with_reviews": 0,
        "stores_with_place_id": 0,
        "avg_rating":          None,
    }
    try:
        cur.execute("""
            SELECT COUNT(*), MAX(review_date), COUNT(DISTINCT store_id),
                   ROUND(AVG(rating::numeric), 2)
            FROM store_reviews
        """)
        row = cur.fetchone()
        if row:
            stats["total_reviews"]       = row[0] or 0
            stats["latest_review_date"]  = row[1]
            stats["stores_with_reviews"] = row[2] or 0
            stats["avg_rating"]          = row[3]
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            cur.execute(
                "SELECT COUNT(*), MAX(review_date), COUNT(DISTINCT store_id), "
                "ROUND(AVG(CAST(rating AS REAL)), 2) FROM store_reviews"
            )
            row = cur.fetchone()
            if row:
                stats["total_reviews"]       = row[0] or 0
                stats["latest_review_date"]  = row[1]
                stats["stores_with_reviews"] = row[2] or 0
                stats["avg_rating"]          = row[3]
        except Exception:
            pass

    try:
        cur.execute(
            "SELECT COUNT(*) FROM stores "
            "WHERE google_place_id IS NOT NULL AND google_place_id != ''"
        )
        row = cur.fetchone()
        if row:
            stats["stores_with_place_id"] = row[0] or 0
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass

    return stats


# ══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    args = set(sys.argv[1:])

    if "--discover" in args:
        print("=== Discover Google Place IDs (run once) ===")
        discover_all_place_ids()

    elif "--fetch" in args or "--update" in args:
        print("=== Fetch Google Reviews ===")
        fetch_all_reviews()

    elif "--stats" in args:
        conn, dialect = get_conn()
        create_tables(conn, dialect)
        s = get_review_stats(conn, dialect)
        conn.close()
        print(f"Total reviews:    {s['total_reviews']:,}")
        print(f"Latest review:    {s['latest_review_date'] or '—'}")
        print(f"Stores w/ reviews:{s['stores_with_reviews']}")
        print(f"Stores w/ PlaceID:{s['stores_with_place_id']}")
        print(f"Avg rating:       {s['avg_rating'] or '—'}")

    else:
        print("Usage:")
        print("  py scripts/fetch_google_reviews.py --discover   # find Place IDs (run once per store)")
        print("  py scripts/fetch_google_reviews.py --fetch      # pull latest reviews (run daily)")
        print("  py scripts/fetch_google_reviews.py --update     # alias for --fetch")
        print("  py scripts/fetch_google_reviews.py --stats      # show DB summary")
