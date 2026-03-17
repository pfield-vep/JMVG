"""
migrate_dates.py
Shifts all PDF-derived week dates from Monday (week-beginning) to
Sunday (week-ending) by adding 6 days. Run once.
"""
import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect("jerseymikes.db")
c = conn.cursor()

tables = ['weekly_sales', 'weekly_market_totals', 'weekly_bread',
          'weekly_bread_totals', 'weekly_loyalty', 'report_log']

total_updated = 0
for t in tables:
    try:
        rows = c.execute(f"SELECT DISTINCT week_ending FROM {t}").fetchall()
        for (old_date,) in rows:
            d = datetime.strptime(old_date, '%Y-%m-%d')
            # Only shift Monday dates (week-beginning) — skip Sundays already correct
            if d.weekday() == 0:  # 0 = Monday
                new_date = (d + timedelta(days=6)).strftime('%Y-%m-%d')
                c.execute(f"UPDATE {t} SET week_ending=? WHERE week_ending=?",
                          (new_date, old_date))
                print(f"  {t}: {old_date} -> {new_date}")
                total_updated += 1
            else:
                print(f"  {t}: {old_date} already week-ending ({d.strftime('%A')}) - skipped")
    except Exception as e:
        print(f"  {t} ERROR: {e}")

conn.commit()
conn.close()
print(f"\nDone - {total_updated} date(s) updated to week-ending format.")
print("Future PDFs will automatically use week-ending dates.")
