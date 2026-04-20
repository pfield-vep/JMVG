"""
pages/4_Update_Data.py
JM Valley Group — One-click weekly data update
────────────────────────────────────────────────
Section 1: Pull latest JM report from email → parse → Supabase
Section 2: Upload BlakeWard benchmark PDFs → parse → Supabase
"""

import streamlit as st
import os, sys, io, re, base64, tempfile, contextlib
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Update Data | JM Valley Group",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Brand ─────────────────────────────────────────────────────────────────────
BLUE   = "#134A7C"
RED    = "#EE3227"
WHITE  = "#FFFFFF"
LIGHT  = "#F5F6F8"
BORDER = "#E0E3E8"
TEXT   = "#1a1a2e"
GREEN  = "#16a34a"
MUTED  = "#6B7280"

st.markdown(f"""<style>
  [data-testid="stAppViewContainer"] {{ background:{LIGHT}; }}
  .page-title {{
    font-family:Arial,sans-serif; font-size:22px; font-weight:700;
    color:{BLUE}; border-bottom:3px solid {RED}; padding-bottom:8px;
    margin-bottom:20px; letter-spacing:1px;
  }}
  .section-card {{
    background:{WHITE}; border:1.5px solid {BORDER}; border-radius:10px;
    padding:20px 24px 24px; margin-bottom:20px;
  }}
  .section-title {{
    font-family:Arial,sans-serif; font-size:12px; font-weight:700;
    letter-spacing:2px; text-transform:uppercase; color:{BLUE};
    border-bottom:2px solid {RED}; padding-bottom:5px; margin-bottom:16px;
  }}
  .status-row {{
    display:flex; gap:20px; flex-wrap:wrap; margin-bottom:16px;
  }}
  .status-chip {{
    background:{LIGHT}; border:1px solid {BORDER}; border-radius:20px;
    padding:5px 14px; font-family:Arial,sans-serif; font-size:12px;
    color:{TEXT}; display:inline-block;
  }}
  .status-chip b {{ color:{BLUE}; }}
  .log-box {{
    background:#1e1e2e; color:#cdd6f4; font-family:"Courier New",monospace;
    font-size:12px; padding:14px; border-radius:8px; max-height:320px;
    overflow-y:auto; white-space:pre-wrap; min-height:60px;
  }}
  div[data-testid="stButton"] button {{
    background:{BLUE} !important; color:{WHITE} !important;
    border:none !important; border-radius:6px !important;
    font-weight:700 !important; letter-spacing:0.5px !important;
    padding:10px 22px !important;
  }}
  div[data-testid="stButton"] button:hover {{
    background:{RED} !important; color:{WHITE} !important;
  }}
</style>""", unsafe_allow_html=True)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# ── DB connection ─────────────────────────────────────────────────────────────
@st.cache_resource(ttl=60)
def get_conn():
    """Returns (connection, dialect). Tries Supabase first, falls back to SQLite."""
    try:
        import psycopg2
        s = st.secrets["supabase"]
        conn = psycopg2.connect(
            host=s["host"], port=int(s["port"]),
            dbname=s["dbname"], user=s["user"],
            password=s["password"], sslmode="require"
        )
        return conn, "postgres"
    except Exception:
        pass
    import sqlite3
    return sqlite3.connect(os.path.join(ROOT, "jerseymikes.db"), check_same_thread=False), "sqlite"

def fresh_conn():
    """Get a fresh (uncached) DB connection."""
    try:
        import psycopg2
        s = st.secrets["supabase"]
        conn = psycopg2.connect(
            host=s["host"], port=int(s["port"]),
            dbname=s["dbname"], user=s["user"],
            password=s["password"], sslmode="require"
        )
        return conn, "postgres"
    except Exception:
        pass
    import sqlite3
    return sqlite3.connect(os.path.join(ROOT, "jerseymikes.db"), check_same_thread=False), "sqlite"

# ── Logger that writes to a Streamlit placeholder ────────────────────────────
class StLogger:
    def __init__(self, placeholder):
        self.ph    = placeholder
        self.lines = []
    def write(self, text):
        for line in str(text).splitlines():
            if line.strip():
                self.lines.append(line)
        self.ph.markdown(
            f'<div class="log-box">' + "\n".join(self.lines[-80:]) + "</div>",
            unsafe_allow_html=True
        )
    def flush(self): pass
    def result_text(self): return "\n".join(self.lines)

# ── Status summary ────────────────────────────────────────────────────────────
def show_status(conn, dialect):
    p = "%s" if dialect == "postgres" else "?"
    cur = conn.cursor()

    # Latest week in weekly_sales
    try:
        cur.execute("SELECT MAX(week_ending) FROM weekly_sales")
        latest_sales = cur.fetchone()[0] or "—"
    except Exception:
        latest_sales = "—"

    # Weeks in DB
    try:
        cur.execute("SELECT COUNT(DISTINCT week_ending) FROM weekly_sales")
        n_weeks = cur.fetchone()[0] or 0
    except Exception:
        n_weeks = 0

    # Latest benchmark
    try:
        cur.execute("SELECT MAX(week_ending) FROM weekly_benchmark")
        latest_bm = cur.fetchone()[0] or "—"
    except Exception:
        latest_bm = "—"

    # Last processed files
    try:
        cur.execute(
            "SELECT filename, processed_at FROM report_log ORDER BY processed_at DESC LIMIT 4"
        )
        recent = cur.fetchall()
    except Exception:
        recent = []

    chips = [
        f"<span class='status-chip'>📅 Latest store week: <b>{latest_sales}</b></span>",
        f"<span class='status-chip'>📊 Weeks in DB: <b>{n_weeks}</b></span>",
        f"<span class='status-chip'>🏆 Latest benchmark: <b>{latest_bm}</b></span>",
    ]
    st.markdown(f'<div class="status-row">{"".join(chips)}</div>', unsafe_allow_html=True)

    if recent:
        with st.expander("📋 Recently processed files", expanded=False):
            for fname, ts in recent:
                st.markdown(f"- `{fname}` — {ts}")

# ── JM email fetch & parse ────────────────────────────────────────────────────
def fetch_jm_from_email(log: StLogger):
    """
    Replicates email_fetch.run() but logs to StLogger instead of stdout.
    Returns number of new PDFs processed.
    """
    import requests

    CLIENT_ID = "44f09a6a-eae4-43d6-bd80-3c806a3b2d1a"
    TENANT_ID = "8dc59d31-158a-4afd-855d-446c26c6adc7"
    SENDER    = "noreply@jerseymikes.com"

    conn, dialect = fresh_conn()

    # ── Get refresh token ──
    def get_refresh_token():
        try:
            cur = conn.cursor()
            p = "%s" if dialect == "postgres" else "?"
            cur.execute(f"SELECT value FROM app_settings WHERE key = {p}", ("azure_refresh_token",))
            row = cur.fetchone()
            if row: return row[0].strip()
        except Exception:
            pass
        return (st.secrets.get("AZURE_REFRESH_TOKEN") or
                os.environ.get("AZURE_REFRESH_TOKEN", "")).strip()

    def save_refresh_token(token):
        try:
            p = "%s" if dialect == "postgres" else "?"
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO app_settings (key,value) VALUES ({p},{p}) "
                f"ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value",
                ("azure_refresh_token", token)
            )
            conn.commit()
        except Exception as e:
            log.write(f"[WARN] Could not save rotated token: {e}")

    # ── Get access token ──
    refresh_token = get_refresh_token()
    if not refresh_token:
        log.write("[ERROR] No Azure refresh token configured.")
        return 0

    log.write("Requesting access token...")
    url = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type":    "refresh_token",
        "client_id":     CLIENT_ID,
        "refresh_token": refresh_token,
        "scope":         "https://graph.microsoft.com/Mail.Read offline_access",
    })
    if resp.status_code != 200:
        log.write(f"[ERROR] Token request failed ({resp.status_code}): {resp.text[:300]}")
        return 0
    result = resp.json()
    access_token = result.get("access_token")
    new_refresh   = result.get("refresh_token")
    if new_refresh and new_refresh != refresh_token:
        save_refresh_token(new_refresh)
        log.write("[OK] Refresh token rotated and saved.")
    log.write("[OK] Access token obtained.")

    # ── Find latest JM email ──
    headers = {"Authorization": f"Bearer {access_token}"}
    log.write(f"Searching for latest email from {SENDER}...")
    search_resp = requests.get(
        "https://graph.microsoft.com/v1.0/me/messages"
        "?$orderby=receivedDateTime desc"
        "&$select=id,subject,receivedDateTime,hasAttachments,from"
        "&$top=30",
        headers=headers
    )
    search_resp.raise_for_status()
    messages = search_resp.json().get("value", [])

    message_id = None
    for msg in messages:
        from_addr = msg.get("from", {}).get("emailAddress", {}).get("address", "")
        if from_addr.lower() == SENDER.lower() and msg.get("hasAttachments"):
            log.write(f"[OK] Found: \"{msg['subject']}\" ({msg['receivedDateTime'][:10]})")
            message_id = msg["id"]
            break

    if not message_id:
        log.write(f"[WARN] No emails from {SENDER} with attachments in recent 30 messages.")
        return 0

    # ── Download attachments ──
    att_resp = requests.get(
        f"https://graph.microsoft.com/v1.0/me/messages/{message_id}/attachments",
        headers=headers
    )
    att_resp.raise_for_status()
    attachments = att_resp.json().get("value", [])

    log.write(f"Downloading {len([a for a in attachments if a.get('name','').lower().endswith('.pdf')])} PDFs...")

    from parse_and_load_cloud import process_pdf

    processed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for att in attachments:
            name = att.get("name", "")
            if not name.lower().endswith(".pdf"):
                continue
            content = att.get("contentBytes", "")
            if not content:
                continue
            pdf_path = os.path.join(tmp, name)
            with open(pdf_path, "wb") as f:
                f.write(base64.b64decode(content))

            # Check if already processed
            try:
                p = "%s" if dialect == "postgres" else "?"
                cur = conn.cursor()
                cur.execute(f"SELECT id FROM report_log WHERE filename = {p}", (name,))
                if cur.fetchone():
                    log.write(f"  [SKIP] Already processed: {name}")
                    continue
            except Exception:
                pass

            log.write(f"  Parsing: {name}")
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    process_pdf(pdf_path, conn)
                for line in buf.getvalue().splitlines():
                    if line.strip():
                        log.write(f"    {line}")
                processed += 1
            except Exception as e:
                log.write(f"  [ERROR] {name}: {e}")

    conn.close()
    return processed


# ── Benchmark PDF processing ──────────────────────────────────────────────────
def process_benchmark_files(uploaded_files, log: StLogger):
    """Parse uploaded BlakeWard Summary PDFs and upsert into weekly_benchmark."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from load_benchmark import parse_summary_pdf, upsert_records, create_table, COLS

    conn, dialect = fresh_conn()
    create_table(conn, dialect)

    processed = 0
    with tempfile.TemporaryDirectory() as tmp:
        for uf in uploaded_files:
            fname = uf.name
            tmp_path = os.path.join(tmp, fname)
            with open(tmp_path, "wb") as f:
                f.write(uf.read())

            log.write(f"\nProcessing: {fname}")
            try:
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    records = parse_summary_pdf(tmp_path)
                    upsert_records(conn, dialect, records)
                for line in buf.getvalue().splitlines():
                    if line.strip():
                        log.write(f"  {line}")
                processed += 1
            except Exception as e:
                log.write(f"  [ERROR] {fname}: {e}")

    conn.close()
    return processed


# ═══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ═══════════════════════════════════════════════════════════════════════════════

st.markdown('<div class="page-title">🔄 UPDATE DATA</div>', unsafe_allow_html=True)

# Status bar
try:
    conn0, dialect0 = get_conn()
    show_status(conn0, dialect0)
except Exception as e:
    st.warning(f"Could not load status: {e}")

st.markdown("---")

# ── Section 1: JM Store Data ─────────────────────────────────────────────────
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📧 JM Store Data — Fetch from Email</div>', unsafe_allow_html=True)
st.markdown(
    "Connects to your Microsoft 365 inbox, finds the latest Jersey Mike's weekly report, "
    "downloads all PDFs, and loads any new data into the database.",
    unsafe_allow_html=False
)

jm_log_ph  = st.empty()
jm_done_ph = st.empty()

if st.button("🔄 Fetch & Process Latest JM Report", key="fetch_jm"):
    jm_log_ph.markdown('<div class="log-box">Starting...</div>', unsafe_allow_html=True)
    log = StLogger(jm_log_ph)
    try:
        n = fetch_jm_from_email(log)
        if n > 0:
            jm_done_ph.success(f"✅ Done — {n} new PDF(s) loaded. Reload the dashboard to see updated data.")
        else:
            jm_done_ph.info("ℹ️ No new files — everything is already up to date.")
        get_conn.clear()   # bust the cached connection so status refreshes
    except Exception as e:
        log.write(f"\n[FATAL] {e}")
        jm_done_ph.error(f"Update failed: {e}")

st.markdown("</div>", unsafe_allow_html=True)

# ── Section 2: Benchmark Data ────────────────────────────────────────────────
st.markdown('<div class="section-card">', unsafe_allow_html=True)
st.markdown('<div class="section-title">📊 BlakeWard Benchmark — Upload PDFs</div>', unsafe_allow_html=True)
st.markdown(
    "Upload one or more **Sales Dashboard Summary (Weekly)** PDFs from BlakeWard. "
    "You can drop multiple weeks at once — duplicates are safely skipped.",
    unsafe_allow_html=False
)

uploaded = st.file_uploader(
    "Drop BlakeWard Summary PDFs here",
    type=["pdf"],
    accept_multiple_files=True,
    label_visibility="collapsed",
)

bm_log_ph  = st.empty()
bm_done_ph = st.empty()

if uploaded:
    names = [f.name for f in uploaded]
    st.markdown(
        "**Selected:** " + " · ".join(f"`{n}`" for n in names),
        unsafe_allow_html=False
    )

    if st.button(f"📊 Process {len(uploaded)} PDF(s)", key="process_bm"):
        bm_log_ph.markdown('<div class="log-box">Starting benchmark parse...</div>', unsafe_allow_html=True)
        log = StLogger(bm_log_ph)
        try:
            n = process_benchmark_files(uploaded, log)
            if n > 0:
                bm_done_ph.success(f"✅ Done — {n} benchmark file(s) loaded.")
            else:
                bm_done_ph.info("ℹ️ No new data loaded — check the log above for details.")
            get_conn.clear()
        except Exception as e:
            log.write(f"\n[FATAL] {e}")
            bm_done_ph.error(f"Benchmark update failed: {e}")

st.markdown("</div>", unsafe_allow_html=True)
