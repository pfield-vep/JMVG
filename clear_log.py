import sqlite3

conn = sqlite3.connect("jerseymikes.db")
types = conn.execute("SELECT DISTINCT report_type FROM report_log").fetchall()
print(f"Clearing {len(types)} report types...")
conn.execute("DELETE FROM report_log")
conn.commit()
conn.close()
print("Done - all report log entries cleared. Ready to re-parse all PDFs.")
