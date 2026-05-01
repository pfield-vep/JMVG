"""
scripts/setup_reviews_schema.py
================================
One-time schema setup for the Google Reviews pipeline.
Runs against the DIRECT Supabase connection (not the PgBouncer pooler),
which has no statement or lock timeouts.

Run once from your terminal:
    py scripts/setup_reviews_schema.py
"""

import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

def get_direct_conn():
    """
    Connect to Supabase using the DIRECT host (db.<ref>.supabase.co)
    instead of the pooler (*.pooler.supabase.com).
    The direct connection has no statement_timeout or lock_timeout limits.
    """
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(secrets_path, "rb") as f:
        cfg = tomllib.load(f)

    s = cfg["supabase"]
    pooler_host = s["host"]   # e.g. aws-0-us-east-1.pooler.supabase.com

    # Derive the direct host from the user string: postgres.<project_ref>
    # Direct host format: db.<project_ref>.supabase.co
    user = s["user"]          # e.g. postgres.duxaqruvgggftxndubpn
    project_ref = user.split(".")[-1] if "." in user else None

    if project_ref:
        direct_host = f"db.{project_ref}.supabase.co"
        print(f"Pooler host : {pooler_host}")
        print(f"Direct host : {direct_host}  ← using this")
    else:
        # Fallback: swap pooler host → direct host heuristically
        direct_host = pooler_host.replace("pooler.supabase.com", "supabase.co")
        if not direct_host.startswith("db."):
            direct_host = pooler_host   # give up and use pooler
        print(f"Using host  : {direct_host}")

    import psycopg2
    conn = psycopg2.connect(
        host=direct_host,
        port=5432,
        dbname=s["dbname"],
        user="postgres",          # direct connection uses plain 'postgres'
        password=s["password"],
        sslmode="require",
        connect_timeout=30,
    )
    conn.autocommit = False
    return conn


SCHEMA_STATEMENTS = [
    (
        "CREATE store_reviews table",
        """
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
        )
        """
    ),
    (
        "ADD stores.google_place_id",
        "ALTER TABLE stores ADD COLUMN IF NOT EXISTS google_place_id TEXT"
    ),
    (
        "ADD stores.google_rating",
        "ALTER TABLE stores ADD COLUMN IF NOT EXISTS google_rating REAL"
    ),
    (
        "ADD stores.google_review_count",
        "ALTER TABLE stores ADD COLUMN IF NOT EXISTS google_review_count INTEGER"
    ),
    (
        "ADD stores.google_rating_updated",
        "ALTER TABLE stores ADD COLUMN IF NOT EXISTS google_rating_updated TEXT"
    ),
]


def main():
    print("=== Google Reviews Schema Setup ===\n")

    print("Connecting via direct Supabase connection…")
    try:
        conn = get_direct_conn()
    except Exception as e:
        print(f"\n❌  Connection failed: {e}")
        print("\nTry connecting manually via Supabase Dashboard:")
        print("  Project → Settings → Database → Connection string → Direct")
        sys.exit(1)

    print("Connected ✓\n")
    cur = conn.cursor()

    all_ok = True
    for label, sql in SCHEMA_STATEMENTS:
        print(f"  {label}… ", end="", flush=True)
        try:
            cur.execute(sql)
            conn.commit()
            print("✓")
        except Exception as e:
            conn.rollback()
            all_ok = False
            print(f"✗  {e}")

    conn.close()

    if all_ok:
        print("\n✅  Schema ready. You can now run:")
        print("    py scripts/fetch_google_reviews.py --discover")
        print("    py scripts/fetch_google_reviews.py --fetch")
    else:
        print("\n⚠️  Some statements failed — check errors above.")
        print("   If you see 'already exists' errors those are fine (schema was already applied).")


if __name__ == "__main__":
    main()
