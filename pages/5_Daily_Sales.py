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
SAN_DIEGO_IDS = ['20071','20091','20171','20177','20291','20292','20300']

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
    if store_id in SAN_DIEGO_IDS:
        return "San Diego"
    return "LA / SoCal"

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
def load_comp_eligible_stores(period_start_str: str) -> set:
    """Return store_ids eligible as comps: open_date + 364 days <= period_start."""
    conn, dialect = get_conn()
    p = "%s" if dialect == "postgres" else "?"
    try:
        stores = pd.read_sql_query(
            f"SELECT store_id, open_date FROM stores WHERE open_date IS NOT NULL",
            conn
        )
        conn.close()
        stores["open_date"] = pd.to_datetime(stores["open_date"], errors="coerce")
        cutoff = pd.to_datetime(period_start_str) - pd.Timedelta(days=364)
        return set(stores[stores["open_date"] <= cutoff]["store_id"].tolist())
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
<style>body {{
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

  /* Section headers */
  .section-title {{
    font-size: 13px; font-weight: 800; letter-spacing: 1.5px;
    text-transform: uppercase; color: {BLUE};
    border-bottom: 2px solid {BLUE};
    padding-bottom: 6px; margin: 18px 0 12px;
  }}

  /* Market table */
  .mkt-table {{ width:100%; border-collapse: collapse; font-size:13px; }}
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

# ── Header ─────────────────────────────────────────────────────────────────────
_logo_html = f'<img src="{_LOGO}" style="height:44px;width:auto;flex-shrink:0;"/>' if _LOGO else ""
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
</div>
""", unsafe_allow_html=True)

# ── Date controls ──────────────────────────────────────────────────────────────
min_date, max_date = get_date_range()
today = max_date  # most recent data date

# Default to last 7 days
default_end   = today
default_start = today - timedelta(days=6)

ctrl1, ctrl2, ctrl3, ctrl4 = st.columns([1.5, 1.2, 1.2, 1.2])

with ctrl1:
    preset = st.selectbox(
        "Period",
        ["Last 7 Days", "Last 14 Days", "Last 28 Days",
         "Last Week (Mon–Sun)", "Month to Date", "Custom"],
        index=0,
        label_visibility="collapsed",
    )

# Compute dates from preset
if preset == "Last 7 Days":
    end_date   = today
    start_date = today - timedelta(days=6)
elif preset == "Last 14 Days":
    end_date   = today
    start_date = today - timedelta(days=13)
elif preset == "Last 28 Days":
    end_date   = today
    start_date = today - timedelta(days=27)
elif preset == "Last Week (Mon–Sun)":
    # Last complete Mon–Sun
    dow = today.weekday()  # 0=Mon
    last_sun  = today - timedelta(days=dow+1)
    last_mon  = last_sun - timedelta(days=6)
    end_date   = last_sun
    start_date = last_mon
elif preset == "Month to Date":
    end_date   = today
    start_date = today.replace(day=1)
else:
    end_date   = default_end
    start_date = default_start

with ctrl2:
    if preset == "Custom":
        start_date = st.date_input("From", value=default_start,
                                   min_value=min_date, max_value=max_date)
    else:
        st.markdown(f"<div style='padding-top:6px;font-size:13px;color:{MUTED};'>"
                    f"<b>From:</b> {start_date.strftime('%b %d, %Y')}</div>",
                    unsafe_allow_html=True)

with ctrl3:
    if preset == "Custom":
        end_date = st.date_input("To", value=default_end,
                                 min_value=min_date, max_value=max_date)
    else:
        st.markdown(f"<div style='padding-top:6px;font-size:13px;color:{MUTED};'>"
                    f"<b>To:</b> {end_date.strftime('%b %d, %Y')}</div>",
                    unsafe_allow_html=True)

with ctrl4:
    mkt_filter = st.selectbox(
        "Market", ["All Markets", "LA / SoCal", "San Diego"],
        label_visibility="collapsed",
    )

# Prior period = same date range 364 days back (preserves day of week)
delta_days   = (end_date - start_date).days
prior_end    = start_date - timedelta(days=364)
prior_start  = prior_end - timedelta(days=delta_days)

st.markdown(
    f"<div style='font-size:11px;color:{MUTED};margin-bottom:8px;'>"
    f"Comparing <b>{start_date.strftime('%b %d')} – {end_date.strftime('%b %d, %Y')}</b>"
    f" vs prior year <b>{prior_start.strftime('%b %d')} – {prior_end.strftime('%b %d, %Y')}</b>"
    f"&nbsp;(364 days back, same day of week)"
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
    curr_comp = curr[curr["store_id"].isin(comp_eligible)] if comp_eligible else curr
    prior_comp = prior[prior["store_id"].isin(comp_eligible)] if comp_eligible else prior

    c_agg = curr_comp.groupby("store_id").agg(
        net_sales=("net_sales","sum"),
        txn=("total_transactions","sum"),
    ).reset_index()
    p_agg = prior_comp.groupby("store_id").agg(
        net_sales_prior=("net_sales","sum"),
        txn_prior=("total_transactions","sum"),
    ).reset_index()

    # Comp stores = eligible + in both periods with non-zero prior sales
    merged = c_agg.merge(p_agg, on="store_id", how="inner")
    merged = merged[merged["net_sales_prior"] > 0]

    comp_count     = len(merged)
    curr_sales     = merged["net_sales"].sum()
    prior_sales    = merged["net_sales_prior"].sum()
    curr_txn       = merged["txn"].sum()
    prior_txn      = merged["txn_prior"].sum()

    sss = (curr_sales - prior_sales) / prior_sales * 100 if prior_sales else None
    sst = (curr_txn  - prior_txn)  / prior_txn  * 100 if prior_txn  else None

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

# ── KPI Cards ──────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Consolidated Performance</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)

cards = [
    (k1, "Net Sales", fmt_dollar(totals["net_sales"]),
     kpi_delta_html((totals["net_sales"]-totals["prior_sales"])/totals["prior_sales"]*100
                    if totals["prior_sales"] else None), "kpi-card"),
    (k2, "Same Store Sales", fmt_pct(totals["sss_pct"]),
     f'<span style="font-size:11px;color:{MUTED};">{totals["comp_count"]} comp stores</span>',
     "kpi-card kpi-card-blue"),
    (k3, "Same Store Txns", fmt_pct(totals["sst_pct"]),
     f'<span style="font-size:11px;color:{MUTED};">{totals["comp_count"]} comp stores</span>',
     "kpi-card kpi-card-blue"),
    (k4, "Avg Ticket", f"${totals['avg_ticket']:.2f}" if totals["avg_ticket"] else "—",
     f'{int(totals["transactions"]):,} transactions', "kpi-card kpi-card-green"),
    (k5, "Online Mix", f"{totals['online_pct']:.1f}%" if totals["online_pct"] else "—",
     f'3P: {totals["thirdp_pct"]:.1f}%' if totals["thirdp_pct"] else "", "kpi-card kpi-card-gold"),
    (k6, "Lunch Mix", f"{totals['lunch_pct']:.1f}%" if totals["lunch_pct"] else "—",
     f'Dinner: {totals["dinner_pct"]:.1f}%' if totals["dinner_pct"] else "", "kpi-card"),
]

for col, label, val, delta, cls in cards:
    col.markdown(f"""
    <div class="{cls}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{val}</div>
      <div class="kpi-delta">{delta}</div>
    </div>""", unsafe_allow_html=True)

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
    return (
        f"<tr>"
        f"<td>{r['market']}</td>"
        f"<td>{r['stores']}</td>"
        f"<td>{fmt_dollar(r['net_sales'])}</td>"
        f"<td class='{sss_cls}'>{fmt_pct(r['sss_pct'])}</td>"
        f"<td class='{sst_cls}'>{fmt_pct(r['sst_pct'])}</td>"
        f"<td>{avg_t}</td>"
        f"<td>{online}</td>"
        f"<td>{thirdp}</td>"
        f"<td>{r['comp_count']}</td>"
        f"</tr>"
    )

rows_html = "".join(_row_html(r, r["market"] == "TOTAL") for r in mkt_rows)
st.markdown(f"""
<table class="mkt-table">
  <thead><tr>
    <th>Market</th><th style="text-align:center">Stores</th>
    <th>Net Sales</th><th>SSS%</th><th>SST%</th>
    <th>Avg Ticket</th><th>Online%</th><th>3P%</th>
    <th style="text-align:center">Comps</th>
  </tr></thead>
  <tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

# ── Charts row ─────────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">Sales Mix</div>', unsafe_allow_html=True)

ch1, ch2 = st.columns(2)

PLOTLY_LAYOUT = dict(
    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
    font=dict(family="Arial, sans-serif", size=12, color=TEXT),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(bgcolor=WHITE, bordercolor=BORDER, borderwidth=1,
                font=dict(size=11), orientation="h",
                yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
)

# Daypart mix
with ch1:
    dp_labels  = ["Morning", "Lunch", "Dinner"]
    dp_values  = [
        totals["morning_sales"] or 0,
        totals["lunch_sales"]   or 0,
        totals["dinner_sales"]  or 0,
    ]
    dp_colors  = [GOLD, RED, BLUE]

    # Daily trend by daypart
    daily_dp = curr_df.groupby("sale_date").agg(
        morning=("morning_sales","sum"),
        lunch=("lunch_sales","sum"),
        dinner=("dinner_sales","sum"),
    ).reset_index().sort_values("sale_date")

    fig_dp = go.Figure()
    for col, color, label in [
        ("morning", GOLD, "Morning"),
        ("lunch",   RED,  "Lunch"),
        ("dinner",  BLUE, "Dinner"),
    ]:
        fig_dp.add_trace(go.Bar(
            x=daily_dp["sale_date"],
            y=daily_dp[col],
            name=label,
            marker_color=color,
        ))
    fig_dp.update_layout(
        **PLOTLY_LAYOUT,
        barmode="stack",
        title=dict(text="Daily Sales by Daypart", font=dict(size=13, color=BLUE), x=0),
        xaxis=dict(tickformat="%b %d", gridcolor="#E5E7EB"),
        yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor="#E5E7EB"),
    )
    st.plotly_chart(fig_dp, use_container_width=True)

# Channel mix
with ch2:
    daily_ch = curr_df.groupby("sale_date").agg(
        walkin=("walkin_sales","sum"),
        online=("online_sales","sum"),
        thirdp=("third_party_sales","sum"),
    ).reset_index().sort_values("sale_date")

    fig_ch = go.Figure()
    for col, color, label in [
        ("walkin", BLUE,  "Walk-In"),
        ("online", RED,   "Online"),
        ("thirdp", GOLD,  "3rd Party"),
    ]:
        fig_ch.add_trace(go.Bar(
            x=daily_ch["sale_date"],
            y=daily_ch[col],
            name=label,
            marker_color=color,
        ))
    fig_ch.update_layout(
        **PLOTLY_LAYOUT,
        barmode="stack",
        title=dict(text="Daily Sales by Channel", font=dict(size=13, color=BLUE), x=0),
        xaxis=dict(tickformat="%b %d", gridcolor="#E5E7EB"),
        yaxis=dict(tickprefix="$", tickformat=",.0f", gridcolor="#E5E7EB"),
    )
    st.plotly_chart(fig_ch, use_container_width=True)

# ── SSS Trend Chart ────────────────────────────────────────────────────────────
st.markdown('<div class="section-title">SSS% Trend (Rolling 7-Day)</div>', unsafe_allow_html=True)

# Build daily SSS: for each day in curr period, compare to same day 364 days back
curr_daily = curr_df.groupby("sale_date")["net_sales"].sum().reset_index()
curr_daily.columns = ["sale_date","curr_sales"]
curr_daily["prior_date"] = curr_daily["sale_date"] - pd.Timedelta(days=364)

prior_daily = prior_df.groupby("sale_date")["net_sales"].sum().reset_index()
prior_daily.columns = ["prior_date","prior_sales"]

sss_trend = curr_daily.merge(prior_daily, on="prior_date", how="left")
sss_trend = sss_trend[sss_trend["prior_sales"] > 0].copy()
sss_trend["sss_pct"] = (sss_trend["curr_sales"] - sss_trend["prior_sales"]) / sss_trend["prior_sales"] * 100
sss_trend["sss_7d"]  = sss_trend["sss_pct"].rolling(7, min_periods=1).mean()

fig_sss = go.Figure()
fig_sss.add_trace(go.Bar(
    x=sss_trend["sale_date"], y=sss_trend["sss_pct"],
    name="Daily SSS%",
    marker_color=[GREEN if v >= 0 else DANGER for v in sss_trend["sss_pct"]],
    opacity=0.5,
))
fig_sss.add_trace(go.Scatter(
    x=sss_trend["sale_date"], y=sss_trend["sss_7d"],
    name="7-Day Avg", line=dict(color=BLUE, width=2),
))
fig_sss.add_hline(y=0, line_color=MUTED, line_width=1)
fig_sss.update_layout(
    **PLOTLY_LAYOUT,
    title=dict(text="Same Store Sales % vs. Prior Year", font=dict(size=13, color=BLUE), x=0),
    xaxis=dict(tickformat="%b %d", gridcolor="#E5E7EB"),
    yaxis=dict(ticksuffix="%", gridcolor="#E5E7EB"),
    height=280,
)
st.plotly_chart(fig_sss, use_container_width=True)

# ── Store Detail Table ─────────────────────────────────────────────────────────
with st.expander("Store Detail", expanded=False):
    store_curr = curr_df.groupby(["store_id","store_name","market"]).agg(
        net_sales=("net_sales","sum"),
        transactions=("total_transactions","sum"),
        walkin=("walkin_sales","sum"),
        online=("online_sales","sum"),
        thirdp=("third_party_sales","sum"),
        lunch=("lunch_sales","sum"),
        dinner=("dinner_sales","sum"),
        morning=("morning_sales","sum"),
    ).reset_index()

    store_prior = prior_df.groupby("store_id").agg(
        net_sales_prior=("net_sales","sum"),
        txn_prior=("total_transactions","sum"),
    ).reset_index()

    store_all = store_curr.merge(store_prior, on="store_id", how="left")
    store_all["sss_pct"] = (
        (store_all["net_sales"] - store_all["net_sales_prior"])
        / store_all["net_sales_prior"] * 100
    ).where(store_all["net_sales_prior"] > 0)
    store_all["sst_pct"] = (
        (store_all["transactions"] - store_all["txn_prior"])
        / store_all["txn_prior"] * 100
    ).where(store_all["txn_prior"] > 0)
    store_all["avg_ticket"] = store_all["net_sales"] / store_all["transactions"].replace(0, float("nan"))
    store_all["online_pct"] = store_all["online"] / store_all["net_sales"].replace(0, float("nan")) * 100

    store_all = store_all.sort_values(["market","net_sales"], ascending=[True,False])

    def store_row(r):
        sss_c = pct_class(r["sss_pct"])
        sst_c = pct_class(r["sst_pct"])
        sss   = fmt_pct(r["sss_pct"]) if pd.notna(r.get("sss_pct")) else "—"
        sst   = fmt_pct(r["sst_pct"]) if pd.notna(r.get("sst_pct")) else "—"
        tkt   = f"${r['avg_ticket']:.2f}" if pd.notna(r.get("avg_ticket")) else "—"
        onl   = f"{r['online_pct']:.1f}%" if pd.notna(r.get("online_pct")) else "—"
        return (
            f"<tr>"
            f"<td>{r['store_name']}</td>"
            f"<td>{r['market']}</td>"
            f"<td>{fmt_dollar(r['net_sales'])}</td>"
            f"<td class='{sss_c}'>{sss}</td>"
            f"<td class='{sst_c}'>{sst}</td>"
            f"<td>{tkt}</td>"
            f"<td>{onl}</td>"
            f"</tr>"
        )

    store_rows = "".join(store_row(r) for _, r in store_all.iterrows())
    st.markdown(f"""
    <table class="store-table">
      <thead><tr>
        <th>Store</th><th>Market</th>
        <th>Net Sales</th><th>SSS%</th><th>SST%</th>
        <th>Avg Ticket</th><th>Online%</th>
      </tr></thead>
      <tbody>{store_rows}</tbody>
    </table>
    """, unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;font-size:11px;color:{MUTED};margin-top:24px;
            border-top:1px solid {BORDER};padding-top:12px;">
  Data through {max_date.strftime('%B %d, %Y')} · JM Valley Group · Vantedge Partners
</div>
""", unsafe_allow_html=True)
