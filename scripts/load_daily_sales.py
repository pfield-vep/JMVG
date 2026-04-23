"""
scripts/load_daily_sales.py
===========================
One-time backfill (and ongoing upsert helper) for the daily_sales table.

Usage:
    py scripts/load_daily_sales.py                          # loads daily_export_seed.xlsx
    py scripts/load_daily_sales.py path/to/export.xlsx      # loads a specific file
"""
import os, sys, re
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

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
                print(f"⚠️  Supabase connection failed ({e}), falling back to SQLite")
    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"

CREATE_PG = """
CREATE TABLE IF NOT EXISTS daily_sales (
    id                 SERIAL  PRIMARY KEY,
    store_id           TEXT    NOT NULL,
    sale_date          DATE    NOT NULL,
    net_sales          REAL,
    total_transactions INTEGER,
    walkin_sales       REAL,
    online_sales       REAL,
    third_party_sales  REAL,
    lunch_sales        REAL,
    dinner_sales       REAL,
    morning_sales      REAL,
    UNIQUE (store_id, sale_date)
)"""

CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS daily_sales (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id           TEXT    NOT NULL,
    sale_date          TEXT    NOT NULL,
    net_sales          REAL,
    total_transactions INTEGER,
    walkin_sales       REAL,
    online_sales       REAL,
    third_party_sales  REAL,
    lunch_sales        REAL,
    dinner_sales       REAL,
    morning_sales      REAL,
    UNIQUE (store_id, sale_date)
)"""

def create_table(conn, dialect):
    cur = conn.cursor()
    cur.execute(CREATE_PG if dialect == "postgres" else CREATE_SQLITE)
    conn.commit()
    print("daily_sales table ready")

def parse_excel(path):
    import pandas as pd, shutil, tempfile, io
    # path can be a file path string OR a BytesIO object (from email fetch).
    # For file paths: copy to a temp file first to avoid OneDrive/Excel file-lock.
    if isinstance(path, (str, os.PathLike)):
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        shutil.copy2(path, tmp.name)
        df = pd.read_excel(tmp.name)
        os.remove(tmp.name)
    else:
        df = pd.read_excel(path)
    # Clean dollar columns
    for col in ["Net Sales","Walk-In Sales","Online Sales","3rd Party Payments",
                "Lunch Net Sales","Dinner Net Sales"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.replace(r"[\$,]","",regex=True)
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"])
    df["Store"] = df["Store"].astype(str).str.strip()
    df["morning_sales"] = (
        df["Net Sales"].fillna(0) - df["Lunch Net Sales"].fillna(0) - df["Dinner Net Sales"].fillna(0)
    ).clip(lower=0)
    return df

def upsert_rows(conn, dialect, df):
    p = "%s" if dialect == "postgres" else "?"
    if dialect == "postgres":
        sql = f"""
            INSERT INTO daily_sales
                (store_id, sale_date, net_sales, total_transactions,
                 walkin_sales, online_sales, third_party_sales,
                 lunch_sales, dinner_sales, morning_sales)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
            ON CONFLICT (store_id, sale_date) DO UPDATE SET
                net_sales          = EXCLUDED.net_sales,
                total_transactions = EXCLUDED.total_transactions,
                walkin_sales       = EXCLUDED.walkin_sales,
                online_sales       = EXCLUDED.online_sales,
                third_party_sales  = EXCLUDED.third_party_sales,
                lunch_sales        = EXCLUDED.lunch_sales,
                dinner_sales       = EXCLUDED.dinner_sales,
                morning_sales      = EXCLUDED.morning_sales
        """
    else:
        sql = f"""
            INSERT OR REPLACE INTO daily_sales
                (store_id, sale_date, net_sales, total_transactions,
                 walkin_sales, online_sales, third_party_sales,
                 lunch_sales, dinner_sales, morning_sales)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
        """
    cur = conn.cursor()
    batch = []
    for _, row in df.iterrows():
        batch.append((
            str(row["Store"]),
            str(row["Date"].date()),
            float(row["Net Sales"])          if row["Net Sales"] == row["Net Sales"] else None,
            int(row["Total Transactions"])   if row["Total Transactions"] == row["Total Transactions"] else None,
            float(row["Walk-In Sales"])      if row["Walk-In Sales"] == row["Walk-In Sales"] else None,
            float(row["Online Sales"])       if row["Online Sales"] == row["Online Sales"] else None,
            float(row["3rd Party Payments"]) if row["3rd Party Payments"] == row["3rd Party Payments"] else None,
            float(row["Lunch Net Sales"])    if row["Lunch Net Sales"] == row["Lunch Net Sales"] else None,
            float(row["Dinner Net Sales"])   if row["Dinner Net Sales"] == row["Dinner Net Sales"] else None,
            float(row["morning_sales"])      if row["morning_sales"] == row["morning_sales"] else None,
        ))
        if len(batch) >= 500:
            cur.executemany(sql, batch)
            conn.commit()
            batch = []
    if batch:
        cur.executemany(sql, batch)
        conn.commit()
    return len(df)

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "daily_export_seed.xlsx")
    if not os.path.exists(path):
        print(f"File not found: {path}")
        sys.exit(1)
    conn, dialect = get_conn()
    create_table(conn, dialect)
    print(f"Parsing {os.path.basename(path)}...")
    df = parse_excel(path)
    print(f"  {len(df)} rows, {df['Store'].nunique()} stores, "
          f"{df['Date'].min().date()} → {df['Date'].max().date()}")
    n = upsert_rows(conn, dialect, df)
    conn.close()
    print(f"✓ {n} rows upserted into daily_sales")

if __name__ == "__main__":
    main()
