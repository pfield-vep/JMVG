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
st.markdown("""
<style>
    /* Sidebar toggle arrows — font-independent, CSP-safe */
    [data-testid="stSidebarCollapseButton"] span,
    [data-testid="stExpandSidebarButton"] span {
        width: 0 !important;
        overflow: hidden !important;
        display: inline-block !important;
    }
    [data-testid="stSidebarCollapseButton"]::after {
        content: "\25C0";
        font-family: Arial, sans-serif !important;
        font-size: 16px !important;
        color: #FFFFFF !important;
    }
    [data-testid="stExpandSidebarButton"]::after {
        content: "\25B6";
        font-family: Arial, sans-serif !important;
        font-size: 16px !important;
        color: #134A7C !important;
    }
    /* Blue sidebar — applied globally so all pages match */
    section[data-testid="stSidebar"] {
        background-color: #134A7C !important;
    }
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown div,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {
        color: white !important;
        font-family: Arial, sans-serif !important;
        font-size: 14px !important;
    }
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        background-color: rgba(255,255,255,0.15) !important;
        border: 1px solid rgba(255,255,255,0.35) !important;
    }
</style>
""", unsafe_allow_html=True)

st.markdown(f"""
<style>html, body, [class*="css"] {{
    font-family: Arial, sans-serif !important;
    background-color: {WHITE};
  }}
  .stApp, .main {{ background-color: {WHITE} !important; }}
  .block-container {{
    padding: 0.75rem 1.25rem 1.5rem !important;
    max-width: 100% !important;
  }}
  section[data-testid="stSidebar"] {{ background-color: {BLUE} !important; }}
  section[data-testid="stSidebar"] label,
  section[data-testid="stSidebar"] span {{ color: white !important; }}
  [data-testid="stToolbar"] {{ visibility: visible !important; }}
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
    p = "%s" if dialect == "postgres" else "?"
    # Pull all daily_sales + daily_weather joined for current and prior year
    sql = """
        SELECT
            s.sale_date,
            s.store_id,
            s.net_sales,
            s.total_transactions,
            s.lunch_sales,
            s.dinner_sales,
            s.morning_sales
        FROM daily_sales s
        WHERE s.net_sales IS NOT NULL AND s.net_sales > 0
        ORDER BY s.sale_date
    """
    sales = pd.read_sql_query(sql, conn)

    weather_sql = """
        SELECT date, market, temp_max_f, temp_min_f, avg_temp_f,
               precip_in, is_rainy, is_cold
        FROM daily_weather
        ORDER BY date
    """
    weather = pd.read_sql_query(weather_sql, conn)
    conn.close()

    sales["sale_date"] = pd.to_datetime(sales["sale_date"])
    weather["date"]    = pd.to_datetime(weather["date"])
    sales["market"]    = sales["store_id"].apply(get_market)
    sales = sales[sales["market"].notna()]   # drop Tampa and any unmapped stores

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

# ── Build daily aggregates by market ──────────────────────────────────────────
# Current period
curr_agg = sales_curr.groupby(["sale_date","market"]).agg(
    net_sales=("net_sales","sum"),
    transactions=("total_transactions","sum"),
    store_count=("store_id","nunique"),
).reset_index()

# Prior year (364 days back)
curr_agg["prior_date"] = curr_agg["sale_date"] - pd.Timedelta(days=364)

prior_agg = sales_raw.groupby(["sale_date","market"]).agg(
    net_sales_prior=("net_sales","sum"),
    txn_prior=("total_transactions","sum"),
).reset_index().rename(columns={"sale_date":"prior_date"})

df = curr_agg.merge(prior_agg, on=["prior_date","market"], how="inner")
df = df[df["net_sales_prior"] > 0].copy()
df["sss_pct"] = (df["net_sales"] - df["net_sales_prior"]) / df["net_sales_prior"] * 100
df["sst_pct"] = (df["transactions"] - df["txn_prior"]) / df["txn_prior"] * 100

# ── Join weather: current + prior ─────────────────────────────────────────────
wx = weather_raw.copy()
wx_curr  = wx.rename(columns={"date":"sale_date",
    "temp_max_f":"curr_max","temp_min_f":"curr_min","avg_temp_f":"curr_avg",
    "precip_in":"curr_precip","is_rainy":"curr_rainy","is_cold":"curr_cold"})
wx_prior = wx.rename(columns={"date":"prior_date",
    "temp_max_f":"prior_max","temp_min_f":"prior_min","avg_temp_f":"prior_avg",
    "precip_in":"prior_precip","is_rainy":"prior_rainy","is_cold":"prior_cold"})

df = df.merge(wx_curr[["sale_date","market","curr_max","curr_min","curr_avg",
                         "curr_precip","curr_rainy","curr_cold"]],
              on=["sale_date","market"], how="left")
df = df.merge(wx_prior[["prior_date","market","prior_max","prior_min","prior_avg",
                          "prior_precip","prior_rainy","prior_cold"]],
              on=["prior_date","market"], how="left")

# Weather deltas (positive = warmer/wetter than prior year)
df["temp_delta"]   = df["curr_avg"]    - df["prior_avg"]
df["precip_delta"] = df["curr_precip"] - df["prior_precip"]
df["rain_change"]  = df["curr_rainy"].fillna(0) - df["prior_rainy"].fillna(0)
# Categorise weather change
def weather_bucket(row):
    if pd.isna(row["curr_rainy"]) or pd.isna(row["curr_avg"]):
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
st.markdown('<div class="section-title">Correlation Scatter</div>', unsafe_allow_html=True)

PLOTLY_BASE = dict(
    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
    font=dict(family="Arial, sans-serif", size=12, color=TEXT),
    margin=dict(l=50, r=20, t=40, b=50),
    xaxis=dict(gridcolor="#E5E7EB", zerolinecolor=BORDER),
    yaxis=dict(gridcolor="#E5E7EB", zerolinecolor=BORDER, ticksuffix="%"),
)

sc1, sc2 = st.columns(2)

# Scatter: temp delta vs SSS%
with sc1:
    scatter_df = df_clean.dropna(subset=["temp_delta","sss_pct"])
    colors = scatter_df["market"].map(
        {"Los Angeles": BLUE, "San Diego": RED, "Tampa": GOLD}
    ).fillna(MUTED)

    fig_t = go.Figure()
    for mkt, mcolor in [("Los Angeles", BLUE), ("San Diego", RED)]:
        sub = scatter_df[scatter_df["market"] == mkt]
        if sub.empty: continue
        fig_t.add_trace(go.Scatter(
            x=sub["temp_delta"], y=sub["sss_pct"],
            mode="markers", name=mkt,
            marker=dict(color=mcolor, size=5, opacity=0.5),
        ))
    # Trend line
    if len(scatter_df) > 10:
        xs = scatter_df["temp_delta"].values
        ys = scatter_df["sss_pct"].values
        mask = np.isfinite(xs) & np.isfinite(ys)
        if mask.sum() > 5:
            coefs = np.polyfit(xs[mask], ys[mask], 1)
            x_line = np.linspace(xs[mask].min(), xs[mask].max(), 50)
            y_line = np.polyval(coefs, x_line)
            fig_t.add_trace(go.Scatter(
                x=x_line, y=y_line, mode="lines",
                name=f"Trend (R={r_temp:+.2f})",
                line=dict(color=DANGER, width=2, dash="dash"),
            ))
    fig_t.add_hline(y=0, line_color=MUTED, line_width=1)
    fig_t.add_vline(x=0, line_color=MUTED, line_width=1)
    fig_t.update_layout(**PLOTLY_BASE,
        title=dict(text="Temp Delta (°F YoY) vs SSS%", font=dict(size=13, color=BLUE), x=0),
        xaxis_title="Temperature Change vs. Prior Year (°F)",
        legend=dict(bgcolor=WHITE, bordercolor=BORDER, borderwidth=1,
                    font=dict(size=10), orientation="h",
                    yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig_t, use_container_width=True)

# Scatter: precip delta vs SSS%
with sc2:
    scatter_p = df_clean.dropna(subset=["precip_delta","sss_pct"])
    fig_p = go.Figure()
    for mkt, mcolor in [("Los Angeles", BLUE), ("San Diego", RED)]:
        sub = scatter_p[scatter_p["market"] == mkt]
        if sub.empty: continue
        fig_p.add_trace(go.Scatter(
            x=sub["precip_delta"], y=sub["sss_pct"],
            mode="markers", name=mkt,
            marker=dict(color=mcolor, size=5, opacity=0.5),
        ))
    if len(scatter_p) > 10:
        xs2 = scatter_p["precip_delta"].values
        ys2 = scatter_p["sss_pct"].values
        mask2 = np.isfinite(xs2) & np.isfinite(ys2)
        if mask2.sum() > 5:
            coefs2 = np.polyfit(xs2[mask2], ys2[mask2], 1)
            x2_line = np.linspace(xs2[mask2].min(), xs2[mask2].max(), 50)
            y2_line = np.polyval(coefs2, x2_line)
            fig_p.add_trace(go.Scatter(
                x=x2_line, y=y2_line, mode="lines",
                name=f"Trend (R={r_rain:+.2f})",
                line=dict(color=DANGER, width=2, dash="dash"),
            ))
    fig_p.add_hline(y=0, line_color=MUTED, line_width=1)
    fig_p.add_vline(x=0, line_color=MUTED, line_width=1)
    fig_p.update_layout(**PLOTLY_BASE,
        title=dict(text="Precip Delta (inches YoY) vs SSS%", font=dict(size=13, color=BLUE), x=0),
        xaxis_title="Precipitation Change vs. Prior Year (inches)",
        legend=dict(bgcolor=WHITE, bordercolor=BORDER, borderwidth=1,
                    font=dict(size=10), orientation="h",
                    yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
    )
    st.plotly_chart(fig_p, use_container_width=True)

# ── Charts row 2: bucket bar chart + time series ───────────────────────────────
st.markdown('<div class="section-title">SSS% by Weather Condition</div>', unsafe_allow_html=True)

b1, b2 = st.columns([1, 1.6])

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

with b1:
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
        margin=dict(l=10, r=80, t=40, b=30),
        xaxis=dict(ticksuffix="%", gridcolor="#E5E7EB", zerolinecolor=BORDER),
        yaxis=dict(gridcolor="rgba(0,0,0,0)"),
        title=dict(text="Avg SSS% by Weather Bucket", font=dict(size=13, color=BLUE), x=0),
        showlegend=False,
        height=320,
    )
    st.plotly_chart(fig_b, use_container_width=True)

# Time series: SSS% trend with rain overlay
with b2:
    ts = (df_clean.groupby("sale_date")
          .agg(sss_pct=("sss_pct","mean"), rainy=("curr_rainy","mean"))
          .reset_index().sort_values("sale_date"))
    ts["sss_7d"] = ts["sss_pct"].rolling(7, min_periods=3).mean()
    rain_days = ts[ts["rainy"] >= 0.5]

    fig_ts = go.Figure()
    # Rain day markers (background shading via scatter with big markers)
    fig_ts.add_trace(go.Bar(
        x=rain_days["sale_date"],
        y=[999]*len(rain_days),
        base=[-999]*len(rain_days),
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
        yaxis=dict(ticksuffix="%", gridcolor="#E5E7EB"),
        title=dict(text="SSS% Over Time (blue bands = rainy days)", font=dict(size=13, color=BLUE), x=0),
        legend=dict(bgcolor=WHITE, bordercolor=BORDER, borderwidth=1,
                    font=dict(size=10), orientation="h",
                    yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
        height=320,
    )
    st.plotly_chart(fig_ts, use_container_width=True)

# ── By-market bucket table ─────────────────────────────────────────────────────
st.markdown('<div class="section-title">SSS% by Market & Weather Condition</div>',
            unsafe_allow_html=True)

markets_avail = [m for m in ["Los Angeles","San Diego"]
                 if m in df_clean["market"].unique()]

pivot = (df_clean[df_clean["weather_bucket"].isin(BUCKET_ORDER)]
         .groupby(["weather_bucket","market"])["sss_pct"]
         .mean().unstack("market").reindex(BUCKET_ORDER))
pivot["All"] = (df_clean[df_clean["weather_bucket"].isin(BUCKET_ORDER)]
                .groupby("weather_bucket")["sss_pct"].mean().reindex(BUCKET_ORDER))

def _cell(v):
    if pd.isna(v): return "—"
    cls = "pos" if v >= 0 else "neg"
    return f'<span class="{cls}">{v:+.1f}%</span>'

col_headers = "".join(f"<th>{m}</th>" for m in [*markets_avail, "All"])
rows_html = ""
for bkt_name in BUCKET_ORDER:
    if bkt_name not in pivot.index: continue
    cells = "".join(_cell(pivot.loc[bkt_name, m])
                    if m in pivot.columns else "<td>—</td>"
                    for m in [*markets_avail, "All"])
    rows_html += f"<tr><td>{bkt_name}</td>{cells}</tr>"

st.markdown(f"""
<table class="bucket-table">
  <thead><tr><th>Weather Condition</th>{col_headers}</tr></thead>
  <tbody>{rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;font-size:11px;color:{MUTED};margin-top:24px;
            border-top:1px solid {BORDER};padding-top:12px;">
  Weather data: Open-Meteo (free, no key) · Sales vs. same day 364 days prior ·
  JM Valley Group · Vantedge Partners
</div>
""", unsafe_allow_html=True)
