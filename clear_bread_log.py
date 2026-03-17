import sqlite3
conn = sqlite3.connect("jerseymikes.db")
deleted = conn.execute("DELETE FROM report_log WHERE report_type='bread'").rowcount
conn.commit()
conn.close()
print(f"Done - cleared {deleted} bread log entries")
