"""
scripts/load_outscraper_reviews.py
==================================
One-time loader for Outscraper Google Reviews exports.

Outscraper pulls full review history (up to 250/store) which is far more
than the 5-reviews-per-call Places API limit.  This script:
  1. Reads the Outscraper XLSX export
  2. Maps google_place_id → store_id via the stores table
  3. Clears the existing small batch of Places-API-fetched reviews
     (only ~5/store, all of which are a subset of this export)
  4. Bulk-upserts all Outscraper reviews using Google's native review ID
  5. Refreshes google_rating + google_review_count on each store row

Usage:
    py scripts/load_outscraper_reviews.py path/to/Outscraper-*.xlsx
"""

import os, sys, io
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)


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
                connect_timeout=10,
                options="-c statement_timeout=0",
            )
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
            s = cfg["supabase"]
            conn = psycopg2.connect(
                host=s["host"], port=int(s["port"]),
                dbname=s["dbname"], user=s["user"],
                password=s["password"], sslmode="require",
                connect_timeout=10,
                options="-c statement_timeout=0",
            )
            print("Connected to Supabase")
            return conn, "postgres"

    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"


def parse_datetime(val):
    """Parse Outscraper datetime string 'MM/DD/YYYY HH:MM:SS' → date."""
    if not val or (hasattr(val, '__class__') and val.__class__.__name__ == 'float'):
        return None
    s = str(val).strip()
    for fmt in ("%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def main():
    if len(sys.argv) < 2:
        print("Usage: py scripts/load_outscraper_reviews.py path/to/Outscraper-*.xlsx")
        sys.exit(1)

    xlsx_path = sys.argv[1]
    if not os.path.exists(xlsx_path):
        print(f"File not found: {xlsx_path}")
        sys.exit(1)

    import pandas as pd
    print(f"Reading {os.path.basename(xlsx_path)}...")
    df = pd.read_excel(xlsx_path)
    print(f"  {len(df):,} rows, {df['place_id'].nunique()} unique place IDs")

    # ── Connect and get place_id → store_id mapping ───────────────────────────
    conn, dialect = get_conn()
    p = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()

    cur.execute(
        "SELECT store_id, google_place_id FROM stores "
        "WHERE google_place_id IS NOT NULL AND google_place_id != ''"
    )
    place_to_store = {row[1]: row[0] for row in cur.fetchall()}
    print(f"  {len(place_to_store)} stores with google_place_id in DB")

    unmapped = set(df['place_id'].unique()) - set(place_to_store.keys())
    if unmapped:
        print(f"  ⚠️  {len(unmapped)} place_id(s) not found in stores table — rows skipped")
        for pid in sorted(unmapped):
            count = (df['place_id'] == pid).sum()
            print(f"      {pid}  ({count} rows)")

    # ── Drop existing Places-API-fetched reviews (small set, all duplicates) ──
    cur.execute("SELECT COUNT(*) FROM store_reviews")
    existing = cur.fetchone()[0]
    if existing > 0:
        print(f"\nClearing {existing:,} existing reviews (Places API batch — all included in Outscraper data)...")
        cur.execute("DELETE FROM store_reviews")
        conn.commit()
        print(f"  ✓ Cleared")

    # ── Bulk upsert Outscraper reviews ────────────────────────────────────────
    print(f"\nLoading Outscraper reviews...")

    if dialect == "postgres":
        sql = f"""
            INSERT INTO store_reviews
                (store_id, review_id, platform, reviewer_name, rating,
                 review_text, review_date)
            VALUES ({p},{p},{p},{p},{p},{p},{p})
            ON CONFLICT (review_id) DO NOTHING
        """
    else:
        sql = f"""
            INSERT OR IGNORE INTO store_reviews
                (store_id, review_id, platform, reviewer_name, rating,
                 review_text, review_date)
            VALUES ({p},{p},{p},{p},{p},{p},{p})
        """

    batch = []
    skipped = 0
    store_meta = {}  # place_id → (rating, review_count)

    for _, row in df.iterrows():
        place_id = str(row.get("place_id", "") or "").strip()
        store_id = place_to_store.get(place_id)
        if not store_id:
            skipped += 1
            continue

        review_id = str(row.get("review_id", "") or "").strip()
        if not review_id:
            skipped += 1
            continue

        rating_val = row.get("review_rating")
        if rating_val != rating_val:  # NaN check
            skipped += 1
            continue
        try:
            rating = int(float(rating_val))
        except (TypeError, ValueError):
            skipped += 1
            continue

        reviewer = str(row.get("author_title", "") or "").strip() or None
        text_val = row.get("review_text")
        text = str(text_val).strip() if (text_val == text_val and text_val is not None) else None
        rev_date = parse_datetime(row.get("review_datetime_utc"))

        batch.append((
            store_id, review_id, "google", reviewer, rating,
            text, rev_date.isoformat() if rev_date else None,
        ))

        # Collect per-store aggregate for metadata update
        g_rating = row.get("rating")
        g_count  = row.get("reviews")
        if place_id not in store_meta and g_rating == g_rating and g_count == g_count:
            try:
                store_meta[place_id] = (float(g_rating), int(float(g_count)))
            except (TypeError, ValueError):
                pass

        if len(batch) >= 500:
            cur.executemany(sql, batch)
            conn.commit()
            batch = []

    if batch:
        cur.executemany(sql, batch)
        conn.commit()

    total_inserted = len(df) - skipped
    print(f"  ✓ {total_inserted:,} reviews inserted  ({skipped} skipped — unmapped/invalid)")

    # ── Update store google_rating + google_review_count ─────────────────────
    print(f"\nUpdating store ratings for {len(store_meta)} stores...")
    from datetime import date
    today = date.today().isoformat()
    updated = 0
    for place_id, (g_rating, g_count) in store_meta.items():
        store_id = place_to_store.get(place_id)
        if not store_id:
            continue
        cur.execute(
            f"UPDATE stores SET "
            f"  google_rating={p}, "
            f"  google_review_count={p}, "
            f"  google_rating_updated={p} "
            f"WHERE store_id={p}",
            (g_rating, g_count, today, store_id)
        )
        updated += cur.rowcount
    conn.commit()
    print(f"  ✓ {updated} store rows updated with rating/count")

    conn.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'─'*50}")
    print(f"✓ Done — {total_inserted:,} reviews loaded from Outscraper export")
    if skipped:
        print(f"  {skipped} rows skipped (unmapped place IDs or missing rating/review_id)")


if __name__ == "__main__":
    main()
