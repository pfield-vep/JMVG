"""
scripts/update_stores.py
=========================
Updates the stores table with data from jm locations.xlsx:
  - open_date (including corrected dates for acquired SD stores)
  - acquisition_date
  - entity_name, broad_geography, sq_footage, format, address
  - dm_name, dm_effective_date (new columns)

Also creates store_dm_history table and seeds it with current DM assignments.

Usage:  py scripts/update_stores.py path/to/jm_locations.xlsx
        py scripts/update_stores.py   (looks for jm_locations.xlsx in Dashboard root)
"""
import os, sys
from datetime import date, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

DEFAULT_XLSX = os.path.join(ROOT, "jm_locations.xlsx")


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
                print(f"⚠️  Supabase failed: {e}")
    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    return sqlite3.connect(db), "sqlite"


def parse_date(val):
    """Parse various date formats to ISO string, return None if unparseable."""
    if val is None or (hasattr(val, '__class__') and val.__class__.__name__ == 'NaTType'):
        return None
    if isinstance(val, (datetime, date)):
        return val.strftime('%Y-%m-%d')
    s = str(val).strip()
    if not s or s.lower() in ('nat', 'none', 'nan', ''):
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(s.split(' ')[0], fmt.split(' ')[0]).strftime('%Y-%m-%d')
        except ValueError:
            continue
    print(f"  ⚠️  Could not parse date: {repr(val)}")
    return None


def migrate_schema(conn, dialect):
    """Add new columns to stores and create store_dm_history if needed."""
    cur = conn.cursor()
    p = "%s" if dialect == "postgres" else "?"

    new_cols = [
        ("open_date",         "TEXT"),
        ("acquisition_date",  "TEXT"),
        ("dm_name",           "TEXT"),
        ("dm_effective_date", "TEXT"),
        ("entity_name",       "TEXT"),
        ("broad_geography",   "TEXT"),
        ("sq_footage",        "REAL"),
        ("store_format",      "TEXT"),
        ("address",           "TEXT"),
    ]
    for col, dtype in new_cols:
        try:
            cur.execute(f"ALTER TABLE stores ADD COLUMN {col} {dtype}")
            print(f"  + Added column: stores.{col}")
        except Exception:
            pass  # column already exists

    # store_dm_history table
    if dialect == "postgres":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS store_dm_history (
                id             SERIAL PRIMARY KEY,
                store_id       TEXT NOT NULL,
                dm_name        TEXT NOT NULL,
                effective_date DATE NOT NULL,
                end_date       DATE,
                UNIQUE (store_id, effective_date)
            )
        """)
    else:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS store_dm_history (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                store_id       TEXT NOT NULL,
                dm_name        TEXT NOT NULL,
                effective_date TEXT NOT NULL,
                end_date       TEXT,
                UNIQUE (store_id, effective_date)
            )
        """)
    conn.commit()
    print("Schema migration complete")


def load_excel(path):
    import pandas as pd
    df = pd.read_excel(path)
    df.columns = [c.strip() for c in df.columns]
    df['Store Number'] = df['Store Number'].astype(str).str.strip()
    return df


def update_stores(conn, dialect, df):
    p = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()
    today = date.today().isoformat()
    updated = 0

    for _, row in df.iterrows():
        store_id        = str(row['Store Number']).strip()
        open_date       = parse_date(row.get('Date Opened'))
        acq_date        = parse_date(row.get('Acquired Date'))
        entity_name     = str(row.get('Entity Name', '') or '').strip() or None
        broad_geo       = str(row.get('Broad Geography', '') or '').strip() or None
        sq_ft           = float(row['Square Footage']) if str(row.get('Square Footage','')).replace('.','').isdigit() else None
        fmt             = str(row.get('Format', '') or '').strip() or None
        address         = str(row.get('Address', '') or '').strip() or None
        dm_name         = str(row.get('DM', '') or '').strip() or None
        dm_update_raw   = row.get('DM Name Update')
        dm_eff_date     = parse_date(dm_update_raw) or today

        sql = f"""
            UPDATE stores SET
                open_date        = {p},
                acquisition_date = {p},
                entity_name      = {p},
                broad_geography  = {p},
                sq_footage       = {p},
                store_format     = {p},
                address          = {p},
                dm_name          = {p},
                dm_effective_date= {p}
            WHERE store_id = {p}
        """
        cur.execute(sql, (
            open_date, acq_date, entity_name, broad_geo,
            sq_ft, fmt, address, dm_name, dm_eff_date,
            store_id
        ))
        if cur.rowcount == 0:
            print(f"  ⚠️  store_id {store_id} not found in stores table")
        else:
            updated += 1
            print(f"  ✓ {store_id:5s}  open={open_date}  acq={acq_date}  DM={dm_name}")

    conn.commit()
    print(f"\n  {updated} store(s) updated")
    return df[['Store Number', 'DM', 'DM Name Update']].copy()


def seed_dm_history(conn, dialect, dm_df):
    """Insert current DM assignments into store_dm_history (skip if already exists)."""
    p = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()
    today = date.today().isoformat()
    inserted = 0

    for _, row in dm_df.iterrows():
        store_id  = str(row['Store Number']).strip()
        dm_name   = str(row['DM'] or '').strip()
        eff_date  = parse_date(row.get('DM Name Update')) or today
        if not dm_name:
            continue
        if dialect == "postgres":
            sql = f"""
                INSERT INTO store_dm_history (store_id, dm_name, effective_date)
                VALUES ({p},{p},{p})
                ON CONFLICT (store_id, effective_date) DO NOTHING
            """
        else:
            sql = f"""
                INSERT OR IGNORE INTO store_dm_history (store_id, dm_name, effective_date)
                VALUES ({p},{p},{p})
            """
        cur.execute(sql, (store_id, dm_name, eff_date))
        if cur.rowcount:
            inserted += 1

    conn.commit()
    print(f"  {inserted} DM history row(s) inserted into store_dm_history")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_XLSX
    if not os.path.exists(path):
        print(f"File not found: {path}")
        print(f"Expected: {DEFAULT_XLSX}")
        sys.exit(1)

    conn, dialect = get_conn()
    print(f"\nMigrating schema...")
    migrate_schema(conn, dialect)

    print(f"\nLoading {os.path.basename(path)}...")
    df = load_excel(path)
    print(f"  {len(df)} stores found\n")

    print("Updating stores table...")
    dm_df = update_stores(conn, dialect, df)

    print("\nSeeding store_dm_history...")
    seed_dm_history(conn, dialect, dm_df)

    conn.close()
    print("\n✓ Done.")


if __name__ == "__main__":
    main()
