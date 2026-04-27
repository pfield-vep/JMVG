"""
scripts/load_hourly_sales.py
============================
One-time backfill (and ongoing upsert helper) for the hourly_sales table.

Table: hourly_sales
  store_id           TEXT   (e.g. '20011')
  sale_date          DATE
  hour               INTEGER  (0–23)
  net_sales          REAL
  total_transactions INTEGER
  UNIQUE (store_id, sale_date, hour)

Source file: JM Valley Daily Export - Hourly Sales.csv (inside a .zip)

Usage:
    py scripts/load_hourly_sales.py                          # loads seed zip in Dashboard root
    py scripts/load_hourly_sales.py path/to/file.zip         # loads a specific zip
    py scripts/load_hourly_sales.py path/to/file.csv         # loads a CSV directly
"""
import os, sys, zipfile, io
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

SEED_ZIP = os.path.join(ROOT, "hourly_export_seed.zip")


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
                print(f"⚠️  Supabase failed ({e}), falling back to SQLite")
    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"


CREATE_PG = """
CREATE TABLE IF NOT EXISTS hourly_sales (
    id                 SERIAL  PRIMARY KEY,
    store_id           TEXT    NOT NULL,
    sale_date          DATE    NOT NULL,
    hour               INTEGER NOT NULL,
    net_sales          REAL,
    total_transactions INTEGER,
    UNIQUE (store_id, sale_date, hour)
)"""

CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS hourly_sales (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    store_id           TEXT    NOT NULL,
    sale_date          TEXT    NOT NULL,
    hour               INTEGER NOT NULL,
    net_sales          REAL,
    total_transactions INTEGER,
    UNIQUE (store_id, sale_date, hour)
)"""


def create_table(conn, dialect):
    cur = conn.cursor()
    cur.execute(CREATE_PG if dialect == "postgres" else CREATE_SQLITE)
    conn.commit()
    print("hourly_sales table ready")


def get_latest_date(conn):
    """Return the latest sale_date already stored, or None."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(sale_date) FROM hourly_sales")
        row = cur.fetchone()
        if row and row[0]:
            import pandas as pd
            return pd.to_datetime(row[0]).date()
    except Exception:
        pass
    return None


def parse_file(source, after_date=None):
    """
    Parse a zip or CSV file path, or a BytesIO/bytes object from an email attachment.
    Returns a DataFrame filtered to rows after after_date (if provided).

    source can be:
      - str path ending in .zip  → extract CSV inside
      - str path ending in .csv  → read directly
      - bytes / BytesIO          → detect zip vs csv by magic bytes
    """
    import pandas as pd, shutil, tempfile

    # Normalise to bytes
    if isinstance(source, (str, os.PathLike)):
        with open(source, "rb") as f:
            raw = f.read()
    elif isinstance(source, (bytes, bytearray)):
        raw = bytes(source)
    else:
        raw = source.read()   # BytesIO

    # Detect zip vs CSV
    if raw[:2] == b'PK':   # ZIP magic bytes
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            csv_names = [n for n in z.namelist() if n.lower().endswith('.csv')]
            if not csv_names:
                raise ValueError("No CSV found inside the zip file")
            with z.open(csv_names[0]) as f:
                df = pd.read_csv(f)
    else:
        df = pd.read_csv(io.BytesIO(raw))

    # Normalise columns
    df.columns = [c.strip() for c in df.columns]
    df["store_id"]  = df["Store"].astype(str).str.strip()
    df["sale_date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["hour"]      = pd.to_numeric(df["Hour"], errors="coerce").astype("Int64")
    df["net_sales"] = pd.to_numeric(df["Net Sales"], errors="coerce")
    df["total_transactions"] = pd.to_numeric(df["Total Transactions"], errors="coerce")

    df = df.dropna(subset=["store_id", "sale_date", "hour"])

    if after_date:
        before = len(df)
        df = df[df["sale_date"].dt.date > after_date]
        print(f"  Incremental mode: {len(df):,} new rows "
              f"(skipped {before - len(df):,} already stored, latest was {after_date})")
    else:
        print(f"  Full load: {len(df):,} rows, "
              f"{df['sale_date'].min().date()} → {df['sale_date'].max().date()}")

    return df


def upsert_rows(conn, dialect, df, batch_size=500):
    """Upsert DataFrame into hourly_sales in batches."""
    if df.empty:
        return 0
    p = "%s" if dialect == "postgres" else "?"
    if dialect == "postgres":
        sql = f"""
            INSERT INTO hourly_sales
                (store_id, sale_date, hour, net_sales, total_transactions)
            VALUES ({p},{p},{p},{p},{p})
            ON CONFLICT (store_id, sale_date, hour) DO UPDATE SET
                net_sales          = EXCLUDED.net_sales,
                total_transactions = EXCLUDED.total_transactions
        """
    else:
        sql = f"""
            INSERT OR REPLACE INTO hourly_sales
                (store_id, sale_date, hour, net_sales, total_transactions)
            VALUES ({p},{p},{p},{p},{p})
        """
    cur = conn.cursor()
    batch = []
    total = len(df)
    inserted = 0
    for _, row in df.iterrows():
        ns  = float(row["net_sales"])  if row["net_sales"]  == row["net_sales"]  else None
        txn = int(row["total_transactions"]) if row["total_transactions"] == row["total_transactions"] else None
        batch.append((
            str(row["store_id"]),
            str(row["sale_date"].date()),
            int(row["hour"]),
            ns, txn,
        ))
        if len(batch) >= batch_size:
            cur.executemany(sql, batch)
            conn.commit()
            inserted += len(batch)
            batch = []
            pct = inserted / total * 100
            print(f"  {inserted:,} / {total:,} rows ({pct:.0f}%)", end="\r", flush=True)
    if batch:
        cur.executemany(sql, batch)
        conn.commit()
        inserted += len(batch)
    print(f"  {inserted:,} / {total:,} rows (100%) — complete          ")
    return inserted


def main():
    import shutil
    path = sys.argv[1] if len(sys.argv) > 1 else SEED_ZIP
    if not os.path.exists(path):
        print(f"File not found: {path}")
        print(f"Copy the zip to {SEED_ZIP} and re-run, or pass the path as an argument.")
        sys.exit(1)

    conn, dialect = get_conn()
    create_table(conn, dialect)

    latest = get_latest_date(conn)
    print(f"Parsing {os.path.basename(path)}...")
    df = parse_file(path, after_date=latest)

    if df.empty:
        print("✓ Already up to date — nothing to upsert.")
        conn.close()
        return

    stores = df["store_id"].nunique()
    print(f"  {stores} stores found")
    n = upsert_rows(conn, dialect, df)
    conn.close()
    print(f"✓ {n:,} rows upserted into hourly_sales")


if __name__ == "__main__":
    main()
