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


def get_access_token():
    """Exchange refresh token for a new access token."""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "refresh_token",
        "client_id":     CLIENT_ID,
        "refresh_token": REFRESH_TOKEN,
        "scope":         "https://graph.microsoft.com/Mail.Read offline_access",
    }
    print(f"[DEBUG] CLIENT_ID: {CLIENT_ID}")
    print(f"[DEBUG] TENANT_ID: {TENANT_ID}")
    print(f"[DEBUG] CLIENT_SECRET present: {bool(CLIENT_SECRET)}")
    print(f"[DEBUG] REFRESH_TOKEN present: {bool(REFRESH_TOKEN)}")
    print(f"[DEBUG] REFRESH_TOKEN first 20 chars: {REFRESH_TOKEN[:20] if REFRESH_TOKEN else 'None'}")
    resp = requests.post(url, data=data)
    print(f"[DEBUG] Token response status: {resp.status_code}")
    print(f"[DEBUG] Token response: {resp.text[:500]}")
    resp.raise_for_status()
    result = resp.json()
    token = result.get("access_token")
    if not token:
        raise ValueError(f"No access token: {result}")
    # Save new refresh token if rotated — print full token so GitHub secret can be updated
    new_refresh = result.get("refresh_token")
    if new_refresh and new_refresh != REFRESH_TOKEN:
        print("[INFO] Refresh token rotated — update AZURE_REFRESH_TOKEN secret with new value:")
        print(f"NEW_REFRESH_TOKEN={new_refresh}")
    print("[OK] Access token obtained")
    return token


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

    missing = [k for k in ["AZURE_CLIENT_ID","AZURE_CLIENT_SECRET","AZURE_TENANT_ID","AZURE_REFRESH_TOKEN",
                            "AZURE_USER_EMAIL","SUPABASE_HOST","SUPABASE_USER","SUPABASE_PASSWORD"]
               if not os.environ.get(k)]
    if missing:
        print(f"[ERROR] Missing environment variables: {missing}")
        sys.exit(1)

    token = get_access_token()
    message_id = find_latest_jm_email(token)

    if not message_id:
        print("[INFO] Nothing to process.")
        sys.exit(0)

    conn = get_pg_connection()
    print("[OK] Connected to Supabase")

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
