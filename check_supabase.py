import tomllib, os, psycopg2

secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.streamlit', 'secrets.toml')
with open(secrets_path, 'rb') as f:
    secrets = tomllib.load(f)
s = secrets['supabase']

conn = psycopg2.connect(host=s['host'], port=int(s['port']),
    dbname=s['dbname'], user=s['user'], password=s['password'], sslmode='require')
cur = conn.cursor()
cur.execute("SELECT DISTINCT week_ending FROM weekly_sales ORDER BY week_ending DESC LIMIT 10")
print("Weeks in Supabase weekly_sales:")
for row in cur.fetchall():
    print(" ", row[0])
conn.close()
