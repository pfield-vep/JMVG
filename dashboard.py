"""
dashboard.py
Jersey Mike's Valley Group — Weekly BI Dashboard
Run with: py -m streamlit run dashboard.py
"""

import streamlit as st
import streamlit.components.v1 as components
import tempfile, json
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "jerseymikes.db")

SAN_DIEGO_STORE_IDS = ['20071', '20091', '20171', '20177', '20291', '20292', '20300']

def get_db_connection():
    """Returns (connection, dialect) — Supabase if secrets available, else SQLite."""
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
        import sqlite3
        return sqlite3.connect(DB_PATH), "sqlite"


st.set_page_config(
    page_title="Jersey Mike's | Valley Group",
    page_icon="🥖",
    layout="wide",
    initial_sidebar_state="collapsed"
)

RED     = "#EE3327"
BLUE    = "#134A7C"
WHITE   = "#FFFFFF"
LIGHT   = "#F5F6F8"
BORDER  = "#E0E3E8"
TEXT    = "#1a1a2e"
MUTED   = "#6B7280"
GREEN   = "#16a34a"
DANGER  = "#dc2626"
CHART_BG   = "#FFFFFF"
GRID_COLOR = "#E5E7EB"

PLOTLY_THEME = dict(
    plot_bgcolor=CHART_BG, paper_bgcolor=CHART_BG,
    font=dict(color=TEXT, family="Arial, sans-serif", size=13),
    xaxis=dict(gridcolor=GRID_COLOR, linecolor=BORDER, tickfont=dict(size=12, color=MUTED)),
    yaxis=dict(gridcolor=GRID_COLOR, linecolor=BORDER, tickfont=dict(size=12, color=MUTED)),
    dragmode='pan',
    modebar=dict(remove=['select2d', 'lasso2d', 'zoomIn2d', 'zoomOut2d',
                         'autoScale2d', 'resetScale2d', 'zoom2d',
                         'pan2d', 'toImage', 'sendDataToCloud']),
)
# Shared legend and margin — pass explicitly, never inside PLOTLY_THEME
DEFAULT_LEGEND = dict(
    bgcolor=WHITE, bordercolor=BORDER, borderwidth=1,
    font=dict(size=11, family='Arial'),
    orientation='h',          # horizontal legend — takes less vertical space
    yanchor='bottom', y=1.02, xanchor='right', x=1
)
DEFAULT_MARGIN = dict(l=40, r=20, t=55, b=80)

st.markdown(f"""
<style>
    /* Arial everywhere */
    html, body, [class*="css"] {{
        font-family: Arial, sans-serif !important;
        font-size: 15px !important;
        background-color: {WHITE};
    }}
    .stApp, .main {{ background-color: {WHITE} !important; }}
    .block-container {{ padding-top: 1rem !important; }}

    /* ── Sidebar: blue background, white text ──
       DO NOT touch [data-testid="collapsedControl"] — let Streamlit handle it natively */
    section[data-testid="stSidebar"] {{
        background-color: {BLUE} !important;
    }}
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown div,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span {{
        color: white !important;
        font-family: Arial, sans-serif !important;
        font-size: 14px !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox > div > div {{
        background-color: rgba(255,255,255,0.15) !important;
        border: 1px solid rgba(255,255,255,0.35) !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox svg {{
        fill: white !important;
    }}

    /* ── KPI Cards — fixed height, flex layout ── */
    .kpi-card {{
        background: {WHITE};
        border: 1px solid {BORDER};
        border-top: 4px solid {RED};
        border-radius: 8px;
        padding: 14px 16px 12px 16px;
        margin-bottom: 12px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.07);
        height: 120px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-sizing: border-box;
    }}
    .kpi-card-blue {{ border-top-color: {BLUE} !important; }}
    .kpi-label {{
        font-family: Arial, sans-serif !important;
        font-size: 11px !important;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: {MUTED} !important;
        font-weight: 700;
    }}
    .kpi-value {{
        font-family: Arial, sans-serif !important;
        font-size: 30px !important;
        font-weight: 700;
        line-height: 1.15;
        color: {TEXT};
    }}
    .kpi-value.green {{ color: {GREEN} !important; }}
    .kpi-value.red   {{ color: {DANGER} !important; }}
    .kpi-sub {{
        display: block;
        font-family: Arial, sans-serif !important;
        font-size: 12px !important;
        color: {MUTED} !important;
        min-height: 18px;
    }}
    .kpi-pos {{ color: {GREEN} !important; font-weight: 700 !important; }}
    .kpi-neg {{ color: {DANGER} !important; font-weight: 700 !important; }}
    .kpi-neutral {{ color: {MUTED} !important; }}

    /* ── Section headers ── */
    .section-header {{
        font-family: Arial, sans-serif !important;
        font-size: 11px !important;
        letter-spacing: 2px;
        text-transform: uppercase;
        color: {BLUE} !important;
        border-bottom: 2px solid {RED};
        padding-bottom: 5px;
        margin-bottom: 16px;
        margin-top: 24px;
        font-weight: 700;
    }}

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {WHITE} !important;
        border-bottom: 2px solid {BORDER};
    }}
    .stTabs [data-baseweb="tab"] {{
        font-family: Arial, sans-serif !important;
        font-size: 13px !important;
        font-weight: 700;
        color: {MUTED} !important;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        padding: 10px 20px;
    }}
    .stTabs [aria-selected="true"] {{
        color: {RED} !important;
        border-bottom: 2px solid {RED} !important;
        background: transparent !important;
    }}

    /* ── Tables & inputs ── */
    .stDataFrame td, .stDataFrame th {{
        font-family: Arial, sans-serif !important;
        font-size: 13px !important;
    }}
    .stRadio label, .stSelectbox label {{
        font-family: Arial, sans-serif !important;
        font-size: 14px !important;
    }}
    p, li, td, th {{
        font-family: Arial, sans-serif !important;
        font-size: 14px !important;
    }}

    .page-header {{
        border-bottom: 1px solid {BORDER};
        padding-bottom: 12px;
        margin-bottom: 8px;
    }}

    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    header {{ visibility: hidden; }}

    /* Hide plotly modebar on mobile — overlaps with title */
    @media (max-width: 768px) {{
        .modebar-container {{ display: none !important; }}
        .modebar {{ display: none !important; }}
    }}

    /* ── MOBILE RESPONSIVE ── */
    @media (max-width: 768px) {{

        /* Filter bar: stack vertically */
        [data-testid="stHorizontalBlock"] > div {{
            min-width: 45% !important;
            flex: 0 0 45% !important;
        }}

        /* KPI tiles: 2 across */
        .kpi-card {{
            height: auto !important;
            min-height: 100px;
            padding: 10px 12px 8px 12px;
        }}
        .kpi-value {{
            font-size: 22px !important;
        }}
        .kpi-label {{
            font-size: 9px !important;
        }}
        .kpi-sub {{
            font-size: 10px !important;
        }}

        /* Tabs: smaller text, scrollable */
        .stTabs [data-baseweb="tab"] {{
            font-size: 10px !important;
            padding: 8px 10px !important;
            letter-spacing: 0.3px !important;
        }}

        /* Charts: allow scroll/zoom, no clipping */
        [data-testid="stPlotlyChart"] {{
            overflow: visible !important;
        }}
        .js-plotly-plot .plotly {{
            touch-action: pan-y pinch-zoom !important;
        }}

        /* Section headers: smaller */
        .section-header {{
            font-size: 9px !important;
            letter-spacing: 1px !important;
        }}

        /* Block container: tighter padding on mobile */
        .block-container {{
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }}

        /* Legend: compact */
        .legend text {{
            font-size: 9px !important;
        }}
    }}
</style>
""", unsafe_allow_html=True)

# ── Sticky header via JS injection ───────────────────────────────────────────
import streamlit.components.v1 as _sc
_sc.html("""
<script>
(function() {
    function makeSticky() {
        // Find the main block container
        var blocks = window.parent.document.querySelectorAll('[data-testid="stVerticalBlock"]');
        if (!blocks.length) return;

        // The first two blocks are the blue nav bar + filter row — freeze both
        for (var i = 0; i < Math.min(2, blocks.length); i++) {
            var el = blocks[i];
            el.style.position = 'sticky';
            el.style.top = (i === 0) ? '0px' : '60px';
            el.style.zIndex = (999 - i).toString();
            el.style.backgroundColor = '#ffffff';
            el.style.paddingBottom = '8px';
            el.style.boxShadow = '0 2px 8px rgba(0,0,0,0.08)';
        }
    }
    // Run immediately and after a short delay to catch Streamlit's render cycle
    makeSticky();
    setTimeout(makeSticky, 500);
    setTimeout(makeSticky, 1500);
})();
</script>
""", height=0, scrolling=False)

STORE_COORDS = {
    '20156': (34.1558, -118.3780, '4821 Lankershim Blvd, North Hollywood CA 91601'),
    '20218': (34.2598, -118.4714, '10388 Sepulveda Blvd, Mission Hills CA 91345'),
    '20267': (34.2244, -118.5000, '8420 Balboa Blvd, Northridge CA 91325'),
    '20294': (34.1784, -118.3345, '531 N Hollywood Way, Burbank CA 91505'),
    '20026': (34.2390, -118.5321, '19350 Nordhoff St, Northridge CA 91324'),
    '20311': (34.2797, -118.5558, '20101 W Rinaldi St, Porter Ranch CA 91326'),
    '20352': (34.2836, -118.4359, '1120 Truman St, San Fernando CA 91340'),
    '20363': (34.1684, -118.5987, '21506 Victory Blvd, Woodland Hills CA 91367'),
    '20273': (34.2436, -116.9114, '42173 Big Bear Blvd, Big Bear Lake CA 92315'),
    '20366': (34.2006, -118.3345, '3015 N Hollywood Way, Burbank CA 91505'),
    '20011': (34.1705, -118.8312, '3825 E Thousand Oaks Blvd, Westlake Village CA 91362'),
    '20255': (34.2145, -118.9101, '2000 Avenida De Los Arboles, Thousand Oaks CA 91362'),
    '20048': (34.1791, -118.8748, '605 Janss Road, Thousand Oaks CA 91360'),
    '20245': (34.1797, -118.9303, '761 Wendy Dr, Newbury Park CA 91320'),
    '20381': (34.3001, -118.3987, '12980 Foothill Blvd, Sylmar CA 91342'),
    '20116': (34.1567, -118.4987, '16350 Ventura Blvd, Encino CA 91436'),
    '20388': (34.2503, -117.1856, '28200 Hwy 189, Lake Arrowhead CA 92352'),
    '20075': (34.4279, -119.8608, '7034 Market Place Dr, Goleta CA 93117'),
    '20335': (34.4401, -119.8278, '163 N Fairview Ave, Goleta CA 93117'),
    '20360': (34.4348, -119.7805, '199 S Turnpike Rd, Santa Barbara CA 93111'),
    '20424': (34.1478, -118.3823, '11990 Ventura Blvd, Studio City CA 91604'),
    '20177': (33.5636, -117.1490, '29910 Murrieta Hot Springs Rd, Murrieta CA 92563'),
    '20171': (33.5174, -117.1543, '26475 Ynez Road, Temecula CA 92591'),
    '20091': (33.4785, -117.0827, '32068 Temecula Parkway, Temecula CA 92592'),
    '20071': (33.1367, -117.0700, '1829 Centre City Pkwy, Escondido CA 92025'),
    '20300': (33.1285, -117.0456, '1497 East Valley Pkwy, Escondido CA 92027'),
    '20292': (33.0422, -116.8734, '1664 Main Street, Ramona CA 92065'),
    '20291': (33.5363, -117.1308, '30680 Rancho California Rd, Temecula CA 92591'),
    '20013': (34.6140, -120.1921, '211 E Highway 246, Buellton CA 93427'),
}

# Region color palette — consistent across ALL charts
REGION_COLORS = {
    'Los Angeles':                    RED,       # Jersey Mike's red
    'Santa Barbara':                  BLUE,      # Jersey Mike's blue
    'Santa Barbara / San Luis Ob':    '#F5A623', # Orange — clearly distinct
    'San Diego':                      '#6B21A8', # Purple
}
DEFAULT_REGION_COLOR = '#AAAAAA'

def region_color(co_op_val):
    if not co_op_val: return DEFAULT_REGION_COLOR
    val = str(co_op_val).replace('\n', ' ').strip().lower()
    # Sort keys longest-first so 'Santa Barbara / San Luis Ob' matches before 'Santa Barbara'
    for k in sorted(REGION_COLORS.keys(), key=len, reverse=True):
        if k.lower() in val:
            return REGION_COLORS[k]
    return DEFAULT_REGION_COLOR

STORE_NAMES = {
    '20156': 'North Hollywood', '20218': 'Mission Hills', '20267': 'Balboa',
    '20294': 'Toluca', '20026': 'Tampa', '20311': 'Porter Ranch',
    '20352': 'San Fernando', '20363': 'Warner Center', '20273': 'Big Bear',
    '20366': 'Burbank North', '20011': 'Westlake', '20255': 'Arboles',
    '20048': 'Janss', '20245': 'Wendy', '20381': 'Sylmar',
    '20116': 'Encino', '20388': 'Lake Arrowhead', '20075': 'Isla Vista',
    '20335': 'Goleta', '20360': 'Santa Barbara', '20424': 'Studio City',
    '20177': 'SD1', '20171': 'SD2', '20091': 'SD3', '20071': 'SD4',
    '20300': 'SD5', '20292': 'SD6', '20291': 'SD7',
    '20013': 'Buellton',
}

@st.cache_data(ttl=300)
def load_data():
    conn, _ = get_db_connection()
    stores = pd.read_sql("SELECT * FROM stores", conn)
    stores['co_op'] = stores['co_op'].str.replace('\n', ' ').str.strip()
    sales = pd.read_sql("""
        SELECT ws.*, s.city, s.co_op, s.franchisee
        FROM weekly_sales ws JOIN stores s ON ws.store_id = s.store_id
        ORDER BY ws.week_ending, ws.store_id
    """, conn)
    sales['co_op'] = sales['co_op'].str.replace('\n', ' ').str.strip()
    bread = pd.read_sql("""
        SELECT wb.*, s.city, s.co_op
        FROM weekly_bread wb JOIN stores s ON wb.store_id = s.store_id
        ORDER BY wb.week_ending, wb.store_id
    """, conn)
    bread['co_op'] = bread['co_op'].str.replace('\n', ' ').str.strip()
    loyalty = pd.read_sql("""
        SELECT wl.*, s.city, s.co_op
        FROM weekly_loyalty wl JOIN stores s ON wl.store_id = s.store_id
        ORDER BY wl.week_ending, wl.store_id
    """, conn)
    loyalty['co_op'] = loyalty['co_op'].str.replace('\n', ' ').str.strip()
    mkt = pd.read_sql("""
        SELECT * FROM weekly_market_totals
        ORDER BY week_ending, market
    """, conn)
    bread_totals = pd.read_sql("""
        SELECT * FROM weekly_bread_totals
        ORDER BY week_ending, market
    """, conn)
    conn.close()
    return stores, sales, bread, loyalty, mkt, bread_totals

stores_df, sales_df, bread_df, loyalty_df, mkt_df, bread_totals_df = load_data()

# ── Top filter bar ───────────────────────────────────────────────────────────
st.markdown(f"""
    <div style='background:{BLUE}; padding:14px 24px 10px 24px;
                margin:-1rem -1rem 1.5rem -1rem; display:flex;
                align-items:center; gap:12px;'>
        <div style='font-family:Arial,sans-serif; font-size:20px;
                    font-weight:800; color:white; margin-right:16px;
                    white-space:nowrap;'>
            🥖 JERSEY MIKE'S
            <span style='font-size:12px; font-weight:400;
                         color:rgba(255,255,255,0.6); margin-left:8px;
                         text-transform:uppercase; letter-spacing:1px;'>
                Valley Group
            </span>
        </div>
    </div>
""", unsafe_allow_html=True)

weeks_available = sorted(sales_df['week_ending'].unique(), reverse=True)

fc1, fc_grp, fc2, fc3, fc4 = st.columns([1.2, 1.2, 1.2, 2, 0.6])
with fc1:
    selected_week = st.selectbox("📅  WEEK ENDING", weeks_available)
with fc_grp:
    groupings = ["All Stores", "Organic Stores", "Acquisition Stores"]
    selected_grouping = st.selectbox("🏷️  GROUPING", groupings)
with fc2:
    markets = ["All Markets"] + sorted(stores_df['co_op'].unique().tolist())
    selected_market = st.selectbox("🗺️  MARKET", markets)

all_stores = stores_df.copy()
if selected_grouping == "Organic Stores":
    all_stores = all_stores[~all_stores['store_id'].isin(SAN_DIEGO_STORE_IDS)]
elif selected_grouping == "Acquisition Stores":
    all_stores = all_stores[all_stores['store_id'].isin(SAN_DIEGO_STORE_IDS)]
if selected_market != "All Markets":
    all_stores = all_stores[all_stores['co_op'].str.replace('\n',' ').str.strip() == selected_market.replace('\n',' ').strip()]
store_options = {f"{r['store_id']} — {STORE_NAMES.get(r['store_id'], r['city'])}": r['store_id']
                 for _, r in all_stores.iterrows()}
st.session_state['selected_grouping'] = selected_grouping
with fc3:
    selected_store_label = st.selectbox("🏪  STORE (detail view)",
                                        ["All Stores"] + list(store_options.keys()))
selected_store = store_options.get(selected_store_label)
with fc4:
    st.markdown(f"""
        <div style='font-family:Arial,sans-serif; font-size:11px;
                    color:{MUTED}; padding-top:28px; line-height:1.8;'>
            {len(weeks_available)} wks &nbsp;·&nbsp; {len(stores_df)} stores
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='margin:0 0 1rem 0; border:none; border-top:1px solid #E0E3E8;'>",
            unsafe_allow_html=True)

def filter_df(df, week, market, grouping="All Stores"):
    d = df[df['week_ending'] == week].copy()
    if grouping == "Organic Stores":
        d = d[~d['store_id'].isin(SAN_DIEGO_STORE_IDS)]
    elif grouping == "Acquisition Stores":
        d = d[d['store_id'].isin(SAN_DIEGO_STORE_IDS)]
    if market != "All Markets":
        d = d[d['co_op'].str.replace('\n',' ').str.strip() == market.replace('\n',' ').strip()]
    return d

week_sales   = filter_df(sales_df,   selected_week, selected_market, selected_grouping)
week_bread   = filter_df(bread_df,   selected_week, selected_market, selected_grouping)
week_loyalty = filter_df(loyalty_df, selected_week, selected_market, selected_grouping)

# Market totals for selected week — use CA/Grand Total row when All Markets
week_mkt = mkt_df[mkt_df['week_ending'] == selected_week].copy()
week_bread_totals = bread_totals_df[bread_totals_df['week_ending'] == selected_week].copy()
if len(week_bread_totals) == 0:
    # fallback: use most recent available week
    most_recent_bt = bread_totals_df['week_ending'].max() if len(bread_totals_df) > 0 else None
    if most_recent_bt:
        week_bread_totals = bread_totals_df[bread_totals_df['week_ending'] == most_recent_bt].copy()
if selected_market in ("All Markets", "!Organic Stores"):
    week_mkt_total = week_mkt[week_mkt['market'].str.upper().str.contains('CA|GRAND', na=False)]                        .sort_values('store_count', ascending=False).head(1)
else:
    week_mkt = week_mkt[week_mkt['market'].str.contains(
        selected_market.split('/')[0].strip(), case=False, na=False)]
    week_mkt_total = week_mkt.sort_values('store_count', ascending=False).head(1)

st.markdown(f"""
    <div class="page-header">
        <span style='font-family:Arial,sans-serif; font-size:28px;
                     font-weight:800; color:{TEXT};'>
            {selected_grouping if selected_grouping != "All Stores" else ""}{" · " if selected_grouping != "All Stores" and selected_market != "All Markets" else ""}{selected_market if selected_market != "All Markets" else ("All Markets" if selected_grouping == "All Stores" else "")}
        </span>
        <span style='font-family:Arial,sans-serif; font-size:13px;
                     letter-spacing:1px; color:{MUTED};
                     text-transform:uppercase; margin-left:14px;'>
            Week ending {selected_week} &nbsp;·&nbsp; {len(week_sales)} stores
        </span>
    </div>
""", unsafe_allow_html=True)

def fmt_delta(val):
    """Return colored span for a percentage delta value."""
    try:
        d = float(val)
        if pd.isna(d):
            return '<span class="kpi-sub kpi-neutral">YTD —</span>'
        color = GREEN if d >= 0 else DANGER
        arrow = "▲" if d >= 0 else "▼"
        return f'<span class="kpi-sub" style="color:{color}; font-weight:600;">{arrow} {abs(d):.1f}%</span>'
    except:
        return '<span class="kpi-sub kpi-neutral">YTD —</span>'

def kpi(label, week_val, ytd_val=None, week_prefix="", week_suffix="",
        ytd_prefix="", ytd_suffix="", blue=False, orange=False, sss_color=False):
    """
    Dual-row KPI card.
    - Top (large):    week_val  — current week
    - Bottom (small): ytd_val   — year to date
    For SSS/ticket metrics, sss_color=True applies green/red to both values.
    """
    accent = "kpi-card-blue" if blue else ("kpi-card-orange" if orange else "")

    # Top value color — green if positive, red if negative for SSS metrics
    if sss_color:
        try:
            wv = float(str(week_val).replace("%","").replace("+","").replace(",","").strip())
            top_color = GREEN if wv >= 0 else DANGER
        except:
            top_color = MUTED
    else:
        top_color = TEXT

    # Bottom row
    if ytd_val is None:
        bottom_html = '<span class="kpi-sub kpi-neutral">&nbsp;</span>'
    else:
        try:
            yv_raw = float(str(ytd_val).replace("%","").replace("+","").replace("$","").replace(",",""))
            if sss_color:
                yc = GREEN if yv_raw >= 0 else DANGER
                arrow = "▲" if yv_raw >= 0 else "▼"
                bottom_html = f'<span class="kpi-sub" style="color:{yc}; font-weight:700;">YTD {arrow} {ytd_prefix}{abs(yv_raw):.1f}{ytd_suffix}</span>'
            else:
                bottom_html = f'<span class="kpi-sub kpi-neutral">YTD {ytd_prefix}{yv_raw:,.0f if ytd_suffix=="" else ".1f"}{ytd_suffix}</span>'
        except:
            bottom_html = f'<span class="kpi-sub kpi-neutral">YTD {ytd_prefix}{ytd_val}{ytd_suffix}</span>'

    # Determine color class for value div
    if sss_color:
        try:
            wv2 = float(str(week_val).replace("%","").replace("+","").replace(",","").strip())
            color_class = "green" if wv2 >= 0 else "red"
        except:
            color_class = ""
    else:
        color_class = ""

    return (
        f'<div class="kpi-card {accent}">' +
        f'<div class="kpi-label">{label}</div>' +
        f'<div class="kpi-value {color_class}">{week_prefix}{week_val}{week_suffix}</div>' +
        bottom_html +
        '</div>'
    )

def color_pct(val):
    if isinstance(val, float) and not pd.isna(val):
        return f'color: {GREEN}' if val > 0 else f'color: {DANGER}'
    return ''

tab1, tab6, tab5, tab3, tab4, tab2 = st.tabs([
    "OVERVIEW", "TRENDS", "MAP", "BREAD & OPS", "LOYALTY", "STORE DETAIL"
])

# ── TAB 1: OVERVIEW ───────────────────────────────────────────────────────────
with tab1:
    # ── Totals from weekly_sales ──
    total_sales  = week_sales['net_sales'].sum()
    import math as _math
    def safe_mean(series):
        v = series.mean()
        return None if (v is None or (isinstance(v, float) and _math.isnan(v))) else v
    avg_loyalty  = safe_mean(week_sales['loyalty_sales_pct'])
    avg_online   = safe_mean(week_sales['online_sales_pct'])
    avg_3p       = safe_mean(week_sales['third_party_sales_pct'])
    total_bread  = week_bread['bread_count'].sum()
    fytd_sales   = week_sales['fytd_net_sales'].sum()
    fytd_loyalty = week_sales['loyalty_sales_pct'].mean()
    fytd_online  = week_sales['online_sales_pct'].mean()
    fytd_3p      = week_sales['third_party_sales_pct'].mean()
    fytd_bread   = week_bread['fytd_bread_count'].sum() if 'fytd_bread_count' in week_bread.columns else None

    # ── SSS / Ticket / Txn from market totals (correct comparable-store methodology) ──
    def mkt_val(col):
        import math
        # Acquisition Stores have no PDF data — return None for all PDF-derived metrics
        if selected_grouping == "Acquisition Stores":
            return None
        if len(week_mkt_total) == 0: return None
        v = week_mkt_total[col].values[0]
        if v is None: return None
        try:
            fv = float(v)
            return None if math.isnan(fv) else fv
        except: return None

    avg_sss  = mkt_val('sss_pct')
    avg_tkt  = mkt_val('same_store_ticket_pct')
    avg_txn  = mkt_val('same_store_txn_pct')
    fytd_sss = mkt_val('fytd_sss_pct')
    fytd_tkt = mkt_val('fytd_same_store_ticket')
    fytd_txn = mkt_val('fytd_same_store_txn_pct')

    def fmt_sss(v):
        if v is None: return "—"
        try: return f"{float(v):+.1f}"
        except: return "—"

    # Wrap all 8 KPI tiles in a CSS grid — desktop: 4 col, mobile: 2 col
    st.markdown(f"""
        <style>
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 12px;
            margin-bottom: 16px;
        }}
        @media (max-width: 768px) {{
            .kpi-grid {{
                grid-template-columns: repeat(2, 1fr) !important;
                gap: 8px;
            }}
        }}
        </style>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(kpi("Net Sales",
                        f"{total_sales:,.0f}", week_prefix="$",
                        ytd_val=f"{fytd_sales:,.0f}", ytd_prefix="$"),
                    unsafe_allow_html=True)
        st.markdown(kpi("Bread",
                        f"{total_bread:,}",
                        ytd_val=f"{int(fytd_bread):,}" if fytd_bread else "—"),
                    unsafe_allow_html=True)
    with col2:
        st.markdown(kpi("Same Store Sales",
                        fmt_sss(avg_sss), week_suffix="%",
                        ytd_val=fytd_sss, ytd_suffix="%",
                        blue=True, sss_color=True),
                    unsafe_allow_html=True)
        st.markdown(kpi("Same Store Avg Ticket",
                        fmt_sss(avg_txn), week_suffix="%",
                        ytd_val=fytd_txn, ytd_suffix="%",
                        blue=True, sss_color=True),
                    unsafe_allow_html=True)
    with col3:
        st.markdown(kpi("Same Store Transactions",
                        fmt_sss(avg_tkt), week_suffix="%",
                        ytd_val=fytd_tkt, ytd_suffix="%",
                        blue=True, sss_color=True),
                    unsafe_allow_html=True)
        st.markdown(kpi("Loyalty Sales %",
                        f"{avg_loyalty:.1f}" if avg_loyalty is not None else "—", week_suffix="%" if avg_loyalty is not None else "",
                        ytd_val=f"{fytd_loyalty:.1f}" if fytd_loyalty is not None else "—", ytd_suffix="%" if fytd_loyalty is not None else "",
                        orange=True),
                    unsafe_allow_html=True)
    with col4:
        st.markdown(kpi("Online Sales %",
                        f"{avg_online:.1f}" if avg_online is not None else "—", week_suffix="%" if avg_online is not None else "",
                        ytd_val=f"{fytd_online:.1f}" if fytd_online is not None else "—", ytd_suffix="%" if fytd_online is not None else "",
                        orange=True),
                    unsafe_allow_html=True)
        st.markdown(kpi("3rd Party Sales %",
                        f"{avg_3p:.1f}" if avg_3p is not None else "—", week_suffix="%" if avg_3p is not None else "",
                        ytd_val=f"{fytd_3p:.1f}" if fytd_3p is not None else "—", ytd_suffix="%" if fytd_3p is not None else "",
                        orange=True),
                    unsafe_allow_html=True)

    # ── REGIONAL DATA PREP ────────────────────────────────────────────────────
    reg_raw = week_mkt[~week_mkt['market'].str.upper().str.match(r'^CA$|^CA\s|GRAND', na=False)].copy()
    reg_raw = reg_raw[reg_raw['store_count'].notna() & (reg_raw['store_count'] > 0)].copy()
    reg_raw['label'] = reg_raw['market'] + ' (' + reg_raw['store_count'].astype(int).astype(str) + ')'
    reg_raw['color'] = reg_raw['market'].apply(region_color)

    def make_regional_vertical(df, col, title, hover_label, system_avg=None, show_legend=False):
        """Build a vertical bar chart for a regional metric, sorted high to low."""
        d = df.dropna(subset=[col]).sort_values(col, ascending=False).copy()
        fig = go.Figure()
        for _, row in d.iterrows():
            fig.add_trace(go.Bar(
                name=row['market'],
                x=[row['label']],
                y=[row[col]],
                marker_color=row['color'],
                marker_opacity=0.88,
                text=[f"{row[col]:+.1f}%"],
                textposition='outside',
                textfont=dict(size=14, color=TEXT, family='Arial'),
                hovertemplate=f"<b>%{{x}}</b><br>{hover_label}: %{{y:.1f}}%<extra></extra>",
                showlegend=show_legend,
            ))
        fig.add_hline(y=0, line_color=BORDER, line_width=1.5)
        if system_avg is not None:
            try:
                _sa = float(system_avg)
                fig.add_hline(y=_sa, line_color=TEXT, line_width=2.5, line_dash='dash',
                    annotation_text=f"System {_sa:+.1f}%",
                    annotation_position="right",
                    annotation_font=dict(size=11, color=TEXT, family='Arial'))
            except: pass
        fig.update_layout(**PLOTLY_THEME, height=300,
            margin=dict(l=20, r=80, t=45, b=50),
            showlegend=show_legend,
            legend=dict(orientation='h', yanchor='bottom', y=1.05,
                       xanchor='center', x=0.5,
                       font=dict(size=11, family='Arial'),
                       bgcolor='rgba(255,255,255,0.9)'),
            title=dict(text=title, font=dict(size=14, color=TEXT, family='Arial')),
            barmode='group')
        fig.update_xaxes(tickfont=dict(size=11, family='Arial', color=TEXT))
        fig.update_yaxes(tickfont=dict(size=11, family='Arial'),
                         zeroline=True, zerolinecolor=BORDER, zerolinewidth=1.5)
        return fig

    # ── Pull CA-level system totals for avg lines ────────────────────────────
    sys_sss     = mkt_val('sss_pct')
    sys_txn     = mkt_val('same_store_ticket_pct')
    sys_ticket  = mkt_val('same_store_txn_pct')
    sys_fytd_sss    = mkt_val('fytd_sss_pct')
    sys_fytd_txn    = mkt_val('fytd_same_store_ticket')
    sys_fytd_ticket = mkt_val('fytd_same_store_txn_pct')

    # ── WEEKLY: Sales | Transactions | Avg Ticket ────────────────────────────
    st.markdown('<div class="section-header">SAME STORE METRICS BY REGION — WEEKLY</div>', unsafe_allow_html=True)

    # Shared legend for regional charts
    _legend_items = ' '.join([
        f"<span style='display:inline-flex;align-items:center;margin-right:16px;'>"
        f"<span style='width:14px;height:14px;border-radius:3px;background:{row['color']};display:inline-block;margin-right:6px;'></span>"
        f"<span style='font-family:Arial;font-size:12px;color:{TEXT};'>{row['market']}</span></span>"
        for _, row in reg_raw.iterrows()
    ])
    st.markdown(f"<div style='margin-bottom:8px;margin-top:4px;'>{_legend_items}</div>",
                unsafe_allow_html=True)

    rw1, rw2, rw3 = st.columns(3)
    with rw1:
        st.plotly_chart(make_regional_vertical(
            reg_raw, 'sss_pct',
            f"SS Sales % — Week ending {selected_week}", "SS Sales %",
            system_avg=sys_sss),
            use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})
    with rw2:
        st.plotly_chart(make_regional_vertical(
            reg_raw, 'same_store_ticket_pct',
            f"SS Transactions % — Week ending {selected_week}", "SS Transactions %",
            system_avg=sys_txn),
            use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})
    with rw3:
        st.plotly_chart(make_regional_vertical(
            reg_raw, 'same_store_txn_pct',
            f"SS Avg Ticket % — Week ending {selected_week}", "SS Avg Ticket %",
            system_avg=sys_ticket),
            use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    # ── YTD: Sales | Transactions | Avg Ticket ───────────────────────────────
    st.markdown('<div class="section-header">SAME STORE METRICS BY REGION — YEAR TO DATE</div>', unsafe_allow_html=True)
    st.markdown(f"<div style='margin-bottom:8px;margin-top:4px;'>{_legend_items}</div>",
                unsafe_allow_html=True)
    ry1, ry2, ry3 = st.columns(3)
    with ry1:
        st.plotly_chart(make_regional_vertical(
            reg_raw, 'fytd_sss_pct',
            f"SS Sales % — YTD (as of {selected_week})", "FYTD SS Sales %",
            system_avg=sys_fytd_sss),
            use_container_width=True)
    with ry2:
        st.plotly_chart(make_regional_vertical(
            reg_raw, 'fytd_same_store_ticket',
            f"SS Transactions % — YTD (as of {selected_week})", "FYTD SS Transactions %",
            system_avg=sys_fytd_txn),
            use_container_width=True)
    with ry3:
        st.plotly_chart(make_regional_vertical(
            reg_raw, 'fytd_same_store_txn_pct',
            f"SS Avg Ticket % — YTD (as of {selected_week})", "FYTD SS Avg Ticket %",
            system_avg=sys_fytd_ticket),
            use_container_width=True)

    # ── SSS BY STORE ──────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">SAME STORE SALES % BY STORE</div>', unsafe_allow_html=True)

    sss_data = week_sales[['store_id', 'sss_pct', 'fytd_sss_pct', 'co_op']].copy()
    sss_data['sss_pct']     = pd.to_numeric(sss_data['sss_pct'],     errors='coerce')
    sss_data['fytd_sss_pct']= pd.to_numeric(sss_data['fytd_sss_pct'],errors='coerce')
    sss_data['co_op']       = sss_data['co_op'].str.replace('\n',' ').str.strip()
    sss_data['store_name']  = sss_data['store_id'].map(STORE_NAMES).fillna(sss_data['store_id'])
    sss_data['label']       = sss_data['store_id'] + ' · ' + sss_data['store_name']
    sss_week = sss_data.dropna(subset=['sss_pct']).sort_values('sss_pct', ascending=True)
    sss_fytd = sss_data.dropna(subset=['fytd_sss_pct']).sort_values('fytd_sss_pct', ascending=True)

    n_stores = max(len(sss_week), len(sss_fytd))
    chart_h   = max(400, n_stores * 26)

    # Shared legend for SSS by store
    _sss_regions = sorted(sss_week['co_op'].str.replace('\n',' ').str.strip().unique())
    _legend_pills = " &nbsp; ".join([
        f"<span style='display:inline-flex;align-items:center;gap:5px;margin-right:8px;'>"
        f"<span style='width:12px;height:12px;border-radius:2px;background:{region_color(r)};display:inline-block;'></span>"
        f"<span style='font-size:12px;font-family:Arial;color:{TEXT};'>{r}</span></span>"
        for r in _sss_regions
    ])
    st.markdown(f"<div style='margin-bottom:8px;'>{_legend_pills}</div>", unsafe_allow_html=True)

    # Weekly — full width
    fig_sw = go.Figure()
    for region, grp in sss_week.groupby('co_op'):
        region_clean = str(region).replace('\n',' ').strip()
        fig_sw.add_trace(go.Bar(
            name=region_clean, showlegend=False,
            x=grp['sss_pct'], y=grp['label'], orientation='h',
            marker_color=region_color(region_clean), marker_opacity=0.88,
            text=[f"{v:+.1f}%" for v in grp['sss_pct']],
            textposition='outside', textfont=dict(size=11, color=TEXT, family='Arial'),
            hovertemplate='<b>%{y}</b><br>SSS: %{x:.1f}%<extra></extra>'
        ))
    fig_sw.add_vline(x=0, line_color=BORDER, line_width=1.5)
    if avg_sss is not None:
        try:
            _sys_sss = float(avg_sss)
            fig_sw.add_vline(x=_sys_sss, line_color=TEXT, line_width=2.5, line_dash='dash',
                annotation_text=f"System {_sys_sss:+.1f}%", annotation_position="top",
                annotation_font=dict(size=11, color=TEXT, family='Arial'))
        except: pass
    fig_sw.update_layout(**PLOTLY_THEME, height=chart_h,
        margin=dict(l=10, r=70, t=45, b=20), showlegend=False,
        title=dict(text=f"Week ending {selected_week}", font=dict(size=15, color=TEXT, family='Arial')))
    fig_sw.update_xaxes(tickfont=dict(size=11, family='Arial'))
    fig_sw.update_yaxes(tickfont=dict(size=11, family='Arial', color=TEXT))
    st.plotly_chart(fig_sw, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    # YTD — full width below
    fig_sf = go.Figure()
    for region, grp in sss_fytd.groupby('co_op'):
        region_clean = str(region).replace('\n',' ').strip()
        fig_sf.add_trace(go.Bar(
            name=region_clean, showlegend=False,
            x=grp['fytd_sss_pct'], y=grp['label'], orientation='h',
            marker_color=region_color(region_clean), marker_opacity=0.88,
            text=[f"{v:+.1f}%" for v in grp['fytd_sss_pct']],
            textposition='outside', textfont=dict(size=11, color=TEXT, family='Arial'),
            hovertemplate='<b>%{y}</b><br>FYTD SSS: %{x:.1f}%<extra></extra>'
        ))
    fig_sf.add_vline(x=0, line_color=BORDER, line_width=1.5)
    if fytd_sss is not None:
        try:
            _sys_fytd = float(fytd_sss)
            fig_sf.add_vline(x=_sys_fytd, line_color=TEXT, line_width=2.5, line_dash='dash',
                annotation_text=f"System {_sys_fytd:+.1f}%", annotation_position="top",
                annotation_font=dict(size=11, color=TEXT, family='Arial'))
        except: pass
    fig_sf.update_layout(**PLOTLY_THEME, height=chart_h,
        margin=dict(l=10, r=70, t=45, b=20), showlegend=False,
        title=dict(text=f"Year to Date (as of {selected_week})", font=dict(size=15, color=TEXT, family='Arial')))
    fig_sf.update_xaxes(tickfont=dict(size=11, family='Arial'))
    fig_sf.update_yaxes(tickfont=dict(size=11, family='Arial', color=TEXT))
    st.plotly_chart(fig_sf, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    st.markdown('<div class="section-header">NET SALES BY STORE</div>', unsafe_allow_html=True)
    # Shared legend for Net Sales
    _ns = week_sales[['store_id', 'net_sales', 'co_op']].copy()
    _ns['label'] = _ns['store_id'] + ' · ' + _ns['store_id'].map(STORE_NAMES).fillna('')
    _ns['region'] = _ns['co_op'].str.replace('\n',' ').str.strip()
    _ns_regions = sorted(_ns['region'].unique())
    _ns_pills = " &nbsp; ".join([
        f"<span style='display:inline-flex;align-items:center;gap:5px;margin-right:8px;'>"
        f"<span style='width:12px;height:12px;border-radius:2px;background:{region_color(r)};display:inline-block;'></span>"
        f"<span style='font-size:12px;font-family:Arial;color:{TEXT};'>{r}</span></span>"
        for r in _ns_regions
    ])
    st.markdown(f"<div style='margin-bottom:8px;'>{_ns_pills}</div>", unsafe_allow_html=True)

    # Weekly Net Sales — full width
    ns = _ns.sort_values('net_sales', ascending=False)
    fig2 = go.Figure()
    for region, grp in ns.groupby('region'):
        fig2.add_trace(go.Bar(
            name=region, showlegend=False,
            x=grp['label'], y=grp['net_sales'],
            marker_color=region_color(region), marker_opacity=0.9,
            hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
        ))
    fig2.update_layout(**PLOTLY_THEME, height=420, barmode='overlay', showlegend=False,
                       title=dict(text=f"Weekly Net Sales — Week ending {selected_week}",
                                  font=dict(size=15, color=TEXT, family='Arial')),
                       xaxis_tickangle=-40, xaxis_tickfont=dict(size=10),
                       margin=dict(l=40, r=20, t=45, b=60))
    st.plotly_chart(fig2, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    # YTD Net Sales — full width below
    ns2 = week_sales[['store_id', 'fytd_net_sales', 'co_op']].copy()
    ns2['label'] = ns2['store_id'] + ' · ' + ns2['store_id'].map(STORE_NAMES).fillna('')
    ns2['region'] = ns2['co_op'].str.replace('\n',' ').str.strip()
    ns2 = ns2.sort_values('fytd_net_sales', ascending=False)
    fig2b = go.Figure()
    for region, grp in ns2.groupby('region'):
        fig2b.add_trace(go.Bar(
            name=region, showlegend=False,
            x=grp['label'], y=grp['fytd_net_sales'],
            marker_color=region_color(region), marker_opacity=0.9,
            hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
        ))
    fig2b.update_layout(**PLOTLY_THEME, height=420, barmode='overlay', showlegend=False,
                        title=dict(text=f"YTD Net Sales (as of {selected_week})",
                                   font=dict(size=15, color=TEXT, family='Arial')),
                        xaxis_tickangle=-40, xaxis_tickfont=dict(size=10),
                        margin=dict(l=40, r=20, t=45, b=60))
    st.plotly_chart(fig2b, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    st.markdown('<div class="section-header">AVERAGE SALES CHANNEL MIX</div>', unsafe_allow_html=True)
    don_a, don_b = st.columns(2)
    with don_a:
        ov = week_sales['online_sales_pct'].mean()
        tv = week_sales['third_party_sales_pct'].mean()
        iv = max(0, 100 - ov - tv)
        fig3 = go.Figure(go.Pie(
            labels=['Online', '3rd Party', 'In-Store'],
            values=[ov, tv, iv],
            hole=0.55,
            marker_colors=[RED, BLUE, '#CCCCCC'],
            textfont=dict(size=15, color=WHITE, family='Arial'),
            hovertemplate='%{label}: %{value:.1f}%<extra></extra>',
            textinfo='label+percent',
        ))
        fig3.add_annotation(text=f"<b>{iv:.0f}%</b><br>In-Store",
                            x=0.5, y=0.5, showarrow=False,
                            font=dict(size=18, color=TEXT, family='Arial'))
        fig3.update_layout(**PLOTLY_THEME, height=450, margin=dict(l=20,r=20,t=60,b=20),
                           title=dict(text=f"Weekly Channel Mix — Week ending {selected_week}",
                                      font=dict(size=16, color=TEXT, family='Arial')),
                           legend=DEFAULT_LEGEND)
        st.plotly_chart(fig3, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    with don_b:
        ov2 = week_sales['online_sales_pct'].mean()   # reuse weekly — no FYTD channel split stored
        tv2 = week_sales['third_party_sales_pct'].mean()
        iv2 = max(0, 100 - ov2 - tv2)
        # Pull FYTD averages from market totals if available
        if len(week_mkt_total) > 0 and 'online_sales_pct' in week_mkt_total.columns:
            try:
                ov2 = float(week_mkt_total['online_sales_pct'].values[0])
                tv2 = float(week_mkt_total['third_party_sales_pct'].values[0])
                iv2 = max(0, 100 - ov2 - tv2)
            except: pass
        fig3b = go.Figure(go.Pie(
            labels=['Online', '3rd Party', 'In-Store'],
            values=[ov2, tv2, iv2],
            hole=0.55,
            marker_colors=[RED, BLUE, '#CCCCCC'],
            textfont=dict(size=15, color=WHITE, family='Arial'),
            hovertemplate='%{label}: %{value:.1f}%<extra></extra>',
            textinfo='label+percent',
        ))
        fig3b.add_annotation(text=f"<b>{iv2:.0f}%</b><br>In-Store",
                             x=0.5, y=0.5, showarrow=False,
                             font=dict(size=18, color=TEXT, family='Arial'))
        fig3b.update_layout(**PLOTLY_THEME, height=450, margin=dict(l=20,r=20,t=60,b=20),
                            title=dict(text=f"YTD Channel Mix (as of {selected_week})",
                                       font=dict(size=16, color=TEXT, family='Arial')),
                            legend=DEFAULT_LEGEND)
        st.plotly_chart(fig3b, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

# ── TAB 2: STORE DETAIL ───────────────────────────────────────────────────────
with tab2:
    st.markdown('<div class="section-header">ALL STORES — THIS WEEK</div>', unsafe_allow_html=True)
    display = week_sales[['store_id', 'city', 'co_op', 'net_sales', 'sss_pct',
                           'same_store_ticket_pct', 'avg_daily_bread', 'online_sales_pct',
                           'third_party_sales_pct', 'loyalty_sales_pct',
                           'fytd_net_sales', 'fytd_weekly_auv', 'fytd_sss_pct']].copy()
    display['store_name'] = display['store_id'].map(STORE_NAMES).fillna('')
    display = display[['store_id', 'store_name', 'city', 'co_op', 'net_sales', 'sss_pct',
                        'same_store_ticket_pct', 'avg_daily_bread', 'online_sales_pct',
                        'third_party_sales_pct', 'loyalty_sales_pct',
                        'fytd_net_sales', 'fytd_weekly_auv', 'fytd_sss_pct']]
    display.columns = ['Store #', 'Name', 'City', 'Market', 'Net Sales', 'SSS %',
                       'Transactions %', 'Avg Daily Bread', 'Online %', '3rd Party %',
                       'Loyalty %', 'FYTD Sales', 'FYTD AUV', 'FYTD SSS %']
    display = display.sort_values('Net Sales', ascending=False)
    styled = display.style\
        .format({'Net Sales': '${:,.0f}', 'SSS %': '{:+.1f}%', 'Transactions %': '{:+.1f}%',
                 'Avg Daily Bread': '{:.0f}', 'Online %': '{:.1f}%', '3rd Party %': '{:.1f}%',
                 'Loyalty %': '{:.1f}%', 'FYTD Sales': '${:,.0f}',
                 'FYTD AUV': '${:,.0f}', 'FYTD SSS %': '{:+.1f}%'}, na_rep='—')\
        .map(color_pct, subset=['SSS %', 'Transactions %', 'FYTD SSS %'])
    st.dataframe(styled, use_container_width=True, height=520)

    if selected_store:
        sn = STORE_NAMES.get(selected_store, selected_store)
        st.markdown(f'<div class="section-header">STORE {selected_store} · {sn.upper()} — DEEP DIVE</div>',
                    unsafe_allow_html=True)
        ss = sales_df[sales_df['store_id'] == selected_store].sort_values('week_ending')
        if len(ss) > 1:
            col1, col2 = st.columns(2)
            with col1:
                fn = px.line(ss, x='week_ending', y='net_sales', title='Net Sales Over Time', markers=True)
                fn.update_traces(line_color=RED, marker_color=RED, marker_size=8, line_width=2.5)
                fn.update_layout(**PLOTLY_THEME, height=300)
                st.plotly_chart(fn, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})
            with col2:
                ss2 = ss.dropna(subset=['sss_pct'])
                fs = go.Figure(go.Bar(x=ss2['week_ending'], y=ss2['sss_pct'],
                                      marker_color=[RED if v >= 0 else BLUE for v in ss2['sss_pct']]))
                fs.add_hline(y=0, line_color=BORDER, line_width=1.5)
                fs.update_layout(**PLOTLY_THEME, height=300,
                                 title=dict(text="SSS % Over Time", font=dict(size=16, color=MUTED)))
                st.plotly_chart(fs, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})
        else:
            st.info("Trend charts appear once multiple weeks of data are loaded.")

# ── TAB 3: BREAD & OPS ────────────────────────────────────────────────────────
with tab3:
    # ── KPI tiles ──
    st.markdown('<div class="section-header">BREAD OVERVIEW</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)

    # SS Bread % from market totals (comparable-store methodology, same as PDF summary)
    def bread_total_val(col):
        import math, pandas as _pd
        if week_bread_totals is None or len(week_bread_totals) == 0:
            return None
        # Filter to relevant market rows
        if selected_market == "All Markets":
            # Largest store_count row that isn't FL
            cand = week_bread_totals[~week_bread_totals['market'].isin(['FL','Miami, Ft. Lauderdale'])]
        else:
            mkt_key = selected_market.split('/')[0].strip()
            cand = week_bread_totals[week_bread_totals['market'].str.contains(mkt_key, case=False, na=False)]
        if len(cand) == 0:
            return None
        row = cand.sort_values('store_count', ascending=False).head(1)
        v = row[col].values[0]
        if v is None: return None
        try:
            fv = float(v)
            return None if math.isnan(fv) else fv
        except:
            return None

    ss_bread_week = bread_total_val('same_store_bread_pct')
    ss_bread_fytd = bread_total_val('fytd_sss_bread_pct')
    avg_spl_ytd   = week_bread['fytd_avg_sales_per_loaf'].mean() if 'fytd_avg_sales_per_loaf' in week_bread.columns else None
    fytd_bread    = week_bread['fytd_bread_count'].sum() if 'fytd_bread_count' in week_bread.columns else None
    fytd_adb      = week_bread['fytd_avg_daily_bread'].mean() if 'fytd_avg_daily_bread' in week_bread.columns else None

    with col1:
        st.markdown(kpi("SS Bread %",
            f"{ss_bread_week:+.1f}" if ss_bread_week is not None else "—", week_suffix="%",
            ytd_val=ss_bread_fytd, ytd_suffix="%", sss_color=True),
            unsafe_allow_html=True)
    with col2:
        st.markdown(kpi("Total Bread Count",
            f"{week_bread['bread_count'].sum():,}",
            ytd_val=f"{int(fytd_bread):,}" if fytd_bread else "—"),
            unsafe_allow_html=True)
    with col3:
        st.markdown(kpi("Avg Daily Bread / Store",
            f"{week_bread['avg_daily_bread'].mean():.0f}",
            ytd_val=f"{fytd_adb:.0f}" if fytd_adb else "—", blue=True),
            unsafe_allow_html=True)
    with col4:
        st.markdown(kpi("Avg Sales / Loaf",
            f"${week_bread['avg_sales_per_loaf'].mean():.2f}",
            ytd_val=f"${avg_spl_ytd:.2f}" if avg_spl_ytd else "—"),
            unsafe_allow_html=True)

    # ── SS Bread % stacked ──
    st.markdown('<div class="section-header">SAME STORE BREAD % BY STORE</div>', unsafe_allow_html=True)
    n_bread = week_bread['same_store_bread_pct'].notna().sum()
    bread_h = max(420, int(n_bread) * 26 + 60)

    _bread_regions = sorted(set(week_bread['co_op'].str.replace('\n',' ').str.strip().dropna()))
    _bread_pills = " &nbsp; ".join([
        "<span style='display:inline-flex;align-items:center;gap:5px;margin-right:8px;'>"
        f"<span style='width:12px;height:12px;border-radius:2px;background:{region_color(r)};display:inline-block;'></span>"
        f"<span style='font-size:12px;font-family:Arial;color:{TEXT};'>{r}</span></span>"
        for r in _bread_regions
    ])
    st.markdown(f"<div style='margin-bottom:8px;'>{_bread_pills}</div>", unsafe_allow_html=True)

    ssb = week_bread[week_bread['same_store_bread_pct'].notna()].copy()
    ssb['label'] = ssb['store_id'] + ' · ' + ssb['store_id'].map(STORE_NAMES).fillna('')
    ssb['region'] = ssb['co_op'].str.replace('\n',' ').str.strip()
    ssb = ssb.sort_values('same_store_bread_pct', ascending=True)
    fb1 = go.Figure()
    for region, grp in ssb.groupby('region'):
        fb1.add_trace(go.Bar(
            name=region, showlegend=False,
            x=grp['same_store_bread_pct'], y=grp['label'], orientation='h',
            marker_color=region_color(region),
            text=[f"{v:+.1f}%" for v in grp['same_store_bread_pct']],
            textposition='outside', textfont=dict(size=11, color=TEXT, family='Arial'),
            hovertemplate='<b>%{y}</b><br>SS Bread: %{x:.1f}%<extra></extra>'
        ))
    fb1.add_vline(x=0, line_color=BORDER, line_width=1.5)
    if ss_bread_week is not None:
        fb1.add_vline(x=ss_bread_week, line_color=TEXT, line_width=2.5, line_dash='dash',
            annotation_text=f"System {ss_bread_week:+.1f}%", annotation_position="top right",
            annotation_font=dict(size=11, color=TEXT, family='Arial'))
    fb1.update_layout(**PLOTLY_THEME, height=bread_h, showlegend=False,
                      margin=dict(l=10,r=70,t=45,b=20),
                      title=dict(text=f"SS Bread % — Week ending {selected_week}",
                                 font=dict(size=15, color=TEXT, family='Arial')))
    fb1.update_yaxes(tickfont=dict(size=11, family='Arial'))
    st.plotly_chart(fb1, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    ssb2 = week_bread[week_bread['fytd_sss_bread_pct'].notna()].copy()
    ssb2['label'] = ssb2['store_id'] + ' · ' + ssb2['store_id'].map(STORE_NAMES).fillna('')
    ssb2['region'] = ssb2['co_op'].str.replace('\n',' ').str.strip()
    ssb2 = ssb2.sort_values('fytd_sss_bread_pct', ascending=True)
    fb2 = go.Figure()
    for region, grp in ssb2.groupby('region'):
        fb2.add_trace(go.Bar(
            name=region, showlegend=False,
            x=grp['fytd_sss_bread_pct'], y=grp['label'], orientation='h',
            marker_color=region_color(region),
            text=[f"{v:+.1f}%" for v in grp['fytd_sss_bread_pct']],
            textposition='outside', textfont=dict(size=11, color=TEXT, family='Arial'),
            hovertemplate='<b>%{y}</b><br>FYTD SS Bread: %{x:.1f}%<extra></extra>'
        ))
    fb2.add_vline(x=0, line_color=BORDER, line_width=1.5)
    if ss_bread_fytd is not None:
        fb2.add_vline(x=ss_bread_fytd, line_color=TEXT, line_width=2.5, line_dash='dash',
            annotation_text=f"System {ss_bread_fytd:+.1f}%", annotation_position="top right",
            annotation_font=dict(size=11, color=TEXT, family='Arial'))
    fb2.update_layout(**PLOTLY_THEME, height=bread_h, showlegend=False,
                      margin=dict(l=10,r=70,t=45,b=20),
                      title=dict(text=f"SS Bread % YTD (as of {selected_week})",
                                 font=dict(size=15, color=TEXT, family='Arial')))
    fb2.update_yaxes(tickfont=dict(size=11, family='Arial'))
    st.plotly_chart(fb2, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    # ── Avg Daily Bread stacked ──
    st.markdown('<div class="section-header">AVG DAILY BREAD BY STORE</div>', unsafe_allow_html=True)
    st.markdown(f"<div style='margin-bottom:8px;'>{_bread_pills}</div>", unsafe_allow_html=True)

    bc = week_bread.copy()
    bc['label'] = bc['store_id'] + ' · ' + bc['store_id'].map(STORE_NAMES).fillna('')
    bc['region'] = bc['co_op'].str.replace('\n',' ').str.strip()
    bc = bc.sort_values('avg_daily_bread', ascending=True)
    fbc1 = go.Figure()
    for region, grp in bc.groupby('region'):
        fbc1.add_trace(go.Bar(
            name=region, showlegend=False,
            x=grp['avg_daily_bread'], y=grp['label'],
            orientation='h', marker_color=region_color(region), marker_opacity=0.88,
            hovertemplate='<b>%{y}</b><br>Avg Daily Bread: %{x:.0f}<extra></extra>'
        ))
    _sys_adb_week = week_bread['avg_daily_bread'].mean()
    fbc1.add_vline(x=_sys_adb_week, line_color=TEXT, line_width=2.5, line_dash='dash',
        annotation_text=f"System {_sys_adb_week:.0f}", annotation_position="top right",
        annotation_font=dict(size=11, color=TEXT, family='Arial'))
    fbc1.update_layout(**PLOTLY_THEME, height=bread_h, showlegend=False,
                       margin=dict(l=10,r=40,t=45,b=20),
                       title=dict(text=f"Avg Daily Bread — Week ending {selected_week}",
                                  font=dict(size=15, color=TEXT, family='Arial')))
    fbc1.update_yaxes(tickfont=dict(size=11, family='Arial'))
    st.plotly_chart(fbc1, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    bc2d = week_bread[week_bread['fytd_avg_daily_bread'].notna()].copy()
    bc2d['label'] = bc2d['store_id'] + ' · ' + bc2d['store_id'].map(STORE_NAMES).fillna('')
    bc2d['region'] = bc2d['co_op'].str.replace('\n',' ').str.strip()
    bc2d = bc2d.sort_values('fytd_avg_daily_bread', ascending=True)
    fbc2 = go.Figure()
    for region, grp in bc2d.groupby('region'):
        fbc2.add_trace(go.Bar(
            name=region, showlegend=False,
            x=grp['fytd_avg_daily_bread'], y=grp['label'],
            orientation='h', marker_color=region_color(region), marker_opacity=0.88,
            hovertemplate='<b>%{y}</b><br>FYTD Avg Daily Bread: %{x:.0f}<extra></extra>'
        ))
    if fytd_adb:
        fbc2.add_vline(x=fytd_adb, line_color=TEXT, line_width=2.5, line_dash='dash',
            annotation_text=f"System {fytd_adb:.0f}", annotation_position="top right",
            annotation_font=dict(size=11, color=TEXT, family='Arial'))
    fbc2.update_layout(**PLOTLY_THEME, height=bread_h, showlegend=False,
                       margin=dict(l=10,r=40,t=45,b=20),
                       title=dict(text=f"Avg Daily Bread YTD (as of {selected_week})",
                                  font=dict(size=15, color=TEXT, family='Arial')))
    fbc2.update_yaxes(tickfont=dict(size=11, family='Arial'))
    st.plotly_chart(fbc2, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})


    st.markdown('<div class="section-header">DISCOUNT ANALYSIS</div>', unsafe_allow_html=True)
    st.markdown(f"""<div style='margin-bottom:8px;'>
        <span style='display:inline-flex;align-items:center;gap:5px;margin-right:16px;'>
            <span style='width:12px;height:12px;border-radius:2px;background:{RED};display:inline-block;'></span>
            <span style='font-size:12px;font-family:Arial;color:{TEXT};'>Non-Loyalty Disc %</span></span>
        <span style='display:inline-flex;align-items:center;gap:5px;'>
            <span style='width:12px;height:12px;border-radius:2px;background:{BLUE};display:inline-block;'></span>
            <span style='font-size:12px;font-family:Arial;color:{TEXT};'>Loyalty Disc %</span></span>
    </div>""", unsafe_allow_html=True)
    disc = week_sales[['store_id', 'non_loyalty_disc_pct', 'loyalty_disc_pct']].copy()
    disc['label'] = disc['store_id'] + ' · ' + disc['store_id'].map(STORE_NAMES).fillna('')
    disc = disc.sort_values('non_loyalty_disc_pct', ascending=False)
    fd = go.Figure()
    fd.add_trace(go.Bar(name='Non-Loyalty Disc %', showlegend=False,
                        x=disc['label'], y=disc['non_loyalty_disc_pct'], marker_color=RED))
    fd.add_trace(go.Bar(name='Loyalty Disc %', showlegend=False,
                        x=disc['label'], y=disc['loyalty_disc_pct'], marker_color=BLUE))
    _sys_non_loy = week_sales['non_loyalty_disc_pct'].mean()
    _sys_loy     = week_sales['loyalty_disc_pct'].mean()
    fd.add_hline(y=_sys_non_loy, line_color=RED, line_width=2, line_dash='dash',
        annotation_text=f"Sys Non-Loyalty {_sys_non_loy:.1f}%",
        annotation_position="right", annotation_font=dict(size=10, color=RED, family='Arial'))
    fd.add_hline(y=_sys_loy, line_color=BLUE, line_width=2, line_dash='dash',
        annotation_text=f"Sys Loyalty {_sys_loy:.1f}%",
        annotation_position="right", annotation_font=dict(size=10, color=BLUE, family='Arial'))
    fd.update_layout(**PLOTLY_THEME, height=380, barmode='group', showlegend=False,
                     margin=dict(l=40,r=120,t=45,b=60),
                     title=dict(text="Discount % by Store", font=dict(size=15, color=TEXT, family='Arial')),
                     xaxis_tickangle=-40)
    st.plotly_chart(fd, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

# ── TAB 4: LOYALTY ────────────────────────────────────────────────────────────
with tab4:
    st.markdown('<div class="section-header">LOYALTY PROGRAM — THIS WEEK</div>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    for col, (label, cc, ac) in zip([col1,col2,col3,col4], [
        ("New Members",    'member_activations_current',  'member_activations_alltime'),
        ("Transactions",   'member_transactions_current', 'member_transactions_alltime'),
        ("Points Earned",  'points_earned_current',       'points_earned_alltime'),
        ("Points Redeemed",'points_redeemed_current',     'points_redeemed_alltime')
    ]):
        with col:
            st.markdown(f'<div class="kpi-card kpi-card-blue"><div class="kpi-label">{label}</div><div class="kpi-value">{week_loyalty[cc].sum():,}</div><span class="kpi-neutral">{week_loyalty[ac].sum():,} all-time</span></div>', unsafe_allow_html=True)

    col_a, col_b = st.columns(2)
    with col_a:
        lc = week_loyalty.copy()
        lc['label'] = lc['store_id'] + ' · ' + lc['store_id'].map(STORE_NAMES).fillna('')
        lc = lc.sort_values('member_transactions_current', ascending=True)
        flt = go.Figure(go.Bar(x=lc['member_transactions_current'], y=lc['label'], orientation='h',
                                marker_color=RED, hovertemplate='<b>%{y}</b><br>Transactions: %{x:,}<extra></extra>'))
        flt.update_layout(**PLOTLY_THEME, height=500,
                          title=dict(text="Loyalty Transactions This Week", font=dict(size=16, color=MUTED)))
        st.plotly_chart(flt, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})
    with col_b:
        pc = week_loyalty.copy()
        pc['label'] = pc['store_id'] + ' · ' + pc['store_id'].map(STORE_NAMES).fillna('')
        pc = pc.sort_values('points_earned_current', ascending=False)
        fpts = go.Figure()
        fpts.add_trace(go.Bar(name='Points Earned', x=pc['label'], y=pc['points_earned_current'], marker_color=RED))
        fpts.add_trace(go.Bar(name='Points Redeemed', x=pc['label'], y=pc['points_redeemed_current'], marker_color=BLUE))
        fpts.update_layout(**PLOTLY_THEME, height=500, barmode='group',
                           title=dict(text="Points Earned vs Redeemed", font=dict(size=16, color=MUTED)),
                           xaxis_tickangle=-40, xaxis_tickfont=dict(size=9))
        st.plotly_chart(fpts, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

    st.markdown('<div class="section-header">LOYALTY SALES % VS NET SALES</div>', unsafe_allow_html=True)
    ls = week_sales[['store_id', 'net_sales', 'loyalty_sales_pct']].copy()
    ls['store_name'] = ls['store_id'].map(STORE_NAMES).fillna(ls['store_id'])
    fls = px.scatter(ls, x='net_sales', y='loyalty_sales_pct', text='store_name', size='net_sales',
                     labels={'net_sales': 'Net Sales ($)', 'loyalty_sales_pct': 'Loyalty Sales %'})
    fls.update_traces(marker_color=RED, textfont_size=9, textposition='top center')
    fls.update_layout(**PLOTLY_THEME, height=400,
                      title=dict(text="Loyalty Sales % vs Net Sales", font=dict(size=16, color=MUTED)))
    st.plotly_chart(fls, use_container_width=True, config={"scrollZoom": True, "responsive": True, "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []})

# ── TAB 5: MAP ────────────────────────────────────────────────────────────────
with tab5:
    st.markdown('<div class="section-header">STORE MAP</div>', unsafe_allow_html=True)

    # Metric selector — large buttons using columns
    st.markdown(f"""
        <div style='font-family:Arial,sans-serif; font-size:18px; font-weight:700;
                    color:{TEXT}; margin-bottom:10px;'>Color stores by:</div>
    """, unsafe_allow_html=True)

    metric_options = ["Weekly SSS %", "FYTD SSS %", "Weekly Net Sales", "FYTD AUV"]
    if 'map_metric' not in st.session_state:
        st.session_state['map_metric'] = "Weekly SSS %"

    btn_cols = st.columns(len(metric_options))
    for i, opt in enumerate(metric_options):
        with btn_cols[i]:
            is_active = st.session_state['map_metric'] == opt
            btn_style = f"""
                background:{"#134A7C" if is_active else "#F5F6F8"};
                color:{"white" if is_active else "#1a1a2e"};
                border:2px solid {"#134A7C" if is_active else "#E0E3E8"};
                border-radius:8px; padding:12px 8px;
                font-family:Arial,sans-serif; font-size:16px; font-weight:700;
                width:100%; cursor:pointer; text-align:center;
            """
            if st.button(opt, key=f"map_btn_{i}", use_container_width=True):
                st.session_state['map_metric'] = opt
                st.rerun()

    map_metric = st.session_state['map_metric']

    metric_col_map = {
        "Weekly SSS %":     ("sss_pct",        "SSS %",      False),
        "FYTD SSS %":       ("fytd_sss_pct",   "FYTD SSS %", False),
        "Weekly Net Sales": ("net_sales",       "Net Sales",  True),
        "FYTD AUV":         ("fytd_weekly_auv", "FYTD AUV",   True),
    }
    col_name, col_label, is_dollar = metric_col_map[map_metric]

    # Build map dataframe from ALL stores (so San Diego appears even without PDF data)
    _all = stores_df[['store_id', 'city', 'co_op']].copy()
    _pdf = week_sales[['store_id', 'net_sales', 'sss_pct', 'fytd_weekly_auv', 'fytd_sss_pct']].copy()
    map_data = _all.merge(_pdf, on='store_id', how='left')
    map_data['store_name'] = map_data['store_id'].map(STORE_NAMES).fillna(map_data['city'])
    map_data['lat']     = map_data['store_id'].map(lambda x: STORE_COORDS.get(x, (None, None, ''))[0])
    map_data['lon']     = map_data['store_id'].map(lambda x: STORE_COORDS.get(x, (None, None, ''))[1])
    map_data['address'] = map_data['store_id'].map(lambda x: STORE_COORDS.get(x, (None, None, ''))[2])
    map_data = map_data.dropna(subset=['lat', 'lon'])

    def fmt_val(v, dollar):
        try:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return "N/A"
            return f"${float(v):,.0f}" if dollar else f"{float(v):+.1f}%"
        except:
            return "N/A"

    map_data['display_val'] = [fmt_val(v, is_dollar) for v in map_data[col_name]]
    map_data['hover'] = (
        "<b>" + map_data['store_name'] + "</b>  (#" + map_data['store_id'] + ")<br>" +
        map_data['address'] + "<br>" +
        col_label + ": " + map_data['display_val'] + "<br>" +
        "Market: " + map_data['co_op']
    )

    fig_map = go.Figure()

    if not is_dollar:
        buckets = [
            ("🔴  Below -2%",  map_data[map_data[col_name].notna() & (map_data[col_name] < -2)],   "#EE3327"),
            ("🟡  -2% to 0%",  map_data[map_data[col_name].notna() & (map_data[col_name] >= -2) & (map_data[col_name] < 0)], "#F5A623"),
            ("🟢  Above 0%",   map_data[map_data[col_name].notna() & (map_data[col_name] >= 0)],   "#22c55e"),
            ("⚪  No Data",    map_data[map_data[col_name].isna()],                                  "#AAAAAA"),
        ]
        for legend_label, subset, color in buckets:
            if len(subset) == 0:
                continue
            fig_map.add_trace(go.Scattermapbox(
                lat=subset['lat'], lon=subset['lon'],
                mode='markers+text',
                name=legend_label,
                marker=dict(size=20, color=color, opacity=0.92),
                text=subset['store_name'],
                textfont=dict(size=9, color="#1a1a2e"),
                textposition="top center",
                hovertext=subset['hover'],
                hoverinfo='text',
            ))
        st.markdown(f"""
            <div style='margin-bottom:8px; font-family:Arial,sans-serif; font-size:16px; color:{MUTED};'>
                <span style='background:#EE3327;color:white;padding:6px 16px;border-radius:12px;margin-right:10px;font-weight:700;font-size:16px;'>▼ Below -2%</span>
                <span style='background:#F5A623;color:white;padding:6px 16px;border-radius:12px;margin-right:10px;font-weight:700;font-size:16px;'>-2% to 0%</span>
                <span style='background:#22c55e;color:white;padding:6px 16px;border-radius:12px;font-weight:700;font-size:16px;'>▲ Above 0%</span>
            </div>
        """, unsafe_allow_html=True)
    else:
        valid = map_data[map_data[col_name].notna()].copy()
        fig_map.add_trace(go.Scattermapbox(
            lat=valid['lat'], lon=valid['lon'],
            mode='markers+text',
            name=col_label,
            marker=dict(
                size=20,
                color=valid[col_name].astype(float),
                colorscale=[[0, RED], [0.5, '#F5A623'], [1, '#22c55e']],
                showscale=True,
                colorbar=dict(
                    title=dict(text=col_label, font=dict(size=18, color=TEXT)),
                    thickness=16, len=0.55,
                    bgcolor=WHITE, bordercolor=BORDER,
                    tickfont=dict(size=16, color=TEXT),
                ),
                opacity=0.92,
            ),
            text=valid['store_name'],
            textfont=dict(size=9, color="#1a1a2e"),
            textposition="top center",
            hovertext=valid['hover'],
            hoverinfo='text',
        ))

    fig_map.update_layout(
        uirevision=f"map_{selected_week}_{selected_market}",
        mapbox=dict(
            style="carto-positron",
            center=dict(lat=34.25, lon=-118.50),
            zoom=8.0,
        ),
        showlegend=False,
        margin=dict(l=0, r=0, t=0, b=0),
        height=620,
        paper_bgcolor=WHITE,
    )
    # Write map to self-contained HTML and embed — preserves zoom across metric switches
    import plotly.io as pio
    map_html = pio.to_html(
        fig_map,
        full_html=True,
        include_plotlyjs=True,
        config={"scrollZoom": True, "doubleClick": "reset", "displayModeBar": True, "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud","hoverClosestCartesian","hoverCompareCartesian","toggleSpikelines"], "modeBarButtonsToAdd": []},
    )
    # Inject the stable uirevision JS so viewport state persists
    map_html = map_html.replace(
        "</head>",
        """<style>body{margin:0;padding:0;overflow:hidden;}</style></head>"""
    )
    components.html(map_html, height=640, scrolling=False)

# ── TAB 6: TRENDS ─────────────────────────────────────────────────────────────
with tab6:
    from datetime import timedelta as _td

    @st.cache_data(ttl=300)
    def compute_sss_trend(market_filter, grouping_filter='All Stores'):
        import pandas as _pd
        _conn, _ = get_db_connection()
        _df = _pd.read_sql(
            "SELECT h.store_id, h.week_ending, h.net_sales, h.transactions, s.co_op "
            "FROM weekly_store_history h JOIN stores s ON h.store_id = s.store_id "
            "WHERE h.net_sales IS NOT NULL AND h.net_sales > 0 "
            "AND h.transactions IS NOT NULL AND h.transactions > 0", _conn)
        _conn.close()
        _df['week_ending'] = _pd.to_datetime(_df['week_ending'])
        _df['co_op'] = _df['co_op'].str.replace('\n',' ').str.strip()
        if grouping_filter == "Organic Stores":
            _df = _df[~_df['store_id'].isin(SAN_DIEGO_STORE_IDS)]
        elif grouping_filter == "Acquisition Stores":
            _df = _df[_df['store_id'].isin(SAN_DIEGO_STORE_IDS)]
        if market_filter != "All Markets":
            _df = _df[_df['co_op'].str.contains(market_filter.split('/')[0].strip(), case=False, na=False)]
        _first = _df.groupby('store_id')['week_ending'].min()
        _rows = []
        for _wk in sorted(_df['week_ending'].unique()):
            _pr = _wk - _pd.Timedelta(days=364)
            # 420-day rule: store must have opened >= 420 days before current week
            _elig = _first[_first <= (_wk - _pd.Timedelta(days=420))].index
            _cur = _df[(_df['week_ending']==_wk) & (_df['store_id'].isin(_elig))].set_index('store_id')
            _prr = _df[(_df['week_ending']==_pr) & (_df['store_id'].isin(_elig))].set_index('store_id')
            # Only include stores with valid (>0) data in BOTH periods
            _both = _cur.index.intersection(_prr.index)
            if len(_both) < 3: continue
            _c = _cur.loc[_both]; _p = _prr.loc[_both]
            # Final guard: drop any store where prior sales or transactions are zero
            _valid = _both[(_p['net_sales'] > 0) & (_p['transactions'] > 0)]
            if len(_valid) < 3: continue
            _c = _c.loc[_valid]; _p = _p.loc[_valid]
            _sss  = (_c['net_sales'].sum()    / _p['net_sales'].sum()    - 1)*100
            _sst  = (_c['transactions'].sum() / _p['transactions'].sum() - 1)*100
            _stkt = ((1+_sss/100)/(1+_sst/100)-1)*100
            _rows.append({'week_ending': _wk.strftime('%Y-%m-%d'),
                          'comp_stores': len(_valid),
                          'sss_pct': round(_sss,2),
                          'ss_txn_pct': round(_sst,2),
                          'ss_ticket_pct': round(_stkt,2),
                          'total_sales': round(_c['net_sales'].sum(),0)})
        return _pd.DataFrame(_rows)

    # If a specific store is selected, show that store's individual trend instead
    if selected_store:
        _store_name = STORE_NAMES.get(selected_store, selected_store)
        import pandas as _spd

        # Load full history for this store
        _conn2, _ = get_db_connection()
        _sh = _spd.read_sql(
            f"SELECT week_ending, net_sales, transactions FROM weekly_store_history "
            f"WHERE store_id = '{selected_store}' AND net_sales > 0 ORDER BY week_ending", _conn2)
        _conn2.close()

        if len(_sh) == 0:
            st.info("No history data available for this store.")
        else:
            _sh['week_ending'] = _spd.to_datetime(_sh['week_ending'])
            _sh = _sh.sort_values('week_ending')
            _sh_idx = _sh.set_index('week_ending')

            # Compute YoY SSS, SS Transactions, SS Avg Ticket per week
            _sss_list = []; _txn_list = []; _tkt_list = []
            for _wk, _row in _sh_idx.iterrows():
                _pr = _wk - _spd.Timedelta(days=364)
                if _pr in _sh_idx.index and _sh_idx.loc[_pr, 'net_sales'] > 0 and _sh_idx.loc[_pr, 'transactions'] > 0:
                    _s = (_row['net_sales'] / _sh_idx.loc[_pr, 'net_sales'] - 1) * 100
                    _t = (_row['transactions'] / _sh_idx.loc[_pr, 'transactions'] - 1) * 100
                    _k = ((1 + _s/100) / (1 + _t/100) - 1) * 100
                    _sss_list.append(round(_s, 2))
                    _txn_list.append(round(_t, 2))
                    _tkt_list.append(round(_k, 2))
                else:
                    _sss_list.append(None); _txn_list.append(None); _tkt_list.append(None)

            _sh['sss_pct'] = _sss_list
            _sh['ss_txn_pct'] = _txn_list
            _sh['ss_ticket_pct'] = _tkt_list
            _sh['week_str'] = _sh['week_ending'].dt.strftime('%Y-%m-%d')
            _plot = _sh.dropna(subset=['sss_pct']).copy()

            # Apply same time range filter as system view
            _active_lbl2 = st.session_state.get('trend_weeks', '26 weeks')
            _nw_opts2 = {'13 weeks': 13, '26 weeks': 26, '52 weeks': 52, 'All history': len(_plot)}
            _nw2 = _nw_opts2.get(_active_lbl2, 26)
            _plot = _plot.tail(_nw2)

            def _store_bar(x, y, title):
                _colors = [GREEN if v >= 0 else DANGER for v in y]
                _fig = go.Figure(go.Bar(
                    x=x, y=y,
                    marker_color=_colors,
                    text=[f"{v:+.1f}%" for v in y],
                    textposition='outside',
                    textfont=dict(size=_bar_font, family='Arial', color=TEXT),
                    hovertemplate=f"Week: %{{x}}<br>{title}: %{{y:+.1f}}%<extra></extra>"
                ))
                _fig.add_hline(y=0, line_color=TEXT, line_width=2, line_dash='solid')
                _fig.update_layout(**PLOTLY_THEME, height=380,
                    margin=dict(l=20,r=20,t=55,b=60), showlegend=False,
                    title=dict(text=f"{title} — {_store_name} ({_active_lbl2})",
                               font=dict(size=16, color=TEXT, family='Arial')))
                _fig.update_xaxes(tickangle=-40, tickfont=dict(size=max(_bar_font-1,8), family='Arial'))
                _fig.update_yaxes(ticksuffix='%', tickfont=dict(size=11, family='Arial'))
                return _fig

            # Show time range buttons (same as system view)
            _n_weeks_options2 = {'13 weeks': 13, '26 weeks': 26, '52 weeks': 52, 'All history': len(_sh.dropna(subset=['sss_pct']))}
            _active_lbl2b = st.session_state.get('trend_weeks', '26 weeks')
            _btn_css2 = []
            for _bi2, _bopt2 in enumerate(_n_weeks_options2.keys()):
                if _bopt2 == _active_lbl2b:
                    _sel2 = "div[data-testid=\"column\"]:nth-child(" + str(_bi2+1) + ") button"
                    _btn_css2.append(_sel2 + " { background-color: #134A7C !important; color: white !important; border: 2px solid #134A7C !important; font-weight: 700 !important; }")
            if _btn_css2:
                st.markdown("<style>" + " ".join(_btn_css2) + "</style>", unsafe_allow_html=True)
            _bcols2 = st.columns(len(_n_weeks_options2))
            for _bi2, _bopt2 in enumerate(_n_weeks_options2.keys()):
                with _bcols2[_bi2]:
                    if st.button(_bopt2, key=f"store_trend_btn_{_bi2}", use_container_width=True):
                        st.session_state['trend_weeks'] = _bopt2
                        st.rerun()
            _bar_font = 16 if _nw2 <= 13 else 13 if _nw2 <= 26 else 11 if _nw2 <= 52 else 9

            _cfg = {"scrollZoom": True, "responsive": True, "displayModeBar": True,
                    "modeBarButtonsToRemove": ["zoom2d","pan2d","select2d","lasso2d","zoomIn2d","zoomOut2d","toImage","sendDataToCloud"]}
            st.plotly_chart(_store_bar(_plot['week_str'], _plot['sss_pct'], "Same Store Sales %"),
                use_container_width=True, config=_cfg)
            st.plotly_chart(_store_bar(_plot['week_str'], _plot['ss_txn_pct'], "Same Store Transactions %"),
                use_container_width=True, config=_cfg)
            st.plotly_chart(_store_bar(_plot['week_str'], _plot['ss_ticket_pct'], "Same Store Avg Ticket %"),
                use_container_width=True, config=_cfg)

    else:
        trend_df = compute_sss_trend(selected_market, selected_grouping)


    if not selected_store:
        # ── Roll forward: append PDF weeks not yet in history ────────────────────
        # PDF data uses store-level sales but no prior-year transactions,
        # so we use the market totals (from PDF summary rows) for the most recent weeks
        @st.cache_data(ttl=300)
        def get_pdf_trend_rows(market_filter):
            import pandas as _pd, math as _m
            _conn, _ = get_db_connection()
            _mkt = _pd.read_sql(
                "SELECT week_ending, market, store_count, sss_pct, same_store_ticket_pct, "
                "same_store_txn_pct FROM weekly_market_totals ORDER BY week_ending", _conn)
            _conn.close()
            # Filter to CA-level total (highest store count, not FL)
            _ca = _mkt[~_mkt['market'].isin(['FL','Miami, Ft. Lauderdale'])].copy()
            _ca = _ca.sort_values('store_count', ascending=False)
            _ca = _ca.drop_duplicates(subset=['week_ending'], keep='first')
            if market_filter != "All Markets":
                _mk = _mkt[_mkt['market'].str.contains(
                    market_filter.split('/')[0].strip(), case=False, na=False)]
                _mk = _mk.sort_values('store_count', ascending=False)
                _ca = _mk.drop_duplicates(subset=['week_ending'], keep='first')
            _rows = []
            for _, r in _ca.iterrows():
                try:
                    _sss = float(r['sss_pct']) if _pd.notna(r['sss_pct']) else None
                    _txn = float(r['same_store_ticket_pct']) if _pd.notna(r['same_store_ticket_pct']) else None
                    _tkt = float(r['same_store_txn_pct']) if _pd.notna(r['same_store_txn_pct']) else None
                    if _sss is None: continue
                    _rows.append({'week_ending': r['week_ending'],
                                  'comp_stores': int(r['store_count']) if _pd.notna(r['store_count']) else 0,
                                  'sss_pct': round(_sss,2),
                                  'ss_txn_pct': round(_txn,2) if _txn else None,
                                  'ss_ticket_pct': round(_tkt,2) if _tkt else None})
                except: pass
            return _pd.DataFrame(_rows)

        pdf_rows = get_pdf_trend_rows(selected_market)

        # Merge: use history for older weeks, PDF data for newer weeks not in history
        if len(trend_df) > 0 and len(pdf_rows) > 0:
            hist_max = trend_df['week_ending'].max()
            new_pdf = pdf_rows[pdf_rows['week_ending'] > hist_max].copy()
            if len(new_pdf) > 0:
                # Rename week_ending column to match
                trend_df = pd.concat([trend_df, new_pdf], ignore_index=True)
                trend_df = trend_df.sort_values('week_ending').reset_index(drop=True)
        elif len(trend_df) == 0 and len(pdf_rows) > 0:
            trend_df = pdf_rows.copy()

        if len(trend_df) == 0:
            st.info("No trend data available for the selected market.")
        else:
            st.markdown('<div class="section-header">SAME STORE PERFORMANCE TRENDS</div>', unsafe_allow_html=True)

            if 'trend_weeks' not in st.session_state:
                st.session_state['trend_weeks'] = '26 weeks'
            n_weeks_options = {'13 weeks': 13, '26 weeks': 26, '52 weeks': 52, 'All history': len(trend_df)}
            st.markdown(
                f"<div style='font-family:Arial,sans-serif; font-size:18px; font-weight:700;"
                f"color:{TEXT}; margin-bottom:10px;'>Show:</div>",
                unsafe_allow_html=True)
            _active_lbl = st.session_state.get('trend_weeks', '26 weeks')
            _btn_css = []
            for _bi, _bopt in enumerate(n_weeks_options.keys()):
                if _bopt == _active_lbl:
                    _sel = "div[data-testid=\"column\"]:nth-child(" + str(_bi+1) + ") button"
                    _rule = _sel + " { background-color: #134A7C !important; color: white !important; border: 2px solid #134A7C !important; font-weight: 700 !important; }"
                    _btn_css.append(_rule)
            if _btn_css:
                st.markdown("<style>" + " ".join(_btn_css) + "</style>", unsafe_allow_html=True)
            btn_cols2 = st.columns(len(n_weeks_options))
            for _i, _opt in enumerate(n_weeks_options.keys()):
                with btn_cols2[_i]:
                    if st.button(_opt, key=f"trend_btn_{_i}", use_container_width=True):
                        st.session_state['trend_weeks'] = _opt
                        st.rerun()
            n_weeks_label = st.session_state['trend_weeks']
            if n_weeks_label not in n_weeks_options:
                n_weeks_label = '26 weeks'
            n_weeks = n_weeks_options[n_weeks_label]
            plot_df = trend_df.tail(n_weeks).copy()

            def bar_colors(vals):
                return [GREEN if v >= 0 else DANGER for v in vals]

            _bar_font = 16 if n_weeks <= 13 else 13 if n_weeks <= 26 else 11 if n_weeks <= 52 else 9

            def sss_bar(df, col, title, hover_label):
                fig = go.Figure(go.Bar(
                    x=df['week_ending'], y=df[col],
                    marker_color=bar_colors(df[col]),
                    text=[f"{v:+.1f}%" for v in df[col]],
                    textposition='outside',
                    textfont=dict(size=_bar_font, family='Arial', color=TEXT),
                    hovertemplate=f"Week: %{{x}}<br>{hover_label}: %{{y:+.1f}}%<extra></extra>"
                ))
                fig.add_hline(y=0, line_color=TEXT, line_width=2, line_dash='solid')
                fig.update_layout(**PLOTLY_THEME, height=380,
                                  margin=dict(l=20,r=20,t=55,b=60),
                                  title=dict(text=title, font=dict(size=16, color=TEXT, family='Arial')))
                fig.update_xaxes(tickangle=-40, tickfont=dict(size=max(_bar_font-1,8), family='Arial'))
                fig.update_yaxes(ticksuffix='%', tickfont=dict(size=11, family='Arial'))
                return fig

            # All three stacked vertically
            st.plotly_chart(sss_bar(plot_df, 'sss_pct',
                f"Same Store Sales % ({n_weeks_label})", "SS Sales"),
                use_container_width=True)
            st.plotly_chart(sss_bar(plot_df, 'ss_txn_pct',
                f"Same Store Transactions % ({n_weeks_label})", "SS Transactions"),
                use_container_width=True)
            st.plotly_chart(sss_bar(plot_df, 'ss_ticket_pct',
                f"Same Store Avg Ticket % ({n_weeks_label})", "SS Avg Ticket"),
                use_container_width=True)

            # 4-week rolling average
            st.markdown('<div class="section-header">4-WEEK ROLLING AVERAGE</div>', unsafe_allow_html=True)
            roll = trend_df.copy()
            roll['sss_4wk']    = roll['sss_pct'].rolling(4).mean()
            roll['txn_4wk']    = roll['ss_txn_pct'].rolling(4).mean()
            roll['ticket_4wk'] = roll['ss_ticket_pct'].rolling(4).mean()
            roll = roll.tail(n_weeks).dropna(subset=['sss_4wk'])

            fig_roll = go.Figure()
            fig_roll.add_trace(go.Scatter(x=roll['week_ending'], y=roll['sss_4wk'],
                name='SS Sales', line=dict(color=RED, width=2.5), mode='lines+markers', marker_size=6,
                hovertemplate="Week: %{x}<br>SS Sales (4wk): %{y:+.1f}%<extra></extra>"))
            fig_roll.add_trace(go.Scatter(x=roll['week_ending'], y=roll['txn_4wk'],
                name='SS Transactions', line=dict(color=BLUE, width=2.5), mode='lines+markers', marker_size=6,
                hovertemplate="Week: %{x}<br>SS Transactions (4wk): %{y:+