"""
scripts/migrate_store_dates.py
==============================
One-time migration: loads open_date, acquisition_date, lat, lon from
store_reference.csv into the stores table in Supabase (or SQLite fallback).

Run once from the Dashboard folder:
    py scripts/migrate_store_dates.py
"""

import os, sys, csv
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CSV_PATH = os.path.join(ROOT, "store_reference.csv")

def parse_date(s):
    if not s or not s.strip():
        return None
    for fmt in ('%m/%d/%y', '%m/%d/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s.strip(), fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return None

def get_conn():
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
                import psycopg2
                s = cfg["supabase"]
                conn = psycopg2.connect(
                    host=s["host"], port=int(s["port"]),
                    dbname=s["dbname"], user=s["user"],
                    password=s["password"], sslmode="require"
                )
                print("Connected to Supabase / Postgres")
                return conn, "postgres"
            except Exception as e:
                print(f"⚠️  Supabase failed ({e}) — falling back to SQLite")
    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"

def main():
    # ── Parse CSV ──────────────────────────────────────────────────────────────
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    clean = []
    skipped = []
    for r in rows:
        od  = parse_date(r.get('open_date', ''))
        ad  = parse_date(r.get('acquisition_date', ''))
        lat = float(r['lat'])  if r.get('lat')  else None
        lon = float(r['lon'])  if r.get('lon')  else None
        if (od or ad) and lat and lon:
            clean.append((r['store_id'], od, ad, lat, lon))
        else:
            skipped.append(r['store_id'])

    print(f"CSV: {len(rows)} rows total — {len(clean)} to migrate, {len(skipped)} skipped")
    if skipped:
        print(f"  Skipped (incomplete): {', '.join(skipped)}")

    conn, dialect = get_conn()
    cur = conn.cursor()

    # ── Add columns if missing ─────────────────────────────────────────────────
    if dialect == 'postgres':
        # Use IF NOT EXISTS (Postgres 9.6+) — safe to run repeatedly, no timeout risk
        for col, typ in [('open_date','TEXT'), ('acquisition_date','TEXT'),
                         ('lat','REAL'), ('lon','REAL')]:
            cur.execute(f"ALTER TABLE stores ADD COLUMN IF NOT EXISTS {col} {typ}")
            conn.commit()
            print(f"  Ensured column: {col}")
    else:
        existing = [r[1] for r in cur.execute("PRAGMA table_info(stores)").fetchall()]
        for col, typ in [('open_date','TEXT'), ('acquisition_date','TEXT'),
                         ('lat','REAL'), ('lon','REAL')]:
            if col not in existing:
                cur.execute(f"ALTER TABLE stores ADD COLUMN {col} {typ}")
                print(f"  Added column: {col}")
        conn.commit()

    # ── Upsert ─────────────────────────────────────────────────────────────────
    p = '%s' if dialect == 'postgres' else '?'
    updated = 0
    for store_id, od, ad, lat, lon in clean:
        cur.execute(f"""
            UPDATE stores
            SET open_date={p}, acquisition_date={p}, lat={p}, lon={p}
            WHERE store_id={p}
        """, (od, ad, lat, lon, store_id))
        print(f"  ✓ {store_id}  open={od}  acq={ad}")
        updated += 1

    conn.commit()
    conn.close()
    print(f"\nDone — {updated} stores updated in {'Supabase' if dialect == 'postgres' else 'SQLite'}.")
    if skipped:
        print(f"\nTODO: add open_date or acquisition_date for: {', '.join(skipped)}")
        print("      (update store_reference.csv and re-run this script)")

if __name__ == "__main__":
    main()
