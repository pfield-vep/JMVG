"""
scripts/load_benchmark.py
=========================
Parses BlakeWard "Sales Dashboard Summary (Weekly)" PDFs and upserts the
Grand Total row into the weekly_benchmark table in Supabase / SQLite.

Usage — process a single file:
    py scripts/load_benchmark.py "benchmark_pdfs/2026-04-06 BlakeWard Sales Dashboard Summary (Weekly).pdf"

Usage — process all PDFs in the benchmark_pdfs/ folder:
    py scripts/load_benchmark.py

Only the "Sales Dashboard Summary" PDF is needed (the one with the Grand Total row).
The other PDFs (Detail, SSS Detail, Bread, Loyalty) are not required for this script.
"""

import os, sys, re
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

BENCHMARK_DIR = os.path.join(ROOT, "benchmark_pdfs")

# ── DB connection (same pattern as dashboard) ────────────────────────────────
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


# ── Create table ─────────────────────────────────────────────────────────────
CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS weekly_benchmark (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_ending     TEXT    NOT NULL UNIQUE,
    operator        TEXT    NOT NULL DEFAULT 'BlakeWard',
    store_count     INTEGER,
    net_sales       REAL,
    sss_pct         REAL,
    ss_ticket_pct   REAL,
    avg_daily_bread REAL,
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
    fytd_ss_ticket_pct     REAL
)
"""

CREATE_PG = """
CREATE TABLE IF NOT EXISTS weekly_benchmark (
    id              SERIAL  PRIMARY KEY,
    week_ending     TEXT    NOT NULL UNIQUE,
    operator        TEXT    NOT NULL DEFAULT 'BlakeWard',
    store_count     INTEGER,
    net_sales       REAL,
    sss_pct         REAL,
    ss_ticket_pct   REAL,
    avg_daily_bread REAL,
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
    fytd_ss_ticket_pct     REAL
)
"""

def create_table(conn, dialect):
    cur = conn.cursor()
    cur.execute(CREATE_PG if dialect == "postgres" else CREATE_SQLITE)
    conn.commit()
    print("weekly_benchmark table ready")


# ── Parsing helpers ───────────────────────────────────────────────────────────
def parse_pct(s):
    """'4.42%' → 4.42,  '-1.86%' → -1.86,  None/'' → None"""
    if not s:
        return None
    s = str(s).strip().replace('%', '').replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None

def parse_dollar(s):
    """'$3,393,630.12' → 3393630.12"""
    if not s:
        return None
    s = str(s).strip().replace('$', '').replace(',', '')
    try:
        return float(s)
    except ValueError:
        return None

def parse_bread(s):
    """'176.06 (+8.65)' → 176.06"""
    if not s:
        return None
    m = re.match(r'^([\d.]+)', str(s).strip())
    return float(m.group(1)) if m else None

def parse_week_ending(text):
    """
    Finds 'X/X/XX to X/X/XX' in the header and returns the end date as YYYY-MM-DD.
    e.g. '4/6/26 to 4/12/26' → '2026-04-12'
    """
    m = re.search(r'(\d{1,2}/\d{1,2}/\d{2,4})\s+to\s+(\d{1,2}/\d{1,2}/\d{2,4})', text)
    if not m:
        raise ValueError(f"Cannot find date range in PDF header. Text snippet:\n{text[:300]}")
    end_str = m.group(2)   # e.g. '4/12/26'
    for fmt in ('%m/%d/%y', '%m/%d/%Y'):
        try:
            d = datetime.strptime(end_str, fmt)
            return d.strftime('%Y-%m-%d')
        except ValueError:
            continue
    raise ValueError(f"Cannot parse end date: {end_str}")

def parse_store_count(label):
    """'GRAND TOTAL (119 Stores)' → 119"""
    m = re.search(r'\((\d+)\s+Stores?\)', str(label), re.IGNORECASE)
    return int(m.group(1)) if m else None


# ── Main PDF parser ───────────────────────────────────────────────────────────
def parse_summary_pdf(pdf_path):
    """
    Returns a dict with week_ending + all Grand Total metrics, ready to insert.
    """
    try:
        import pdfplumber
    except ImportError:
        print("Installing pdfplumber...")
        os.system(f"{sys.executable} -m pip install pdfplumber --break-system-packages -q")
        import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) == 0:
            raise ValueError("PDF has no pages")

        page = pdf.pages[0]
        full_text = page.extract_text() or ""
        week_ending = parse_week_ending(full_text)

        tables = page.extract_tables()
        if not tables:
            raise ValueError("No tables found in PDF")

        # The main table is the largest one
        table = max(tables, key=len)

        # Find the Grand Total row
        grand_row = None
        for row in table:
            if row and row[0] and 'GRAND TOTAL' in str(row[0]).upper():
                grand_row = row
                break

        if grand_row is None:
            raise ValueError("GRAND TOTAL row not found in table")

    # Column layout (0-indexed) based on observed PDF structure:
    # 0=Co-Op State, 1=Co-Op Name (Grand Total label), 2=Net Sales,
    # 3=SSS%, 4=SS Ticket%, 5=Avg Bread, 6=Online%, 7=3rd Party%,
    # 8=Non-Loyalty Disc%, 9=Loyalty Disc%, 10=Loyalty Sales%,
    # 11=FYTD Net Sales, 12=Weekly AUV, 13=Avg Ticket Size,
    # 14=FYTD Avg Bread, 15=FYTD SSS%, 16=FYTD SS Ticket%

    store_count = parse_store_count(grand_row[0])

    result = {
        "week_ending":            week_ending,
        "store_count":            store_count,
        "net_sales":              parse_dollar(grand_row[2]),
        "sss_pct":                parse_pct(grand_row[3]),
        "ss_ticket_pct":          parse_pct(grand_row[4]),
        "avg_daily_bread":        parse_bread(grand_row[5]),
        "online_sales_pct":       parse_pct(grand_row[6]),
        "third_party_sales_pct":  parse_pct(grand_row[7]),
        "non_loyalty_disc_pct":   parse_pct(grand_row[8]),
        "loyalty_disc_pct":       parse_pct(grand_row[9]),
        "loyalty_sales_pct":      parse_pct(grand_row[10]),
        "fytd_net_sales":         parse_dollar(grand_row[11]),
        "weekly_auv":             parse_dollar(grand_row[12]),
        "avg_ticket_size":        parse_dollar(grand_row[13]),
        "fytd_avg_daily_bread":   parse_bread(grand_row[14]),
        "fytd_sss_pct":           parse_pct(grand_row[15]),
        "fytd_ss_ticket_pct":     parse_pct(grand_row[16]),
    }

    print(f"  Parsed: week_ending={week_ending}, stores={store_count}, "
          f"SSS={result['sss_pct']:+.2f}%, Ticket={result['ss_ticket_pct']:+.2f}%")
    return result


# ── Upsert to DB ──────────────────────────────────────────────────────────────
def upsert(conn, dialect, row):
    p = "%s" if dialect == "postgres" else "?"

    if dialect == "postgres":
        sql = f"""
            INSERT INTO weekly_benchmark
                (week_ending, store_count, net_sales, sss_pct, ss_ticket_pct,
                 avg_daily_bread, online_sales_pct, third_party_sales_pct,
                 non_loyalty_disc_pct, loyalty_disc_pct, loyalty_sales_pct,
                 fytd_net_sales, weekly_auv, avg_ticket_size, fytd_avg_daily_bread,
                 fytd_sss_pct, fytd_ss_ticket_pct)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
            ON CONFLICT (week_ending) DO UPDATE SET
                store_count           = EXCLUDED.store_count,
                net_sales             = EXCLUDED.net_sales,
                sss_pct               = EXCLUDED.sss_pct,
                ss_ticket_pct         = EXCLUDED.ss_ticket_pct,
                avg_daily_bread       = EXCLUDED.avg_daily_bread,
                online_sales_pct      = EXCLUDED.online_sales_pct,
                third_party_sales_pct = EXCLUDED.third_party_sales_pct,
                non_loyalty_disc_pct  = EXCLUDED.non_loyalty_disc_pct,
                loyalty_disc_pct      = EXCLUDED.loyalty_disc_pct,
                loyalty_sales_pct     = EXCLUDED.loyalty_sales_pct,
                fytd_net_sales        = EXCLUDED.fytd_net_sales,
                weekly_auv            = EXCLUDED.weekly_auv,
                avg_ticket_size       = EXCLUDED.avg_ticket_size,
                fytd_avg_daily_bread  = EXCLUDED.fytd_avg_daily_bread,
                fytd_sss_pct          = EXCLUDED.fytd_sss_pct,
                fytd_ss_ticket_pct    = EXCLUDED.fytd_ss_ticket_pct
        """
    else:
        sql = f"""
            INSERT OR REPLACE INTO weekly_benchmark
                (week_ending, store_count, net_sales, sss_pct, ss_ticket_pct,
                 avg_daily_bread, online_sales_pct, third_party_sales_pct,
                 non_loyalty_disc_pct, loyalty_disc_pct, loyalty_sales_pct,
                 fytd_net_sales, weekly_auv, avg_ticket_size, fytd_avg_daily_bread,
                 fytd_sss_pct, fytd_ss_ticket_pct)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p})
        """

    vals = (
        row["week_ending"], row["store_count"], row["net_sales"],
        row["sss_pct"], row["ss_ticket_pct"], row["avg_daily_bread"],
        row["online_sales_pct"], row["third_party_sales_pct"],
        row["non_loyalty_disc_pct"], row["loyalty_disc_pct"], row["loyalty_sales_pct"],
        row["fytd_net_sales"], row["weekly_auv"], row["avg_ticket_size"],
        row["fytd_avg_daily_bread"], row["fytd_sss_pct"], row["fytd_ss_ticket_pct"],
    )

    conn.cursor().execute(sql, vals)
    conn.commit()
    print(f"  ✓ Upserted week_ending={row['week_ending']} into weekly_benchmark")


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    conn, dialect = get_conn()
    create_table(conn, dialect)

    # Collect PDFs to process
    if len(sys.argv) > 1:
        # Explicit file(s) passed on command line
        pdf_files = sys.argv[1:]
    else:
        # Scan benchmark_pdfs/ for Summary PDFs
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
                  "Drop the 'Sales Dashboard Summary (Weekly).pdf' files there and re-run.")
            return

    processed = 0
    for pdf_path in pdf_files:
        print(f"\nProcessing: {os.path.basename(pdf_path)}")
        try:
            row = parse_summary_pdf(pdf_path)
            upsert(conn, dialect, row)
            processed += 1
        except Exception as e:
            print(f"  ⚠️  Error: {e}")

    conn.close()
    print(f"\nDone — {processed} file(s) loaded into weekly_benchmark.")


if __name__ == "__main__":
    main()
