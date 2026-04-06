"""
migrate_to_supabase.py
Migrates all data from local SQLite (jerseymikes.db) to Supabase PostgreSQL.
Run once from your Jersey Mikes folder.

Usage:
    py migrate_to_supabase.py
"""

import sqlite3
import os
import sys

# ── Install psycopg2 if needed ────────────────────────────────────────────────
try:
    import psycopg2
    from psycopg2.extras import execute_values
except ImportError:
    print("Installing psycopg2...")
    os.system("py -m pip install psycopg2-binary")
    import psycopg2
    from psycopg2.extras import execute_values

# ── Connection details — fill in your password below ─────────────────────────
# Use separate params to avoid issues with special characters in passwords
DB_HOST     = "aws-1-us-east-1.pooler.supabase.com"
DB_PORT     = 5432
DB_NAME     = "postgres"
DB_USER     = "postgres.duxaqruvgggftxndubpn"
DB_PASSWORD = "a/TQ8,b6Xeh%X7!"   # <-- replace this, special characters are fine here

SQLITE_PATH = "jerseymikes.db"

# ── Tables to migrate (in dependency order) ───────────────────────────────────
TABLES = [
    'stores',
    'weekly_sales',
    'weekly_market_totals',
    'weekly_bread',
    'weekly_bread_totals',
    'weekly_loyalty',
    'weekly_store_history',
    'report_log',
]

# ── PostgreSQL CREATE TABLE statements ────────────────────────────────────────
CREATE_STATEMENTS = {
    'stores': """
        CREATE TABLE IF NOT EXISTS stores (
            id          SERIAL PRIMARY KEY,
            store_id    TEXT NOT NULL UNIQUE,
            city        TEXT,
            state       TEXT,
            co_op       TEXT,
            franchisee  TEXT,
            created_at  TEXT
        )""",

    'weekly_sales': """
        CREATE TABLE IF NOT EXISTS weekly_sales (
            id                      SERIAL PRIMARY KEY,
            week_ending             TEXT NOT NULL,
            store_id                TEXT NOT NULL,
            net_sales               REAL,
            sss_pct                 REAL,
            same_store_ticket_pct   REAL,
            avg_daily_bread         REAL,
            avg_daily_wraps         REAL,
            online_sales_pct        REAL,
            third_party_sales_pct   REAL,
            non_loyalty_disc_pct    REAL,
            loyalty_disc_pct        REAL,
            loyalty_sales_pct       REAL,
            fytd_net_sales          REAL,
            fytd_weekly_auv         REAL,
            fytd_avg_ticket         REAL,
            fytd_avg_daily_bread    REAL,
            fytd_avg_daily_wraps    REAL,
            fytd_sss_pct            REAL,
            fytd_same_store_ticket  REAL,
            same_store_txn_pct      REAL,
            fytd_same_store_txn_pct REAL,
            UNIQUE(week_ending, store_id)
        )""",

    'weekly_market_totals': """
        CREATE TABLE IF NOT EXISTS weekly_market_totals (
            id                      SERIAL PRIMARY KEY,
            week_ending             TEXT NOT NULL,
            market                  TEXT NOT NULL,
            store_count             INTEGER,
            net_sales               REAL,
            sss_pct                 REAL,
            same_store_ticket_pct   REAL,
            same_store_txn_pct      REAL,
            avg_daily_bread         REAL,
            online_sales_pct        REAL,
            third_party_sales_pct   REAL,
            non_loyalty_disc_pct    REAL,
            loyalty_disc_pct        REAL,
            loyalty_sales_pct       REAL,
            fytd_net_sales          REAL,
            fytd_weekly_auv         REAL,
            fytd_avg_ticket         REAL,
            fytd_avg_daily_bread    REAL,
            fytd_sss_pct            REAL,
            fytd_same_store_ticket  REAL,
            fytd_same_store_txn_pct REAL,
            UNIQUE(week_ending, market)
        )""",

    'weekly_bread': """
        CREATE TABLE IF NOT EXISTS weekly_bread (
            id                          SERIAL PRIMARY KEY,
            week_ending                 TEXT NOT NULL,
            store_id                    TEXT NOT NULL,
            bread_count                 INTEGER,
            avg_daily_bread             REAL,
            avg_sales_per_loaf          REAL,
            wrap_bowl_bread             INTEGER,
            wrap_bowl_avg_daily         REAL,
            prior_bread_count           INTEGER,
            prior_avg_daily_bread       REAL,
            prior_avg_sales_per_loaf    REAL,
            prior_wrap_bowl_bread       INTEGER,
            prior_wrap_bowl_avg_daily   REAL,
            same_store_bread_pct        REAL,
            fytd_bread_count            INTEGER,
            fytd_avg_daily_bread        REAL,
            fytd_avg_sales_per_loaf     REAL,
            fytd_sss_bread_pct          REAL,
            fytd_wrap_bowl_bread        INTEGER,
            fytd_wrap_bowl_avg_daily    REAL,
            UNIQUE(week_ending, store_id)
        )""",

    'weekly_bread_totals': """
        CREATE TABLE IF NOT EXISTS weekly_bread_totals (
            id                      SERIAL PRIMARY KEY,
            week_ending             TEXT NOT NULL,
            market                  TEXT NOT NULL,
            store_count             INTEGER,
            bread_count             INTEGER,
            avg_daily_bread         REAL,
            avg_sales_per_loaf      REAL,
            same_store_bread_pct    REAL,
            fytd_bread_count        INTEGER,
            fytd_avg_daily_bread    REAL,
            fytd_avg_sales_per_loaf REAL,
            fytd_sss_bread_pct      REAL,
            UNIQUE(week_ending, market)
        )""",

    'weekly_loyalty': """
        CREATE TABLE IF NOT EXISTS weekly_loyalty (
            id                              SERIAL PRIMARY KEY,
            week_ending                     TEXT NOT NULL,
            store_id                        TEXT NOT NULL,
            member_activations_current      INTEGER,
            member_transactions_current     INTEGER,
            points_earned_current           INTEGER,
            points_redeemed_current         INTEGER,
            member_activations_alltime      INTEGER,
            member_transactions_alltime     INTEGER,
            points_earned_alltime           INTEGER,
            points_redeemed_alltime         INTEGER,
            UNIQUE(week_ending, store_id)
        )""",

    'weekly_store_history': """
        CREATE TABLE IF NOT EXISTS weekly_store_history (
            id           SERIAL PRIMARY KEY,
            store_id     TEXT NOT NULL,
            week_ending  TEXT NOT NULL,
            net_sales    REAL,
            transactions INTEGER,
            UNIQUE(store_id, week_ending)
        )""",

    'report_log': """
        CREATE TABLE IF NOT EXISTS report_log (
            id          SERIAL PRIMARY KEY,
            week_ending TEXT,
            report_type TEXT,
            filename    TEXT,
            processed_at TEXT
        )""",
}


def migrate():
    if 'YOUR-PASSWORD-HERE' in DB_PASSWORD:
        print("[ERROR] Please edit migrate_to_supabase.py and replace YOUR-PASSWORD-HERE with your Supabase password.")
        sys.exit(1)

    print("Connecting to Supabase...")
    pg = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD,
        sslmode='require'
    )
    pg_cur = pg.cursor()

    print("Connecting to SQLite...")
    sqlite = sqlite3.connect(SQLITE_PATH)
    sqlite.row_factory = sqlite3.Row

    for table in TABLES:
        print(f"\n-- Migrating {table} --")

        # Create table in PostgreSQL
        pg_cur.execute(CREATE_STATEMENTS[table])
        pg.commit()

        # Read all rows from SQLite
        rows = sqlite.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  (empty, skipping)")
            continue

        # Get column names (skip 'id' — PostgreSQL uses SERIAL)
        col_names = [d[0] for d in sqlite.execute(f"SELECT * FROM {table} LIMIT 0").description]
        col_names = [c for c in col_names if c != 'id']

        # Build INSERT
        placeholders = ','.join(['%s'] * len(col_names))
        cols_str = ','.join(col_names)
        sql = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        # Convert rows to tuples (skip id column)
        id_idx = [d[0] for d in sqlite.execute(f"SELECT * FROM {table} LIMIT 0").description].index('id') if 'id' in [d[0] for d in sqlite.execute(f"SELECT * FROM {table} LIMIT 0").description] else None
        data = []
        for row in rows:
            row_list = list(row)
            if id_idx is not None:
                row_list.pop(id_idx)
            data.append(tuple(row_list))

        execute_values(pg_cur, f"INSERT INTO {table} ({cols_str}) VALUES %s ON CONFLICT DO NOTHING",
                       data, template=None, page_size=500)
        pg.commit()
        print(f"  [OK] {len(data)} rows migrated")

    sqlite.close()
    pg.close()
    print("\n[OK] Migration complete! All data is now in Supabase.")
    print("Next step: update dashboard.py to connect to Supabase.")


if __name__ == "__main__":
    migrate()
