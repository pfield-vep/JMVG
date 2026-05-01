"""
pages/7_Hourly_Heatmap.py
JM Valley Group — Hourly Sales Heatmap
Three views: Rolling Weeks · Day of Week · SSS% by Hour × DOW
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import date, timedelta
import os

st.set_page_config(
    page_title="Hourly Heatmap | JM Valley Group",
    page_icon="🕐",
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

# ── Sub-region / store constants ───────────────────────────────────────────────
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
SUBREGION_ORDER = ['Valley','Conejo Valley','Mountains','Santa Barbara',
                   'Inland Riverside','Inland SD']
STORE_NAMES = {
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
STORE_NAME_TO_ID = {v: k for k, v in STORE_NAMES.items()}

OP_HOURS   = list(range(10, 22))   # 10 AM – 9 PM
DOW_LABELS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

def _fmt_hour(h):
    if h < 12:  return f"{h} AM"
    if h == 12: return "12 PM"
    return f"{h-12} PM"

HOUR_LABELS = [_fmt_hour(h) for h in OP_HOURS]

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
  html, body, .stApp {{ overflow-x: hidden !important; max-width: 100vw !important; }}
  body {{ font-family: Arial, sans-serif; }}
  .stApp, .main {{ background-color: {WHITE} !important; }}
  .block-container {{ padding: 0.75rem 1.25rem 1.5rem !important; max-width: 100% !important; }}
  [data-testid="stExpandSidebarButton"] * {{ visibility: visible !important; }}
  [data-testid="stSidebarCollapseButton"] * {{ visibility: visible !important; }}
  header {{ visibility: hidden; }}
  .section-title {{
    font-size: 13px; font-weight: 800; letter-spacing: 1.5px;
    text-transform: uppercase; color: {BLUE};
    border-bottom: 2px solid {BLUE}; padding-bottom: 6px; margin: 18px 0 12px;
  }}
  .filter-label {{
    font-size: 10px; font-weight: 700; letter-spacing: 1.1px;
    text-transform: uppercase; color: {MUTED}; margin-bottom: 2px;
  }}
  .summary-table {{ width:100%; border-collapse:collapse; }}
  .summary-table td {{ padding:5px 10px; font-size:12px;
                       border-bottom:1px solid {BORDER}; }}
  .summary-table tr:last-child td {{ border-bottom:none; }}
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

@st.cache_data(ttl=300)
def _hourly_freshness():
    conn, _ = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(sale_date) FROM hourly_sales")
        row = cur.fetchone()
        conn.close()
        return pd.to_datetime(row[0]).date() if row and row[0] else None
    except Exception:
        conn.close()
        return None

_h_fresh = _hourly_freshness()
_h_fresh_str = _h_fresh.strftime("%a %b %d, %Y") if _h_fresh else "—"
_logo_html = f'<img src="{_LOGO}" style="height:44px;width:auto;flex-shrink:0;"/>' if _LOGO else ""
st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;
            background:{BLUE};border-radius:10px;padding:12px 20px;margin-bottom:16px;">
  {_logo_html}
  <div style="font-size:13px;font-weight:800;color:{WHITE};
              letter-spacing:2px;text-transform:uppercase;">
    Hourly Sales Heatmap
  </div>
  <div style="margin-left:auto;font-size:10px;color:rgba(255,255,255,0.72);
              text-align:right;white-space:nowrap;line-height:1.5;">
    🕐 Data through<br/><b style="font-size:11px;">{_h_fresh_str}</b>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Data loaders ───────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_dm_store_map():
    conn, _ = get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT store_id, dm_name, broad_geography FROM stores WHERE dm_name IS NOT NULL",
            conn)
        conn.close()
        df["store_id"] = df["store_id"].astype(str).str.strip()
        def _mkt(g):
            g = str(g or "")
            if "San Diego" in g:                      return "San Diego"
            if "Santa Barbara" in g or "San Luis" in g: return "Santa Barbara"
            return "Los Angeles"
        df["display_market"] = df["broad_geography"].apply(_mkt)
        df["dm_first"]  = df["dm_name"].apply(lambda n: str(n or "").strip().split()[0])
        df["dm_group"]  = df["display_market"] + " – " + df["dm_first"]
        return df
    except Exception:
        conn.close()
        return None

@st.cache_data(ttl=300)
def get_hourly_max_date():
    conn, _ = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(sale_date) FROM hourly_sales")
        row = cur.fetchone()
        conn.close()
        if row and row[0]:
            return pd.to_datetime(row[0]).date()
    except Exception:
        conn.close()
    return date.today()

@st.cache_data(ttl=300)
def load_hourly(overall_start: str, overall_end: str):
    conn, dialect = get_conn()
    p = "%s" if dialect == "postgres" else "?"
    try:
        df = pd.read_sql_query(
            f"SELECT store_id, sale_date, hour, net_sales, total_transactions "
            f"FROM hourly_sales WHERE sale_date >= {p} AND sale_date <= {p} "
            f"ORDER BY sale_date, store_id, hour",
            conn, params=(overall_start, overall_end))
        conn.close()
        df["sale_date"] = pd.to_datetime(df["sale_date"])
        df["store_id"]  = df["store_id"].astype(str)
        return df
    except Exception:
        conn.close()
        return pd.DataFrame()

# ── Cascading filters ──────────────────────────────────────────────────────────
dm_map   = load_dm_store_map()
max_date = get_hourly_max_date()

fl1, fl2, fl3, fl4, fl5 = st.columns([2, 2, 2, 1.5, 1.5])

with fl1:
    st.markdown('<div class="filter-label">Sub-Region</div>', unsafe_allow_html=True)
    subr_sel = st.selectbox("Sub-Region",
        ["All Sub-Regions"] + SUBREGION_ORDER,
        label_visibility="collapsed", key="subr")

# Build store scope from sub-region
if subr_sel != "All Sub-Regions":
    scope_stores = {s for s, r in SUBREGION_MAP.items() if r == subr_sel}
else:
    scope_stores = set(SUBREGION_MAP.keys())

with fl2:
    st.markdown('<div class="filter-label">District Manager</div>', unsafe_allow_html=True)
    dm_in_scope = []
    if dm_map is not None:
        for g in sorted(dm_map["dm_group"].unique()):
            if set(dm_map[dm_map["dm_group"] == g]["store_id"]) & scope_stores:
                dm_in_scope.append(g)
    dm_sel = st.selectbox("DM", ["All DMs"] + dm_in_scope,
                          label_visibility="collapsed", key="dm")

# Narrow by DM
if dm_sel != "All DMs" and dm_map is not None:
    scope_stores &= set(dm_map[dm_map["dm_group"] == dm_sel]["store_id"])

with fl3:
    st.markdown('<div class="filter-label">Store</div>', unsafe_allow_html=True)
    store_opts = ["All Stores"] + sorted(
        [STORE_NAMES[s] for s in scope_stores if s in STORE_NAMES])
    store_sel = st.selectbox("Store", store_opts,
                             label_visibility="collapsed", key="store")

# Narrow by store
if store_sel != "All Stores":
    sid = STORE_NAME_TO_ID.get(store_sel)
    if sid:
        scope_stores = {sid}

if not scope_stores:
    st.warning("No stores match the selected filters.")
    st.stop()

with fl4:
    st.markdown('<div class="filter-label">Lookback</div>', unsafe_allow_html=True)
    lookback = st.selectbox("Lookback",
        ["Last 30 Days","Last 60 Days","Last 90 Days","Last 180 Days"],
        index=2, label_visibility="collapsed", key="lookback")

with fl5:
    st.markdown('<div class="filter-label">Metric</div>', unsafe_allow_html=True)
    metric = st.selectbox("Metric",
        ["Net Sales $","Transactions","% of Daily Total"],
        label_visibility="collapsed", key="metric")

# ── Date window ────────────────────────────────────────────────────────────────
lookback_days = {"Last 30 Days":30,"Last 60 Days":60,
                 "Last 90 Days":90,"Last 180 Days":180}[lookback]
end_date    = max_date
start_date  = max_date - timedelta(days=lookback_days)
prior_start = start_date - timedelta(days=364)
prior_end   = end_date   - timedelta(days=364)

st.markdown(
    f"<div style='font-size:11px;color:{MUTED};margin-bottom:6px;'>"
    f"<b>{start_date.strftime('%b %d, %Y')}</b> – <b>{end_date.strftime('%b %d, %Y')}</b>"
    f" &nbsp;·&nbsp; {len(scope_stores)} store(s)"
    f" &nbsp;·&nbsp; SSS% vs <b>{prior_start.strftime('%b %d')} – {prior_end.strftime('%b %d, %Y')}</b>"
    f"</div>",
    unsafe_allow_html=True
)

# ── Load & filter data ─────────────────────────────────────────────────────────
raw = load_hourly(str(prior_start), str(end_date))

if raw.empty:
    st.warning("No hourly sales data found. Load data with `py scripts/load_hourly_sales.py`.")
    st.stop()

raw = raw[raw["store_id"].isin(scope_stores) & raw["hour"].isin(OP_HOURS)]
curr_df  = raw[raw["sale_date"].dt.date.between(start_date, end_date)].copy()
prior_df = raw[raw["sale_date"].dt.date.between(prior_start, prior_end)].copy()

if curr_df.empty:
    st.warning("No hourly data for the selected filters and date range.")
    st.stop()

# ── Preprocessing ──────────────────────────────────────────────────────────────
def _enrich(df):
    """Add pct_of_day, dow, week_start columns."""
    if df.empty:
        return df
    daily = (df.groupby(["store_id","sale_date"])["net_sales"]
               .sum().reset_index().rename(columns={"net_sales":"daily_total"}))
    df = df.merge(daily, on=["store_id","sale_date"], how="left")
    df["pct_of_day"]  = np.where(df["daily_total"] > 0,
                                  df["net_sales"] / df["daily_total"] * 100, np.nan)
    df["dow"]         = df["sale_date"].dt.dayofweek  # 0=Mon
    df["week_start"]  = (df["sale_date"]
                         - pd.to_timedelta(df["sale_date"].dt.weekday, unit="d"))
    return df

curr_df  = _enrich(curr_df)
prior_df = _enrich(prior_df)

METRIC_COL = {"Net Sales $":"net_sales",
              "Transactions":"total_transactions",
              "% of Daily Total":"pct_of_day"}[metric]

def _fmt_val(v):
    if v is None or (isinstance(v, float) and np.isnan(v)): return ""
    if metric == "Net Sales $":
        return f"${v/1000:.1f}K" if v >= 1000 else f"${v:,.0f}"
    if metric == "Transactions":
        return f"{v:.0f}"
    return f"{v:.1f}%"

# Human-readable scope label for chart titles
scope_label = (
    store_sel if store_sel != "All Stores" else
    (dm_sel.split(" – ")[-1] if dm_sel != "All DMs" else
     (subr_sel if subr_sel != "All Sub-Regions" else "All Stores"))
)

# ── Color scales ───────────────────────────────────────────────────────────────
CS_SEQ = [
    [0.0, "#EEF4FF"],[0.25, "#93C5FD"],
    [0.5, "#3B82F6"],[0.75, "#1D4ED8"],[1.0, "#134A7C"],
]
CS_DIV = [
    [0.0, "#dc2626"],[0.35, "#FCA5A5"],
    [0.5, "#F9FAFB"],[0.65, "#86EFAC"],[1.0, "#16a34a"],
]

PLOTLY_BASE = dict(
    plot_bgcolor=WHITE, paper_bgcolor=WHITE,
    font=dict(family="Arial, sans-serif", size=11, color=TEXT),
    dragmode=False,
    modebar=dict(remove=["select2d","lasso2d","zoom2d","pan2d",
                         "autoScale2d","resetScale2d","toImage","sendDataToCloud"]),
    margin=dict(l=70, r=30, t=50, b=60),
)

def _draw_heatmap(z_matrix, x_labels, y_labels, title,
                  colorscale, fmt_fn, zmid=None, zmin=None, zmax=None,
                  colorbar_title="", cell_font_size=10):
    """Render an annotated Plotly heatmap."""
    text_mat = [[fmt_fn(v) for v in row] for row in z_matrix]
    trace = go.Heatmap(
        z=z_matrix, x=x_labels, y=y_labels,
        colorscale=colorscale, zmid=zmid,
        zmin=zmin, zmax=zmax,
        text=text_mat, texttemplate="%{text}",
        textfont=dict(size=cell_font_size, family="Arial, sans-serif"),
        hoverongaps=False,
        hovertemplate="<b>%{y}</b>  ·  <b>%{x}</b><br>%{text}<extra></extra>",
        colorbar=dict(
            title=dict(text=colorbar_title, font=dict(size=10)),
            thickness=12, len=0.75,
            tickfont=dict(size=9),
        ),
    )
    fig = go.Figure(trace)
    fig.update_layout(
        **PLOTLY_BASE,
        title=dict(text=title, font=dict(size=13, color=BLUE), x=0),
        yaxis=dict(autorange="reversed", tickfont=dict(size=10),
                   gridcolor=BORDER, title=""),
        xaxis=dict(side="top", tickfont=dict(size=10), tickangle=0,
                   gridcolor="rgba(0,0,0,0)", title=""),
        height=max(400, len(y_labels) * 32 + 130),
    )
    return fig

# ═══════════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["📅  By Week","📆  Day of Week","📊  SSS% by Hour"])

# ───────────────────────────────────────────────────────────────────
# TAB 1 — Hours × Rolling Weeks
# ───────────────────────────────────────────────────────────────────
with tab1:
    wk_agg = (curr_df.groupby(["week_start","hour"])[METRIC_COL]
              .mean().reset_index())
    if wk_agg.empty:
        st.info("Not enough data for the selected filters.")
    else:
        pvt_w = wk_agg.pivot(index="hour", columns="week_start", values=METRIC_COL)
        weeks_sorted = sorted(pvt_w.columns)
        pvt_w = pvt_w[weeks_sorted].reindex(index=OP_HOURS)

        # Cap at 16 most-recent weeks to keep the chart readable
        if len(weeks_sorted) > 16:
            weeks_sorted = weeks_sorted[-16:]
            pvt_w = pvt_w[weeks_sorted]

        col_labels = [w.strftime("%b %d") for w in weeks_sorted]
        z_w = pvt_w.values.tolist()

        fig_w = _draw_heatmap(
            z_w, col_labels, HOUR_LABELS,
            f"Avg {metric} by Hour  ·  Rolling Weeks  ·  {scope_label}",
            CS_SEQ, _fmt_val,
            colorbar_title=metric,
        )
        st.plotly_chart(fig_w, use_container_width=True)
        st.markdown(
            f"<div style='font-size:11px;color:{MUTED};margin-top:-8px;'>"
            f"Each cell = avg {metric.lower()} per store-day for that hour within the week. "
            f"Showing {len(weeks_sorted)} week(s). Most recent week may be partial.</div>",
            unsafe_allow_html=True
        )

# ───────────────────────────────────────────────────────────────────
# TAB 2 — Hours × Day of Week
# ───────────────────────────────────────────────────────────────────
with tab2:
    dow_agg = (curr_df.groupby(["dow","hour"])[METRIC_COL]
               .mean().reset_index())
    if dow_agg.empty:
        st.info("Not enough data for the selected filters.")
    else:
        pvt_d = (dow_agg.pivot(index="hour", columns="dow", values=METRIC_COL)
                        .reindex(index=OP_HOURS, columns=range(7)))
        pvt_d.columns = DOW_LABELS

        z_d = pvt_d.values.tolist()
        fig_d = _draw_heatmap(
            z_d, DOW_LABELS, HOUR_LABELS,
            f"Avg {metric} by Hour  ·  Day of Week  ·  {scope_label}",
            CS_SEQ, _fmt_val,
            colorbar_title=metric,
        )
        st.plotly_chart(fig_d, use_container_width=True)

        # ── Day totals bar (always Net Sales for context) ──
        day_ns = curr_df.groupby("dow")["net_sales"].sum().reindex(range(7))
        fig_bar = go.Figure(go.Bar(
            x=DOW_LABELS,
            y=day_ns.values,
            marker_color=BLUE, opacity=0.75,
            text=[f"${v/1000:.0f}K" if pd.notna(v) else ""
                  for v in day_ns.values],
            textposition="outside",
            textfont=dict(size=10),
        ))
        fig_bar.add_hline(y=day_ns.mean(), line_color=MUTED,
                          line_dash="dot", line_width=1,
                          annotation_text="avg",
                          annotation_font_size=9)
        fig_bar.update_layout(**PLOTLY_BASE)
        fig_bar.update_layout(
            title=dict(text="Total Net Sales by Day of Week",
                       font=dict(size=12, color=BLUE), x=0),
            xaxis=dict(gridcolor="rgba(0,0,0,0)"),
            yaxis=dict(tickprefix="$", gridcolor="#E5E7EB"),
            height=220, margin=dict(l=60, r=30, t=40, b=30),
            showlegend=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

# ───────────────────────────────────────────────────────────────────
# TAB 3 — SSS% by Hour × Day of Week
# ───────────────────────────────────────────────────────────────────
with tab3:
    if prior_df.empty:
        st.info("No prior-year data available for this period — SSS% cannot be calculated.")
    else:
        curr_dow  = (curr_df .groupby(["dow","hour"])["net_sales"]
                             .mean().reset_index().rename(columns={"net_sales":"curr"}))
        prior_dow = (prior_df.groupby(["dow","hour"])["net_sales"]
                             .mean().reset_index().rename(columns={"net_sales":"prior"}))

        sss_df = curr_dow.merge(prior_dow, on=["dow","hour"], how="inner")
        sss_df = sss_df[sss_df["prior"] > 0].copy()
        sss_df["sss_pct"] = (sss_df["curr"] - sss_df["prior"]) / sss_df["prior"] * 100

        if sss_df.empty:
            st.info("Not enough overlap between current and prior-year data.")
        else:
            pvt_s = (sss_df.pivot(index="hour", columns="dow", values="sss_pct")
                           .reindex(index=OP_HOURS, columns=range(7)))
            pvt_s.columns = DOW_LABELS
            z_s = pvt_s.values.tolist()

            # Symmetric color scale — clip at 95th-pct absolute value
            flat_vals = [v for row in z_s for v in row
                         if v is not None and not np.isnan(v)]
            cap = float(np.percentile([abs(v) for v in flat_vals], 95)) if flat_vals else 15
            cap = min(max(cap, 5), 40)

            fig_s = _draw_heatmap(
                z_s, DOW_LABELS, HOUR_LABELS,
                f"SSS% by Hour  ·  Day of Week  ·  {scope_label}  ·  vs prior year",
                CS_DIV,
                lambda v: f"{v:+.1f}%" if (v is not None and not np.isnan(v)) else "",
                zmid=0, zmin=-cap, zmax=cap,
                colorbar_title="SSS%",
            )
            st.plotly_chart(fig_s, use_container_width=True)

            # ── Top / Bottom 5 hour-day combos ──────────────────────
            sss_df["hour_lbl"] = sss_df["hour"].apply(_fmt_hour)
            sss_df["dow_lbl"]  = sss_df["dow"].map(dict(enumerate(DOW_LABELS)))
            sss_df["combo"]    = sss_df["dow_lbl"] + "  " + sss_df["hour_lbl"]

            top5 = sss_df.nlargest(5, "sss_pct")[["combo","sss_pct"]]
            bot5 = sss_df.nsmallest(5, "sss_pct")[["combo","sss_pct"]]

            def _summary_card(df, header, is_positive):
                accent = GREEN if is_positive else DANGER
                rows = "".join(
                    f"<tr>"
                    f"<td style='padding:6px 12px;font-size:12px;'>{r['combo']}</td>"
                    f"<td style='padding:6px 12px;font-size:12px;font-weight:700;"
                    f"color:{accent};text-align:right;'>{r['sss_pct']:+.1f}%</td>"
                    f"</tr>"
                    for _, r in df.iterrows()
                )
                return (
                    f'<div style="border:1px solid {BORDER};border-radius:8px;'
                    f'overflow:hidden;">'
                    f'<div style="background:{BLUE};color:white;padding:7px 12px;'
                    f'font-size:11px;font-weight:700;letter-spacing:1px;'
                    f'text-transform:uppercase;">{header}</div>'
                    f'<table style="width:100%;border-collapse:collapse;">{rows}</table>'
                    f'</div>'
                )

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(_summary_card(top5, "🟢  Strongest Hour × Day", True),
                            unsafe_allow_html=True)
            with col_b:
                st.markdown(_summary_card(bot5, "🔴  Weakest Hour × Day", False),
                            unsafe_allow_html=True)

            st.markdown(
                f"<div style='font-size:11px;color:{MUTED};margin-top:10px;'>"
                f"SSS% compares avg hourly sales for each (hour, weekday) combination "
                f"vs the same weekday 364 days prior. Color scale capped at ±{cap:.0f}%.</div>",
                unsafe_allow_html=True
            )

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="text-align:center;font-size:11px;color:{MUTED};margin-top:24px;
            border-top:1px solid {BORDER};padding-top:12px;">
  Operational hours shown: 10 AM – 9 PM ·
  SSS% vs same period 364 days prior · JM Valley Group · Vantedge Partners
</div>
""", unsafe_allow_html=True)
