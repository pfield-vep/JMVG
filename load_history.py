# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
"""
load_history.py
Loads weekly sales and transaction history from Excel into SQLite.
Also updates the schema on the user's machine if needed.

Usage:
    py load_history.py "Weekly_Sales_and_trans.xlsx"
    py load_history.py  (looks for file in same folder automatically)
"""

import sqlite3
import pandas as pd
import os
import sys
import glob

DB_PATH = "jerseymikes.db"

# ── San Diego store coordinates (for map) ─────────────────────────────────────
SAN_DIEGO_STORES = [
    ('20071', 'Escondido, CA',  'CA', 'San Diego', 'Daniel Neciosup-Acuna'),
    ('20091', 'Temecula, CA',   'CA', 'San Diego', 'Daniel Neciosup-Acuna'),
    ('20171', 'Temecula, CA',   'CA', 'San Diego', 'Daniel Neciosup-Acuna'),
    ('20177', 'Murrieta, CA',   'CA', 'San Diego', 'Daniel Neciosup-Acuna'),
    ('20291', 'Temecula, CA',   'CA', 'San Diego', 'Daniel Neciosup-Acuna'),
    ('20292', 'Ramona, CA',     'CA', 'San Diego', 'Daniel Neciosup-Acuna'),
    ('20300', 'Escondido, CA',  'CA', 'San Diego', 'Daniel Neciosup-Acuna'),
]


def ensure_schema(conn):
    """Add any missing tables/columns to the database."""
    c = conn.cursor()

    # Add San Diego stores
    for row in SAN_DIEGO_STORES:
        c.execute(
            "INSERT OR IGNORE INTO stores (store_id, city, state, co_op, franchisee) VALUES (?,?,?,?,?)",
            row
        )

    # Create history table
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

    conn.commit()
    print("[OK] Schema ready")


def load_excel(filepath, conn):
    """Read Excel, melt to long format, load into weekly_store_history."""
    print(f"\n[FILE] Loading: {os.path.basename(filepath)}")

    # Read both sheets
    sales_wide = pd.read_excel(filepath, sheet_name='Weekly Sales Summary')
    txns_wide  = pd.read_excel(filepath, sheet_name='Weekly Ticket Summary')

    # Melt sales to long format
    sales_long = sales_wide.melt(
        id_vars='Store Number',
        var_name='week_ending',
        value_name='net_sales'
    )
    sales_long.columns = ['store_id', 'week_ending', 'net_sales']
    sales_long['store_id']    = sales_long['store_id'].astype(str)
    sales_long['week_ending'] = pd.to_datetime(sales_long['week_ending']).dt.strftime('%Y-%m-%d')

    # Melt transactions to long format
    txns_long = txns_wide.melt(
        id_vars='Store Number',
        var_name='week_ending',
        value_name='transactions'
    )
    txns_long.columns = ['store_id', 'week_ending', 'transactions']
    txns_long['store_id']    = txns_long['store_id'].astype(str)
    txns_long['week_ending'] = pd.to_datetime(txns_long['week_ending']).dt.strftime('%Y-%m-%d')

    # Merge
    merged = sales_long.merge(txns_long, on=['store_id', 'week_ending'], how='outer')

    # Drop rows where both are null (store not yet open that week)
    merged = merged.dropna(subset=['net_sales', 'transactions'], how='all')

    # Load into DB
    rows_loaded = 0
    rows_skipped = 0
    c = conn.cursor()

    for _, row in merged.iterrows():
        try:
            net_sales    = float(row['net_sales'])    if pd.notna(row['net_sales'])    else None
            transactions = int(row['transactions'])   if pd.notna(row['transactions']) else None
            c.execute("""
                INSERT OR REPLACE INTO weekly_store_history
                    (store_id, week_ending, net_sales, transactions)
                VALUES (?, ?, ?, ?)
            """, (row['store_id'], row['week_ending'], net_sales, transactions))
            rows_loaded += 1
        except Exception as e:
            rows_skipped += 1

    conn.commit()
    print(f"  [OK] {rows_loaded:,} store-week rows loaded ({rows_skipped} skipped)")

    # Summary
    stores = merged['store_id'].nunique()
    weeks  = merged['week_ending'].nunique()
    print(f"  [DATA] {stores} stores × {weeks} weeks")
    print(f"  [DATE] {merged['week_ending'].min()} → {merged['week_ending'].max()}")


def compute_sss_preview(conn):
    """
    Show a preview of computed SSS metrics using the 420-day comp store rule.
    A store is 'comparable' for a given current week if it has data both in:
      - the current week
      - the equivalent week 364 days prior
    AND the store was open at least 420 days before the current week.
    """
    print("\n[DATA] Computing SSS preview (most recent week in history)...")

    df = pd.read_sql("""
        SELECT h.store_id, h.week_ending, h.net_sales, h.transactions,
               s.co_op
        FROM weekly_store_history h
        LEFT JOIN stores s ON h.store_id = s.store_id
        WHERE h.net_sales IS NOT NULL
        ORDER BY h.week_ending
    """, conn)

    df['week_ending'] = pd.to_datetime(df['week_ending'])

    most_recent = df['week_ending'].max()
    prior_week  = most_recent - pd.Timedelta(days=364)

    current = df[df['week_ending'] == most_recent].set_index('store_id')
    prior   = df[df['week_ending'] == prior_week].set_index('store_id')

    # 420-day comp eligibility: store must have opened >= 420 days before current week
    first_week = df.groupby('store_id')['week_ending'].min()
    comp_eligible = first_week[first_week <= (most_recent - pd.Timedelta(days=420))].index

    comp_current = current[current.index.isin(comp_eligible) & current.index.isin(prior.index)]
    comp_prior   = prior[prior.index.isin(comp_eligible) & prior.index.isin(current.index)]

    if len(comp_current) == 0:
        print("  [WARN]  No comparable stores found for most recent week")
        return

    sss_sales = (comp_current['net_sales'].sum() / comp_prior['net_sales'].sum() - 1) * 100
    sss_txns  = (comp_current['transactions'].sum() / comp_prior['transactions'].sum() - 1) * 100
    sss_tkt   = ((1 + sss_sales/100) / (1 + sss_txns/100) - 1) * 100

    print(f"  Week of {most_recent.strftime('%Y-%m-%d')} vs {prior_week.strftime('%Y-%m-%d')}")
    print(f"  Comparable stores: {len(comp_current)}")
    print(f"  SS Sales:        {sss_sales:+.2f}%")
    print(f"  SS Transactions: {sss_txns:+.2f}%")
    print(f"  SS Ticket:       {sss_tkt:+.2f}%")


if __name__ == "__main__":
    # Find Excel file
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
    else:
        # Auto-detect in current folder
        matches = glob.glob("*.xlsx") + glob.glob("Weekly_Sales*.xlsx")
        matches = [m for m in matches if 'sales' in m.lower() or 'trans' in m.lower() or 'weekly' in m.lower()]
        if not matches:
            print("[ERROR] No Excel file found. Usage: py load_history.py <filename.xlsx>")
            sys.exit(1)
        filepath = matches[0]
        print(f"Auto-detected: {filepath}")

    if not os.path.exists(filepath):
        print(f"[ERROR] File not found: {filepath}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    load_excel(filepath, conn)
    compute_sss_preview(conn)
    conn.close()

    print("\n[OK] Done. History loaded into jerseymikes.db")
    print("   Run 'py -m streamlit run dashboard.py' to see updated dashboard.")
