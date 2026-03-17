"""
email_fetch.py
Connects to Microsoft 365 via Graph API, finds the latest Jersey Mike's
weekly report email, downloads PDF attachments, and loads them into Supabase.

Run manually: py email_fetch.py
Run automatically: GitHub Actions (weekly_update.yml)
"""

import os
import sys
import json
import base64
import sqlite3
import tempfile
import requests
from datetime import datetime, timedelta

# ── Credentials from environment variables (set by GitHub Actions secrets) ────
CLIENT_ID     = os.environ.get("AZURE_CLIENT_ID")
CLIENT_SECRET = os.environ.get("AZURE_CLIENT_SECRET")
TENANT_ID     = os.environ.get("AZURE_TENANT_ID")
USER_EMAIL    = os.environ.get("AZURE_USER_EMAIL")

SENDER_EMAIL  = "noreply@jerseymikes.com"

# ── Database connection (Supabase) ────────────────────────────────────────────
DB_HOST     = os.environ.get("SUPABASE_HOST", "aws-1-us-east-1.pooler.supabase.com")
DB_PORT     = 5432
DB_NAME     = os.environ.get("SUPABASE_DBNAME", "postgres")
DB_USER     = os.environ.get("SUPABASE_USER")
DB_PASSWORD = os.environ.get("SUPABASE_PASSWORD")


def get_access_token():
    """Get OAuth2 access token from Azure AD."""
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    data = {
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scope":         "https://graph.microsoft.com/.default",
    }
    resp = requests.post(url, data=data)
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError(f"No access token returned: {resp.json()}")
    print("[OK] Access token obtained")
    return token


def find_latest_jm_email(token):
    """Find the most recent unprocessed email from Jersey Mike's."""
    headers = {"Authorization": f"Bearer {token}"}

    # Search inbox for emails from Jersey Mike's in last 10 days
    since = (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%dT00:00:00Z")
    url = (
        f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/messages"
        f"?$filter=from/emailAddress/address eq '{SENDER_EMAIL}'"
        f" and receivedDateTime ge {since}"
        f"&$orderby=receivedDateTime desc"
        f"&$select=id,subject,receivedDateTime,hasAttachments"
        f"&$top=5"
    )

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    messages = resp.json().get("value", [])

    if not messages:
        print(f"[WARN] No emails found from {SENDER_EMAIL} in the last 10 days")
        return None

    # Pick the most recent one with attachments
    for msg in messages:
        if msg.get("hasAttachments"):
            print(f"[OK] Found email: '{msg['subject']}' ({msg['receivedDateTime']})")
            return msg["id"]

    print("[WARN] No emails with attachments found")
    return None


def download_attachments(token, message_id, dest_folder):
    """Download all PDF attachments from the email to dest_folder."""
    headers = {"Authorization": f"Bearer {token}"}
    url = f"https://graph.microsoft.com/v1.0/users/{USER_EMAIL}/messages/{message_id}/attachments"

    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    attachments = resp.json().get("value", [])

    pdf_paths = []
    for att in attachments:
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
    """Connect to Supabase PostgreSQL."""
    import psycopg2
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, sslmode="require"
    )


def already_processed(pdf_filename, conn):
    """Check if this PDF has already been loaded."""
    cur = conn.cursor()
    cur.execute("SELECT id FROM report_log WHERE filename = %s", (pdf_filename,))
    return cur.fetchone() is not None


def run():
    print(f"\n{'='*60}")
    print(f"Jersey Mike's Weekly Update — {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}\n")

    # Validate credentials
    missing = [k for k in ["AZURE_CLIENT_ID","AZURE_CLIENT_SECRET","AZURE_TENANT_ID",
                            "AZURE_USER_EMAIL","SUPABASE_HOST","SUPABASE_USER","SUPABASE_PASSWORD"]
               if not os.environ.get(k)]
    if missing:
        print(f"[ERROR] Missing environment variables: {missing}")
        sys.exit(1)

    # Get token
    token = get_access_token()

    # Find latest email
    message_id = find_latest_jm_email(token)
    if not message_id:
        print("[INFO] Nothing to process. Exiting.")
        sys.exit(0)

    # Connect to DB
    conn = get_pg_connection()
    print("[OK] Connected to Supabase")

    # Create temp folder for PDFs
    with tempfile.TemporaryDirectory() as tmp_dir:
        print(f"\n[INFO] Downloading attachments to {tmp_dir}...")
        pdf_paths = download_attachments(token, message_id, tmp_dir)

        if not pdf_paths:
            print("[WARN] No PDF attachments found in email")
            sys.exit(0)

        print(f"\n[INFO] Found {len(pdf_paths)} PDFs. Processing...")

        # Import parse_and_load functions
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
                print(f"  [ERROR] Failed to process {filename}: {e}")

        conn.close()
        print(f"\n[OK] Done. {processed} new PDFs loaded into Supabase.")


if __name__ == "__main__":
    run()
