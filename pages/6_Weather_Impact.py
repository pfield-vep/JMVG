"""
pages/6_Weather_Impact.py
JM Valley Group — Weather Impact on Daily Sales
Correlates same-store-sales % change Y/Y with weather delta Y/Y
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import os

st.set_page_config(
    page_title="Weather Impact | JM Valley Group",
    page_icon="🌤️",
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

# ── Market → store mapping ─────────────────────────────────────────────────────
SAN_DIEGO_IDS = ['20071','20091','20171','20177','20291','20292','20300']
CA_ONLY_STORES = None  # Tampa (20026) excluded — not owned by JM Valley Group

def get_market(store_id):
    if store_id in SAN_DIEGO_IDS: return "San Diego"
    if store_id == '20026':       return None   # Tampa — exclude
    return "Los Angeles"

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

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  /* No horizontal page scroll on mobile */
  html, body, .stApp {{ overflow-x: hidden !important; max-width: 100vw !important; }}
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

  .kpi-card {{
    background: {WHITE}; border: 1px solid {BORDER};
    border-top: 4px solid {RED}; border-radius: 8px;
    padding: 14px 16px 12px; margin-bottom: 8px;
    height: 110px; display: flex; flex-direction: column;
    justify-content: space-between; box-sizing: border-box;
  }}
  .kpi-card-blue  {{ border-top-color: {BLUE}  !important; }}
  .kpi-card-green {{ border-top-color: {GREEN} !important; }}
  .kpi-card-gold  {{ border-top-color: {GOLD}  !important; }}
  .kpi-label {{
    font-size: 11px; font-weight: 700; letter-spacing: 1.2px;
    text-transform: uppercase; color: {MUTED};
  }}
  .kpi-value {{ font-size: 26px; font-weight: 700; color: {TEXT}; line-height: 1.2; }}
  .kpi-sub   {{ font-size: 11px; color: {MUTED}; }}

  .section-title {{
    font-size: 13px; font-weight: 800; letter-spacing: 1.5px;
    text-transform: uppercase; color: {BLUE};
    border-bottom: 2px solid {BLUE};
    padding-bottom: 6px; margin: 18px 0 12px;
  }}

  .insight-box {{
    background: {LIGHT}; border-left: 4px solid {BLUE};
    border-radius: 0 8px 8px 0; padding: 12px 16px;
    font-size: 13px; color: {TEXT}; margin-bottom: 12px;
  }}
  .insight-box b {{ color: {BLUE}; }}

  .bucket-table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  .bucket-table th {{
    background:{BLUE}; color:white; padding:8px 14px;
    font-size:11px; font-weight:700; letter-spacing:1px;
    text-transform:uppercase; text-align:right;
  }}
  .bucket-table th:first-child {{ text-align:left; }}
  .bucket-table td {{
    padding:8px 14px; border-bottom:1px solid {BORDER}; text-align:right;
  }}
  .bucket-table td:first-child {{ text-align:left; font-weight:600; }}
  .bucket-table tr:last-child {{ font-weight:700; background:{LIGHT}; }}
  .pos {{ color:{GREEN}; font-weight:700; }}
  .neg {{ color:{DANGER}; font-weight:700; }}
</style>
""", unsafe_allow_html=True)

# ── Logo / header ──────────────────────────────────────────────────────────────
try:
    import re as _re
    _bs_src = open(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                "pages", "2_Balanced_Scorecard.py")).read()
    _m = _re.search(r'_LOGO\s*=\s*"(data:image[^"]+)"', _bs_src)
    _LOGO = _m.group(1) if _m else None
except Exception:
    _LOGO = None

_logo_html = f'<img src="{_LOGO}" style="height:44px;width:auto;flex-shrink:0;"/>' if _LOGO else ""
st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;
            background:{BLUE};border-radius:10px;padding:12px 20px;margin-bottom:16px;">
  {_logo_html}
  <div style="font-size:13px;font-weight:800;color:{WHITE};
              letter-spacing:2px;text-transform:uppercase;">
    Weather Impact Analysis
  </div>
</div>
""", unsafe_allow_html=True)

# ── Controls ───────────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns([1.5, 1.5, 2])
with c1:
    lookback = st.selectbox("Period",
        ["Last 90 Days", "Last 180 Days", "Last 365 Days", "All Available"],
        index=1, label_visibility="collapsed")
with c2:
    mkt_opts = ["All Markets", "Los Angeles", "San Diego"]
    mkt_sel  = st.selectbox("Market", mkt_opts, label_visibility="collapsed")
with c3:
    st.markdown(
        f"<div style='padding-top:8px;font-size:12px;color:{MUTED};'>"
        "SSS% = (daily net sales vs. same day 364 days prior) · "
        "Weather delta = today's temp/rain vs. same day 364 days prior"
        "</div>", unsafe_allow_html=True)

# ── Load data ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_correlation_data():
    conn, dialect = get_conn()
    sales = pd.read_sql_query(
        "SELECT sale_date, store_id, net_sales, total_transactions "
        "FROM daily_sales WHERE net_sales IS NOT NULL AND net_sales > 0 "
        "ORDER BY sale_date", conn)
    try:
        weather = pd.read_sql_query(
            "SELECT date, store_id, temp_max_f, precip_in, is_rainy, is_cold, "
            "temp_spread_f, lunch_temp_f, lunch_precip_in, lunch_is_rainy, "
            "dinner_temp_f, dinner_precip_in, dinner_is_rainy "
            "FROM store_daily_weather ORDER BY date", conn)
    except Exception:
        # Fall back to market-level daily_weather if store table not ready
        weather = pd.read_sql_query(
            "SELECT date, market, temp_max_f, NULL AS temp_min_f, "
            "temp_max_f AS avg_temp_f, precip_in, is_rainy, is_cold, "
            "NULL AS temp_spread_f, NULL AS lunch_temp_f, NULL AS lunch_precip_in, "
            "NULL AS lunch_is_rainy, NULL AS dinner_temp_f, NULL AS dinner_precip_in, "
            "NULL AS dinner_is_rainy FROM daily_weather ORDER BY date", conn)
        weather["store_id"] = None
    conn.close()
    sales["sale_date"] = pd.to_datetime(sales["sale_date"])
    weather["date"]    = pd.to_datetime(weather["date"])
    sales["store_id"]  = sales["store_id"].astype(str)
    weather["store_id"] = weather["store_id"].astype(str)
    sales["market"]    = sales["store_id"].apply(get_market)
    sales = sales[sales["market"].notna()]
    return sales, weather

sales_raw, weather_raw = load_correlation_data()

if sales_raw.empty:
    st.warning("No daily sales data found. Run the backfill script first.")
    st.stop()
if weather_raw.empty:
    st.warning("No weather data found. Run `py scripts/fetch_weather.py` to populate it.")
    st.stop()

# ── Filter by lookback ─────────────────────────────────────────────────────────
max_date = sales_raw["sale_date"].max()
if lookback == "Last 90 Days":
    cutoff = max_date - pd.Timedelta(days=90)
elif lookback == "Last 180 Days":
    cutoff = max_date - pd.Timedelta(days=180)
elif lookback == "Last 365 Days":
    cutoff = max_date - pd.Timedelta(days=365)
else:
    cutoff = sales_raw["sale_date"].min()

sales_curr = sales_raw[sales_raw["sale_date"] > cutoff].copy()

# ── Build store-level aggregates (per-store, per-day) ─────────────────────────
curr_agg = sales_curr.groupby(["sale_date","store_id","market"]).agg(
    net_sales=("net_sales","sum"),
    transactions=("total_transactions","sum"),
).reset_index()

curr_agg["prior_date"] = curr_agg["sale_date"] - pd.Timedelta(days=364)

prior_agg = sales_raw.groupby(["sale_date","store_id"]).agg(
    net_sales_prior=("net_sales","sum"),
    txn_prior=("total_transactions","sum"),
).reset_index().rename(columns={"sale_date":"prior_date"})

df = curr_agg.merge(prior_agg, on=["prior_date","store_id"], how="inner")
df = df[df["net_sales_prior"] > 0].copy()
df["sss_pct"] = (df["net_sales"] - df["net_sales_prior"]) / df["net_sales_prior"] * 100
df["sst_pct"] = (df["transactions"] - df["txn_prior"]) / df["txn_prior"] * 100

# ── Join per-store weather: current + prior ────────────────────────────────────
wx = weather_raw.copy()
wx_curr = wx.rename(columns={"date":"sale_date",
    "temp_max_f":"curr_max","precip_in":"curr_precip","is_rainy":"curr_rainy",
    "is_cold":"curr_cold","temp_spread_f":"curr_spread",
    "lunch_temp_f":"curr_lunch_t","lunch_precip_in":"curr_lunch_p",
    "lunch_is_rainy":"curr_lunch_rain",
    "dinner_temp_f":"curr_dinner_t","dinner_precip_in":"curr_dinner_p",
    "dinner_is_rainy":"curr_dinner_rain"})
wx_prior = wx.rename(columns={"date":"prior_date",
    "temp_max_f":"prior_max","precip_in":"prior_precip","is_rainy":"prior_rainy",
    "lunch_precip_in":"prior_lunch_p","lunch_is_rainy":"prior_lunch_rain",
    "dinner_precip_in":"prior_dinner_p","dinner_is_rainy":"prior_dinner_rain"})

wx_curr_cols  = ["sale_date","store_id","curr_max","curr_precip","curr_rainy",
                 "curr_cold","curr_spread","curr_lunch_t","curr_lunch_p",
                 "curr_lunch_rain","curr_dinner_t","curr_dinner_p","curr_dinner_rain"]
wx_prior_cols = ["prior_date","store_id","prior_max","prior_precip","prior_rainy",
                 "prior_lunch_p","prior_lunch_rain","prior_dinner_p","prior_dinner_rain"]

wx_curr_cols  = [c for c in wx_curr_cols  if c in wx_curr.columns]
wx_prior_cols = [c for c in wx_prior_cols if c in wx_prior.columns]

df = df.merge(wx_curr[wx_curr_cols],   on=["sale_date","store_id"], how="left")
df = df.merge(wx_prior[wx_prior_cols], on=["prior_date","store_id"], how="left")

# Weather deltas (positive = warmer/wetter than prior year)
df["temp_delta"]         = df["curr_max"]      - df["prior_max"]
df["precip_delta"]       = df["curr_precip"]   - df["prior_precip"]
df["rain_change"]        = df["curr_rainy"].fillna(0)       - df["prior_rainy"].fillna(0)
df["lunch_rain_change"]  = df.get("curr_lunch_rain",  pd.Series(0, index=df.index)).fillna(0)                          - df.get("prior_lunch_rain", pd.Series(0, index=df.index)).fillna(0)
df["dinner_rain_change"] = df.get("curr_dinner_rain",  pd.Series(0, index=df.index)).fillna(0)                          - df.get("prior_dinner_rain", pd.Series(0, index=df.index)).fillna(0)
# Categorise weather change
def weather_bucket(row):
    if pd.isna(row.get("curr_rainy")) or pd.isna(row.get("curr_max")):
        return "Unknown"
    if row["curr_rainy"] == 1 and row["prior_rainy"] == 0:
        return "Rain (was dry)"
    if row["curr_rainy"] == 0 and row["prior_rainy"] == 1:
        return "Dry (was rain)"
    if row["curr_rainy"] == 1 and row["prior_rainy"] == 1:
        return "Rain both years"
    td = row["temp_delta"] if pd.notna(row["temp_delta"]) else 0
    if td >= 5:  return "Warmer (+5°F+)"
    if td <= -5: return "Cooler (-5°F+)"
    return "Similar temp"
df["weather_bucket"] = df.apply(weather_bucket, axis=1)

# Apply market filter
if mkt_sel != "All Markets":
    df = df[df["market"] == mkt_sel]

if df.empty:
    st.warning("Not enough overlapping sales + weather data for the selected period.")
    st.stop()

# Remove extreme outliers for correlation (keep middle 98%)
q_lo, q_hi = df["sss_pct"].quantile(0.01), df["sss_pct"].quantile(0.99)
df_clean = df[(df["sss_pct"] >= q_lo) & (df["sss_pct"] <= q_hi) &
              df["temp_delta"].notna()].copy()

# For the precip scatter: exclude days where precip didn't meaningfully change
# (delta near zero adds noise and pulls the correlation line toward zero)
df_precip_scatter = df_clean[df_clean["precip_delta"].abs() >= 0.05].copy()

# ── Summary KPIs ───────────────────────────────────────────────────────────────
# Correlation: temp_delta vs sss_pct
from numpy.polynomial.polynomial import polyfit as nppolyfit
r_temp = df_clean[["temp_delta","sss_pct"]].dropna().corr().iloc[0,1] if len(df_clean) > 5 else None
r_rain = df_clean[["rain_change","sss_pct"]].dropna().corr().iloc[0,1] if len(df_clean) > 5 else None

rainy_days    = df_clean[df_clean["curr_rainy"] == 1]
dry_days      = df_clean[df_clean["curr_rainy"] == 0]
rainy_sss     = rainy_days["sss_pct"].mean() if len(rainy_days) else None
dry_sss       = dry_days["sss_pct"].mean()   if len(dry_days)   else None
new_rain_sss  = df_clean[df_clean["weather_bucket"]=="Rain (was dry)"]["sss_pct"].mean()
dry_from_rain = df_clean[df_clean["weather_bucket"]=="Dry (was rain)"]["sss_pct"].mean()

st.markdown('<div class="section-title">Key Findings</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
def _kpi(col, label, val, sub, cls="kpi-card"):
    col.markdown(f"""<div class="{cls}">
      <div class="kpi-label">{label}</div>
      <div class="kpi-value">{val}</div>
      <div class="kpi-sub">{sub}</div>
    </div>""", unsafe_allow_html=True)

_kpi(k1, "Temp vs SSS Correlation",
     f"{r_temp:+.2f}" if r_temp is not None else "—",
     "R (higher = stronger link)", "kpi-card kpi-card-blue")
_kpi(k2, "Rain vs SSS Correlation",
     f"{r_rain:+.2f}" if r_rain is not None else "—",
     "R (negative = rain hurts sales)", "kpi-card kpi-card-blue")
_kpi(k3, "Rainy Day Avg SSS%",
     f"{rainy_sss:+.1f}%" if rainy_sss is not None else "—",
     f"{len(rainy_days):,} rainy days", "kpi-card")
_kpi(k4, "Dry Day Avg SSS%",
     f"{dry_sss:+.1f}%" if dry_sss is not None else "—",
     f"{len(dry_days):,} dry days", "kpi-card kpi-card-green")
_kpi(k5, "Days Analysed",
     f"{len(df_clean):,}",
     f"{df_clean['market'].nunique()} market(s) · {lookback}", "kpi-card kpi-card-gold")

# ── Insight box ────────────────────────────────────────────────────────────────
if r_temp is not None and rainy_sss is not None and dry_sss is not None:
    rain_diff  = dry_sss - rainy_sss
    temp_dir   = "warmer" if r_temp > 0 else "cooler"
    temp_str   = f"When it's <b>{temp_dir}</b> than the same day last year, SSS tends to be {'higher' if r_temp > 0 else 'lower'} (R = {r_temp:+.2f})."
    rain_str   = (f"Rainy days average <b>{rainy_sss:+.1f}% SSS</b> vs "
                  f"<b>{dry_sss:+.1f}% SSS</b> on dry days — a <b>{rain_diff:.1f}pp gap</b>.")
    new_rain   = (f" Days that are rainy this year but were dry last year average "
                  f"<b>{new_rain_sss:+.1f}% SSS</b>." if new_rain_sss is not None else "")
    st.markdown(f'<div class="insight-box">📊 {temp_str} {rain_str}{new_rain}</div>',
                unsafe_allow_html=True)

# ── Charts row 1: scatter plots ────────────────────────────────────────────────
# Sub-region definitions (shared with the table below)
SUBREGION_MAP = {
    '20026':'Valley', '20267':'Valley', '20116':'Valley', '20363':'Valley',
    '20156':'Valley', '20424':'Valley', '20366':'Valley', '20294':'Valley',
    '20352':'Valley', '20218':'Valley', '20381':'Valley', '20311':'Valley',
    '20011':'Conejo Valley', '20048':'Conejo Valley',
    '20245':'Conejo Valley', '20255':'Conejo Valley',
    '20273':'Mountains', '20388':'Mountains',
    '20075':'Santa Barbara', '20335':'Santa Barbara',
    '20360':'Santa Barbara', '20013':'Santa Barbara',
    '20171':'Inland Riverside', '20177':'Inland Riverside',
    '20291':'Inland Riverside', '20091':'Inland Riverside',
    '20071':'Inland SD', '20300':'Inland SD', '20292':'Inland SD',
}
SUBREGION_ORDER  = ['Valley','Conejo Valley','Mountains','Santa Barbara',
                    'Inland Riverside','Inland SD']
SUBREGION_COLORS = {
    'Valley':           '#1d4ed8',
    'Conejo Valley':    '#7c3aed',
    'Mountains':        '#0891b2',
    'Santa Barbara':    '#059669',
    'Inland Riverside': '#d97706',
    'Inland SD':        '#dc2626',
}

df_clean["subregion"] = df_clean["store_id"].map(SUBREGION_MAP)

st.markdown('<div class="section-title">Correlation Scatter — by Sub-Region</div>', unsafe_allow_html=True)

PLOTLY_BASE = dict(
    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
    font=dict(family="Arial, sans-serif", size=12, color=TEXT),
    dragmode=False,
    modebar=dict(remove=["select2d","lasso2d","zoom2d","pan2d",
                          "autoScale2d","resetScale2d","toImage","sendDataToCloud"]),
    margin=dict(l=50, r=20, t=40, b=90),
    xaxis=dict(gridcolor="#E5E7EB", zerolinecolor=BORDER),
    yaxis=dict(gridcolor="#E5E7EB", zerolinecolor=BORDER, ticksuffix="%"),
    legend=dict(bgcolor=WHITE, bordercolor="#E5E7EB", borderwidth=1,
                font=dict(size=10), orientation="h",
                yanchor="top", y=-0.2, xanchor="center", x=0.5),
)

sc1, sc2 = st.columns(2)

def _scatter_by_region(df_s, x_col, title, x_label):
    fig = go.Figure()
    for reg in SUBREGION_ORDER:
        sub = df_s[df_s["subregion"] == reg].dropna(subset=[x_col,"sss_pct"])
        if sub.empty: continue
        color = SUBREGION_COLORS.get(reg, MUTED)
        fig.add_trace(go.Scatter(
            x=sub[x_col], y=sub["sss_pct"],
            mode="markers", name=reg,
            marker=dict(color=color, size=5, opacity=0.55),
        ))
        xs, ys = sub[x_col].values, sub["sss_pct"].values
        mask = np.isfinite(xs) & np.isfinite(ys)
        if mask.sum() > 5:
            coefs = np.polyfit(xs[mask], ys[mask], 1)
            r = np.corrcoef(xs[mask], ys[mask])[0,1]
            xl = np.linspace(xs[mask].min(), xs[mask].max(), 40)
            fig.add_trace(go.Scatter(
                x=xl, y=np.polyval(coefs, xl),
                mode="lines", showlegend=False,
                line=dict(color=color, width=1.5, dash="dot"),
            ))
    fig.add_hline(y=0, line_color=MUTED, line_width=1)
    fig.add_vline(x=0, line_color=MUTED, line_width=1)
    fig.update_layout(**PLOTLY_BASE,
        title=dict(text=title, font=dict(size=13, color=BLUE), x=0))
    fig.update_xaxes(title_text=x_label, gridcolor="#E5E7EB")
    fig.update_yaxes(ticksuffix="%", gridcolor="#E5E7EB")
    return fig

with sc1:
    scatter_df = df_clean[df_clean["subregion"].notna()].dropna(subset=["temp_delta","sss_pct"])
    fig_t = _scatter_by_region(scatter_df, "temp_delta",
                               "Temp Delta (°F YoY) vs SSS% — by Sub-Region",
                               "Temperature Change vs. Prior Year (°F)")
    st.plotly_chart(fig_t, use_container_width=True)

with sc2:
    scatter_p = df_precip_scatter[df_precip_scatter["subregion"].notna()].dropna(subset=["precip_delta","sss_pct"])
    fig_p = _scatter_by_region(scatter_p, "precip_delta",
                               "Precip Delta (in YoY) vs SSS% — by Sub-Region (|Δ|≥0.05\" only)",
                               "Precipitation Change vs. Prior Year (inches)")
    st.plotly_chart(fig_p, use_container_width=True)

# ── Charts row 2: bucket bar chart + time series (full width, stacked) ────────
st.markdown('<div class="section-title">SSS% by Weather Condition</div>', unsafe_allow_html=True)

BUCKET_ORDER = ["Warmer (+5°F+)", "Similar temp", "Cooler (-5°F+)",
                "Dry (was rain)", "Rain (was dry)", "Rain both years"]
BUCKET_COLORS = {
    "Warmer (+5°F+)": RED,
    "Similar temp":   BLUE,
    "Cooler (-5°F+)": "#93C5FD",
    "Dry (was rain)": GREEN,
    "Rain (was dry)": AMBER,
    "Rain both years":"#9CA3AF",
}

bkt = (df_clean.groupby("weather_bucket")["sss_pct"]
       .agg(avg_sss="mean", count="count").reset_index())
bkt = bkt[bkt["weather_bucket"].isin(BUCKET_ORDER)].copy()
bkt["order"] = bkt["weather_bucket"].map({b:i for i,b in enumerate(BUCKET_ORDER)})
bkt = bkt.sort_values("order")

fig_b = go.Figure(go.Bar(
    y=bkt["weather_bucket"],
    x=bkt["avg_sss"],
    orientation="h",
    marker_color=[BUCKET_COLORS.get(b, MUTED) for b in bkt["weather_bucket"]],
    text=[f"{v:+.1f}% ({n:,}d)" for v,n in zip(bkt["avg_sss"], bkt["count"])],
    textposition="outside",
    textfont=dict(size=11),
))
fig_b.add_vline(x=0, line_color=MUTED, line_width=1)
fig_b.update_layout(
    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
    font=dict(family="Arial, sans-serif", size=12),
    margin=dict(l=140, r=90, t=40, b=30),
    xaxis=dict(ticksuffix="%", gridcolor="#E5E7EB", zerolinecolor=BORDER),
    yaxis=dict(gridcolor="rgba(0,0,0,0)", automargin=True),
    title=dict(text="Avg SSS% by Weather Bucket", font=dict(size=13, color=BLUE), x=0),
    showlegend=False,
    height=320,
)
st.plotly_chart(fig_b, use_container_width=True)

# Time series: SSS% trend with rain overlay — filter by sub-region
_ts_regions = ["All"] + [r for r in SUBREGION_ORDER if r in df_clean["subregion"].unique()]
_ts_sel = st.selectbox("Sub-region", _ts_regions, label_visibility="collapsed", key="ts_region")
_ts_df = df_clean if _ts_sel == "All" else df_clean[df_clean["subregion"] == _ts_sel]

ts = (_ts_df.groupby("sale_date")
      .agg(sss_pct=("sss_pct","mean"), rainy=("curr_rainy","mean"))
      .reset_index().sort_values("sale_date"))
ts["sss_7d"] = ts["sss_pct"].rolling(7, min_periods=3).mean()
rain_days = ts[ts["rainy"] >= 0.5]

fig_ts = go.Figure()
fig_ts.add_trace(go.Bar(
    x=rain_days["sale_date"],
    y=[80]*len(rain_days),
    base=[-40]*len(rain_days),
    name="Rainy day",
    marker=dict(color="rgba(100,150,255,0.15)", line_width=0),
    hoverinfo="skip",
))
fig_ts.add_trace(go.Scatter(
    x=ts["sale_date"], y=ts["sss_pct"],
    mode="markers", name="Daily SSS%",
    marker=dict(size=4, opacity=0.35,
                color=[GREEN if v >= 0 else DANGER for v in ts["sss_pct"]]),
))
fig_ts.add_trace(go.Scatter(
    x=ts["sale_date"], y=ts["sss_7d"],
    mode="lines", name="7-Day Avg SSS%",
    line=dict(color=BLUE, width=2),
))
fig_ts.add_hline(y=0, line_color=MUTED, line_width=1)
fig_ts.update_layout(
    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
    font=dict(family="Arial, sans-serif", size=12, color=TEXT),
    margin=dict(l=40, r=20, t=40, b=50),
    xaxis=dict(tickformat="%b '%y", gridcolor="#E5E7EB"),
    yaxis=dict(ticksuffix="%", gridcolor="#E5E7EB", range=[-40, 40]),
    legend=dict(bgcolor=WHITE, bordercolor=BORDER, borderwidth=1,
                font=dict(size=11), orientation="h",
                yanchor="top", y=-0.12, xanchor="center", x=0.5),
    title=dict(text="SSS% Over Time (blue bands = rainy days)", font=dict(size=13, color=BLUE), x=0),
    height=320,
)
st.plotly_chart(fig_ts, use_container_width=True)

# ── By sub-region bucket table ────────────────────────────────────────────────
st.markdown('<div class="section-title">SSS% by Sub-Region & Weather Condition</div>',
            unsafe_allow_html=True)

df_sub = df_clean[df_clean["subregion"].notna()].copy()

pivot = (df_sub[df_sub["weather_bucket"].isin(BUCKET_ORDER)]
         .groupby(["weather_bucket","subregion"])["sss_pct"]
         .mean().unstack("subregion").reindex(BUCKET_ORDER))
pivot["All"] = (df_clean[df_clean["weather_bucket"].isin(BUCKET_ORDER)]
                .groupby("weather_bucket")["sss_pct"].mean().reindex(BUCKET_ORDER))

cols_avail = [c for c in SUBREGION_ORDER if c in pivot.columns]

def _cell(v):
    if pd.isna(v): return "—"
    cls = "pos" if v >= 0 else "neg"
    return f'<span class="{cls}">{v:+.1f}%</span>'

col_headers = "".join(f"<th>{m}</th>" for m in [*cols_avail, "All"])
rows_html = ""
for bkt_name in BUCKET_ORDER:
    if bkt_name not in pivot.index: continue
    cells = "".join(
        f"<td>{_cell(pivot.loc[bkt_name, m])}</td>" if m in pivot.columns
        else "<td>—</td>"
        for m in [*cols_avail, "All"]
    )
    rows_html += f"<tr><td>{bkt_name}</td>{cells}</tr>"

st.markdown(f"""
<table class="bucket-table">
  <thead><tr><th>Weather Condition</th>{col_headers}</tr></thead>
  <tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

# ── Store location map with sub-region outlines ───────────────────────────────
st.markdown('<div class="section-title">Store Locations by Sub-Region</div>',
            unsafe_allow_html=True)

# Known store coordinates
STORE_COORDS = {
    '20013':(34.6140,-120.1921),'20335':(34.4401,-119.8278),
    '20360':(34.4348,-119.7805),'20075':(34.4279,-119.8608),
    '20381':(34.3001,-118.3987),'20352':(34.2836,-118.4359),
    '20311':(34.2797,-118.5558),'20218':(34.2598,-118.4714),
    '20388':(34.2503,-117.1856),'20273':(34.2436,-116.9114),
    '20026':(34.2390,-118.5321),'20267':(34.2244,-118.5000),
    '20255':(34.2145,-118.9101),'20366':(34.2006,-118.3345),
    '20245':(34.1797,-118.9303),'20048':(34.1791,-118.8748),
    '20294':(34.1784,-118.3345),'20011':(34.1705,-118.8312),
    '20363':(34.1684,-118.5987),'20116':(34.1567,-118.4987),
    '20156':(34.1558,-118.3780),'20424':(34.1478,-118.3823),
    '20177':(33.5636,-117.1490),'20291':(33.5363,-117.1308),
    '20171':(33.5174,-117.1543),'20091':(33.4785,-117.0827),
    '20071':(33.1367,-117.0700),'20300':(33.1285,-117.0456),
    '20292':(33.0422,-116.8734),
}
STORE_NAMES_MAP = {
    '20156':'North Hollywood','20218':'Mission Hills','20267':'Balboa',
    '20294':'Toluca','20026':'Tampa (Northridge)','20311':'Porter Ranch',
    '20352':'San Fernando','20363':'Warner Center','20273':'Big Bear',
    '20366':'Burbank North','20011':'Westlake','20255':'Arboles',
    '20048':'Janss','20245':'Newbury Park','20381':'Sylmar',
    '20116':'Encino','20388':'Lake Arrowhead','20075':'Isla Vista',
    '20335':'Goleta','20360':'Santa Barbara','20424':'Studio City',
    '20177':'Murrieta','20171':'Temecula Ynez','20091':'Temecula Pkwy',
    '20071':'Escondido Ctr','20300':'Escondido E','20292':'Ramona',
    '20291':'Temecula Ranch','20013':'Buellton',
}

fig_map = go.Figure()

for reg in SUBREGION_ORDER:
    color = SUBREGION_COLORS[reg]
    store_ids = [s for s,r in SUBREGION_MAP.items() if r == reg]
    lats = [STORE_COORDS[s][0] for s in store_ids if s in STORE_COORDS]
    lons = [STORE_COORDS[s][1] for s in store_ids if s in STORE_COORDS]
    names = [STORE_NAMES_MAP.get(s, s) for s in store_ids if s in STORE_COORDS]

    # Draw convex hull outline around each region's stores
    if len(lats) >= 3:
        try:
            from scipy.spatial import ConvexHull
            import numpy as _np
            pts = _np.array(list(zip(lats, lons)))
            hull = ConvexHull(pts)
            hull_lats = list(pts[hull.vertices, 0]) + [pts[hull.vertices[0], 0]]
            hull_lons = list(pts[hull.vertices, 1]) + [pts[hull.vertices[0], 1]]
            # Add a small buffer
            clat = sum(hull_lats)/len(hull_lats)
            clon = sum(hull_lons)/len(hull_lons)
            hull_lats = [clat + (lat-clat)*1.3 for lat in hull_lats]
            hull_lons = [clon + (lon-clon)*1.3 for lon in hull_lons]
            fig_map.add_trace(go.Scattermapbox(
                lat=hull_lats, lon=hull_lons, mode="lines",
                line=dict(color=color, width=2),
                fill="toself", fillcolor=color.replace("#","rgba(").rstrip(")") if False else color,
                opacity=0.12, showlegend=False, hoverinfo="skip",
                name=f"{reg} boundary",
            ))
        except Exception:
            pass

    # Store dots
    fig_map.add_trace(go.Scattermapbox(
        lat=lats, lon=lons, mode="markers+text",
        marker=dict(size=12, color=color),
        text=names,
        textposition="top right",
        textfont=dict(size=9, color=TEXT),
        name=reg,
        hovertemplate="<b>%{text}</b><br>" + reg + "<extra></extra>",
    ))

center_lat = sum(c[0] for c in STORE_COORDS.values()) / len(STORE_COORDS)
center_lon = sum(c[1] for c in STORE_COORDS.values()) / len(STORE_COORDS)

fig_map.update_layout(
    mapbox=dict(style="open-street-map", zoom=7.5,
                center=dict(lat=center_lat, lon=center_lon)),
    margin=dict(l=0, r=0, t=10, b=0),
    height=550,
    legend=dict(bgcolor=WHITE, bordercolor=BORDER, borderwidth=1,
                font=dict(size=11), orientation="v",
                yanchor="top", y=0.99, xanchor="left", x=0.01),
    dragmode=False,
)
st.plotly_chart(fig_map, use_container_width=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;font-size:11px;color:{MUTED};margin-top:24px;
            border-top:1px solid {BORDER};padding-top:12px;">
  Weather data: Open-Meteo (free, no key) · Sales vs. same day 364 days prior ·
  JM Valley Group · Vantedge Partners
</div>
""", unsafe_allow_html=True)
