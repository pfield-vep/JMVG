"""
setup_token_storage.py
Run ONCE to create the app_settings table in Supabase and store the refresh token.
After running, the token is managed automatically — no more manual GitHub secret updates.
"""
import os, tomllib, psycopg2

secrets_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.streamlit', 'secrets.toml')
with open(secrets_path, 'rb') as f:
    secrets = tomllib.load(f)
s = secrets['supabase']

conn = psycopg2.connect(
    host=s['host'], port=int(s['port']),
    dbname=s['dbname'], user=s['user'],
    password=s['password'], sslmode='require'
)
cur = conn.cursor()

# Create table if not exists
cur.execute("""
    CREATE TABLE IF NOT EXISTS app_settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
""")

# Read token from refresh_token.txt
token_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'refresh_token.txt')
with open(token_path, 'r') as f:
    token = f.read().strip()

# Insert or update
cur.execute("""
    INSERT INTO app_settings (key, value) VALUES ('azure_refresh_token', %s)
    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
""", (token,))

conn.commit()
conn.close()
print("✅ Done! Token stored in Supabase. You can now delete refresh_token.txt.")
