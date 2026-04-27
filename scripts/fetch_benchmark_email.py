"""
scripts/fetch_benchmark_email.py
=================================
Automated weekly pull of BlakeWard benchmark PDFs.

Sender:  Daniel Acuna <daniel@jmvalley.com>
Subject: Contains "BlakeWard" (e.g. "Fwd: Weekly Reports: BlakeWard 4/20/26 - 4/26/26")
PDFs:    Sales Dashboard Summary (Weekly) — parsed for region + sub-region data

Runs automatically via the scheduled task every Monday at 9 AM CT.
Can also be run manually:  py scripts/fetch_benchmark_email.py

Auth: same MS Graph OAuth refresh-token pattern as other fetch scripts.
"""

import os, sys, base64, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

CLIENT_ID = "44f09a6a-eae4-43d6-bd80-3c806a3b2d1a"
TENANT_ID = "8dc59d31-158a-4afd-855d-446c26c6adc7"
SENDER    = "daniel@jmvalley.com"
SUBJECT_KW = "BlakeWard"


# ── DB connection ──────────────────────────────────────────────────────────────
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
                print("Connected to Supabase / Postgres")
                return conn, "postgres"
            except Exception as e:
                print(f"⚠️  Supabase failed: {e}")
    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"


# ── OAuth token ────────────────────────────────────────────────────────────────
def get_access_token(conn, dialect):
    import requests
    p = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()
    cur.execute(f"SELECT value FROM app_settings WHERE key = {p}", ("azure_refresh_token",))
    row = cur.fetchone()
    refresh_token = (row[0].strip() if row else "").strip()
    if not refresh_token:
        refresh_token = os.environ.get("AZURE_REFRESH_TOKEN", "").strip()
    if not refresh_token:
        raise RuntimeError("No Azure refresh token in DB or environment")

    resp = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "grant_type":    "refresh_token",
            "client_id":     CLIENT_ID,
            "refresh_token": refresh_token,
            "scope":         "https://graph.microsoft.com/Mail.Read offline_access",
        }
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
        print("  ✓ Refresh token rotated and saved")
    return access_tok


# ── Find latest BlakeWard email ────────────────────────────────────────────────
def find_latest_email(access_token):
    import requests
    headers = {"Authorization": f"Bearer {access_token}"}

    # Strategy 1: subject search for "BlakeWard"
    r = requests.get(
        "https://graph.microsoft.com/v1.0/me/messages"
        f"?$search=\"{SUBJECT_KW}\""
        "&$select=id,subject,receivedDateTime,hasAttachments,from"
        "&$top=10",
        headers={**headers, "ConsistencyLevel": "eventual"},
    )
    if r.status_code == 200:
        for msg in r.json().get("value", []):
            from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
            subj      = msg.get("subject", "")
            if msg.get("hasAttachments") and (
                from_addr.lower() == SENDER.lower()
                or SUBJECT_KW.lower() in subj.lower()
            ):
                print(f"  Found via search: \"{subj}\" from {from_addr} "
                      f"({msg['receivedDateTime'][:10]})")
                return msg["id"]

    # Strategy 2: scan recent 100 messages
    r2 = requests.get(
        "https://graph.microsoft.com/v1.0/me/messages"
        "?$orderby=receivedDateTime desc"
        "&$select=id,subject,receivedDateTime,hasAttachments,from"
        "&$top=100",
        headers=headers,
    )
    r2.raise_for_status()
    for msg in r2.json().get("value", []):
        from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        subj      = msg.get("subject", "")
        if msg.get("hasAttachments") and (
            from_addr.lower() == SENDER.lower()
            or SUBJECT_KW.lower() in subj.lower()
        ):
            print(f"  Found via scan: \"{subj}\" from {from_addr} "
                  f"({msg['receivedDateTime'][:10]})")
            return msg["id"]

    return None


# ── Download + parse PDFs ──────────────────────────────────────────────────────
def process_email(conn, dialect, access_token, message_id):
    import requests
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from load_benchmark import (create_table, parse_summary_pdf,
                                 upsert_records, upsert_detail_records)

    create_table(conn, dialect)

    headers = {"Authorization": f"Bearer {access_token}"}
    r = requests.get(
        f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments",
        headers=headers
    )
    r.raise_for_status()
    attachments = r.json().get("value", [])
    pdfs = [a for a in attachments if a.get("name", "").lower().endswith(".pdf")]
    print(f"  {len(pdfs)} PDF attachment(s) found")

    processed = 0
    skipped   = 0
    with tempfile.TemporaryDirectory() as tmp:
        for att in pdfs:
            name    = att.get("name", "")
            content = att.get("contentBytes", "")
            if not content:
                continue

            # Only parse Summary PDFs — skip Detail, Loyalty, Bread PDFs
            if "summary" not in name.lower():
                print(f"  [SKIP] {name} — only Summary PDFs are parsed")
                skipped += 1
                continue

            pdf_path = os.path.join(tmp, name)
            with open(pdf_path, "wb") as f:
                f.write(base64.b64decode(content))

            print(f"  Parsing: {name}")
            try:
                region_recs, detail_recs = parse_summary_pdf(pdf_path)
                upsert_records(conn, dialect, region_recs)
                upsert_detail_records(conn, dialect, detail_recs)
                processed += 1
            except Exception as e:
                print(f"  ⚠️  {name}: {e}")

    if skipped:
        print(f"  ℹ️  {skipped} non-Summary PDF(s) skipped")
    return processed


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print("=== BlakeWard Benchmark Email Fetch ===")
    conn, dialect = get_conn()

    print("Getting access token...")
    access_token = get_access_token(conn, dialect)
    print("  ✓ Access token obtained")

    print(f"Searching for latest email from {SENDER} with '{SUBJECT_KW}' in subject...")
    msg_id = find_latest_email(access_token)
    if not msg_id:
        print(f"  ✗ No matching email found — check that Daniel has forwarded "
              f"the latest BlakeWard report to your inbox.")
        conn.close()
        return 0

    n = process_email(conn, dialect, access_token, msg_id)
    conn.close()

    if n > 0:
        print(f"\n✓ Done — {n} Summary PDF(s) loaded into "
              f"weekly_benchmark + weekly_benchmark_detail.")
    else:
        print("\n✓ Done — no new Summary PDFs found or already up to date.")
    return n


if __name__ == "__main__":
    main()
