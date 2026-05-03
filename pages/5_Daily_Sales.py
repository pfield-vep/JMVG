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

tab1, tab2 = st.tabs(["Overview", "By District Manager"])
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
    # _SR_COL_W = sub-region label (150px) + legend column (72px)
    # Chart margin.l is set to this combined width so bars align with day columns.
    _SR_COL_W = 222  # px  (150 label + 72 legend)
    PLOTLY_LAYOUT = dict(
        plot_bgcolor=WHITE, paper_bgcolor=WHITE,
        font=dict(family="Arial, sans-serif", size=12, color=TEXT),
        dragmode=False,
        modebar=dict(remove=["select2d","lasso2d","zoom2d","pan2d",
                              "autoScale2d","resetScale2d","toImage","sendDataToCloud"]),
        margin=dict(l=_SR_COL_W, r=20, t=40, b=80),
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

    # On mobile, reduce the 222px left margin so the chart fills the screen width
    st.markdown("""
<div id="sss-mobile-fix"></div>
<script>
(function() {
  if (window.innerWidth > 768) return;
  var attempts = 0;
  function fix() {
    if (attempts++ > 30) return;
    var plots = document.querySelectorAll('.js-plotly-plot');
    for (var i = 0; i < plots.length; i++) {
      try {
        var t = (plots[i]._fullLayout || {}).title || {};
        var txt = (t.text || t || '').toString();
        if (txt.indexOf('Daily SSS') !== -1) {
          Plotly.relayout(plots[i], {'margin.l': 10, 'margin.r': 8});
          return;
        }
      } catch(e) {}
    }
    setTimeout(fix, 300);
  }
  setTimeout(fix, 400);
})();
</script>
""", unsafe_allow_html=True)

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

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;font-size:11px;color:{MUTED};margin-top:24px;
            border-top:1px solid {BORDER};padding-top:12px;">
  Data through {max_date.strftime('%B %d, %Y')} · JM Valley Group · Vantedge Partners
</div>
""", unsafe_allow_html=True)
