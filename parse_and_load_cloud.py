"""
parse_and_load.py - Updated with market totals + SS transaction derivation
"""

import pdfplumber
# Cloud version — uses psycopg2 (PostgreSQL) instead of sqlite3
import psycopg2
import re
import os
import argparse

DB_PATH = "jerseymikes.db"

def clean_money(val):
    if not val or not str(val).strip(): return None
    try: return float(re.sub(r'[$,]', '', str(val).strip()))
    except: return None

def clean_pct(val):
    if not val or not str(val).strip(): return None
    try: return float(str(val).strip().replace('%', ''))
    except: return None

def clean_num(val):
    if not val or not str(val).strip(): return None
    try: return float(re.sub(r'[,$]', '', str(val).strip()))
    except: return None

def clean_bread(val):
    if not val: return None, None
    match = re.match(r'([\d.]+)\s*\(\+([\d.]+)\)', str(val).strip())
    if match: return float(match.group(1)), float(match.group(2))
    try: return float(str(val).strip()), None
    except: return None, None

def derive_txn_pct(sss_pct, ticket_pct):
    """(1+SSS) = (1+TXN)*(1+TICKET)  =>  TXN = (1+SSS)/(1+TICKET) - 1"""
    if sss_pct is None or ticket_pct is None: return None
    try: return round(((1 + sss_pct/100) / (1 + ticket_pct/100) - 1) * 100, 4)
    except: return None

def extract_week_ending(filename):
    """Extract date from filename and convert to week-ENDING (Sunday) by adding 6 days."""
    match = re.match(r'(\d{4}-\d{2}-\d{2})', os.path.basename(filename))
    if not match: return None
    from datetime import datetime, timedelta
    d = datetime.strptime(match.group(1), '%Y-%m-%d') + timedelta(days=6)
    return d.strftime('%Y-%m-%d')

def is_store_row(row):
    if not row or len(row) < 3: return False
    return bool(row[2] and re.match(r'^\d{5}$', str(row[2]).strip()))

def is_total_row(row):
    if not row: return False, None, None
    for cell in row:
        if cell and 'Total' in str(cell):
            label = str(cell).strip()
            count_match = re.search(r'\((\d+)\s+Store', label)
            count = int(count_match.group(1)) if count_match else None
            market = re.sub(r'\s*Total.*$', '', label).strip()
            return True, market, count
    return False, None, None

def get_db(): return sqlite3.connect(DB_PATH)

def upsert_store(conn, store_id, city, state, co_op, franchisee):
    cur = conn.cursor()
    cur.execute("INSERT INTO stores (store_id, city, state, co_op, franchisee) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (store_id) DO NOTHING",
                 (store_id, city, state, co_op, franchisee))

def parse_sales_detail(pdf_path, week_ending, conn):
    store_rows = 0; total_rows = 0
    current_state = None; current_coop = None
    cur = conn.cursor()

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not row or len(row) < 14: continue

                    if row[0] and str(row[0]).strip() not in ('Co-\nOp\nState','Co-Op\nState',''):
                        current_state = str(row[0]).strip()
                    if row[1] and len(str(row[1]).strip()) > 1:
                        val = str(row[1]).strip()
                        if val not in ('Co-Op',): current_coop = val

                    if is_store_row(row):
                        store_id = row[2].strip()
                        upsert_store(conn, store_id,
                                     row[3].strip() if row[3] else None,
                                     current_state, current_coop,
                                     row[4].strip() if row[4] else None)
                        sss=clean_pct(row[6]); tkt=clean_pct(row[7])
                        txn=derive_txn_pct(sss,tkt)
                        fytd_sss=clean_pct(row[18]) if len(row)>18 else None
                        fytd_tkt=clean_pct(row[19]) if len(row)>19 else None
                        fytd_txn=derive_txn_pct(fytd_sss,fytd_tkt)
                        bread,wraps=clean_bread(row[8])
                        fytd_bread,fytd_wraps=clean_bread(row[17]) if len(row)>17 else (None,None)
                        cur.execute("""INSERT INTO weekly_sales (
                            week_ending,store_id,net_sales,sss_pct,same_store_ticket_pct,same_store_txn_pct,
                            avg_daily_bread,avg_daily_wraps,online_sales_pct,third_party_sales_pct,
                            non_loyalty_disc_pct,loyalty_disc_pct,loyalty_sales_pct,
                            fytd_net_sales,fytd_weekly_auv,fytd_avg_ticket,fytd_avg_daily_bread,
                            fytd_avg_daily_wraps,fytd_sss_pct,fytd_same_store_ticket,fytd_same_store_txn_pct
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (week_ending,store_id,clean_money(row[5]),sss,tkt,txn,
                         bread,wraps,clean_pct(row[9]),clean_pct(row[10]),
                         clean_pct(row[11]),clean_pct(row[12]),clean_pct(row[13]),
                         clean_money(row[14]) if len(row)>14 else None,
                         clean_money(row[15]) if len(row)>15 else None,
                         clean_money(row[16]) if len(row)>16 else None,
                         fytd_bread,fytd_wraps,fytd_sss,fytd_tkt,fytd_txn))
                        store_rows += 1

                    else:
                        is_tot,market,store_count=is_total_row(row)
                        if is_tot and market:
                            sss=clean_pct(row[6]); tkt=clean_pct(row[7])
                            txn=derive_txn_pct(sss,tkt)
                            fytd_sss=clean_pct(row[18]) if len(row)>18 else None
                            fytd_tkt=clean_pct(row[19]) if len(row)>19 else None
                            fytd_txn=derive_txn_pct(fytd_sss,fytd_tkt)
                            bread,_=clean_bread(row[8])
                            fytd_bread,_=clean_bread(row[17]) if len(row)>17 else (None,None)
                            cur.execute("""INSERT INTO weekly_market_totals (
                                week_ending,market,store_count,net_sales,sss_pct,
                                same_store_ticket_pct,same_store_txn_pct,avg_daily_bread,
                                online_sales_pct,third_party_sales_pct,non_loyalty_disc_pct,
                                loyalty_disc_pct,loyalty_sales_pct,fytd_net_sales,fytd_weekly_auv,
                                fytd_avg_ticket,fytd_avg_daily_bread,fytd_sss_pct,
                                fytd_same_store_ticket,fytd_same_store_txn_pct
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (week_ending,market,store_count,clean_money(row[5]),sss,tkt,txn,bread,
                             clean_pct(row[9]),clean_pct(row[10]),clean_pct(row[11]),
                             clean_pct(row[12]),clean_pct(row[13]),
                             clean_money(row[14]) if len(row)>14 else None,
                             clean_money(row[15]) if len(row)>15 else None,
                             clean_money(row[16]) if len(row)>16 else None,
                             fytd_bread,fytd_sss,fytd_tkt,fytd_txn))
                            total_rows += 1

    conn.commit()
    print(f"  ✅ Sales detail: {store_rows} store-weeks, {total_rows} market totals loaded")

def parse_bread_detail(pdf_path, week_ending, conn):
    rows_loaded = 0
    total_rows = 0
    cur = conn.cursor()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if is_store_row(row) and len(row) >= 16:
                        store_id = row[2].strip()
                        cur.execute("""INSERT INTO weekly_bread (
                            week_ending,store_id,bread_count,avg_daily_bread,avg_sales_per_loaf,
                            wrap_bowl_bread,wrap_bowl_avg_daily,prior_bread_count,prior_avg_daily_bread,
                            prior_avg_sales_per_loaf,prior_wrap_bowl_bread,prior_wrap_bowl_avg_daily,
                            same_store_bread_pct,fytd_bread_count,fytd_avg_daily_bread,
                            fytd_avg_sales_per_loaf,fytd_sss_bread_pct,fytd_wrap_bowl_bread,fytd_wrap_bowl_avg_daily
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (week_ending,store_id,clean_num(row[5]),clean_num(row[6]),clean_money(row[7]),
                         clean_num(row[8]),clean_num(row[9]),clean_num(row[10]),clean_num(row[11]),
                         clean_money(row[12]),clean_num(row[13]),clean_num(row[14]),clean_pct(row[15]),
                         clean_num(row[16]) if len(row)>16 else None,
                         clean_num(row[17]) if len(row)>17 else None,
                         clean_money(row[18]) if len(row)>18 else None,
                         clean_pct(row[19]) if len(row)>19 else None,
                         clean_num(row[20]) if len(row)>20 else None,
                         clean_num(row[21]) if len(row)>21 else None))
                        rows_loaded += 1
                    else:
                        is_tot, market, store_count = is_total_row(row)
                        if is_tot and market and len(row) >= 16:
                            cur.execute("""INSERT INTO weekly_bread_totals (
                                week_ending,market,store_count,
                                bread_count,avg_daily_bread,avg_sales_per_loaf,
                                same_store_bread_pct,fytd_bread_count,fytd_avg_daily_bread,
                                fytd_avg_sales_per_loaf,fytd_sss_bread_pct
                            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (week_ending,market,store_count,
                             clean_num(row[5]),clean_num(row[6]),clean_money(row[7]),
                             clean_pct(row[15]) if len(row)>15 else None,
                             clean_num(row[16]) if len(row)>16 else None,
                             clean_num(row[17]) if len(row)>17 else None,
                             clean_money(row[18]) if len(row)>18 else None,
                             clean_pct(row[19]) if len(row)>19 else None))
                            total_rows += 1
    conn.commit()
    print(f"  [OK] Bread detail: {rows_loaded} store-weeks, {total_rows} market totals loaded")

def parse_loyalty_detail(pdf_path, week_ending, conn):
    rows_loaded = 0
    cur = conn.cursor()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    if not is_store_row(row) or len(row) < 13: continue
                    store_id = row[2].strip()
                    cur.execute("""INSERT INTO weekly_loyalty (
                        week_ending,store_id,member_activations_current,member_activations_alltime,
                        member_transactions_current,member_transactions_alltime,
                        points_earned_current,points_earned_alltime,
                        points_redeemed_current,points_redeemed_alltime
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (week_ending,store_id,clean_num(row[5]),clean_num(row[6]),
                     clean_num(row[7]),clean_num(row[8]),clean_num(row[9]),
                     clean_num(row[10]),clean_num(row[11]),clean_num(row[12])))
                    rows_loaded += 1
    conn.commit()
    print(f"  ✅ Loyalty detail: {rows_loaded} store-weeks loaded")

def detect_report_type(filename):
    name = os.path.basename(filename).lower()
    if 'loyalty' in name: return 'loyalty'
    if 'bread' in name: return 'bread'
    if 'summary' in name: return 'summary'
    if 'sss' in name and 'bread' not in name: return 'sss'
    if 'detail' in name or 'dashboard' in name: return 'sales_detail'
    return 'unknown'

def process_pdfs(pdf_files):
    conn = get_db()
    for pdf_path in pdf_files:
        week_ending = extract_week_ending(pdf_path)
        report_type = detect_report_type(pdf_path)
        if not week_ending:
            print(f"⚠️  Could not extract date from: {pdf_path}"); continue
        already = conn.execute("SELECT id FROM report_log WHERE week_ending=%s AND report_type=%s",
                               (week_ending, report_type)).fetchone()
        if already:
            print(f"⏭️  Already processed: {os.path.basename(pdf_path)} — skipping"); continue
        print(f"\n📄 Processing: {os.path.basename(pdf_path)}")
        print(f"   Week ending: {week_ending} | Type: {report_type}")
        try:
            if report_type == 'sales_detail': parse_sales_detail(pdf_path, week_ending, conn)
            elif report_type == 'bread':      parse_bread_detail(pdf_path, week_ending, conn)
            elif report_type == 'loyalty':    parse_loyalty_detail(pdf_path, week_ending, conn)
            elif report_type in ('summary','sss'):
                print(f"  ℹ️  {report_type} — data covered by sales_detail, skipping")
            else:
                print(f"  ⚠️  Unknown type — skipping"); continue
            conn.execute("INSERT OR IGNORE INTO report_log (week_ending,report_type,filename) VALUES (%s,%s,%s)",
                         (week_ending,report_type,os.path.basename(pdf_path)))
            conn.commit()
        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback; traceback.print_exc()
    conn.close()
    print("\n✅ All PDFs processed.")

def process_pdf_folder(folder_path):
    process_pdfs([os.path.join(folder_path,f) for f in os.listdir(folder_path) if f.lower().endswith('.pdf')])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--folder'); group.add_argument('--files', nargs='+')
    args = parser.parse_args()
    if args.folder: process_pdf_folder(args.folder)
    else: process_pdfs(args.files)


def process_pdf(pdf_path, conn):
    """Process a single PDF file and load into PostgreSQL connection."""
    import os, re as _re
    from datetime import datetime, timedelta

    filename = os.path.basename(pdf_path)

    # Extract date from filename and convert to week-ending (Sunday)
    match = _re.match(r'(\d{4}-\d{2}-\d{2})', filename)
    if not match:
        print(f"  [SKIP] Cannot extract date from filename: {filename}")
        return

    d = datetime.strptime(match.group(1), '%Y-%m-%d') + timedelta(days=6)
    week_ending = d.strftime('%Y-%m-%d')

    # Detect report type
    fn_lower = filename.lower()
    if 'sales_dashboard_detail' in fn_lower or 'sales dashboard detail' in fn_lower:
        report_type = 'sales_detail'
    elif 'sss_bread_detail' in fn_lower or 'bread detail' in fn_lower:
        report_type = 'bread'
    elif 'loyalty_detail' in fn_lower or 'loyalty detail' in fn_lower:
        report_type = 'loyalty'
    else:
        print(f"  [SKIP] Unrecognized report type: {filename}")
        return

    cur = conn.cursor()

    if report_type == 'sales_detail':
        parse_sales_detail(pdf_path, week_ending, conn)
    elif report_type == 'bread':
        parse_bread_detail(pdf_path, week_ending, conn)
    elif report_type == 'loyalty':
        parse_loyalty_detail(pdf_path, week_ending, conn)

    # Log it
    cur.execute(
        "INSERT INTO report_log (week_ending, report_type, filename, processed_at) VALUES (%s, %s, %s, %s)",
        (week_ending, report_type, filename, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
    )
    conn.commit()
    print(f"  [OK] Loaded: {filename}")
