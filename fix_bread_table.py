import sqlite3
import os

conn = sqlite3.connect("jerseymikes.db")
c = conn.cursor()

# Create weekly_bread_totals table
c.execute("""
    CREATE TABLE IF NOT EXISTS weekly_bread_totals (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
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
    )
""")
print("OK - weekly_bread_totals table created")

# Create weekly_store_history if missing
c.execute("""
    CREATE TABLE IF NOT EXISTS weekly_store_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id     TEXT NOT NULL,
        week_ending  TEXT NOT NULL,
        net_sales    REAL,
        transactions INTEGER,
        UNIQUE(store_id, week_ending)
    )
""")
print("OK - weekly_store_history table ready")

# Clear bread from report log so PDFs re-parse
c.execute("DELETE FROM report_log WHERE report_type='bread'")
print("OK - bread entries cleared from report log")

conn.commit()
conn.close()

print("")
print("Now run:")
print('  py parse_and_load.py --folder "WeeklyPDF\\2026-03-09"')
print('  py parse_and_load.py --folder "WeeklyPDF\\2026-03-02"')
print("  py -m streamlit run dashboard.py")
