"""
fix_supabase_stores.py
Drops and recreates the stores table in Supabase with correct columns.
Run once before migrate_to_supabase.py
"""
import psycopg2

DB_HOST     = "aws-1-us-east-1.pooler.supabase.com"
DB_PORT     = 5432
DB_NAME     = "postgres"
DB_USER     = "postgres.duxaqruvgggftxndubpn"
DB_PASSWORD = "a/TQ8,b6Xeh%X7!"  # <-- replace this

pg = psycopg2.connect(
    host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
    user=DB_USER, password=DB_PASSWORD, sslmode='require'
)
cur = pg.cursor()

# Drop all tables and recreate clean
tables = [
    'report_log', 'weekly_store_history', 'weekly_loyalty',
    'weekly_bread_totals', 'weekly_bread', 'weekly_market_totals',
    'weekly_sales', 'stores'
]
for t in tables:
    cur.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    print(f"Dropped {t}")

pg.commit()
pg.close()
print("\nDone - all tables dropped. Now run migrate_to_supabase.py")
