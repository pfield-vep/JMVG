import sqlite3

conn = sqlite3.connect("jerseymikes.db")
c = conn.cursor()

# Add new columns to weekly_sales if they don't exist
existing = [r[1] for r in c.execute("PRAGMA table_info(weekly_sales)").fetchall()]

added = []
for col in ['same_store_txn_pct', 'fytd_same_store_txn_pct']:
    if col not in existing:
        c.execute(f"ALTER TABLE weekly_sales ADD COLUMN {col} REAL")
        added.append(col)

# Create weekly_market_totals if it doesn't exist
c.execute("""
    CREATE TABLE IF NOT EXISTS weekly_market_totals (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
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
    )
""")


# Add weekly_store_history table
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

# Add San Diego stores
san_diego = [
    ('20071','Escondido, CA','CA','San Diego','Daniel Neciosup-Acuna'),
    ('20091','Temecula, CA', 'CA','San Diego','Daniel Neciosup-Acuna'),
    ('20171','Temecula, CA', 'CA','San Diego','Daniel Neciosup-Acuna'),
    ('20177','Murrieta, CA', 'CA','San Diego','Daniel Neciosup-Acuna'),
    ('20291','Temecula, CA', 'CA','San Diego','Daniel Neciosup-Acuna'),
    ('20292','Ramona, CA',   'CA','San Diego','Daniel Neciosup-Acuna'),
    ('20300','Escondido, CA','CA','San Diego','Daniel Neciosup-Acuna'),
]
for row in san_diego:
    c.execute("INSERT OR IGNORE INTO stores (store_id,city,state,co_op,franchisee) VALUES (?,?,?,?,?)", row)
print("✅ weekly_store_history table ready")
print("✅ San Diego stores added")

conn.commit()
conn.close()

if added:
    print(f"✅ Added columns: {', '.join(added)}")
else:
    print("✅ weekly_sales columns already up to date")
print("✅ weekly_market_totals table ready")
print("\nDatabase schema updated. Now run:")
print('  py parse_and_load.py --folder "WeeklyPDF\\2026-03-09"')
print('  py parse_and_load.py --folder "WeeklyPDF\\2026-03-02"')
