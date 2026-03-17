import sqlite3

conn = sqlite3.connect("jerseymikes.db")

rows = conn.execute("SELECT week_ending, market, store_count, same_store_bread_pct, fytd_sss_bread_pct FROM weekly_bread_totals ORDER BY week_ending, store_count DESC").fetchall()

if not rows:
    print("ERROR - weekly_bread_totals table is EMPTY")
    print("You need to re-parse the bread PDFs:")
    print('  py parse_and_load.py --folder "WeeklyPDF\\2026-03-09"')
    print('  py parse_and_load.py --folder "WeeklyPDF\\2026-03-02"')
else:
    print(f"OK - {len(rows)} rows in weekly_bread_totals:")
    for r in rows:
        print(f"  {r[0]} | {r[1]:<30} | stores:{r[2]} | SS Bread:{r[3]} | FYTD:{r[4]}")

conn.close()
