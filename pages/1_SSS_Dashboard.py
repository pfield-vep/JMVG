"""
pages/1_SSS_Dashboard.py
Runs the existing Jersey Mike's Same Store Sales dashboard.
"""
import os, sys, re

# Point to repo root so all imports in dashboard.py resolve correctly
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)
os.chdir(root)

with open(os.path.join(root, "dashboard.py"), encoding="utf-8") as _f:
    code = _f.read()

# Remove st.set_page_config(...) — handled below with sidebar shown
code = re.sub(r'st\.set_page_config\([^)]*\)', '', code, flags=re.DOTALL)

import streamlit as st
st.set_page_config(
    page_title="Same Store Sales | JM Valley Group",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="auto",
)

# ── Data freshness badge ──────────────────────────────────────────────────────
import pandas as pd
@st.cache_data(ttl=300)
def _sss_freshness():
    try:
        import psycopg2
        s = st.secrets["supabase"]
        conn = psycopg2.connect(host=s["host"], port=int(s["port"]),
                                dbname=s["dbname"], user=s["user"],
                                password=s["password"], sslmode="require")
        cur = conn.cursor()
        cur.execute("SELECT MAX(sale_date) FROM daily_sales")
        row = cur.fetchone(); conn.close()
        return pd.to_datetime(row[0]).date() if row and row[0] else None
    except Exception:
        return None

_sss_fresh = _sss_freshness()
if _sss_fresh:
    st.markdown(
        f'<div style="text-align:right;font-size:11px;color:#6B7280;margin-bottom:4px;">'
        f'🕐 Data through <b>{_sss_fresh.strftime("%a %b %d, %Y")}</b></div>',
        unsafe_allow_html=True,
    )

# Home navigation is handled by the ⌂ Home link inside the blue filter bar
exec(code, {"__name__": "__main__", "__file__": os.path.join(root, "dashboard.py")})
