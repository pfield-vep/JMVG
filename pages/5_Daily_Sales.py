"""
pages/5_Daily_Sales.py
JM Valley Group — Daily Sales Dashboard
SSS / SST / Comp Check + Daypart & Channel mix
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import date, timedelta

st.set_page_config(
    page_title="Daily Sales | JM Valley Group",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Brand colors ───────────────────────────────────────────────────────────────
RED    = "#EE3227"
BLUE   = "#134A7C"
GOLD   = "#D4AF37"
WHITE  = "#FFFFFF"
LIGHT  = "#F5F6F8"
BORDER = "#E0E3E8"
TEXT   = "#1a1a2e"
MUTED  = "#6B7280"
GREEN  = "#16a34a"
DANGER = "#dc2626"
AMBER  = "#d97706"

# ── Market definitions ─────────────────────────────────────────────────────────
SAN_DIEGO_IDS      = ['20071','20091','20171','20177','20291','20292','20300']
SANTA_BARBARA_IDS  = ['20075','20335','20360','20013']

STORE_NAMES = {
    '20156':'North Hollywood','20218':'Mission Hills','20267':'Balboa',
    '20294':'Toluca','20026':'Tampa','20311':'Porter Ranch',
    '20352':'San Fernando','20363':'Warner Center','20273':'Big Bear',
    '20366':'Burbank North','20011':'Westlake','20255':'Arboles',
    '20048':'Janss','20245':'Wendy','20381':'Sylmar',
    '20116':'Encino','20388':'Lake Arrowhead','20075':'Isla Vista',
    '20335':'Goleta','20360':'Santa Barbara','20424':'Studio City',
    '20177':'SD Mission Valley','20171':'SD Chula Vista','20091':'SD El Cajon',
    '20071':'SD Santee','20300':'SD Escondido','20292':'SD La Mesa',
    '20291':'SD Poway','20013':'Buellton',
}

def get_market(store_id):
    if store_id in SAN_DIEGO_IDS:     return "San Diego"
    if store_id in SANTA_BARBARA_IDS: return "Santa Barbara"
    return "LA - San Fernando Valley"

# ── DB connection ──────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jerseymikes.db")

def get_conn():
    try:
        import psycopg2
        s = st.secrets["supabase"]
        return psycopg2.connect(
            host=s["host"], port=int(s["port"]),
            dbname=s["dbname"], user=s["user"],
            password=s["password"], sslmode="require"
        ), "postgres"
    except Exception:
        import sqlite3
        return sqlite3.connect(DB_PATH), "sqlite"

# ── Load data ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_dm_store_map():
    """Load store → DM name + market from stores table."""
    conn, _ = get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT store_id, dm_name, broad_geography "
            "FROM stores WHERE dm_name IS NOT NULL",
            conn
        )
        conn.close()
        df["store_id"] = df["store_id"].astype(str).str.strip()

        def _market(geo):
            g = str(geo or "").strip()
            if "San Diego" in g:                 return "San Diego"
            if "Santa Barbara" in g or "San Luis" in g: return "Santa Barbara"
            return "LA - San Fernando Valley"

        def _first(name):
            return str(name or "").strip().split()[0]

        df["display_market"] = df["broad_geography"].apply(_market)
        df["dm_first"]       = df["dm_name"].apply(_first)
        df["dm_group"]       = df["display_market"] + " - " + df["dm_first"]
        # Note: store 20026 is named "Tampa" but is located in Los Angeles (Northridge)
        # — include it in Josiah's LA/SoCal group
        return df
    except Exception:
        conn.close()
        return None

@st.cache_data(ttl=300)
def load_comp_eligible_stores(period_start_str: str) -> set:
    """
    Return store_ids eligible as comps.

    Eligibility rules (applied in order):
      1. open_date IS NULL  → include unconditionally (acquired stores whose
         original open date is unknown but are clearly established franchises;
         the inner-join in comp_metrics will drop them if prior-year data is absent)
      2. open_date IS NOT NULL AND open_date + 364 days <= period_start → include
      3. open_date IS NOT NULL AND open_date + 364 days > period_start → exclude
         (store not yet open for a full year relative to the period start)

    All store_ids are returned as strings to match daily_sales.store_id (TEXT).
    """
    conn, dialect = get_conn()
    try:
        stores = pd.read_sql_query(
            "SELECT store_id, open_date FROM stores",
            conn
        )
        conn.close()
        stores["store_id"] = stores["store_id"].astype(str).str.strip()
        stores["open_date"] = pd.to_datetime(stores["open_date"], errors="coerce")
        cutoff = pd.to_datetime(period_start_str) - pd.Timedelta(days=364)
        eligible = stores[
            stores["open_date"].isna() |          # unknown open date → assume established
            (stores["open_date"] <= cutoff)        # known open date old enough
        ]
        return set(eligible["store_id"].tolist())
    except Exception:
        conn.close()
        return set()

@st.cache_data(ttl=300)
def load_sales(start_str: str, end_str: str, prior_start_str: str, prior_end_str: str):
    """Load current + prior period daily_sales rows."""
    conn, dialect = get_conn()
    p = "%s" if dialect == "postgres" else "?"
    overall_start = min(start_str, prior_start_str)
    overall_end   = max(end_str,   prior_end_str)
    df = pd.read_sql_query(
        f"""SELECT store_id, sale_date,
               net_sales, total_transactions,
               walkin_sales, online_sales, third_party_sales,
               lunch_sales, dinner_sales, morning_sales
        FROM daily_sales
        WHERE sale_date >= {p} AND sale_date <= {p}
        ORDER BY sale_date""",
        conn,
        params=(overall_start, overall_end),
    )
    conn.close()
    df["sale_date"] = pd.to_datetime(df["sale_date"])
    df["store_id"]  = df["store_id"].astype(str).str.strip()
    df["market"] = df["store_id"].apply(get_market)
    df["store_name"] = df["store_id"].map(STORE_NAMES).fillna(df["store_id"])
    return df

@st.cache_data(ttl=300)
def get_date_range():
    """Return min/max dates available in daily_sales."""
    conn, dialect = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MIN(sale_date), MAX(sale_date) FROM daily_sales")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return pd.to_datetime(row[0]).date(), pd.to_datetime(row[1]).date()
    except Exception:
        pass
    return date(2024, 1, 1), date.today()

@st.cache_data(ttl=300)
def load_all_daily_for_trends():
    """Full daily_sales history (net_sales + transactions) for weekly trend computation."""
    conn, dialect = get_conn()
    df = pd.read_sql_query(
        "SELECT store_id, sale_date, net_sales, total_transactions "
        "FROM daily_sales WHERE net_sales > 0 AND total_transactions > 0 "
        "ORDER BY sale_date",
        conn,
    )
    conn.close()
    df["sale_date"]  = pd.to_datetime(df["sale_date"])
    df["store_id"]   = df["store_id"].astype(str).str.strip()
    return df

@st.cache_data(ttl=300)
def load_stores_open_dates():
    """Return store_id → open_date for comp-eligibility checks."""
    conn, _ = get_conn()
    df = pd.read_sql_query("SELECT store_id, open_date FROM stores", conn)
    conn.close()
    df["store_id"]  = df["store_id"].astype(str).str.strip()
    df["open_date"] = pd.to_datetime(df["open_date"], errors="coerce")
    return df

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  /* No horizontal page scroll on mobile */
  html, body, .stApp {{ overflow-x: clip !important; max-width: 100vw !important; }}
  body {{
        font-family: Arial, sans-serif;
    }}

  .stApp, .main {{ background-color: {WHITE} !important; }}
  .block-container {{
    padding: 0.75rem 1.25rem 1.5rem !important;
    max-width: 100% !important;
  }}
  [data-testid="stExpandSidebarButton"],
  [data-testid="stExpandSidebarButton"] * {{ visibility: visible !important; }}
  [data-testid="stSidebarCollapseButton"],
  [data-testid="stSidebarCollapseButton"] * {{ visibility: visible !important; }}
  header {{ visibility: hidden; }}

  /* ── Period toggle: style radio as pill buttons ── */
  /* Hide the "Period" group label entirely */
  [data-testid="stRadio"] > label,
  [data-testid="stRadio"] > div > label:not([data-baseweb]) {{
    display: none !important;
  }}
  [data-testid="stRadio"] div[role="radiogroup"] {{
    display: flex !important;
    flex-wrap: nowrap !important;
    gap: 6px !important;
    justify-content: center !important;
  }}
  /* Sticky period toggle on mobile so it stays visible while scrolling */
  @media (max-width: 768px) {{
    [data-testid="stRadio"] {{
      position: sticky !important;
      top: 0 !important;
      z-index: 999 !important;
      background: white !important;
      padding: 8px 0 6px !important;
    }}
  }}
  [data-testid="stRadio"] div[role="radiogroup"] label {{
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    padding: 5px 16px !important;
    border: 2px solid {BLUE} !important;
    border-radius: 20px !important;
    cursor: pointer !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    color: {BLUE} !important;
    background: white !important;
    white-space: nowrap !important;
    margin: 0 !important;
    text-align: center !important;
  }}
  [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) {{
    background: {BLUE} !important;
    color: white !important;
  }}
  [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) p,
  [data-testid="stRadio"] div[role="radiogroup"] label:has(input:checked) span {{
    color: white !important;
  }}
  /* Hide the radio circle dot */
  [data-testid="stRadio"] div[role="radiogroup"] label > div:first-child {{
    display: none !important;
  }}

  /* KPI cards */
  .kpi-card {{
    background: {WHITE};
    border: 1px solid {BORDER};
    border-top: 4px solid {RED};
    border-radius: 8px;
    padding: 14px 16px 12px;
    margin-bottom: 8px;
    height: 110px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    box-sizing: border-box;
  }}
  .kpi-card-blue {{ border-top-color: {BLUE} !important; }}
  .kpi-card-green {{ border-top-color: {GREEN} !important; }}
  .kpi-card-gold  {{ border-top-color: {GOLD} !important; }}
  .kpi-label {{
    font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
    text-transform: uppercase; color: {MUTED};
  }}
  .kpi-value {{
    font-size: 28px; font-weight: 700; color: {TEXT}; line-height: 1.2;
  }}
  .kpi-delta {{
    font-size: 12px; font-weight: 600; color: {MUTED};
  }}
  .kpi-pos {{ color: {GREEN} !important; }}
  .kpi-neg {{ color: {DANGER} !important; }}

  /* ── Landing cards (Comp Sales / Sales / Sales Mix) ── */
  .dl-groups {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    margin-bottom: 20px;
  }}
  .dl-group {{
    border: 1.5px solid {BORDER};
    border-radius: 8px;
    overflow: hidden;
  }}
  .dl-header {{
    background: {BLUE}; color: white;
    font-family: Arial, sans-serif;
    font-size: 11px; font-weight: 700;
    letter-spacing: 1.5px; text-transform: uppercase;
    padding: 8px 10px; text-align: center;
  }}
  .dl-tiles {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    background: {WHITE};
    padding: 10px 6px 10px;
  }}
  .dl-tile {{
    padding: 4px 8px;
    display: flex; flex-direction: column;
  }}
  .dl-tile + .dl-tile {{ border-left: 1px solid {BORDER}; }}
  .dl-lbl {{
    font-family: Arial, sans-serif;
    font-size: 9px; letter-spacing: 1.1px;
    text-transform: uppercase; color: {MUTED};
    font-weight: 700;
    border-bottom: 1.5px solid {BORDER};
    padding-bottom: 4px; margin-bottom: 5px;
    white-space: nowrap;
  }}
  .dl-val {{
    font-family: Arial, sans-serif;
    font-size: 22px; font-weight: 700;
    line-height: 1.1; color: {TEXT};
  }}
  .dl-val.pos {{ color: {GREEN}; }}
  .dl-val.neg {{ color: {DANGER}; }}
  .dl-sub {{
    font-family: Arial, sans-serif;
    font-size: 10px; color: {MUTED};
    margin-top: 3px; min-height: 13px;
  }}
  @media (max-width: 768px) {{
    .dl-groups {{ grid-template-columns: 1fr; }}
  }}

  /* Section headers */
  .section-title {{
    font-size: 13px; font-weight: 800; letter-spacing: 1.5px;
    text-transform: uppercase; color: {BLUE};
    border-bottom: 2px solid {BLUE};
    padding-bottom: 6px; margin: 18px 0 12px;
  }}

  /* Market table — horizontal scroll container (mobile only scrolls inside) */
  .mkt-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
  .mkt-table {{ min-width: 500px; width:100%; border-collapse: collapse; font-size:13px; }}
  .mkt-table th {{
    background: {BLUE}; color: white; padding: 8px 12px;
    font-size: 11px; font-weight: 700; letter-spacing: 1px;
    text-transform: uppercase; text-align: right;
  }}
  .mkt-table th:first-child {{ text-align: left; }}
  .mkt-table td {{
    padding: 8px 12px; border-bottom: 1px solid {BORDER};
    text-align: right;
  }}
  .mkt-table td:first-child {{ text-align: left; font-weight: 600; }}
  .mkt-table tr:last-child {{ font-weight: 700; background: {LIGHT}; }}
  .mkt-table tr:hover td {{ background: #f0f4fa; }}
  .pos {{ color: {GREEN}; font-weight: 700; }}
  .neg {{ color: {DANGER}; font-weight: 700; }}
  .neu {{ color: {MUTED}; }}

  /* Chart containers */
  .chart-card {{
    background: {WHITE}; border: 1px solid {BORDER};
    border-radius: 8px; padding: 16px; margin-bottom: 8px;
  }}

  /* Trends tab — charts scroll horizontally on mobile */
  .trend-chart-wrap {{
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    margin-bottom: 4px;
  }}
  @media (max-width: 768px) {{
    .trend-chart-wrap [data-testid="stPlotlyChart"] > div {{
      min-width: 480px;
    }}
  }}

  /* Trends filter labels */
  .t-label {{
    font-size: 10px; font-weight: 700; letter-spacing: .8px;
    text-transform: uppercase; color: {MUTED};
    margin-bottom: 2px;
  }}

  /* Store detail table */
  .store-table {{ width:100%; border-collapse: collapse; font-size:12px; }}
  .store-table th {{
    background: {LIGHT}; color: {MUTED}; padding: 7px 10px;
    font-size: 10px; font-weight: 700; letter-spacing: 0.8px;
    text-transform: uppercase; text-align: right;
    border-bottom: 2px solid {BORDER};
  }}
  .store-table th:first-child, .store-table th:nth-child(2) {{ text-align: left; }}
  .store-table td {{
    padding: 7px 10px; border-bottom: 1px solid {BORDER};
    text-align: right; color: {TEXT};
  }}
  .store-table td:first-child, .store-table td:nth-child(2) {{
    text-align: left;
  }}
  .store-table tr:hover td {{ background: #f8f9fb; }}
</style>
""", unsafe_allow_html=True)

# ── Logo ───────────────────────────────────────────────────────────────────────
# (reuse the same base64 logo from other pages)
import sys
_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, _ROOT)
try:
    # Try to import logo from the main dashboard module
    import importlib.util
    spec = importlib.util.spec_from_file_location("dashboard", os.path.join(_ROOT, "dashboard.py"))
    _dash = importlib.util.module_from_spec(spec)
    # Don't execute the whole module — just grab the _LOGO from 2_Balanced_Scorecard
    _LOGO = None
except Exception:
    _LOGO = None

# Get logo from Balanced Scorecard module
try:
    spec2 = importlib.util.spec_from_file_location(
        "bs", os.path.join(_ROOT, "pages", "2_Balanced_Scorecard.py"))
    _bs_src = open(os.path.join(_ROOT, "pages", "2_Balanced_Scorecard.py")).read()
    import re as _re
    _m = _re.search(r'_LOGO\s*=\s*"(data:image[^"]+)"', _bs_src)
    if _m:
        _LOGO = _m.group(1)
except Exception:
    _LOGO = None

# ── Date controls (loaded before header so we can show freshness) ──────────────
min_date, max_date = get_date_range()
today = max_date  # most recent data date

# ── Header ─────────────────────────────────────────────────────────────────────
_logo_html = f'<img src="{_LOGO}" style="height:44px;width:auto;flex-shrink:0;"/>' if _LOGO else ""
_fresh_str = max_date.strftime("%a %b %d, %Y") if max_date else "—"
st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;
            background:{BLUE};border-radius:10px;padding:12px 20px;
            margin-bottom:16px;">
  {_logo_html}
  <div style="font-size:13px;font-weight:800;color:{WHITE};
              letter-spacing:2px;text-transform:uppercase;
              font-family:Arial,sans-serif;">
    Daily Sales Dashboard
  </div>
  <div style="margin-left:auto;font-size:10px;color:rgba(255,255,255,0.72);
              text-align:right;white-space:nowrap;line-height:1.5;">
    🕐 Data through<br/><b style="font-size:11px;">{_fresh_str}</b>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Period toggle ──────────────────────────────────────────────────────────────
mkt_filter = "All Markets"   # no market filter — DM tab shows all markets

period = st.radio(
    "Period",
    ["Day", "WTD", "PTD", "YTD"],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
)

# ── Compute date window from toggle ───────────────────────────────────────────
end_date = today
if period == "Day":
    start_date = today                          # single day
elif period == "WTD":
    dow = today.weekday()                       # 0=Monday
    start_date = today - timedelta(days=dow)    # back to Monday
elif period == "PTD":
    start_date = today.replace(day=1)           # start of calendar month
else:  # YTD
    start_date = today.replace(month=1, day=1)

# Prior period: same window 364 days earlier (preserves day of week)
prior_start = start_date - timedelta(days=364)
prior_end   = end_date   - timedelta(days=364)

# ── Date range label + last updated tag ───────────────────────────────────────
period_label = start_date.strftime('%b %d') if start_date != end_date \
               else start_date.strftime('%b %d, %Y')
st.markdown(
    f"<div style='font-size:11px;color:{MUTED};margin-bottom:8px;"
    f"display:flex;justify-content:space-between;'>"
    f"<span>Comparing <b>{period_label}"
    f"{' – ' + end_date.strftime('%b %d, %Y') if start_date != end_date else ''}</b>"
    f" vs prior year <b>{prior_start.strftime('%b %d')} – {prior_end.strftime('%b %d, %Y')}</b>"
    f"&nbsp;(364 days back)</span>"
    f"<span style='color:{MUTED};'>🕐 Last updated: "
    f"<b>{max_date.strftime('%B %d, %Y')}</b></span>"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Load data ──────────────────────────────────────────────────────────────────
all_df = load_sales(
    str(prior_start), str(end_date),
    str(prior_start), str(prior_end),
)

if all_df.empty:
    st.warning("No daily sales data found. Run the backfill script to load data.")
    st.stop()

# Load comp-eligible stores: open_date + 364 days <= start_date
comp_eligible = load_comp_eligible_stores(str(start_date))

curr_df  = all_df[all_df["sale_date"].dt.date.between(start_date, end_date)].copy()
prior_df = all_df[all_df["sale_date"].dt.date.between(prior_start, prior_end)].copy()

# Apply market filter
if mkt_filter != "All Markets":
    curr_df  = curr_df[curr_df["market"] == mkt_filter]
    prior_df = prior_df[prior_df["market"] == mkt_filter]

# ── YTD data for sub-labels (always Jan 1 → today vs prior year) ──────────────
_ytd_start  = today.replace(month=1, day=1)
_ytd_ps     = _ytd_start - timedelta(days=364)
_ytd_pe     = today      - timedelta(days=364)
_ytd_all    = load_sales(str(_ytd_ps), str(today), str(_ytd_ps), str(_ytd_pe))
ytd_curr_df  = _ytd_all[_ytd_all["sale_date"].dt.date.between(_ytd_start, today)].copy()
ytd_prior_df = _ytd_all[_ytd_all["sale_date"].dt.date.between(_ytd_ps, _ytd_pe)].copy()
ytd_curr_df["market"]  = ytd_curr_df["store_id"].apply(get_market)
ytd_prior_df["market"] = ytd_prior_df["store_id"].apply(get_market)

# ── Helper: compute SSS/SST for a grouped dataframe ───────────────────────────
def comp_metrics(curr: pd.DataFrame, prior: pd.DataFrame):
    """
    Returns dict with: net_sales, total_transactions, sss_pct, sst_pct,
    comp_store_count, avg_ticket, walkin_pct, online_pct, thirdparty_pct,
    lunch_pct, dinner_pct, morning_pct, prior_net_sales.

    Comp eligibility: restricted to comp_eligible set (open_date + 364 days
    before period start). SSS/SST calculated on comp stores only; channel/
    daypart mix calculated on all stores in the filtered dataframe.
    """
    # Restrict to comp-eligible stores for SSS/SST
    # Note: comp_eligible is a set of strings; store_id in curr/prior are also strings.
    # If comp_eligible is empty (DB error), fall through gracefully — SSS returns None.
    if comp_eligible:
        curr_comp  = curr[curr["store_id"].astype(str).isin(comp_eligible)]
        prior_comp = prior[prior["store_id"].astype(str).isin(comp_eligible)]
    else:
        curr_comp  = curr.iloc[0:0]   # empty — no comps available
        prior_comp = prior.iloc[0:0]

    c_agg = curr_comp.groupby("store_id").agg(
        net_sales=("net_sales","sum"),
        txn=("total_transactions","sum"),
    ).reset_index()
    p_agg = prior_comp.groupby("store_id").agg(
        net_sales_prior=("net_sales","sum"),
        txn_prior=("total_transactions","sum"),
    ).reset_index()

    # Merge comp store data for both periods
    merged = c_agg.merge(p_agg, on="store_id", how="inner")

    # SSS uses net_sales only — comp set = stores with prior net_sales > 0
    sss_mg     = merged[merged["net_sales_prior"] > 0]
    curr_sales = sss_mg["net_sales"].sum()
    prior_sales= sss_mg["net_sales_prior"].sum()
    sss        = (curr_sales - prior_sales) / prior_sales * 100 if prior_sales > 0 else None

    # SST uses total_transactions only — comp set = stores with prior txn > 0
    sst_mg    = merged[merged["txn_prior"] > 0]
    curr_txn  = sst_mg["txn"].sum()
    prior_txn = sst_mg["txn_prior"].sum()
    sst       = (curr_txn - prior_txn) / prior_txn * 100 if prior_txn > 0 else None

    comp_count = len(sss_mg)   # report SSS comp store count

    # Totals from full curr (all stores) for channel/daypart mix
    total_sales = curr["net_sales"].sum()
    total_txn   = curr["total_transactions"].sum()
    avg_ticket  = total_sales / total_txn if total_txn else None

    walkin    = curr["walkin_sales"].sum()
    online    = curr["online_sales"].sum()
    thirdp    = curr["third_party_sales"].sum()
    lunch     = curr["lunch_sales"].sum()
    dinner    = curr["dinner_sales"].sum()
    morning   = curr["morning_sales"].sum()

    return {
        "net_sales":    total_sales,
        "prior_sales":  prior_sales,
        "transactions": total_txn,
        "sss_pct":      sss,
        "sst_pct":      sst,
        "comp_count":   comp_count,
        "avg_ticket":   avg_ticket,
        "walkin_pct":   walkin / total_sales * 100 if total_sales else None,
        "online_pct":   online / total_sales * 100 if total_sales else None,
        "thirdp_pct":   thirdp / total_sales * 100 if total_sales else None,
        "lunch_sales":  lunch,
        "dinner_sales": dinner,
        "morning_sales":morning,
        "lunch_pct":    lunch  / total_sales * 100 if total_sales else None,
        "dinner_pct":   dinner / total_sales * 100 if total_sales else None,
        "morning_pct":  morning/ total_sales * 100 if total_sales else None,
    }

totals = comp_metrics(curr_df, prior_df)

# ── Formatting helpers ─────────────────────────────────────────────────────────
def fmt_dollar(v):
    if v is None: return "—"
    if v >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if v >= 1_000:     return f"${v/1_000:,.0f}K"
    return f"${v:,.0f}"

def fmt_pct(v, plus=True):
    if v is None: return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"

def pct_class(v):
    if v is None: return "neu"
    return "pos" if v >= 0 else "neg"

def kpi_delta_html(v):
    if v is None: return ""
    cls = "kpi-pos" if v >= 0 else "kpi-neg"
    arrow = "▲" if v >= 0 else "▼"
    return f'<span class="{cls}">{arrow} {fmt_pct(v)}</span> vs prior year'

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "By District Manager", "Trends", "Benchmark"])
with tab1:
    # ── Compute metrics for selected period and YTD ───────────────────────────
    T  = comp_metrics(curr_df, prior_df)      # current period
    TY = comp_metrics(ytd_curr_df, ytd_prior_df)  # YTD

    # CHECK% = ticket change = (1+SSS)/(1+SST) - 1
    def _check(sss, sst):
        if sss is None or sst is None: return None
        return ((1 + sss/100) / (1 + sst/100) - 1) * 100

    check_pct    = _check(T["sss_pct"],  T["sst_pct"])
    check_pct_yt = _check(TY["sss_pct"], TY["sst_pct"])

    # AUV = annualized net sales per store (run-rate)
    days = max((end_date - start_date).days + 1, 1)
    ytd_days = max((today - _ytd_start).days + 1, 1)
    stores = max(curr_df["store_id"].nunique(), 1)
    ytd_stores = max(ytd_curr_df["store_id"].nunique(), 1)
    auv    = (T["net_sales"]  / days    * 365) / stores      if T["net_sales"]  else None
    auv_yt = (TY["net_sales"] / ytd_days * 365) / ytd_stores if TY["net_sales"] else None

    period_lbl = {"Day": "Day", "WTD": "WTD", "PTD": "MTD", "YTD": "YTD"}[period]

    def _pv(v, pct=True, dollar=False):
        """Format a metric value with color class."""
        if v is None: return ("—", "")
        if pct:
            cls = "pos" if v >= 0 else "neg"
            sign = "+" if v >= 0 else ""
            return (f"{sign}{v:.1f}%", cls)
        if dollar:
            return (fmt_dollar(v), "")
        return (f"{v:.1f}%", "")

    def _sub(v, pct=True, dollar=False, label="YTD"):
        if v is None: return ""
        if pct:
            sign = "+" if v >= 0 else ""
            return f"{label} {sign}{v:.1f}%"
        if dollar:
            return f"{label} {fmt_dollar(v)}"
        return f"{label} {v:.1f}%"

    def _tile(lbl, val, cls, sub):
        return (
            f'<div class="dl-tile">'
            f'<div class="dl-lbl">{lbl}</div>'
            f'<div class="dl-val {cls}">{val}</div>'
            f'<div class="dl-sub">{sub}</div>'
            f'</div>'
        )

    sss_v, sss_c   = _pv(T["sss_pct"])
    sst_v, sst_c   = _pv(T["sst_pct"])
    chk_v, chk_c   = _pv(check_pct)
    ns_v,  _       = _pv(T["net_sales"],  pct=False, dollar=True)
    auv_v, _       = _pv(auv,             pct=False, dollar=True)
    wi_v,  _       = _pv(T["walkin_pct"], pct=False)
    on_v,  _       = _pv(T["online_pct"], pct=False)
    tp_v,  _       = _pv(T["thirdp_pct"], pct=False)

    comp_tiles = (
        _tile("SSS",  sss_v, sss_c, _sub(TY["sss_pct"])) +
        _tile("SST",  sst_v, sst_c, _sub(TY["sst_pct"])) +
        _tile("CHECK", chk_v, chk_c, _sub(check_pct_yt))
    )
    sales_tiles = (
        _tile("AUV",         auv_v, "", _sub(auv_yt,            pct=False, dollar=True)) +
        _tile("Net Sales",   ns_v,  "", _sub(TY["net_sales"],    pct=False, dollar=True)) +
        _tile("Avg Check",
              f"${T['avg_ticket']:.2f}"  if T["avg_ticket"]  else "—", "",
              f"YTD ${TY['avg_ticket']:.2f}" if TY["avg_ticket"] else "")
    )
    mix_tiles = (
        _tile("In-Store", wi_v, "", _sub(TY["walkin_pct"], pct=False)) +
        _tile("Online",   on_v, "", _sub(TY["online_pct"], pct=False)) +
        _tile("3PD",      tp_v, "", _sub(TY["thirdp_pct"], pct=False))
    )

    st.markdown(f"""
    <div class="dl-groups">
      <div class="dl-group">
        <div class="dl-header">Comp Sales</div>
        <div class="dl-tiles">{comp_tiles}</div>
      </div>
      <div class="dl-group">
        <div class="dl-header">Sales</div>
        <div class="dl-tiles">{sales_tiles}</div>
      </div>
      <div class="dl-group">
        <div class="dl-header">Sales Mix</div>
        <div class="dl-tiles">{mix_tiles}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── By-Market Table ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-title">By Market</div>', unsafe_allow_html=True)
    
    markets = curr_df["market"].unique().tolist()
    if mkt_filter == "All Markets":
        markets = sorted(markets)
    
    mkt_rows = []
    for mkt in markets:
        mc = curr_df[curr_df["market"] == mkt]
        mp = prior_df[prior_df["market"] == mkt]
        m  = comp_metrics(mc, mp)
        mkt_rows.append({
            "market": mkt,
            "stores": mc["store_id"].nunique(),
            **m,
        })
    
    # Add TOTAL row
    mkt_rows.append({
        "market": "TOTAL",
        "stores": curr_df["store_id"].nunique(),
        **totals,
    })
    
    def _row_html(r, is_total=False):
        sss_cls  = pct_class(r["sss_pct"])
        sst_cls  = pct_class(r["sst_pct"])
        online   = f"{r['online_pct']:.1f}%" if r["online_pct"] else "—"
        thirdp   = f"{r['thirdp_pct']:.1f}%" if r["thirdp_pct"] else "—"
        avg_t    = f"${r['avg_ticket']:.2f}" if r["avg_ticket"] else "—"
        # AUV = (net_sales / stores / days in period) * 364  →  annualised per-store run-rate
        _n_stores = r["stores"] if r["stores"] else 1
        auv_val  = (r["net_sales"] / _n_stores / days) * 364 if r["net_sales"] else None
        auv_str  = fmt_dollar(auv_val) if auv_val else "—"
        _n_label = (f"&nbsp;<span style='font-size:9px;font-weight:400;color:#6B7280;'>"
                    f"n={r['stores']}</span>") if not is_total else ""
        return (
            f"<tr>"
            f"<td>{r['market']}{_n_label}</td>"
            f"<td class='{sss_cls}'>{fmt_pct(r['sss_pct'])}</td>"
            f"<td class='{sst_cls}'>{fmt_pct(r['sst_pct'])}</td>"
            f"<td>{auv_str}</td>"
            f"<td>{fmt_dollar(r['net_sales'])}</td>"
            f"<td>{avg_t}</td>"
            f"<td>{online}</td>"
            f"<td>{thirdp}</td>"
            f"<td style='text-align:center'>{r['comp_count']}</td>"
            f"</tr>"
        )

    rows_html = "".join(_row_html(r, r["market"] == "TOTAL") for r in mkt_rows)
    st.markdown(f"""
    <div class="mkt-scroll">
    <table class="mkt-table">
      <thead><tr>
        <th>Market</th><th>SSS%</th><th>SST%</th>
        <th>AUV</th><th>Total Sales</th><th>Avg Ticket</th>
        <th>Online%</th><th>3P%</th>
        <th style="text-align:center">Comps</th>
      </tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    </div>
    """, unsafe_allow_html=True)
    
    # ── Daily SSS Trend (always last 7 days, independent of period toggle) ────────
    # _SR_COL_W used by the sub-region weather grid below (labels + legend columns)
    _SR_COL_W = 222  # px  (150 label + 72 legend)
    PLOTLY_LAYOUT = dict(
        plot_bgcolor=WHITE, paper_bgcolor=WHITE,
        font=dict(family="Arial, sans-serif", size=12, color=TEXT),
        dragmode=False,
        modebar=dict(remove=["select2d","lasso2d","zoom2d","pan2d",
                              "autoScale2d","resetScale2d","toImage","sendDataToCloud"]),
        margin=dict(l=55, r=20, t=40, b=80),
        legend=dict(bgcolor=WHITE, bordercolor=BORDER, borderwidth=1,
                    font=dict(size=11), orientation="h",
                    yanchor="top", y=-0.25, xanchor="center", x=0.5),
    )
    st.markdown('<div class="section-title">Daily SSS Trend</div>', unsafe_allow_html=True)

    # Always last 7 days regardless of the period toggle
    _chart_end   = today
    _chart_start = today - timedelta(days=6)
    _2yr_ago     = _chart_start - timedelta(days=728)

    # Load enough history to cover the 2yr lookback (cached, fast)
    _chart_all = load_sales(
        str(_2yr_ago), str(_chart_end),
        str(_2yr_ago), str(_chart_end),
    )

    # Use comp_eligible stores fixed to the chart window start (not period toggle)
    _chart_comp = load_comp_eligible_stores(str(_chart_start))

    # Filter to comp stores only
    _comp_data = _chart_all[_chart_all["store_id"].astype(str).isin(_chart_comp)].copy()

    def _sss_per_day(chart_days, lookback_days):
        """
        Compute SSS% for each day using only the intersection of stores that
        have data on BOTH the current day AND the equivalent prior-year day.
        This matches the comp_metrics() inner-join methodology used in the tiles,
        so a store missing data on any given day is excluded from both sides of
        that day's calc — never inflating/deflating the denominator.
        Returns DataFrame with columns [sale_date, sss].
        """
        rows = []
        for curr_day in chart_days:
            prior_day = curr_day - timedelta(days=lookback_days)
            curr_sub  = _comp_data[_comp_data["sale_date"].dt.date == curr_day]
            prior_sub = _comp_data[_comp_data["sale_date"].dt.date == prior_day]
            both = set(curr_sub["store_id"]) & set(prior_sub["store_id"])
            if not both:
                continue
            c_sales = curr_sub[curr_sub["store_id"].isin(both)]["net_sales"].sum()
            p_sales = prior_sub[prior_sub["store_id"].isin(both)]["net_sales"].sum()
            if p_sales > 0:
                rows.append({"sale_date": pd.Timestamp(curr_day), "sss": (c_sales - p_sales) / p_sales * 100})
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["sale_date", "sss"])

    _days7 = [_chart_start + timedelta(days=i) for i in range(7)]

    _sss1 = _sss_per_day(_days7, 364)
    _sss2 = _sss_per_day(_days7, 728)

    _trend = _sss1.rename(columns={"sss": "sss_1yr"}) \
                  .merge(_sss2.rename(columns={"sss": "sss_2yr"}),
                         on="sale_date", how="outer") \
                  .sort_values("sale_date")
    _trend = _trend[_trend["sss_1yr"].notna()].copy()

    fig_sss = go.Figure()
    fig_sss.add_trace(go.Bar(
        x=_trend["sale_date"], y=_trend["sss_1yr"],
        name="SSS% vs. 1yr ago",
        marker_color=[GREEN if v >= 0 else DANGER for v in _trend["sss_1yr"]],
        opacity=0.7,
        text=[f"{v:+.1f}%" for v in _trend["sss_1yr"]],
        textposition="outside",
        textfont=dict(size=11, family="Arial, sans-serif",
                      color=[GREEN if v >= 0 else DANGER for v in _trend["sss_1yr"]]),
    ))
    fig_sss.add_trace(go.Scatter(
        x=_trend["sale_date"], y=_trend["sss_2yr"],
        name="SSS% vs. 2yr ago",
        line=dict(color=GOLD, width=2.5),
        mode="lines+markers",
        marker=dict(size=6, color=GOLD),
    ))
    fig_sss.add_hline(y=0, line_color=MUTED, line_width=1)
    fig_sss.update_layout(
        **PLOTLY_LAYOUT,
        title=dict(text="Daily SSS% — Last 7 Days", font=dict(size=13, color=BLUE), x=0),
        xaxis=dict(tickformat="%a %b %d", gridcolor="#E5E7EB"),
        yaxis=dict(ticksuffix="%", gridcolor="#E5E7EB"),
        height=300,
    )
    st.plotly_chart(fig_sss, use_container_width=True, key="sss_trend_chart")

    # ── Sub-Region Weather × SSS Attribution Panel ───────────────────────────────
    _SR_MAP = {
        '20026':'Valley',    '20267':'Valley',    '20116':'Valley',    '20363':'Valley',
        '20156':'Valley',    '20424':'Valley',    '20366':'Valley',    '20294':'Valley',
        '20352':'Valley',    '20218':'Valley',    '20381':'Valley',    '20311':'Valley',
        '20011':'Conejo',    '20048':'Conejo',    '20245':'Conejo',    '20255':'Conejo',
        '20273':'Mountains', '20388':'Mountains',
        '20075':'Santa Barbara', '20335':'Santa Barbara',
        '20360':'Santa Barbara', '20013':'Santa Barbara',
        '20171':'Inland Riverside', '20177':'Inland Riverside',
        '20291':'Inland Riverside', '20091':'Inland Riverside',
        '20071':'Inland SD', '20300':'Inland SD', '20292':'Inland SD',
    }
    _SR_ORDER = ['Valley','Conejo','Mountains','Santa Barbara','Inland Riverside','Inland SD']

    # Store counts per sub-region
    _sr_counts = {}
    for _sid, _srn in _SR_MAP.items():
        _sr_counts[_srn] = _sr_counts.get(_srn, 0) + 1

    # Column widths (must sum to _SR_COL_W so day columns align with chart bars)
    _LABEL_W  = 150  # sub-region name column
    _LEGEND_W = 72   # how-to-read column

    @st.cache_data(ttl=300)
    def load_weather_by_store_7d(start_str, end_str):
        conn, dialect = get_conn()
        p = "%s" if dialect == "postgres" else "?"
        try:
            df = pd.read_sql_query(
                f"SELECT store_id, date, temp_max_f, precip_in, is_rainy "
                f"FROM store_daily_weather WHERE date >= {p} AND date <= {p}",
                conn, params=(start_str, end_str))
            conn.close()
            df["date"]     = pd.to_datetime(df["date"])
            df["store_id"] = df["store_id"].astype(str).str.strip()
            return df
        except Exception:
            conn.close()
            return pd.DataFrame()

    def _agg_wx_by_sr(raw_df, sr_map):
        """Aggregate per-store weather → per-subregion, return lookup dict keyed (sr, date)."""
        if raw_df.empty:
            return {}
        raw_df = raw_df.copy()
        raw_df["subregion"] = raw_df["store_id"].map(sr_map)
        agg = (raw_df[raw_df["subregion"].notna()]
               .groupby(["subregion","date"])
               .agg(temp=("temp_max_f","mean"),
                    precip=("precip_in","mean"),
                    rainy=("is_rainy","max"))
               .reset_index())
        return {(r.subregion, r.date.date()): r for _, r in agg.iterrows()}

    # Current 7-day window weather + prior-year window (364 days back)
    _wx7_curr  = load_weather_by_store_7d(str(_chart_start), str(_chart_end))
    _1yr_wx_s  = _chart_start - timedelta(days=364)
    _1yr_wx_e  = _chart_end   - timedelta(days=364)
    _wx7_prior = load_weather_by_store_7d(str(_1yr_wx_s), str(_1yr_wx_e))

    _wx_lookup = _agg_wx_by_sr(_wx7_curr, _SR_MAP)

    # Build prior-year lookup keyed to CURRENT dates (shift +364 days)
    _wx_prior_raw = _agg_wx_by_sr(_wx7_prior, _SR_MAP)
    _wx_prior_lookup = {
        (sr, d + timedelta(days=364)): row
        for (sr, d), row in _wx_prior_raw.items()
    }

    # SSS% per sub-region per day — intersection methodology (matches tiles)
    _comp_sr = _comp_data.copy()
    _comp_sr["subregion"] = _comp_sr["store_id"].map(_SR_MAP)
    _comp_sr = _comp_sr[_comp_sr["subregion"].notna()]

    def _sr_sss_per_day(chart_days):
        """
        For each (subregion, day) pair compute SSS% using only stores that
        have data on both the current day and 364 days prior — same inner-join
        logic as comp_metrics() so sub-region cells agree with the tiles.
        """
        rows = []
        for curr_day in chart_days:
            prior_day = curr_day - timedelta(days=364)
            curr_sub  = _comp_sr[_comp_sr["sale_date"].dt.date == curr_day]
            prior_sub = _comp_sr[_comp_sr["sale_date"].dt.date == prior_day]
            for sr in _SR_ORDER:
                c = curr_sub[curr_sub["subregion"] == sr]
                p = prior_sub[prior_sub["subregion"] == sr]
                both = set(c["store_id"]) & set(p["store_id"])
                if not both:
                    continue
                c_sales = c[c["store_id"].isin(both)]["net_sales"].sum()
                p_sales = p[p["store_id"].isin(both)]["net_sales"].sum()
                if p_sales > 0:
                    rows.append({
                        "subregion": sr,
                        "sale_date": pd.Timestamp(curr_day),
                        "sss": (c_sales - p_sales) / p_sales * 100,
                    })
        return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["subregion","sale_date","sss"])

    _sss_sr_df = _sr_sss_per_day(_days7)
    _sss_lookup = {
        (r.subregion, r.sale_date.date()): r.sss
        for _, r in _sss_sr_df.iterrows()
    }

    # ── Cell helpers ──────────────────────────────────────────────────────────────
    def _wx_icon_sr(r):
        if r is None: return "—"
        if pd.notna(r.rainy) and r.rainy >= 0.5: return "🌧️"
        t = r.temp
        if pd.isna(t): return "—"
        if t >= 90: return "🔥"
        if t >= 80: return "☀️"
        if t >= 68: return "🌤️"
        if t >= 55: return "⛅"
        return "❄️"

    def _cell_bg(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return "#F9FAFB"
        if v >=  4: return "#bbf7d0"
        if v >=  1: return "#dcfce7"
        if v >= -1: return "#fef2f2"
        if v >= -4: return "#fecaca"
        return "#fca5a5"

    def _sss_clr(v):
        if v is None or (isinstance(v, float) and pd.isna(v)): return MUTED
        return GREEN if v >= 0 else DANGER

    def _fmt_delta(curr_r, prior_r):
        """Return (temp_delta_html, precip_delta_html) strings."""
        # Temp delta
        if (curr_r is not None and prior_r is not None
                and pd.notna(curr_r.temp) and pd.notna(prior_r.temp)):
            dt = curr_r.temp - prior_r.temp
            dt_clr = "#ea580c" if dt > 3 else ("#3b82f6" if dt < -3 else MUTED)
            dt_s = f'<span style="color:{dt_clr};font-size:9px;">{dt:+.0f}°</span>'
        else:
            dt_s = ""
        # Precip delta
        if (curr_r is not None and prior_r is not None
                and pd.notna(curr_r.precip) and pd.notna(prior_r.precip)):
            dp = curr_r.precip - prior_r.precip
            if abs(dp) >= 0.01:
                dp_clr = "#3b82f6" if dp > 0.02 else ("#d97706" if dp < -0.02 else MUTED)
                dp_s = f'<span style="color:{dp_clr};font-size:9px;">{dp:+.2f}"</span>'
            else:
                dp_s = ""
        else:
            dp_s = ""
        sep = ' <span style="color:#d1d5db;font-size:8px;">|</span> ' if dt_s and dp_s else ""
        return dt_s + sep + dp_s

    # ── Build header row ──────────────────────────────────────────────────────────
    _th_base = (f'padding:7px 6px;font-size:10px;font-weight:700;color:{WHITE};'
                f'border-right:1px solid rgba(255,255,255,0.2);')
    _hdr = (
        f'<th style="width:{_LABEL_W}px;min-width:{_LABEL_W}px;{_th_base}'
        f'text-align:left;padding-left:10px;white-space:nowrap;">Sub-Region</th>'
        f'<th style="width:{_LEGEND_W}px;min-width:{_LEGEND_W}px;{_th_base}'
        f'text-align:left;font-style:italic;opacity:0.75;">How to read</th>'
    )
    for _d in _days7:
        _hdr += (f'<th style="text-align:center;{_th_base}white-space:nowrap;min-width:68px;">'
                 f'{_d.strftime("%a")}<br/>{_d.strftime("%b %d")}</th>')

    # ── Build data rows ───────────────────────────────────────────────────────────
    _legend_td = (
        f'<td style="width:{_LEGEND_W}px;min-width:{_LEGEND_W}px;padding:5px 6px;'
        f'border-right:1px solid {BORDER};border-top:1px solid {BORDER};'
        f'background:{LIGHT};vertical-align:middle;text-align:left;">'
        f'<div style="font-size:9px;color:{MUTED};line-height:1.8;white-space:nowrap;">'
        f'🌡 Cond / Hi<br/>Δ vs yr ago<br/>SSS% (1yr)'
        f'</div></td>'
    )

    _body = ""
    for _sr in _SR_ORDER:
        _n = _sr_counts.get(_sr, 0)
        _label_td = (
            f'<td style="width:{_LABEL_W}px;min-width:{_LABEL_W}px;max-width:{_LABEL_W}px;'
            f'padding:6px 10px;border-right:1px solid {BORDER};'
            f'border-top:1px solid {BORDER};background:{LIGHT};vertical-align:middle;">'
            f'<div style="font-size:11px;font-weight:700;color:{TEXT};white-space:nowrap;">{_sr}</div>'
            f'<div style="font-size:9px;color:{MUTED};margin-top:1px;">n={_n} stores</div>'
            f'</td>'
        )
        _cells = _label_td + _legend_td

        for _d in _days7:
            _wr  = _wx_lookup.get((_sr, _d))
            _wpr = _wx_prior_lookup.get((_sr, _d))
            _sv  = _sss_lookup.get((_sr, _d))
            _ico = _wx_icon_sr(_wr)
            _tmp = f"{_wr.temp:.0f}°" if _wr is not None and pd.notna(_wr.temp) else "—"
            _prc = (f'<span style="color:#3b82f6;font-size:9px;">&nbsp;{_wr.precip:.2f}"</span>'
                    if _wr is not None and pd.notna(_wr.precip) and _wr.precip > 0.01 else "")
            _delta_html = _fmt_delta(_wr, _wpr)
            _bg  = _cell_bg(_sv)
            _ss  = f"{_sv:+.1f}%" if _sv is not None and not (isinstance(_sv, float) and pd.isna(_sv)) else "—"
            _sc  = _sss_clr(_sv)
            _cells += (
                f'<td style="text-align:center;padding:5px 4px;background:{_bg};'
                f'border-right:1px solid {BORDER};border-top:1px solid {BORDER};min-width:68px;">'
                f'<div style="font-size:16px;line-height:1.1;">{_ico}&nbsp;'
                f'<span style="font-size:10px;color:{MUTED};">{_tmp}{_prc}</span></div>'
                f'<div style="font-size:9px;line-height:1.4;min-height:14px;">{_delta_html}</div>'
                f'<div style="font-size:12px;font-weight:700;color:{_sc};margin-top:1px;">{_ss}</div>'
                f'</td>'
            )
        _body += f'<tr>{_cells}</tr>'

    st.markdown(f"""
    <div style="background:{WHITE};border:1px solid {BORDER};border-radius:8px;
                overflow:hidden;margin-top:6px;">
      <div style="background:{BLUE};padding:6px 12px;
                  display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:10px;font-weight:700;letter-spacing:1px;
                     text-transform:uppercase;color:{WHITE};">
          🌡️ Weather × SSS Attribution — Last 7 Days</span>
        <span style="font-size:10px;color:rgba(255,255,255,0.7);">
          Cell color = SSS% vs. prior year &nbsp;·&nbsp;
          🔥 ≥90° &nbsp;☀️ 80-89° &nbsp;🌤️ 68-79° &nbsp;⛅ 55-67° &nbsp;❄️ &lt;55° &nbsp;🌧️ rain
          &nbsp;·&nbsp; Δ = change vs. same week 1yr ago</span>
      </div>
      <div style="overflow-x:auto;">
        <table style="width:100%;border-collapse:collapse;">
          <thead><tr style="background:{BLUE};">{_hdr}</tr></thead>
          <tbody>{_body}</tbody>
        </table>
      </div>
    </div>
    """, unsafe_allow_html=True)


with tab2:
    # ── CSS for nested tree table ──────────────────────────────────────────────
    st.markdown(f"""
    <style>
      /* Scroll wrapper — horizontal scroll on mobile */
      .dm-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
      .dm-tree {{ font-family: Arial, sans-serif; font-size: 13px; min-width: 660px; width: 100%; }}
      .dm-tree summary {{ list-style: none; cursor: pointer; }}
      .dm-tree summary::-webkit-details-marker {{ display: none; }}

      /* Shared grid — same column positions for header, every row, and total */
      .tree-header,
      .tree-row,
      .total-row {{
        display: grid;
        grid-template-columns: minmax(150px,1fr) 75px 75px 90px 110px 60px 70px;
        align-items: center;
        padding: 8px 12px;
      }}
      /* Prevent header text from ever wrapping */
      .tree-header span {{ white-space: nowrap; }}
      /* Right-align all columns except the first */
      .tree-header span:not(:first-child),
      .tree-row   span:not(:first-child),
      .total-row  span:not(:first-child) {{ text-align: right; padding: 0 4px; }}
      .tree-header span:first-child,
      .tree-row   span:first-child,
      .total-row  span:first-child {{ padding: 0 4px; }}

      /* Header */
      .tree-header {{
        background: {BLUE}; color: white;
        font-size: 11px; font-weight: 700; letter-spacing: 1px;
        text-transform: uppercase;
        border-radius: 6px 6px 0 0; margin-bottom: 2px;
      }}
      /* Market rows — light blue */
      .mkt-summary .tree-row {{
        background: #d0e4f7; color: {TEXT};
        font-weight: 700; font-size: 13px;
        border-radius: 4px; margin: 3px 0;
      }}
      .mkt-summary:hover .tree-row {{ background: #bcd6ef; }}
      /* DM rows — indent NAME column only via first-child padding */
      .dm-summary .tree-row {{
        background: {LIGHT}; color: {TEXT};
        font-weight: 600; border-bottom: 1px solid {BORDER};
      }}
      .dm-summary .tree-row > span:first-child {{ padding-left: 24px !important; }}
      .dm-summary:hover .tree-row {{ background: #e4eaf4; }}
      /* Store rows — indent NAME column only */
      .store-row .tree-row {{
        background: white; color: {TEXT};
        border-bottom: 1px solid {BORDER}; font-size: 12px;
      }}
      .store-row .tree-row > span:first-child {{ padding-left: 44px !important; }}
      .store-row:last-child .tree-row {{ border-bottom: none; }}
      /* Total row — dark blue */
      .total-row {{
        background: {BLUE}; color: white;
        font-weight: 700; font-size: 13px;
        border-radius: 0 0 6px 6px; margin-top: 3px;
      }}
      .pos-val {{ color: {GREEN}; font-weight: 700; }}
      .neg-val {{ color: {DANGER}; font-weight: 700; }}
      .na-val  {{ color: {MUTED}; }}
      details > summary {{ display: block; }}
      /* Use > (direct child) so ::before only hits the name column,
         not the nested spans inside the SSS/SST percentage cells */
      details[open] .mkt-summary .tree-row > span:first-child::before {{ content: "▼ "; }}
      details:not([open]) .mkt-summary .tree-row > span:first-child::before {{ content: "▶ "; }}
      details[open] .dm-summary .tree-row > span:first-child::before {{ content: "▼ "; }}
      details:not([open]) .dm-summary .tree-row > span:first-child::before {{ content: "▶ "; }}
    </style>
    """, unsafe_allow_html=True)

    dm_map = load_dm_store_map()

    if dm_map is None or dm_map.empty:
        st.info("DM data not yet loaded — run `py scripts/update_stores.py`.")
    else:
        # ── Compute store-level SSS/SST ────────────────────────────────────────
        def _store_metrics(store_id):
            c = curr_df[curr_df["store_id"] == store_id]
            p = prior_df[prior_df["store_id"] == store_id]
            ns  = c["net_sales"].sum()
            txn = int(c["total_transactions"].sum())
            if store_id not in comp_eligible:
                return ns, txn, None, None
            pns  = p["net_sales"].sum()
            ptxn = p["total_transactions"].sum()
            sss = (ns  - pns)  / pns  * 100 if pns  > 0 else None
            sst = (txn - ptxn) / ptxn * 100 if ptxn > 0 else None
            return ns, txn, sss, sst

        # ── HTML helpers ───────────────────────────────────────────────────────
        def _pct_span(v):
            if v is None: return f'<span class="na-val">—</span>'
            cls = "pos-val" if v >= 0 else "neg-val"
            sign = "+" if v >= 0 else ""
            return f'<span class="{cls}">{sign}{v:.1f}%</span>'

        def _row(name, stores, ns, txn, sss, sst, comps=""):
            return (
                f'<div class="tree-row">'
                f'<span>{name}</span>'
                f'<span style="text-align:right">{_pct_span(sss)}</span>'
                f'<span style="text-align:right">{_pct_span(sst)}</span>'
                f'<span style="text-align:right">{fmt_dollar(ns)}</span>'
                f'<span style="text-align:right">{txn:,}</span>'
                f'<span style="text-align:right">{stores}</span>'
                f'<span style="text-align:right">{comps}</span>'
                f'</div>'
            )

        MARKET_ORDER = {"Los Angeles": 0, "San Diego": 1, "Santa Barbara": 2}
        html_parts = [
            '<div class="dm-scroll"><div class="dm-tree">',
            '<div class="tree-header">'
            '<span>Group / Store</span>'
            '<span>SSS%</span><span>SST%</span>'
            '<span>Net Sales</span><span>Transactions</span>'
            '<span>Stores</span><span>Comps</span>'
            '</div>',
        ]

        for market in sorted(dm_map["display_market"].unique(),
                             key=lambda m: MARKET_ORDER.get(m, 9)):
            mkt_dm = dm_map[dm_map["display_market"] == market]
            if mkt_filter != "All Markets" and market != mkt_filter:
                continue

            # Market-level aggregation
            mkt_c = curr_df[curr_df["market"] == market]  if market != "Santa Barbara" \
                    else curr_df[~curr_df["market"].isin(["Los Angeles","San Diego"])]
            # Override: use DM store_ids to define market scope accurately
            mkt_store_ids = set(mkt_dm["store_id"].tolist())
            mkt_c = curr_df[curr_df["store_id"].isin(mkt_store_ids)]
            mkt_p = prior_df[prior_df["store_id"].isin(mkt_store_ids)]

            mkt_sss_mg = mkt_c[mkt_c["store_id"].isin(comp_eligible)].groupby("store_id")["net_sales"].sum()
            mkt_sss_p  = mkt_p[mkt_p["store_id"].isin(comp_eligible)].groupby("store_id")["net_sales"].sum()
            mkt_sss_mg2 = mkt_sss_mg.reset_index().merge(mkt_sss_p.reset_index(), on="store_id", suffixes=("_c","_p"))
            mkt_sss_mg2 = mkt_sss_mg2[mkt_sss_mg2["net_sales_p"] > 0]
            mkt_sss = (mkt_sss_mg2["net_sales_c"].sum() - mkt_sss_mg2["net_sales_p"].sum()) / \
                       mkt_sss_mg2["net_sales_p"].sum() * 100 if mkt_sss_mg2["net_sales_p"].sum() > 0 else None

            mkt_sst_mg = mkt_c[mkt_c["store_id"].isin(comp_eligible)].groupby("store_id")["total_transactions"].sum()
            mkt_sst_p  = mkt_p[mkt_p["store_id"].isin(comp_eligible)].groupby("store_id")["total_transactions"].sum()
            mkt_sst_mg2 = mkt_sst_mg.reset_index().merge(mkt_sst_p.reset_index(), on="store_id", suffixes=("_c","_p"))
            mkt_sst_mg2 = mkt_sst_mg2[mkt_sst_mg2["total_transactions_p"] > 0]
            mkt_sst = (mkt_sst_mg2["total_transactions_c"].sum() - mkt_sst_mg2["total_transactions_p"].sum()) / \
                       mkt_sst_mg2["total_transactions_p"].sum() * 100 if mkt_sst_mg2["total_transactions_p"].sum() > 0 else None

            mkt_ns  = mkt_c["net_sales"].sum()
            mkt_txn = int(mkt_c["total_transactions"].sum())
            mkt_comps = len(mkt_sss_mg2)

            # Build market details block (open by default)
            mkt_html = [f'<details open><summary class="mkt-summary">']
            mkt_html.append(_row(market, len(mkt_store_ids), mkt_ns, mkt_txn,
                                 mkt_sss, mkt_sst, mkt_comps))
            mkt_html.append('</summary>')

            # DM groups within market
            for dm_group, dm_grp in mkt_dm.groupby("dm_group"):
                dm_store_ids = set(dm_grp["store_id"].tolist())
                dm_c = curr_df[curr_df["store_id"].isin(dm_store_ids)]
                dm_p = prior_df[prior_df["store_id"].isin(dm_store_ids)]

                # DM-level SSS/SST
                dc_agg = dm_c[dm_c["store_id"].isin(comp_eligible)].groupby("store_id").agg(
                    cs=("net_sales","sum"), ct=("total_transactions","sum")).reset_index()
                dp_agg = dm_p[dm_p["store_id"].isin(comp_eligible)].groupby("store_id").agg(
                    ps=("net_sales","sum"), pt=("total_transactions","sum")).reset_index()
                dm_mg = dc_agg.merge(dp_agg, on="store_id", how="inner")
                dm_sss_mg = dm_mg[dm_mg["ps"] > 0]
                dm_sss = (dm_sss_mg["cs"].sum() - dm_sss_mg["ps"].sum()) / dm_sss_mg["ps"].sum() * 100 \
                         if dm_sss_mg["ps"].sum() > 0 else None
                dm_sst_mg = dm_mg[dm_mg["pt"] > 0]
                dm_sst = (dm_sst_mg["ct"].sum() - dm_sst_mg["pt"].sum()) / dm_sst_mg["pt"].sum() * 100 \
                         if dm_sst_mg["pt"].sum() > 0 else None

                dm_ns  = dm_c["net_sales"].sum()
                dm_txn = int(dm_c["total_transactions"].sum())
                dm_name_short = dm_group.split(" - ")[-1]  # just first name

                # DM details block (collapsed by default — expand to see stores)
                mkt_html.append('<details><summary class="dm-summary">')
                mkt_html.append(_row(dm_name_short,  # first name only
                                     len(dm_store_ids), dm_ns, dm_txn,
                                     dm_sss, dm_sst, len(dm_sss_mg)))
                mkt_html.append('</summary>')

                # Store rows within DM
                for _, srow in dm_grp.iterrows():
                    sid   = srow["store_id"]
                    sname = STORE_NAMES.get(sid, sid)
                    s_ns, s_txn, s_sss, s_sst = _store_metrics(sid)
                    mkt_html.append(
                        f'<div class="store-row">'
                        + _row(sname, "", s_ns, s_txn, s_sss, s_sst,
                               "✓" if sid in comp_eligible else "—")
                        + '</div>'
                    )
                mkt_html.append('</details>')  # close DM details

            mkt_html.append('</details>')  # close market details
            html_parts.extend(mkt_html)

        # ── Grand Total row (dark blue) — includes all stores inc. Tampa (LA) ─
        all_c = curr_df.copy()
        all_p = prior_df.copy()
        if mkt_filter != "All Markets":
            market_store_ids = set(dm_map["store_id"].tolist())
            all_c = curr_df[curr_df["store_id"].isin(market_store_ids)]
            all_p = prior_df[prior_df["store_id"].isin(market_store_ids)]

        tot_c_agg = all_c[all_c["store_id"].isin(comp_eligible)].groupby("store_id").agg(
            cs=("net_sales","sum"), ct=("total_transactions","sum")).reset_index()
        tot_p_agg = all_p[all_p["store_id"].isin(comp_eligible)].groupby("store_id").agg(
            ps=("net_sales","sum"), pt=("total_transactions","sum")).reset_index()
        tot_mg = tot_c_agg.merge(tot_p_agg, on="store_id", how="inner")
        tot_sss_mg = tot_mg[tot_mg["ps"] > 0]
        tot_sss = (tot_sss_mg["cs"].sum() - tot_sss_mg["ps"].sum()) / tot_sss_mg["ps"].sum() * 100 \
                  if tot_sss_mg["ps"].sum() > 0 else None
        tot_sst_mg = tot_mg[tot_mg["pt"] > 0]
        tot_sst = (tot_sst_mg["ct"].sum() - tot_sst_mg["pt"].sum()) / tot_sst_mg["pt"].sum() * 100 \
                  if tot_sst_mg["pt"].sum() > 0 else None
        tot_ns  = all_c["net_sales"].sum()
        tot_txn = int(all_c["total_transactions"].sum())
        tot_stores = all_c["store_id"].nunique()

        def _pct_white(v):
            if v is None: return '<span style="opacity:.6">—</span>'
            sign = "+" if v >= 0 else ""
            return f'<span>{sign}{v:.1f}%</span>'

        html_parts.append(
            f'<div class="total-row">'
            f'<span>TOTAL</span>'
            f'<span>{_pct_white(tot_sss)}</span>'
            f'<span>{_pct_white(tot_sst)}</span>'
            f'<span>{fmt_dollar(tot_ns)}</span>'
            f'<span>{tot_txn:,}</span>'
            f'<span>{tot_stores}</span>'
            f'<span>{len(tot_sss_mg)}</span>'
            f'</div>'
        )

        html_parts.append('</div></div>')  # close dm-tree and scroll wrapper
        st.markdown('\n'.join(html_parts), unsafe_allow_html=True)

with tab3:
    # ── Filters ──────────────────────────────────────────────────────────────
    dm_map_t = load_dm_store_map()

    tf1, tf2, tf3 = st.columns([1.4, 1.4, 2.2])
    with tf1:
        st.markdown('<div class="t-label">Market</div>', unsafe_allow_html=True)
        mkt_opts = ["All Markets"] + sorted(dm_map_t["display_market"].dropna().unique().tolist())
        t_market = st.selectbox("Market", mkt_opts, key="t_mkt", label_visibility="collapsed")
    dm_base = dm_map_t if t_market == "All Markets" else dm_map_t[dm_map_t["display_market"] == t_market]
    with tf2:
        st.markdown('<div class="t-label">DM</div>', unsafe_allow_html=True)
        dm_opts = ["All DMs"] + sorted(dm_base["dm_name"].dropna().unique().tolist())
        t_dm = st.selectbox("DM", dm_opts, key="t_dm", label_visibility="collapsed")
    store_base = dm_base if t_dm == "All DMs" else dm_base[dm_base["dm_name"] == t_dm]
    store_opts = {"All Stores": None}
    for _, _r in store_base.sort_values("store_id").iterrows():
        _nm = STORE_NAMES.get(_r["store_id"], _r["store_id"])
        store_opts[_nm] = _r["store_id"]
    with tf3:
        st.markdown('<div class="t-label">Store</div>', unsafe_allow_html=True)
        t_store = st.selectbox("Store", list(store_opts.keys()), key="t_store", label_visibility="collapsed")

    # Resolve which store IDs to include
    _filtered = t_store != "All Stores" or t_market != "All Markets" or t_dm != "All DMs"
    if t_store != "All Stores" and store_opts.get(t_store):
        t_sids = {store_opts[t_store]}
    elif t_market != "All Markets" or t_dm != "All DMs":
        t_sids = set(store_base["store_id"].tolist())
    else:
        t_sids = None  # all comp-eligible stores

    # ── Load + filter data ────────────────────────────────────────────────────
    t_raw = load_all_daily_for_trends()
    if t_sids is not None:
        t_raw = t_raw[t_raw["store_id"].isin(t_sids)].copy()

    if t_raw.empty:
        st.info("No data available for the selected filters.")
    else:
        # Assign week-ending (Sunday) to every row
        t_raw["week_ending"] = (
            t_raw["sale_date"]
            .dt.to_period("W-SUN")
            .apply(lambda p: p.end_time.date())
        )

        # Pre-build comp-eligibility lookup: store_id → first date eligible (or None = always)
        _sm = load_stores_open_dates()
        _comp_from = {}
        for _, _sr in _sm.iterrows():
            _sid2 = _sr["store_id"]
            if pd.isna(_sr["open_date"]):
                _comp_from[_sid2] = None
            else:
                _comp_from[_sid2] = (_sr["open_date"] + pd.Timedelta(days=364)).date()

        # Aggregate daily → weekly by store
        weekly_agg = (
            t_raw.groupby(["store_id", "week_ending"])
            .agg(net_sales=("net_sales", "sum"), transactions=("total_transactions", "sum"))
            .reset_index()
        )
        wk_index = weekly_agg.set_index(["store_id", "week_ending"])

        # Only show weeks with a FULL 7 days of daily data ingested.
        # Without this guard, an in-progress week (e.g. today=Tue, week_ending=Sun)
        # compares 2 days of current sales against a full 7-day prior-year week,
        # producing nonsense like -85.9% on the trend chart.
        _all_dates = pd.Series(t_raw["sale_date"].dt.date.unique())
        weeks_all = []
        for _wk in sorted(weekly_agg["week_ending"].unique()):
            _wk_start = _wk - timedelta(days=6)
            _days_in_wk = _all_dates[(_all_dates >= _wk_start) & (_all_dates <= _wk)].nunique()
            if _days_in_wk >= 7:
                weeks_all.append(_wk)
        min_stores = 1 if t_sids else 3

        trend_rows = []
        for wk in weeks_all:
            prior_wk = wk - timedelta(days=364)
            curr  = weekly_agg[weekly_agg["week_ending"] == wk].set_index("store_id")
            prior = weekly_agg[weekly_agg["week_ending"] == prior_wk].set_index("store_id")
            if curr.empty or prior.empty:
                continue
            both = curr.index.intersection(prior.index)
            # Comp filter only when no specific store/DM selection
            if t_sids is None:
                both = pd.Index([
                    s for s in both
                    if _comp_from.get(s) is None or _comp_from[s] <= wk
                ])
            if len(both) < min_stores:
                continue
            c = curr.loc[both]; p = prior.loc[both]
            valid = both[(p["net_sales"] > 0) & (p["transactions"] > 0)]
            if len(valid) < min_stores:
                continue
            c = c.loc[valid]; p = p.loc[valid]
            sss   = (c["net_sales"].sum()    / p["net_sales"].sum()    - 1) * 100
            sst   = (c["transactions"].sum() / p["transactions"].sum() - 1) * 100
            check = ((1 + sss / 100) / (1 + sst / 100) - 1) * 100
            trend_rows.append({
                "week_ending": wk.strftime("%m/%d/%y"),
                "sss_pct":     round(sss,   2),
                "sst_pct":     round(sst,   2),
                "check_pct":   round(check, 2),
                "comp_stores": len(valid),
            })

        trend_df_t = pd.DataFrame(trend_rows)

        if trend_df_t.empty:
            st.info("Not enough comp data for the selected filters.")
        else:
            # ── Week range toggle ─────────────────────────────────────────────
            if "t_weeks" not in st.session_state:
                st.session_state["t_weeks"] = "13 weeks"
            t_n_opts = {"13 weeks": 13, "26 weeks": 26, "52 weeks": 52, "All": len(trend_df_t)}
            t_active = st.session_state.get("t_weeks", "13 weeks")
            if t_active not in t_n_opts:
                t_active = "13 weeks"

            _bcols = st.columns(len(t_n_opts))
            for _bi, _lbl in enumerate(t_n_opts):
                with _bcols[_bi]:
                    if st.button(_lbl, key=f"t_btn_{_bi}", use_container_width=True,
                                 type="primary" if _lbl == t_active else "secondary"):
                        st.session_state["t_weeks"] = _lbl
                        st.rerun()

            t_n    = t_n_opts[t_active]
            plot_t = trend_df_t.tail(t_n).copy()
            _bf    = 13 if t_n <= 13 else 11 if t_n <= 26 else 9

            def _tbar(col, title):
                _vals = plot_t[col].tolist()
                _clrs = [GREEN if v >= 0 else DANGER for v in _vals]
                _fig  = go.Figure(go.Bar(
                    x=plot_t["week_ending"], y=_vals,
                    marker_color=_clrs,
                    text=[f"{v:+.1f}%" for v in _vals],
                    textposition="outside",
                    textfont=dict(size=_bf, family="Arial", color=TEXT),
                    hovertemplate=f"Week ending %{{x}}<br>{title}: %{{y:+.1f}}%<extra></extra>",
                ))
                _fig.add_hline(y=0, line_color=TEXT, line_width=1.5)
                _fig.update_layout(
                    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                    font=dict(family="Arial", size=12, color=TEXT),
                    dragmode=False,
                    modebar=dict(remove=["zoom2d","pan2d","select2d","lasso2d",
                                         "autoScale2d","resetScale2d","toImage"]),
                    height=300,
                    margin=dict(l=50, r=15, t=45, b=70),
                    title=dict(text=title, font=dict(size=13, color=BLUE), x=0),
                    xaxis=dict(tickangle=-45, tickfont=dict(size=max(_bf-1, 8)),
                               gridcolor=BORDER),
                    yaxis=dict(ticksuffix="%", gridcolor=BORDER, zeroline=False),
                    showlegend=False,
                )
                return _fig

            for _col, _title in [
                ("sss_pct",   f"Same Store Sales % — {t_active}"),
                ("sst_pct",   f"Same Store Transactions % — {t_active}"),
                ("check_pct", f"SS Avg Check % — {t_active}"),
            ]:
                st.markdown('<div class="trend-chart-wrap">', unsafe_allow_html=True)
                st.plotly_chart(_tbar(_col, _title), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            _avg_c = int(plot_t["comp_stores"].mean())
            st.markdown(
                f"<div style='font-size:11px;color:{MUTED};margin-top:2px;'>"
                f"Avg <b>{_avg_c}</b> comp stores/week &nbsp;·&nbsp; 364-day YoY &nbsp;·&nbsp; "
                f"Weeks: {trend_df_t['week_ending'].iloc[0]} – {trend_df_t['week_ending'].iloc[-1]}"
                f"</div>",
                unsafe_allow_html=True,
            )

with tab4:
    # ── Benchmark tab: JMVG vs. BlakeWard peer comparison ─────────────────────
    # Current-week + FYTD plaques (SSS%, SS Ticket%, Avg Daily Bread, Loyalty
    # Sales%) followed by BlakeWard regional breakdown bar charts.
    #
    # Data sources (all Supabase):
    #   • weekly_benchmark (region='TOTAL')  → BW system snapshot + FYTD
    #   • weekly_benchmark (region != 'TOTAL') → BW regional bars
    #   • weekly_sales (per-store)           → JMVG snapshot + FYTD (unweighted
    #                                          .mean() across stores, matching
    #                                          dashboard.py's existing approach)
    #
    # Note: JM Valley FY2026 began 12/29/25. FYTD values are pulled from the
    # fytd_* columns the PDF parser stored, so they already respect JM's
    # fiscal calendar — we don't need to compute the start ourselves.

    FY26_START = date(2025, 12, 29)   # JM Valley FY2026 fiscal year start

    # ── Load RBW benchmark data ──────────────────────────────────────────────
    _bm_df = None
    try:
        _bm_conn, _ = get_conn()
        _bm_df = pd.read_sql_query(
            "SELECT * FROM weekly_benchmark ORDER BY week_ending, region",
            _bm_conn,
        )
        _bm_conn.close()
        if _bm_df.empty:
            _bm_df = None
        else:
            _bm_df["week_ending"] = pd.to_datetime(_bm_df["week_ending"])
    except Exception as _bm_e:
        st.error(f"Could not load weekly_benchmark: {_bm_e}")
        _bm_df = None

    if _bm_df is None:
        st.warning(
            "No RBW benchmark data found in `weekly_benchmark`. "
            "Drop the BlakeWard 'Sales Dashboard Summary (Weekly)' PDF into "
            "`benchmark_pdfs/` and run `py scripts/load_benchmark.py`."
        )
    else:
        # Separate TOTAL row from regional rows
        _bm_total = _bm_df[_bm_df["region"] == "TOTAL"].copy().sort_values("week_ending")
        _bm_reg   = _bm_df[_bm_df["region"] != "TOTAL"].copy()

        # Latest BW week
        _bm_snap_row  = _bm_total.iloc[-1]
        _bm_snap_week = _bm_snap_row["week_ending"]
        _bm_week_str  = _bm_snap_week.strftime("%-m/%-d/%y") if hasattr(_bm_snap_week, "strftime") \
                        else pd.to_datetime(_bm_snap_week).strftime("%m/%d/%y").lstrip("0").replace("/0", "/")
        try:
            _store_cnt = int(_bm_snap_row["store_count"]) if _bm_snap_row["store_count"] else "?"
        except Exception:
            _store_cnt = "?"

        # ── Load JM Valley weekly_sales for the BW snapshot week ──────────────
        _jm_week = pd.DataFrame()
        try:
            _jm_conn, _jm_dialect = get_conn()
            _p = "%s" if _jm_dialect == "postgres" else "?"
            _jm_week = pd.read_sql_query(
                f"SELECT * FROM weekly_sales WHERE week_ending = {_p}",
                _jm_conn,
                params=(_bm_snap_week.strftime("%Y-%m-%d"),),
            )
            _jm_conn.close()
        except Exception as _jm_e:
            st.warning(f"Could not load weekly_sales: {_jm_e}")

        # Identify the SS Ticket column name (schema variant tolerance)
        _tkt_col = "same_store_txn_pct" if "same_store_txn_pct" in _jm_week.columns \
                   else "same_store_ticket_pct" if "same_store_ticket_pct" in _jm_week.columns \
                   else None
        _fytd_tkt_col = "fytd_same_store_txn_pct" if "fytd_same_store_txn_pct" in _jm_week.columns \
                        else "fytd_same_store_ticket" if "fytd_same_store_ticket" in _jm_week.columns \
                        else None

        # ── JM Valley aggregates ──────────────────────────────────────────────
        # Methodology — using sales-weighted aggregation so the system totals
        # match the JM Inspire weekly PDF Grand Total (which is what Pete sees
        # on paper). The prior earlier version used unweighted .mean() which
        # diverged from the PDF (e.g., showed JMVG SSS as -5.2% when the
        # Inspire Grand Total reported -6.1% for week ending 5/10/26).
        #
        # SSS / SS Ticket are YoY % changes. Without prior-year sales stored
        # directly, we reconstruct them per store from current sales and the
        # per-store YoY pct:
        #     implied_prior = curr_net_sales / (1 + pct/100)
        # then aggregate:
        #     system_pct = sum(curr) / sum(implied_prior) - 1
        # This is algebraically equivalent to a sales-weighted average.
        #
        # Loyalty % (and similar $-share metrics) are dollar-weighted directly:
        #     sum(pct_i * sales_i) / sum(sales_i)
        #
        # Avg Daily Bread is a per-store-per-day count; equal-weighted mean
        # across stores is the correct interpretation of "system avg per store"
        # — matches how RBW's Grand Total is computed.

        def _safe_mean(df_, col):
            """Unweighted cross-store mean. Used only for avg_daily_bread."""
            if df_.empty or col is None or col not in df_.columns:
                return None
            try:
                v = df_[col].dropna().mean()
                return float(v) if pd.notna(v) else None
            except Exception:
                return None

        def _weighted_yoy(df_, pct_col, sales_col):
            """
            Sales-weighted YoY % aggregate from per-store rows.
            Reconstructs prior-year sales as net_sales / (1 + pct/100), then
            returns (sum(curr) / sum(implied_prior) - 1) * 100.
            Returns None if no valid comp rows.
            """
            if df_.empty or pct_col is None or pct_col not in df_.columns \
                    or sales_col not in df_.columns:
                return None
            d = df_[[pct_col, sales_col]].dropna()
            d = d[(d[sales_col] > 0)]
            factor = 1.0 + d[pct_col] / 100.0
            d = d[factor > 0]
            if d.empty:
                return None
            implied_prior = (d[sales_col] / (1.0 + d[pct_col] / 100.0)).sum()
            if implied_prior <= 0:
                return None
            return (d[sales_col].sum() / implied_prior - 1.0) * 100.0

        def _weighted_share(df_, pct_col, sales_col="net_sales"):
            """Dollar-weighted average of a $-share %: sum(pct·sales)/sum(sales)."""
            if df_.empty or pct_col is None or pct_col not in df_.columns \
                    or sales_col not in df_.columns:
                return None
            d = df_[[pct_col, sales_col]].dropna()
            d = d[d[sales_col] > 0]
            if d.empty:
                return None
            return float((d[pct_col] * d[sales_col]).sum() / d[sales_col].sum())

        # Current-week aggregates
        _jm_sss = _weighted_yoy(_jm_week, "sss_pct", "net_sales")
        _jm_tkt = _weighted_yoy(_jm_week, _tkt_col, "net_sales")
        _jm_brd = _safe_mean(_jm_week, "avg_daily_bread")
        _jm_loy = _weighted_share(_jm_week, "loyalty_sales_pct", "net_sales")

        # FYTD aggregates — weight by fytd_net_sales when available, else
        # fall back to current-week net_sales
        _fytd_sales_col = "fytd_net_sales" if "fytd_net_sales" in _jm_week.columns \
                          else "net_sales"
        _jm_fytd_sss = _weighted_yoy(_jm_week, "fytd_sss_pct", _fytd_sales_col)
        _jm_fytd_tkt = _weighted_yoy(_jm_week, _fytd_tkt_col, _fytd_sales_col)
        _jm_fytd_brd = _safe_mean(_jm_week, "fytd_avg_daily_bread")
        # weekly_sales has no fytd_loyalty column — leave None

        # ── Header strip ──────────────────────────────────────────────────────
        st.markdown(f"""
        <div style='background:{BLUE};padding:14px 20px;border-radius:8px;margin-bottom:18px;'>
          <span style='color:white;font-family:Arial,sans-serif;font-size:15px;font-weight:700;
                       letter-spacing:1px;'>
            PEER BENCHMARK — JM VALLEY GROUP &nbsp;vs.&nbsp; BLAKEWARD ({_store_cnt} STORES)
          </span>
          <span style='color:rgba(255,255,255,0.65);font-size:12px;margin-left:16px;'>
            Week ending {_bm_week_str}
          </span>
        </div>
        """, unsafe_allow_html=True)

        # ── Plaque builder ────────────────────────────────────────────────────
        def _bm_card(label, jm_val, bm_val, fmt="{:+.1f}%"):
            jm_str = fmt.format(jm_val) if jm_val is not None else "—"
            bm_str = fmt.format(bm_val) if bm_val is not None else "—"
            if jm_val is not None and bm_val is not None:
                delta   = jm_val - bm_val
                d_str   = f"{delta:+.1f}pp"
                d_color = GREEN if delta >= 0 else DANGER
                d_arrow = "▲" if delta >= 0 else "▼"
            else:
                d_str, d_color, d_arrow = "—", MUTED, ""
            return f"""
            <div style='background:#F8F9FB;border:1px solid {BORDER};border-radius:8px;
                        padding:14px 16px;text-align:center;'>
              <div style='font-size:11px;color:{MUTED};font-family:Arial;
                          letter-spacing:.5px;margin-bottom:8px;'>{label}</div>
              <div style='display:flex;justify-content:space-around;align-items:flex-end;'>
                <div>
                  <div style='font-size:10px;color:{BLUE};font-weight:700;font-family:Arial;
                               margin-bottom:3px;'>JM VALLEY</div>
                  <div style='font-size:22px;font-weight:700;color:{TEXT};
                               font-family:Arial;'>{jm_str}</div>
                </div>
                <div style='font-size:18px;color:{MUTED};padding-bottom:4px;'>vs</div>
                <div>
                  <div style='font-size:10px;color:{MUTED};font-weight:700;font-family:Arial;
                               margin-bottom:3px;'>BLAKEWARD</div>
                  <div style='font-size:22px;font-weight:700;color:{MUTED};
                               font-family:Arial;'>{bm_str}</div>
                </div>
              </div>
              <div style='margin-top:8px;font-size:13px;font-weight:700;
                           color:{d_color};font-family:Arial;'>{d_arrow} {d_str} vs peer</div>
            </div>"""

        # ── Section: Current Week ─────────────────────────────────────────────
        st.markdown(
            f"<div style='font-size:12px;font-weight:800;letter-spacing:1.5px;"
            f"text-transform:uppercase;color:{BLUE};border-bottom:2px solid {BLUE};"
            f"padding-bottom:6px;margin:8px 0 14px;'>"
            f"Current Week — JM Valley vs. BlakeWard Total</div>",
            unsafe_allow_html=True,
        )
        _bc1, _bc2, _bc3, _bc4 = st.columns(4)
        with _bc1:
            st.markdown(_bm_card("SAME STORE SALES %", _jm_sss,
                                 float(_bm_snap_row["sss_pct"]) if pd.notna(_bm_snap_row["sss_pct"]) else None),
                        unsafe_allow_html=True)
        with _bc2:
            st.markdown(_bm_card("SS TICKET %", _jm_tkt,
                                 float(_bm_snap_row["ss_ticket_pct"]) if pd.notna(_bm_snap_row["ss_ticket_pct"]) else None),
                        unsafe_allow_html=True)
        with _bc3:
            st.markdown(_bm_card("AVG DAILY BREAD", _jm_brd,
                                 float(_bm_snap_row["avg_daily_bread"]) if pd.notna(_bm_snap_row["avg_daily_bread"]) else None,
                                 fmt="{:.0f}"),
                        unsafe_allow_html=True)
        with _bc4:
            st.markdown(_bm_card("LOYALTY SALES %", _jm_loy,
                                 float(_bm_snap_row["loyalty_sales_pct"]) if pd.notna(_bm_snap_row["loyalty_sales_pct"]) else None),
                        unsafe_allow_html=True)

        # ── Section: FYTD ─────────────────────────────────────────────────────
        st.markdown(
            f"<div style='font-size:12px;font-weight:800;letter-spacing:1.5px;"
            f"text-transform:uppercase;color:{BLUE};border-bottom:2px solid {BLUE};"
            f"padding-bottom:6px;margin:20px 0 6px;'>"
            f"Fiscal Year to Date — JM Valley vs. BlakeWard Total</div>"
            f"<div style='font-size:11px;color:{MUTED};margin-bottom:14px;'>"
            f"JM Valley FY2026 began <b>{FY26_START.strftime('%-m/%-d/%y')}</b>. "
            f"FYTD figures come from the <code>fytd_*</code> columns in each "
            f"source PDF, so JM and BW each respect their own fiscal calendars."
            f"</div>",
            unsafe_allow_html=True,
        )
        _yc1, _yc2, _yc3, _yc4 = st.columns(4)
        with _yc1:
            st.markdown(_bm_card("FYTD SSS %", _jm_fytd_sss,
                                 float(_bm_snap_row["fytd_sss_pct"]) if pd.notna(_bm_snap_row["fytd_sss_pct"]) else None),
                        unsafe_allow_html=True)
        with _yc2:
            st.markdown(_bm_card("FYTD SS TICKET %", _jm_fytd_tkt,
                                 float(_bm_snap_row["fytd_ss_ticket_pct"]) if pd.notna(_bm_snap_row["fytd_ss_ticket_pct"]) else None),
                        unsafe_allow_html=True)
        with _yc3:
            st.markdown(_bm_card("FYTD AVG DAILY BREAD", _jm_fytd_brd,
                                 float(_bm_snap_row["fytd_avg_daily_bread"]) if pd.notna(_bm_snap_row["fytd_avg_daily_bread"]) else None,
                                 fmt="{:.0f}"),
                        unsafe_allow_html=True)
        with _yc4:
            # No FYTD loyalty in either schema — show "—"
            st.markdown(_bm_card("FYTD LOYALTY SALES %", None, None), unsafe_allow_html=True)

        # ── Section: BlakeWard Regional Breakdown — Latest Week ───────────────
        st.markdown(
            f"<div style='font-size:12px;font-weight:800;letter-spacing:1.5px;"
            f"text-transform:uppercase;color:{BLUE};border-bottom:2px solid {BLUE};"
            f"padding-bottom:6px;margin:22px 0 14px;'>"
            f"BlakeWard Regional Breakdown — Latest Week</div>",
            unsafe_allow_html=True,
        )

        _reg_latest = _bm_reg[_bm_reg["week_ending"] == _bm_snap_week] \
                          .sort_values("sss_pct", ascending=False)

        _REGION_COLORS = {
            "FL": "#134A7C", "KC": "#EE3227", "KS": "#D4AF37",
            "MO": "#16a34a", "NC": "#6B21A8", "NY": "#0ea5e9", "SC": "#f97316",
        }

        if _reg_latest.empty:
            st.info(f"No regional data available for week ending {_bm_week_str}.")
        else:
            _rb1, _rb2 = st.columns(2)

            with _rb1:
                _fig_rb1 = go.Figure()
                _bar_colors = [_REGION_COLORS.get(r, MUTED) for r in _reg_latest["region"]]
                _fig_rb1.add_trace(go.Bar(
                    x=_reg_latest["region"],
                    y=_reg_latest["sss_pct"],
                    marker_color=_bar_colors,
                    text=[f"{v:+.1f}%" for v in _reg_latest["sss_pct"]],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>SSS: %{y:+.1f}%<extra></extra>",
                ))
                if _jm_sss is not None:
                    _fig_rb1.add_hline(
                        y=_jm_sss, line_color=BLUE, line_width=2, line_dash="dot",
                        annotation_text=f"JM Valley {_jm_sss:+.1f}%",
                        annotation_position="top right",
                        annotation_font=dict(color=BLUE, size=11),
                    )
                _fig_rb1.add_hline(
                    y=float(_bm_snap_row["sss_pct"]),
                    line_color=MUTED, line_width=1.5, line_dash="dash",
                    annotation_text=f"BW Avg {float(_bm_snap_row['sss_pct']):+.1f}%",
                    annotation_position="bottom right",
                    annotation_font=dict(color=MUTED, size=10),
                )
                _fig_rb1.update_layout(
                    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                    font=dict(family="Arial", size=12, color=TEXT),
                    height=340,
                    title=dict(text="SSS % by BlakeWard Region",
                               font=dict(size=14, color=TEXT, family="Arial")),
                    margin=dict(l=40, r=20, t=55, b=40),
                    showlegend=False,
                    yaxis=dict(ticksuffix="%", zeroline=True, zerolinecolor=MUTED,
                               gridcolor=BORDER),
                    xaxis=dict(gridcolor=BORDER),
                )
                st.plotly_chart(_fig_rb1, use_container_width=True,
                                config={"responsive": True, "displayModeBar": False})

            with _rb2:
                _fig_rb2 = go.Figure()
                _reg_tkt = _reg_latest.sort_values("ss_ticket_pct", ascending=False)
                _bar_colors2 = [_REGION_COLORS.get(r, MUTED) for r in _reg_tkt["region"]]
                _fig_rb2.add_trace(go.Bar(
                    x=_reg_tkt["region"],
                    y=_reg_tkt["ss_ticket_pct"],
                    marker_color=_bar_colors2,
                    text=[f"{v:+.1f}%" for v in _reg_tkt["ss_ticket_pct"]],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>Ticket: %{y:+.1f}%<extra></extra>",
                ))
                if _jm_tkt is not None:
                    _fig_rb2.add_hline(
                        y=_jm_tkt, line_color=BLUE, line_width=2, line_dash="dot",
                        annotation_text=f"JM Valley {_jm_tkt:+.1f}%",
                        annotation_position="top right",
                        annotation_font=dict(color=BLUE, size=11),
                    )
                _fig_rb2.add_hline(
                    y=float(_bm_snap_row["ss_ticket_pct"]),
                    line_color=MUTED, line_width=1.5, line_dash="dash",
                    annotation_text=f"BW Avg {float(_bm_snap_row['ss_ticket_pct']):+.1f}%",
                    annotation_position="bottom right",
                    annotation_font=dict(color=MUTED, size=10),
                )
                _fig_rb2.update_layout(
                    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                    font=dict(family="Arial", size=12, color=TEXT),
                    height=340,
                    title=dict(text="SS Ticket % by BlakeWard Region",
                               font=dict(size=14, color=TEXT, family="Arial")),
                    margin=dict(l=40, r=20, t=55, b=40),
                    showlegend=False,
                    yaxis=dict(ticksuffix="%", zeroline=True, zerolinecolor=MUTED,
                               gridcolor=BORDER),
                    xaxis=dict(gridcolor=BORDER),
                )
                st.plotly_chart(_fig_rb2, use_container_width=True,
                                config={"responsive": True, "displayModeBar": False})

        # ── Section: BlakeWard Regional Breakdown — FYTD ──────────────────────
        st.markdown(
            f"<div style='font-size:12px;font-weight:800;letter-spacing:1.5px;"
            f"text-transform:uppercase;color:{BLUE};border-bottom:2px solid {BLUE};"
            f"padding-bottom:6px;margin:22px 0 14px;'>"
            f"BlakeWard Regional Breakdown — FYTD</div>",
            unsafe_allow_html=True,
        )

        # _reg_latest already pinned to the latest BW week; the fytd_* columns
        # on those rows are the cumulative fiscal-YTD values, so we just sort
        # and chart them.
        if _reg_latest.empty:
            st.info(f"No regional FYTD data for week ending {_bm_week_str}.")
        else:
            _reg_fytd_sss = _reg_latest.sort_values("fytd_sss_pct", ascending=False)
            _reg_fytd_tkt = _reg_latest.sort_values("fytd_ss_ticket_pct", ascending=False)
            _bw_fytd_sss = float(_bm_snap_row["fytd_sss_pct"]) if pd.notna(_bm_snap_row["fytd_sss_pct"]) else None
            _bw_fytd_tkt = float(_bm_snap_row["fytd_ss_ticket_pct"]) if pd.notna(_bm_snap_row["fytd_ss_ticket_pct"]) else None

            _yb1, _yb2 = st.columns(2)

            with _yb1:
                _fig_yb1 = go.Figure()
                _bar_colors_y1 = [_REGION_COLORS.get(r, MUTED) for r in _reg_fytd_sss["region"]]
                _fig_yb1.add_trace(go.Bar(
                    x=_reg_fytd_sss["region"],
                    y=_reg_fytd_sss["fytd_sss_pct"],
                    marker_color=_bar_colors_y1,
                    text=[f"{v:+.1f}%" if pd.notna(v) else "—"
                          for v in _reg_fytd_sss["fytd_sss_pct"]],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>FYTD SSS: %{y:+.1f}%<extra></extra>",
                ))
                if _jm_fytd_sss is not None:
                    _fig_yb1.add_hline(
                        y=_jm_fytd_sss, line_color=BLUE, line_width=2, line_dash="dot",
                        annotation_text=f"JM Valley {_jm_fytd_sss:+.1f}%",
                        annotation_position="top right",
                        annotation_font=dict(color=BLUE, size=11),
                    )
                if _bw_fytd_sss is not None:
                    _fig_yb1.add_hline(
                        y=_bw_fytd_sss, line_color=MUTED, line_width=1.5, line_dash="dash",
                        annotation_text=f"BW Avg {_bw_fytd_sss:+.1f}%",
                        annotation_position="bottom right",
                        annotation_font=dict(color=MUTED, size=10),
                    )
                _fig_yb1.update_layout(
                    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                    font=dict(family="Arial", size=12, color=TEXT),
                    height=340,
                    title=dict(text="FYTD SSS % by BlakeWard Region",
                               font=dict(size=14, color=TEXT, family="Arial")),
                    margin=dict(l=40, r=20, t=55, b=40),
                    showlegend=False,
                    yaxis=dict(ticksuffix="%", zeroline=True, zerolinecolor=MUTED,
                               gridcolor=BORDER),
                    xaxis=dict(gridcolor=BORDER),
                )
                st.plotly_chart(_fig_yb1, use_container_width=True,
                                config={"responsive": True, "displayModeBar": False})

            with _yb2:
                _fig_yb2 = go.Figure()
                _bar_colors_y2 = [_REGION_COLORS.get(r, MUTED) for r in _reg_fytd_tkt["region"]]
                _fig_yb2.add_trace(go.Bar(
                    x=_reg_fytd_tkt["region"],
                    y=_reg_fytd_tkt["fytd_ss_ticket_pct"],
                    marker_color=_bar_colors_y2,
                    text=[f"{v:+.1f}%" if pd.notna(v) else "—"
                          for v in _reg_fytd_tkt["fytd_ss_ticket_pct"]],
                    textposition="outside",
                    hovertemplate="<b>%{x}</b><br>FYTD Ticket: %{y:+.1f}%<extra></extra>",
                ))
                if _jm_fytd_tkt is not None:
                    _fig_yb2.add_hline(
                        y=_jm_fytd_tkt, line_color=BLUE, line_width=2, line_dash="dot",
                        annotation_text=f"JM Valley {_jm_fytd_tkt:+.1f}%",
                        annotation_position="top right",
                        annotation_font=dict(color=BLUE, size=11),
                    )
                if _bw_fytd_tkt is not None:
                    _fig_yb2.add_hline(
                        y=_bw_fytd_tkt, line_color=MUTED, line_width=1.5, line_dash="dash",
                        annotation_text=f"BW Avg {_bw_fytd_tkt:+.1f}%",
                        annotation_position="bottom right",
                        annotation_font=dict(color=MUTED, size=10),
                    )
                _fig_yb2.update_layout(
                    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
                    font=dict(family="Arial", size=12, color=TEXT),
                    height=340,
                    title=dict(text="FYTD SS Ticket % by BlakeWard Region",
                               font=dict(size=14, color=TEXT, family="Arial")),
                    margin=dict(l=40, r=20, t=55, b=40),
                    showlegend=False,
                    yaxis=dict(ticksuffix="%", zeroline=True, zerolinecolor=MUTED,
                               gridcolor=BORDER),
                    xaxis=dict(gridcolor=BORDER),
                )
                st.plotly_chart(_fig_yb2, use_container_width=True,
                                config={"responsive": True, "displayModeBar": False})

        st.markdown(
            f"<div style='font-family:Arial,sans-serif;font-size:11px;color:{MUTED};"
            f"margin-top:8px;line-height:1.5;'>"
            f"JM Valley SSS / SS Ticket = sales-weighted aggregate "
            f"(implied prior = curr ÷ (1 + pct/100); system pct = Σcurr ÷ Σimplied − 1). "
            f"Loyalty % = dollar-weighted (Σ pct·sales ÷ Σ sales). "
            f"Avg Daily Bread = cross-store mean. "
            f"Source: <code>weekly_sales</code> for week ending {_bm_week_str}. "
            f"BlakeWard = system Grand Total from <code>weekly_benchmark</code>."
            f"</div>",
            unsafe_allow_html=True,
        )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;font-size:11px;color:{MUTED};margin-top:24px;
            border-top:1px solid {BORDER};padding-top:12px;">
  Data through {max_date.strftime('%B %d, %Y')} · JM Valley Group · Vantedge Partners
</div>
""", unsafe_allow_html=True)
