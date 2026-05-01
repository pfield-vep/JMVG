"""
scripts/fetch_google_reviews.py
===============================
Fetches Google Maps reviews for all JM Valley Group stores via the
Google Places API (New) and stores them in the store_reviews table.

The Places API (New) returns up to 5 most recent reviews per call.
Run daily to accumulate a growing review history — duplicates are skipped.

Usage
-----
  py scripts/fetch_google_reviews.py --discover   # find Google Place IDs (run once)
  py scripts/fetch_google_reviews.py --fetch      # pull latest reviews (run daily)
  py scripts/fetch_google_reviews.py --update     # alias for --fetch
  py scripts/fetch_google_reviews.py --stats      # show DB summary

API Key Setup
-------------
Add your Google Places API key to .streamlit/secrets.toml:

    [google]
    places_api_key = "AIzaSy..."

Or set environment variable:  GOOGLE_PLACES_API_KEY=AIzaSy...

Enable "Places API (New)" in Google Cloud Console.
Pricing: ~$0.017/Place Details call → ~$15/month for 29 stores daily.
Google's $200/month free credit covers this entirely.

Places API (New) differences from Legacy
-----------------------------------------
- Base URL: https://places.googleapis.com/v1/
- Auth via header X-Goog-Api-Key (not ?key= param)
- Fields requested via header X-Goog-FieldMask
- Text Search: POST /places:searchText  (JSON body)
- Place Details: GET  /places/{place_id}
- place_id stored as "id" (not "place_id") in search results
- Reviews use publishTime (ISO 8601) not time (Unix epoch)
- reviewer name at authorAttribution.displayName
- review text at text.text
- review count at userRatingCount (not user_ratings_total)
"""

import os, sys, time, json, hashlib
from datetime import date, datetime
from urllib.request import urlopen, Request
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

PLACES_NEW_BASE = "https://places.googleapis.com/v1"


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


# ── DB connection ─────────────────────────────────────────────────────────────

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
    review_id         TEXT    NOT NULL UNIQUE,
    platform          TEXT    NOT NULL DEFAULT 'google',
    reviewer_name     TEXT,
    rating            INTEGER NOT NULL,
    review_text       TEXT,
    review_date       DATE,
    fetched_at        TIMESTAMP DEFAULT NOW(),
    topic_speed       INTEGER,
    topic_accuracy    INTEGER,
    topic_staff       INTEGER,
    topic_food        INTEGER,
    topic_cleanliness INTEGER,
    topic_online      INTEGER,
    sentiment         TEXT,
    classified_at     TIMESTAMP
)"""

CREATE_REVIEWS_SQLITE = CREATE_REVIEWS_PG.replace(
    "SERIAL  PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT"
).replace("DEFAULT NOW()", "DEFAULT CURRENT_TIMESTAMP")

STORES_NEW_COLS = [
    ("google_place_id",       "TEXT"),
    ("google_rating",         "REAL"),
    ("google_review_count",   "INTEGER"),
    ("google_rating_updated", "TEXT"),
]


def create_tables(conn, dialect):
    cur = conn.cursor()
    cur.execute(CREATE_REVIEWS_PG if dialect == "postgres" else CREATE_REVIEWS_SQLITE)
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
# PLACES API (NEW) HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _headers(api_key, field_mask):
    return {
        "Content-Type":    "application/json",
        "X-Goog-Api-Key":  api_key,
        "X-Goog-FieldMask": field_mask,
    }


def places_text_search(query, api_key):
    """
    POST /v1/places:searchText
    Returns list of place dicts from the 'places' array, or [].
    Each place has: id, displayName.text, formattedAddress
    """
    url  = f"{PLACES_NEW_BASE}/places:searchText"
    body = json.dumps({
        "textQuery":    query,
        "includedType": "restaurant",
        "maxResultCount": 5,
    }).encode()
    req = Request(url, data=body, method="POST",
                  headers=_headers(api_key,
                                   "places.id,places.displayName,places.formattedAddress"))
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read()).get("places", [])
    except Exception as e:
        print(f"  Text Search error: {e}")
        return []


def places_details(place_id, api_key):
    """
    GET /v1/places/{place_id}
    Returns dict with: displayName, rating, userRatingCount, reviews[]
    Each review has: rating, text.text, publishTime, authorAttribution.displayName
    """
    url = f"{PLACES_NEW_BASE}/places/{place_id}"
    req = Request(url, method="GET",
                  headers=_headers(api_key,
                                   "displayName,rating,userRatingCount,reviews"))
    try:
        with urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  Place Details error for {place_id}: {e}")
        return None


def make_review_id(store_id, reviewer, publish_time):
    """
    Stable 16-char unique ID: hash(store_id | reviewer | publish_time).
    Uses publishTime string directly — no Unix epoch conversion needed.
    """
    raw = f"{store_id}|{reviewer}|{publish_time}"
    return hashlib.sha1(raw.encode()).hexdigest()[:16]


def parse_publish_time(publish_time_str):
    """Convert ISO 8601 publishTime → date object. Returns None on failure."""
    if not publish_time_str:
        return None
    try:
        # Format: "2024-03-15T18:42:00Z" or "2024-03-15T18:42:00.123456Z"
        dt = datetime.fromisoformat(publish_time_str.replace("Z", "+00:00"))
        return dt.date()
    except Exception:
        try:
            return date.fromisoformat(publish_time_str[:10])
        except Exception:
            return None


# ══════════════════════════════════════════════════════════════════════════════
# UPSERT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def upsert_review(cur, dialect, store_id, rev):
    """
    Insert one review from the Places API (New) response into store_reviews.
    Silently skips duplicates (ON CONFLICT DO NOTHING / INSERT OR IGNORE).
    Returns 1 if inserted, 0 if skipped.
    """
    p = "%s" if dialect == "postgres" else "?"

    publish_time = rev.get("publishTime", "")
    reviewer     = (rev.get("authorAttribution") or {}).get("displayName", "")
    rid          = make_review_id(store_id, reviewer, publish_time)
    rating       = rev.get("rating", 0)
    text         = (rev.get("text") or {}).get("text", "")
    rev_date     = parse_publish_time(publish_time)

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
    cur.execute(sql, (store_id, rid, "google", reviewer, rating, text,
                      rev_date.isoformat() if rev_date else None))
    return cur.rowcount


def update_store_meta(cur, dialect, store_id, rating, review_count):
    """Refresh google_rating + google_review_count snapshot on the store row."""
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
# DISCOVER  (run once — map store addresses → google_place_id)
# ══════════════════════════════════════════════════════════════════════════════

def discover_all_place_ids():
    """
    For every store without a google_place_id, use Text Search to find one.
    Saves place IDs back to the DB. Safe to re-run — skips already-mapped stores.

    Pattern: read DB → CLOSE connection → call Google for all stores →
             reconnect → write all results in one fast batch.
    This avoids Supabase pooler statement timeouts that occur when a connection
    sits idle during API calls and sleeps.
    """
    api_key = get_api_key()
    if not api_key:
        print("❌  No Google Places API key found.")
        print("    Add to .streamlit/secrets.toml:  [google] / places_api_key = 'AIza...'")
        return

    # ── Phase 1: Read stores from DB, then close immediately ─────────────────
    conn, dialect = get_conn()
    create_tables(conn, dialect)
    cur = conn.cursor()
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
    conn.close()   # close before any API calls

    if not stores:
        print("✓  All stores already have a Google Place ID.")
        return

    print(f"Discovering Place IDs for {len(stores)} stores via Places API (New)…")

    # ── Phase 2: Call Google API with NO DB connection open ───────────────────
    results_map = {}   # store_id → (place_id, name, formatted_address)

    for store_id, address in stores:
        if not address:
            print(f"  {store_id}: no address in DB — skipping")
            continue

        query   = f"Jersey Mike's Subs {address}"
        results = places_text_search(query, api_key)

        if not results:
            print(f"  {store_id}: no results for '{query}'")
            time.sleep(0.4)
            continue

        place = results[0]
        pid   = place.get("id", "")
        name  = (place.get("displayName") or {}).get("text", "")
        addr  = place.get("formattedAddress", "")
        print(f"  {store_id}: '{name}' — {addr} → {pid}")

        if pid:
            results_map[store_id] = (pid, name, addr)

        time.sleep(0.35)

    if not results_map:
        print("\nNo Place IDs found — check addresses in the stores table.")
        return

    # ── Phase 3: Reconnect and write all results in one fast batch ────────────
    print(f"\nSaving {len(results_map)} Place IDs to database…")
    conn, dialect = get_conn()
    cur  = conn.cursor()
    p    = "%s" if dialect == "postgres" else "?"
    found = 0

    for store_id, (pid, name, addr) in results_map.items():
        cur.execute(
            f"UPDATE stores SET google_place_id = {p} WHERE store_id = {p}",
            (pid, store_id)
        )
        found += cur.rowcount

    conn.commit()
    conn.close()

    print(f"Done — {found}/{len(stores)} stores now have a Google Place ID.")
    skipped = len(stores) - len(results_map)
    if skipped > 0:
        print(f"  {skipped} store(s) had no address or no Google match.")
        print("  Set manually:  UPDATE stores SET google_place_id='ChIJ...' WHERE store_id='XXXXX';")


# ══════════════════════════════════════════════════════════════════════════════
# FETCH  (run daily to accumulate reviews)
# ══════════════════════════════════════════════════════════════════════════════

def fetch_all_reviews(log=None):
    """
    For every store with a google_place_id, fetch the 5 most recent reviews
    and upsert new ones into store_reviews. Fully idempotent.

    Pattern: read store list → CLOSE connection → call Google for all stores →
             reconnect → write everything in one fast batch.
    Avoids Supabase pooler timeouts from a connection sitting idle during API calls.

    `log` is an optional callable(str) for streaming output to the UI.
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

    # ── Phase 1: Read store list from DB, then close immediately ─────────────
    conn, dialect = get_conn()
    create_tables(conn, dialect)
    cur = conn.cursor()
    cur.execute("""
        SELECT store_id, google_place_id
        FROM   stores
        WHERE  google_place_id IS NOT NULL AND google_place_id != ''
        ORDER  BY store_id
    """)
    stores = cur.fetchall()
    conn.close()   # close before any API calls

    if not stores:
        out("No stores have a Google Place ID yet — run --discover first.")
        return 0, 0

    out(f"Fetching reviews for {len(stores)} stores via Places API (New)…")

    # ── Phase 2: Call Google API with NO DB connection open ───────────────────
    # Collect all results in memory before touching the DB again.
    api_results = []   # list of (store_id, rating, review_count, reviews[])

    for store_id, place_id in stores:
        result = places_details(place_id, api_key)
        if result is None:
            out(f"  {store_id}: ⚠️  no data returned")
            time.sleep(0.5)
            continue

        rating       = result.get("rating")
        review_count = result.get("userRatingCount")
        reviews      = result.get("reviews") or []

        stars     = f"★{rating:.1f}" if rating else "★?"
        total_str = f"{review_count:,}" if review_count else "?"
        out(f"  {store_id}: {stars}  {total_str} total on Google  {len(reviews)} reviews fetched")

        api_results.append((store_id, rating, review_count, reviews))
        time.sleep(0.3)

    if not api_results:
        out("No data returned from Google — nothing to write.")
        return 0, 0

    # ── Phase 3: Reconnect and write everything in one fast batch ─────────────
    out(f"\nWriting results to database…")
    conn, dialect = get_conn()
    cur = conn.cursor()
    total_new    = 0
    total_stores = 0

    for store_id, rating, review_count, reviews in api_results:
        if rating is not None:
            update_store_meta(cur, dialect, store_id, rating, review_count)

        new_count = sum(upsert_review(cur, dialect, store_id, r) for r in reviews)
        total_new    += new_count
        total_stores += 1
        out(f"  {store_id}: +{new_count} new review(s) stored")

    conn.commit()
    conn.close()

    out(f"\nDone — {total_new} new reviews stored across {total_stores} stores.")
    return total_new, total_stores


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY STATS  (used by Update Data page)
# ══════════════════════════════════════════════════════════════════════════════

def get_review_stats(conn, dialect):
    """
    Returns dict with:
      total_reviews, latest_review_date, stores_with_reviews,
      stores_with_place_id, avg_rating
    """
    cur = conn.cursor()
    stats = {
        "total_reviews":        0,
        "latest_review_date":   None,
        "stores_with_reviews":  0,
        "stores_with_place_id": 0,
        "avg_rating":           None,
    }

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
        try:
            conn.rollback()
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
        print("=== Discover Google Place IDs (Places API New) ===")
        discover_all_place_ids()

    elif "--fetch" in args or "--update" in args:
        print("=== Fetch Google Reviews (Places API New) ===")
        fetch_all_reviews()

    elif "--stats" in args:
        conn, dialect = get_conn()
        create_tables(conn, dialect)
        s = get_review_stats(conn, dialect)
        conn.close()
        print(f"Total reviews      : {s['total_reviews']:,}")
        print(f"Latest review date : {s['latest_review_date'] or '—'}")
        print(f"Stores w/ reviews  : {s['stores_with_reviews']}")
        print(f"Stores w/ Place ID : {s['stores_with_place_id']}")
        print(f"Avg rating         : {s['avg_rating'] or '—'}")

    else:
        print("Usage:")
        print("  py scripts/fetch_google_reviews.py --discover   # map store addresses → Place IDs")
        print("  py scripts/fetch_google_reviews.py --fetch      # pull latest reviews (run daily)")
        print("  py scripts/fetch_google_reviews.py --update     # alias for --fetch")
        print("  py scripts/fetch_google_reviews.py --stats      # show DB summary")
