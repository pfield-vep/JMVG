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
    Connect to Supabase using the DIRECT host (no pooler).
    Reads 'direct_host' from secrets.toml if set; otherwise falls back to
    the pooler with autocommit=True and a best-effort statement_timeout=0.

    To set direct_host: Supabase dashboard → Settings → Database →
    Connection string → Direct connection tab → copy the Host field.
    Add to .streamlit/secrets.toml:
        [supabase]
        direct_host = "aws-0-us-east-1.aws.neon.tech"  (or whatever it shows)
    """
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib

    with open(secrets_path, "rb") as f:
        cfg = tomllib.load(f)

    s = cfg["supabase"]
    pooler_host = s["host"]
    direct_host = s.get("direct_host", "").strip()

    import psycopg2

    # ── Try explicit direct_host from secrets.toml first ─────────────────────
    if direct_host:
        print(f"Pooler host : {pooler_host}")
        print(f"Direct host : {direct_host}  ← using this (from secrets.toml)")
        # Direct connection uses plain 'postgres' user (not postgres.<ref>)
        conn = psycopg2.connect(
            host=direct_host,
            port=5432,
            dbname=s["dbname"],
            user="postgres",
            password=s["password"],
            sslmode="require",
            connect_timeout=30,
        )
        conn.autocommit = True   # each DDL statement is its own transaction
        return conn

    # ── Fallback: pooler with autocommit + no timeout ─────────────────────────
    # autocommit=True means each statement is its own implicit transaction —
    # no long-running transaction to trigger pooler timeouts.
    print(f"No direct_host in secrets.toml — using pooler with autocommit")
    print(f"  (Add direct_host to secrets.toml for a more reliable connection)")
    conn = psycopg2.connect(
        host=pooler_host,
        port=int(s["port"]),
        dbname=s["dbname"],
        user=s["user"],
        password=s["password"],
        sslmode="require",
        connect_timeout=30,
    )
    conn.autocommit = True
    cur = conn.cursor()
    try:
        cur.execute("SET statement_timeout = 0")
    except Exception:
        pass
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
            print("✓")
        except Exception as e:
            # "already exists" / "duplicate column" errors are fine — schema
            # was already applied, just keep going.
            msg = str(e).strip().splitlines()[0]
            if "already exists" in msg or "duplicate column" in msg.lower():
                print(f"✓  (already exists)")
            else:
                all_ok = False
                print(f"✗  {msg}")

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
