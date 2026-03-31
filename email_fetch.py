"""
email_fetch.py
Connects to Microsoft 365 via Graph API using a refresh token,
finds the latest Jersey Mike's weekly report email, downloads PDF
attachments, and loads them into Supabase.
"""

import os
import sys
import json
import base64
import tempfile
import requests
from datetime import datetime, timedelta

CLIENT_ID     = "44f09a6a-eae4-43d6-bd80-3c806a3b2d1a"   # Azure App (public client)
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")     # Not used for public client
TENANT_ID     = "8dc59d31-158a-4afd-855d-446c26c6adc7"   # Must match token issuer tenant
REFRESH_TOKEN = (os.environ.get("AZURE_REFRESH_TOKEN") or "").strip()
USER_EMAIL    = os.environ.get("AZURE_USER_EMAIL")
SENDER_EMAIL  = "noreply@jerseymikes.com"

DB_HOST     = os.environ.get("SUPABASE_HOST", "aws-1-us-east-1.pooler.supabase.com")
DB_PORT     = 5432
DB_NAME     = os.environ.get("SUPABASE_DBNAME", "postgres")
DB_USER     = os.environ.get("SUPABASE_USER")
DB_PASSWORD = os.environ.get("SUPABASE_PASSWORD")


def get_token_from_supabase(conn):
    """Read the current refresh token from Supabase app_settings table."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT value FROM app_settings WHERE key = 'azure_refresh_token'")
        row = cur.fetchone()
        return row[0].strip() if row else None
    except Exception as e:
        print(f"[WARN] Could not read token from Supabase: {e}")
        return None

def save_token_to_supabase(conn, token):
    """Save rotated refresh token back to Supabase automatically."""
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO app_settings (key, value) VALUES ('azure_refresh_token', %s)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """, (token,))
        conn.commit()
        print("[INFO] Refresh token auto-updated in Supabase")
    except Exception as e:
        print(f"[WARN] Could not save rotated token to Supabase: {e}")

def get_access_token(conn):
    """Exchange refresh token for a new access token. Auto-saves rotated token to Supabase."""
    # Try Supabase first, fall back to env var
    refresh_token = get_token_from_supabase(conn) or REFRESH_TOKEN
    if not refresh_token:
        raise ValueError("No refresh token available")
    print(f"[INFO] Refresh token source: {'Supabase' if get_token_from_supabase(conn) else 'env var'}")

    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "refresh_token",
        "client_id":     CLIENT_ID,
        "refresh_token": refresh_token,
        "scope":         "https://graph.microsoft.com/Mail.Read offline_access",
    }
    resp = requests.post(url, data=data)
    print(f"[INFO] Token response status: {resp.status_code}")
    if resp.status_code != 200:
        print(f"[ERROR] Token response: {resp.text[:500]}")
    resp.raise_for_status()
    result = resp.json()
    access_token = result.get("access_token")
    if not access_token:
        raise ValueError(f"No access token: {result}")
    # Auto-save rotated token back to Supabase
    new_refresh = result.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        print("[INFO] Refresh token rotated — saving automatically to Supabase")
        save_token_to_supabase(conn, new_refresh)
    print("[OK] Access token obtained")
    return access_token


def find_latest_jm_email(token):
    """Find the most recent email from Jersey Mike's with attachments."""
    headers = {"Authorization": f"Bearer {token}"}
    url = (
        f"https://graph.microsoft.com/v1.0/me/messages"
        f"?$orderby=receivedDateTime desc"
        f"&$select=id,subject,receivedDateTime,hasAttachments,from"
        f"&$top=25"
    )
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    messages = resp.json().get("value", [])

    for msg in messages:
        from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        if from_addr.lower() == SENDER_EMAIL.lower() and msg.get("hasAttachments"):
            print(f"[OK] Found: '{msg['subject']}' ({msg['receivedDateTime']})")
            return msg["id"]

    print(f"[WARN] No emails from {SENDER_EMAIL} in last 25 messages")
    return None


def download_attachments(token, message_id, dest_folder):
    """Download all PDF attachments to dest_folder."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()

    pdf_paths = []
    for att in resp.json().get("value", []):
        name = att.get("name", "")
        if not name.lower().endswith(".pdf"):
            continue
        content = att.get("contentBytes", "")
        if not content:
            continue
        dest_path = os.path.join(dest_folder, name)
        with open(dest_path, "wb") as f:
            f.write(base64.b64decode(content))
        print(f"  [OK] Downloaded: {name}")
        pdf_paths.append(dest_path)

    return pdf_paths


def get_pg_connection():
    import psycopg2
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, sslmode="require"
    )


def already_processed(filename, conn):
    cur = conn.cursor()
    cur.execute("SELECT id FROM report_log WHERE filename = %s", (filename,))
    return cur.fetchone() is not None


def run():
    print(f"\n{'='*60}")
    print(f"Jersey Mike's Weekly Update — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    missing = [k for k in ["SUPABASE_HOST","SUPABASE_USER","SUPABASE_PASSWORD"]
               if not os.environ.get(k)]
    if missing:
        print(f"[ERROR] Missing environment variables: {missing}")
        sys.exit(1)

    conn = get_pg_connection()
    print("[OK] Connected to Supabase")

    token = get_access_token(conn)
    message_id = find_latest_jm_email(token)

    if not message_id:
        print("[INFO] Nothing to process.")
        conn.close()
        sys.exit(0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_paths = download_attachments(token, message_id, tmp_dir)

        if not pdf_paths:
            print("[WARN] No PDFs found in email")
            sys.exit(0)

        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from parse_and_load_cloud import process_pdf

        processed = 0
        for pdf_path in sorted(pdf_paths):
            filename = os.path.basename(pdf_path)
            if already_processed(filename, conn):
                print(f"  [SKIP] Already processed: {filename}")
                continue
            try:
                process_pdf(pdf_path, conn)
                processed += 1
            except Exception as e:
                print(f"  [ERROR] {filename}: {e}")

    conn.close()
    print(f"\n[OK] Done — {processed} new PDFs loaded.")


if __name__ == "__main__":
    run()
