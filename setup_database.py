"""
setup_database.py
Creates the SQLite database and all tables for the Jersey Mike's reporting pipeline.
Run this once to initialize the database.
"""

import sqlite3
import os

DB_PATH = "jerseymikes.db"


def create_database():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # --- Stores master table ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS stores (
            store_id    TEXT PRIMARY KEY,
            city        TEXT,
            state       TEXT,
            co_op       TEXT,
            franchisee  TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # --- Report log (prevents double-processing) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS report_log (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            week_ending     TEXT NOT NULL,
            report_type     TEXT NOT NULL,
            filename        TEXT,
            processed_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(week_ending, report_type)
        )
    """)

    # --- Weekly sales (from Sales Dashboard Detail) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS weekly_sales (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            week_ending             TEXT NOT NULL,
            store_id                TEXT NOT NULL,
            -- Current week
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
            -- Fiscal year to date
            fytd_net_sales          REAL,
            fytd_weekly_auv         REAL,
            fytd_avg_ticket         REAL,
            fytd_avg_daily_bread    REAL,
            fytd_avg_daily_wraps    REAL,
            fytd_sss_pct            REAL,
            fytd_same_store_ticket  REAL,
            UNIQUE(week_ending, store_id)
        )
    """)

    # --- Weekly bread counts (from Bread Count Detail) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS weekly_bread (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            week_ending             TEXT NOT NULL,
            store_id                TEXT NOT NULL,
            -- Current week
            bread_count             INTEGER,
            avg_daily_bread         REAL,
            avg_sales_per_loaf      REAL,
            wrap_bowl_bread         INTEGER,
            wrap_bowl_avg_daily     REAL,
            -- Prior year comparable
            prior_bread_count       INTEGER,
            prior_avg_daily_bread   REAL,
            prior_avg_sales_per_loaf REAL,
            prior_wrap_bowl_bread   INTEGER,
            prior_wrap_bowl_avg_daily REAL,
            same_store_bread_pct    REAL,
            -- FYTD
            fytd_bread_count        INTEGER,
            fytd_avg_daily_bread    REAL,
            fytd_avg_sales_per_loaf REAL,
            fytd_sss_bread_pct      REAL,
            fytd_wrap_bowl_bread    INTEGER,
            fytd_wrap_bowl_avg_daily REAL,
            UNIQUE(week_ending, store_id)
        )
    """)

    # --- Weekly loyalty (from Loyalty Detail) ---
    c.execute("""
        CREATE TABLE IF NOT EXISTS weekly_loyalty (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            week_ending                 TEXT NOT NULL,
            store_id                    TEXT NOT NULL,
            -- Current week
            member_activations_current  INTEGER,
            member_transactions_current INTEGER,
            points_earned_current       INTEGER,
            points_redeemed_current     INTEGER,
            -- All time
            member_activations_alltime  INTEGER,
            member_transactions_alltime INTEGER,
            points_earned_alltime       INTEGER,
            points_redeemed_alltime     INTEGER,
            UNIQUE(week_ending, store_id)
        )
    """)

    conn.commit()
    conn.close()
    print(f"✅ Database created at: {os.path.abspath(DB_PATH)}")
    print("   Tables: stores, report_log, weekly_sales, weekly_bread, weekly_loyalty")


if __name__ == "__main__":
    create_database()
