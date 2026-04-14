"""
scripts/load_benchmark.py
=========================
Parses BlakeWard "Sales Dashboard Summary (Weekly)" PDFs and upserts every
region Total row + the Grand Total into the weekly_benchmark table.

Regions stored: FL, KC, KS, MO, NC, NY, SC  +  TOTAL (Grand Total)

Usage — process all PDFs in benchmark_pdfs/ folder (most common):
    py scripts/load_benchmark.py

Usage — process a specific file:
    py scripts/load_benchmark.py "path/to/file.pdf"

Only the "Sales Dashboard Summary" PDF is needed per week.
"""

import os, sys, re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

BENCHMARK_DIR = os.path.join(ROOT, "benchmark_pdfs")

# ── DB connection ─────────────────────────────────────────────────────────────
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
            import psycopg2
            s = cfg["supabase"]
            conn = psycopg2.connect(
                host=s["host"], port=int(s["port"]),
                dbname=s["dbname"], user=s["user"],
                password=s["password"], sslmode="require"
            )
            print("Connected to Supabase / Postgres")
            return conn, "postgres"
    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"


# ── Create / migrate table ────────────────────────────────────────────────────
CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS weekly_benchmark (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_ending     TEXT    NOT NULL,
    region          TEXT    NOT NULL DEFAULT 'TOTAL',
    region_name     TEXT,
    store_count     INTEGER,
    net_sales              REAL,
    sss_pct                REAL,
    ss_ticket_pct          REAL,
    avg_daily_bread        REAL,
    online_sales_pct       REAL,
    third_party_sales_pct  REAL,
    non_loyalty_disc_pct   REAL,
    loyalty_disc_pct       REAL,
    loyalty_sales_pct      REAL,
    fytd_net_sales         REAL,
    weekly_auv             REAL,
    avg_ticket_size        REAL,
    fytd_avg_daily_bread   REAL,
    fytd_sss_pct           REAL,
    fytd_ss_ticket_pct     REAL,
    UNIQUE (week_ending, region)
)
"""

CREATE_PG = """
CREATE TABLE IF NOT EXISTS weekly_benchmark (
    id              SERIAL  PRIMARY KEY,
    week_ending     TEXT    NOT NULL,
    region          TEXT    NOT NULL DEFAULT 'TOTAL',
    region_name     TEXT,
    store_count     INTEGER,
    net_sales              REAL,
    sss_pct                REAL,
    ss_ticket_pct          REAL,
    avg_daily_bread        REAL,
    online_sales_pct       REAL,
    third_party_sales_pct  REAL,
    non_loyalty_disc_pct   REAL,
    loyalty_disc_pct       REAL,
    loyalty_sales_pct      REAL,
    fytd_net_sales         REAL,
    weekly_auv             REAL,
    avg_ticket_size        REAL,
    fytd_avg_daily_bread   REAL,
    fytd_sss_pct           REAL,
    fytd_ss_ticket_pct     REAL,
    UNIQUE (week_ending, region)
)
"""

def create_table(conn, dialect):
    cur = conn.cursor()
    if dialect == "postgres":
        # Drop and recreate so schema is always current
        cur.execute("DROP TABLE IF EXISTS weekly_benchmark")
        cur.execute(CREATE_PG)
    else:
        cur.execute(CREATE_SQLITE)
    conn.commit()
    print("weekly_benchmark table ready")


# ── Parsing helpers ───────────────────────────────────────────────────────────
def parse_pct(s):
    if not s:
        return None
    s = str(s).strip().replace('%', '').replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None

def parse_dollar(s):
    if not s:
        return None
    s = str(s).strip().replace('$', '').replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None

def parse_bread(s):
    if not s:
        return None
    m = re.match(r'^([\d.]+)', str(s).strip())
    return float(m.group(1)) if m else None

def parse_store_count(label):
    m = re.search(r'\((\d+)\s+Stores?\)', str(label), re.IGNORECASE)
    return int(m.group(1)) if m else None

def parse_week_ending(text):
    """'4/6/26 to 4/12/26' → '2026-04-12'"""
    m = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}\s+to\s+(\d{1,2}/\d{1,2}/\d{2,4})', text)
    if not m:
        raise ValueError(f"Cannot find date range in PDF. Text:\n{text[:300]}")
    end_str = m.group(1)
    for fmt in ('%m/%d/%y', '%m/%d/%Y'):
        try:
            return datetime.strptime(end_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    raise ValueError(f"Cannot parse end date: {end_str}")

def row_to_record(row, region, region_name, week_ending):
    """Convert a table row (columns 2–16) to a dict."""
    return {
        "week_ending":           week_ending,
        "region":                region,
        "region_name":           region_name,
        "store_count":           parse_store_count(region_name),
        "net_sales":             parse_dollar(row[2]),
        "sss_pct":               parse_pct(row[3]),
        "ss_ticket_pct":         parse_pct(row[4]),
        "avg_daily_bread":       parse_bread(row[5]),
        "online_sales_pct":      parse_pct(row[6]),
        "third_party_sales_pct": parse_pct(row[7]),
        "non_loyalty_disc_pct":  parse_pct(row[8]),
        "loyalty_disc_pct":      parse_pct(row[9]),
        "loyalty_sales_pct":     parse_pct(row[10]),
        "fytd_net_sales":        parse_dollar(row[11]),
        "weekly_auv":            parse_dollar(row[12]),
        "avg_ticket_size":       parse_dollar(row[13]),
        "fytd_avg_daily_bread":  parse_bread(row[14]),
        "fytd_sss_pct":          parse_pct(row[15]),
        "fytd_ss_ticket_pct":    parse_pct(row[16]) if len(row) > 16 else None,
    }


# ── PDF parser ────────────────────────────────────────────────────────────────
def parse_summary_pdf(pdf_path):
    """
    Returns a list of dicts — one per region (FL, KC, KS, MO, NC, NY, SC) +
    one for TOTAL (Grand Total).  Only Total/Grand-Total rows are captured;
    sub-region detail rows are skipped.
    """
    try:
        import pdfplumber
    except ImportError:
        print("Installing pdfplumber...")
        os.system(f"{sys.executable} -m pip install pdfplumber --break-system-packages -q")
        import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        if not pdf.pages:
            raise ValueError("PDF has no pages")
        page = pdf.pages[0]
        full_text = page.extract_text() or ""
        week_ending = parse_week_ending(full_text)

        tables = page.extract_tables()
        if not tables:
            raise ValueError("No tables found in PDF")
        table = max(tables, key=len)   # main data table

    records = []
    for row in table:
        if not row or not any(row):
            continue

        col0 = str(row[0] or "").strip()
        col1 = str(row[1] or "").strip()

        # Grand Total row: col0 = "GRAND TOTAL (119 Stores)"
        if "GRAND TOTAL" in col0.upper():
            rec = row_to_record(row, "TOTAL", col0, week_ending)
            records.append(rec)

        # State Total rows: col1 = "FL Total (11 Stores)", etc.
        elif re.match(r'^[A-Z]{2,}\s+Total', col1):
            m = re.match(r'^([A-Z]{2,})', col1)
            region = m.group(1) if m else col1[:5]
            rec = row_to_record(row, region, col1, week_ending)
            records.append(rec)
        # else: sub-region detail row — skip

    if not records:
        raise ValueError("No Total or Grand Total rows found in table")

    print(f"  Week ending {week_ending}: {len(records)} rows parsed")
    for r in records:
        print(f"    {r['region']:6s}  {r['region_name'][:35]:35s}  "
              f"SSS={r['sss_pct']:+.2f}%  Ticket={r['ss_ticket_pct']:+.2f}%")
    return records


# ── Upsert ────────────────────────────────────────────────────────────────────
COLS = [
    "week_ending","region","region_name","store_count","net_sales",
    "sss_pct","ss_ticket_pct","avg_daily_bread","online_sales_pct",
    "third_party_sales_pct","non_loyalty_disc_pct","loyalty_disc_pct",
    "loyalty_sales_pct","fytd_net_sales","weekly_auv","avg_ticket_size",
    "fytd_avg_daily_bread","fytd_sss_pct","fytd_ss_ticket_pct",
]

def upsert_records(conn, dialect, records):
    p = "%s" if dialect == "postgres" else "?"
    placeholders = ",".join([p] * len(COLS))
    col_list = ",".join(COLS)

    if dialect == "postgres":
        update_set = ",\n".join(
            f"    {c} = EXCLUDED.{c}"
            for c in COLS if c not in ("week_ending", "region")
        )
        sql = f"""
            INSERT INTO weekly_benchmark ({col_list})
            VALUES ({placeholders})
            ON CONFLICT (week_ending, region) DO UPDATE SET
            {update_set}
        """
    else:
        sql = f"INSERT OR REPLACE INTO weekly_benchmark ({col_list}) VALUES ({placeholders})"

    cur = conn.cursor()
    for rec in records:
        vals = tuple(rec[c] for c in COLS)
        cur.execute(sql, vals)
    conn.commit()
    print(f"  ✓ {len(records)} rows upserted into weekly_benchmark")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    conn, dialect = get_conn()
    create_table(conn, dialect)

    if len(sys.argv) > 1:
        pdf_files = sys.argv[1:]
    else:
        if not os.path.isdir(BENCHMARK_DIR):
            print(f"No benchmark_pdfs/ folder found at {BENCHMARK_DIR}")
            print("Create it and drop the BlakeWard Summary PDFs inside, then re-run.")
            return
        pdf_files = [
            os.path.join(BENCHMARK_DIR, f)
            for f in sorted(os.listdir(BENCHMARK_DIR))
            if f.lower().endswith(".pdf") and "summary" in f.lower()
        ]
        if not pdf_files:
            print("No Summary PDFs found in benchmark_pdfs/. "
                  "Drop 'Sales Dashboard Summary (Weekly).pdf' files there and re-run.")
            return

    processed = 0
    for pdf_path in pdf_files:
        print(f"\nProcessing: {os.path.basename(pdf_path)}")
        try:
            records = parse_summary_pdf(pdf_path)
            upsert_records(conn, dialect, records)
            processed += 1
        except Exception as e:
            print(f"  ⚠️  Error: {e}")

    conn.close()
    print(f"\nDone — {processed} file(s) loaded into weekly_benchmark.")


if __name__ == "__main__":
    main()
