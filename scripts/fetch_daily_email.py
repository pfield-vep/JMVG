"""
scripts/fetch_daily_email.py
============================
Fetches the latest "JM Valley Daily Export" email from Vantage Point,
extracts the Excel attachment, and upserts into daily_sales.

Runs automatically via the scheduled task at 11:15 AM CT daily.
Can also be run manually:  py scripts/fetch_daily_email.py
"""
import os, sys, io, base64, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CLIENT_ID  = "44f09a6a-eae4-43d6-bd80-3c806a3b2d1a"
TENANT_ID  = "8dc59d31-158a-4afd-855d-446c26c6adc7"
SENDER     = "vpnotifications@vp-analytics.com"
SUBJECT_KW = "JM Valley Daily Export"

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
            try:
                import psycopg2
                s = cfg["supabase"]
                conn = psycopg2.connect(
                    host=s["host"], port=int(s["port"]),
                    dbname=s["dbname"], user=s["user"],
                    password=s["password"], sslmode="require"
                )
                return conn, "postgres"
            except Exception as e:
                print(f"⚠️  Supabase failed: {e}")
    import sqlite3
    return sqlite3.connect(os.path.join(ROOT, "jerseymikes.db")), "sqlite"

def get_tokens(conn, dialect):
    """Read refresh token from DB, return (access_token, new_refresh_token)."""
    import requests
    p = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()
    cur.execute(f"SELECT value FROM app_settings WHERE key = {p}", ("azure_refresh_token",))
    row = cur.fetchone()
    refresh_token = (row[0].strip() if row else "")
    if not refresh_token:
        import streamlit as st
        refresh_token = (st.secrets.get("AZURE_REFRESH_TOKEN") or
                         os.environ.get("AZURE_REFRESH_TOKEN","")).strip()
    if not refresh_token:
        raise RuntimeError("No Azure refresh token found in DB or secrets")

    resp = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={"grant_type":"refresh_token","client_id":CLIENT_ID,
              "refresh_token":refresh_token,
              "scope":"https://graph.microsoft.com/Mail.Read offline_access"},
    )
    resp.raise_for_status()
    result      = resp.json()
    access_tok  = result["access_token"]
    new_refresh = result.get("refresh_token", refresh_token)
    if new_refresh != refresh_token:
        cur.execute(
            f"INSERT INTO app_settings (key,value) VALUES ({p},{p}) "
            f"ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
            ("azure_refresh_token", new_refresh)
        )
        conn.commit()
    return access_tok

def find_latest_email(access_token):
    import requests
    headers = {"Authorization": f"Bearer {access_token}"}

    # Strategy 1: Graph search by subject
    r = requests.get(
        "https://graph.microsoft.com/v1.0/me/messages"
        f"?$search=\"{SUBJECT_KW}\""
        "&$select=id,subject,receivedDateTime,hasAttachments,from"
        "&$top=5",
        headers={**headers, "ConsistencyLevel": "eventual"},
    )
    if r.status_code == 200:
        for msg in r.json().get("value", []):
            from_addr = msg.get("from",{}).get("emailAddress",{}).get("address","")
            if msg.get("hasAttachments") and (
                from_addr.lower() == SENDER.lower() or
                "vp-analytics" in from_addr.lower() or
                SUBJECT_KW.lower() in msg.get("subject","").lower()
            ):
                print(f"  Found via search: \"{msg['subject']}\" from {from_addr}")
                return msg["id"]

    # Strategy 2: scan recent 50 messages
    r2 = requests.get(
        "https://graph.microsoft.com/v1.0/me/messages"
        "?$orderby=receivedDateTime desc"
        "&$select=id,subject,receivedDateTime,hasAttachments,from"
        "&$top=50",
        headers=headers,
    )
    r2.raise_for_status()
    for msg in r2.json().get("value", []):
        from_addr = msg.get("from",{}).get("emailAddress",{}).get("address","")
        subj      = msg.get("subject","")
        if msg.get("hasAttachments") and (
            from_addr.lower() == SENDER.lower() or
            "vp-analytics" in from_addr.lower() or
            SUBJECT_KW.lower() in subj.lower()
        ):
            print(f"  Found via scan: \"{subj}\" from {from_addr}")
            return msg["id"]
    return None

def download_excel(access_token, message_id):
    import requests
    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments",
        headers=headers,
    )
    r.raise_for_status()
    for att in r.json().get("value", []):
        name = att.get("name","")
        if name.lower().endswith(".xlsx") or name.lower().endswith(".xls"):
            print(f"  Downloading attachment: {name}")
            return att.get("contentBytes",""), name
    return None, None

def main():
    print("=== JM Valley Daily Sales Fetch ===")
    conn, dialect = get_conn()

    print("Getting access token...")
    access_token = get_tokens(conn, dialect)
    print("  ✓ Access token obtained")

    print("Searching for latest daily export email...")
    msg_id = find_latest_email(access_token)
    if not msg_id:
        print("  ✗ No matching email found — check sender address or subject")
        conn.close()
        return 0

    content_b64, fname = download_excel(access_token, msg_id)
    if not content_b64:
        print("  ✗ No Excel attachment found in email")
        conn.close()
        return 0

    xl_bytes = base64.b64decode(content_b64)
    print(f"  ✓ Downloaded {fname} ({len(xl_bytes):,} bytes)")

    # Parse and upsert — only new rows
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from load_daily_sales import create_table, parse_excel, upsert_rows
    create_table(conn, dialect)

    import pandas as pd

    # Find the latest date already stored so we only upsert new rows
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(sale_date) FROM daily_sales")
        row = cur.fetchone()
        latest_stored = pd.to_datetime(row[0]).date() if row and row[0] else None
    except Exception:
        latest_stored = None

    df = parse_excel(io.BytesIO(xl_bytes))
    total_rows = len(df)

    if latest_stored:
        df = df[df["Date"].dt.date > latest_stored]
        print(f"  Latest in DB: {latest_stored}  →  {len(df)} new rows to upsert "
              f"(skipped {total_rows - len(df):,} already-stored rows)")
    else:
        print(f"  No existing data — upserting all {total_rows:,} rows")

    if df.empty:
        conn.close()
        print("✓ Done — already up to date, nothing new to upsert")
        return 0

    n = upsert_rows(conn, dialect, df)
    conn.close()
    print(f"✓ Done — {n} new rows upserted into daily_sales")
    return n

if __name__ == "__main__":
    main()
