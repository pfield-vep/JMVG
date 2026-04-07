"""
pages/2_Balanced_Scorecard.py
JM Valley Group — Operational Balanced Scorecard
"""

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Balanced Scorecard | JM Valley Group",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Shared constants (mirrors dashboard.py) ──────────────────────────────────
SAN_DIEGO_STORE_IDS = ['20071', '20091', '20171', '20177', '20291', '20292', '20300']

STORE_NAMES = {
    '20156': 'North Hollywood', '20218': 'Mission Hills', '20267': 'Balboa',
    '20294': 'Toluca',          '20026': 'Tampa',          '20311': 'Porter Ranch',
    '20352': 'San Fernando',   '20363': 'Warner Center',   '20273': 'Big Bear',
    '20366': 'Burbank North',  '20011': 'Westlake',        '20255': 'Arboles',
    '20048': 'Janss',          '20245': 'Wendy',           '20381': 'Sylmar',
    '20116': 'Encino',         '20388': 'Lake Arrowhead',  '20075': 'Isla Vista',
    '20335': 'Goleta',         '20360': 'Santa Barbara',   '20424': 'Studio City',
    '20177': 'SD1',            '20171': 'SD2',             '20091': 'SD3',
    '20071': 'SD4',            '20300': 'SD5',             '20292': 'SD6',
    '20291': 'SD7',            '20013': 'Buellton',
}

def get_db_connection():
    try:
        import psycopg2
        s = st.secrets["supabase"]
        conn = psycopg2.connect(
            host=s["host"], port=int(s["port"]),
            dbname=s["dbname"], user=s["user"],
            password=s["password"], sslmode="require"
        )
        return conn
    except Exception:
        return None

@st.cache_data(ttl=300)
def load_stores():
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        df = pd.read_sql("SELECT store_id, city, co_op FROM stores", conn)
        df['co_op'] = df['co_op'].str.replace('\n', ' ').str.strip()
        return df
    except Exception:
        return None

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] { background: #FFFFFF; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }

    /* ── Filter bar ── */
    .filter-bar {
        background: #f0f4f8;
        border-bottom: 2px solid #d0d8e4;
        padding: 10px 0 10px 0;
        margin-bottom: 18px;
    }

    /* ── Overall score bubble ── */
    .overall-wrap {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 16px;
        padding: 12px 0 18px 0;
    }
    .overall-bubble {
        width: 64px;
        height: 64px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.6em;
        font-weight: 900;
        color: #FFFFFF;
        flex-shrink: 0;
        box-shadow: 0 4px 18px rgba(0,0,0,0.18);
    }
    .overall-text {
        font-size: 2.0em;
        font-weight: 800;
        color: #111;
        font-family: Arial, sans-serif;
        letter-spacing: 1px;
    }
    .overall-arrow {
        font-size: 1.5em;
        color: #1a3a6e;
    }

    /* ── Category header card ── */
    .cat-header {
        background: #0d2042;
        border-radius: 10px 10px 0 0;
        padding: 14px 16px 12px 16px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 6px;
    }
    .cat-left {
        display: flex;
        align-items: baseline;
        gap: 10px;
    }
    .cat-pct {
        font-size: 1.55em;
        font-weight: 900;
        color: #FFFFFF;
        font-family: Arial, sans-serif;
    }
    .cat-name {
        font-size: 1.05em;
        font-weight: 700;
        color: #FFFFFF;
        font-family: Arial, sans-serif;
        letter-spacing: 0.5px;
    }
    .cat-arrow {
        color: rgba(255,255,255,0.6);
        font-size: 1.1em;
    }

    /* ── Metric card ── */
    .metric-card {
        background: #1e3d6e;
        border-radius: 8px;
        padding: 10px 12px 10px 12px;
        margin-bottom: 7px;
    }
    .metric-top {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 8px;
    }
    .harvey-ball {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.0em;
        font-weight: 900;
        color: #FFFFFF;
    }
    .hb-green  { background: #27AE60; box-shadow: 0 0 8px rgba(39,174,96,0.5); }
    .hb-yellow { background: #F39C12; box-shadow: 0 0 8px rgba(243,156,18,0.5); }
    .hb-red    { background: #E74C3C; box-shadow: 0 0 8px rgba(231,76,60,0.5); }
    .hb-grey   { background: #4a5568; }

    .metric-name-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-grow: 1;
    }
    .metric-name {
        font-size: 0.88em;
        font-weight: 700;
        color: #FFFFFF;
        font-family: Arial, sans-serif;
    }
    .metric-arrow {
        color: rgba(255,255,255,0.5);
        font-size: 0.9em;
    }

    /* ── Stats row ── */
    .stats-row {
        display: flex;
        gap: 6px;
        border-top: 1px solid rgba(255,255,255,0.12);
        padding-top: 7px;
    }
    .stat-cell {
        flex: 1;
        text-align: center;
    }
    .stat-val {
        font-size: 0.92em;
        font-weight: 700;
        color: #FFFFFF;
        font-family: Arial, sans-serif;
        line-height: 1;
    }
    .stat-lbl {
        font-size: 0.60em;
        color: rgba(255,255,255,0.50);
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-top: 2px;
        font-family: Arial, sans-serif;
    }

    /* ── Sample data banner ── */
    .sample-banner {
        background: rgba(245,158,11,0.10);
        border: 1px solid rgba(245,158,11,0.35);
        border-radius: 8px;
        padding: 6px 16px;
        color: #b45309;
        font-size: 0.80em;
        font-weight: 600;
        text-align: center;
        margin-bottom: 14px;
        font-family: Arial, sans-serif;
    }

    /* ── Home/back button ── */
    div[data-testid="stButton"] > button {
        background: #C41230 !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        font-size: 0.88em !important;
        font-weight: 700 !important;
        padding: 6px 18px !important;
    }
    div[data-testid="stButton"] > button:hover {
        background: #a00e26 !important;
    }

    /* ── Legend ── */
    .legend-bar {
        display: flex;
        gap: 28px;
        justify-content: center;
        align-items: center;
        padding: 12px;
        background: #f5f5f5;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        font-family: Arial, sans-serif;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 0.82em;
        color: #444444;
        font-weight: 600;
    }
    .legend-dot {
        width: 14px; height: 14px;
        border-radius: 50%;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────────────────────
def get_status(actual, green_thresh, yellow_thresh, higher=True):
    if actual is None: return "grey"
    if higher:
        return "green" if actual >= green_thresh else ("yellow" if actual >= yellow_thresh else "red")
    else:
        return "green" if actual <= green_thresh else ("yellow" if actual <= yellow_thresh else "red")

def score_from_status(s):
    return {"green": 1.0, "yellow": 0.5, "red": 0.0, "grey": 0.0}[s]

def harvey_html(status):
    symbol = {"green": "✓", "yellow": "!", "red": "✗", "grey": "–"}[status]
    return f'<div class="harvey-ball hb-{status}">{symbol}</div>'

# ── Load store / market data ──────────────────────────────────────────────────
stores_df = load_stores()

if stores_df is not None:
    markets = ["All Markets"] + sorted(stores_df['co_op'].dropna().unique().tolist())
else:
    markets = ["All Markets", "Los Angeles", "Santa Barbara", "San Diego"]

# ── Top bar ──────────────────────────────────────────────────────────────────
home_col, title_col = st.columns([1, 9])
with home_col:
    if st.button("⌂  Home"):
        st.switch_page("app.py")
with title_col:
    st.markdown("""
    <div style="padding-top:6px;">
        <span style="font-size:1.45em;font-weight:800;color:#111111;
                     font-family:Arial,sans-serif;">🎯 &nbsp;Balanced Scorecard</span>
        <span style="font-size:0.9em;color:#C41230;font-weight:700;
                     margin-left:12px;font-family:Arial,sans-serif;">JM Valley Group</span>
    </div>
    """, unsafe_allow_html=True)

# ── Filter bar ───────────────────────────────────────────────────────────────
st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
f1, f2, f3, f4 = st.columns([1.2, 1.5, 2.0, 4])

with f1:
    st.markdown("<div style='font-size:0.72em;font-weight:700;color:#666;text-transform:uppercase;"
                "letter-spacing:1px;margin-bottom:2px;font-family:Arial,sans-serif;'>Period</div>",
                unsafe_allow_html=True)
    selected_period = st.selectbox(
        "Period", ["2026-02", "2026-01", "2025-12", "2025-11"],
        label_visibility="collapsed"
    )

with f2:
    st.markdown("<div style='font-size:0.72em;font-weight:700;color:#666;text-transform:uppercase;"
                "letter-spacing:1px;margin-bottom:2px;font-family:Arial,sans-serif;'>Market</div>",
                unsafe_allow_html=True)
    selected_market = st.selectbox(
        "Market", markets, label_visibility="collapsed"
    )

with f3:
    # Build store list filtered by market
    if stores_df is not None:
        filtered = stores_df.copy()
        if selected_market != "All Markets":
            filtered = filtered[filtered['co_op'] == selected_market]
        store_options = {"All Stores": None}
        for _, r in filtered.sort_values('store_id').iterrows():
            label = f"{r['store_id']} — {STORE_NAMES.get(r['store_id'], r['city'])}"
            store_options[label] = r['store_id']
    else:
        store_options = {"All Stores": None}

    st.markdown("<div style='font-size:0.72em;font-weight:700;color:#666;text-transform:uppercase;"
                "letter-spacing:1px;margin-bottom:2px;font-family:Arial,sans-serif;'>Store</div>",
                unsafe_allow_html=True)
    selected_store_label = st.selectbox(
        "Store", list(store_options.keys()), label_visibility="collapsed"
    )
    selected_store = store_options.get(selected_store_label)

st.markdown("<div style='height:4px;border-bottom:1px solid #e0e0e0;margin-bottom:14px;'></div>",
            unsafe_allow_html=True)

# ── Sample data banner ───────────────────────────────────────────────────────
st.markdown("""
<div class="sample-banner">
    ⚠️ &nbsp; SAMPLE DATA — Connect a live data source to display real metrics
</div>
""", unsafe_allow_html=True)

# ── Scorecard data ───────────────────────────────────────────────────────────
METRICS = {
    "People": {
        "items": [
            {
                "name":          "Certified Managers",
                "actual":        94.2, "green_thresh": 90, "yellow_thresh": 85, "higher": True,
                "actual_fmt":    "94.2%", "target_fmt": "≥ 90%",
                "pts_avail": 488, "pts_scored": 464, "average": "94.2%", "inlier_pct": "95%",
            },
            {
                "name":          "Team & Shift Turnover",
                "actual":        88.0, "green_thresh": 100, "yellow_thresh": 120, "higher": False,
                "actual_fmt":    "88%", "target_fmt": "≤ 100%",
                "pts_avail": 488, "pts_scored": 352, "average": "103%", "inlier_pct": "72%",
            },
            {
                "name":          "Staffing vs. Benchmark",
                "actual":        100.0, "green_thresh": 100, "yellow_thresh": 95, "higher": False,
                "actual_fmt":    "100%", "target_fmt": "≤ 100%",
                "pts_avail": 488, "pts_scored": 488, "average": "100%", "inlier_pct": "100%",
            },
        ],
    },
    "Customer": {
        "items": [
            {
                "name":          "Speed (OTD)",
                "actual":        208, "green_thresh": 210, "yellow_thresh": 240, "higher": False,
                "actual_fmt":    "3:28", "target_fmt": "≤ 3:30",
                "pts_avail": 488, "pts_scored": 352, "average": "3:25", "inlier_pct": "72%",
            },
            {
                "name":          "Supreme Rating",
                "actual":        4.1, "green_thresh": 4.0, "yellow_thresh": 3.8, "higher": True,
                "actual_fmt":    "4.1", "target_fmt": "≥ 4.0",
                "pts_avail": 488, "pts_scored": 440, "average": "4.1", "inlier_pct": "90%",
            },
            {
                "name":          "Complaints",
                "actual":        7, "green_thresh": 5, "yellow_thresh": 8, "higher": False,
                "actual_fmt":    "7", "target_fmt": "≤ 5",
                "pts_avail": 488, "pts_scored": 232, "average": "9.5", "inlier_pct": "48%",
            },
            {
                "name":          "Core OPS, F/S",
                "actual":        98.0, "green_thresh": 98, "yellow_thresh": 95, "higher": True,
                "actual_fmt":    "98%", "target_fmt": "≥ 98%",
                "pts_avail": 488, "pts_scored": 244, "average": "—", "inlier_pct": "98%",
            },
        ],
    },
    "Sales": {
        "items": [
            {
                "name":          "Sales vs. Budget",
                "actual":        102.3, "green_thresh": 100, "yellow_thresh": 97, "higher": True,
                "actual_fmt":    "+2.3%", "target_fmt": "≥ 100%",
                "pts_avail": 488, "pts_scored": 376, "average": "2.7%", "inlier_pct": "77%",
            },
            {
                "name":          "Transactions vs. Budget",
                "actual":        99.1, "green_thresh": 100, "yellow_thresh": 97, "higher": True,
                "actual_fmt":    "-0.9%", "target_fmt": "≥ 100%",
                "pts_avail": 488, "pts_scored": 384, "average": "2.8%", "inlier_pct": "79%",
            },
            {
                "name":          "Hours of Operation",
                "actual":        99.0, "green_thresh": 100, "yellow_thresh": 98, "higher": True,
                "actual_fmt":    "99%", "target_fmt": "≥ 100%",
                "pts_avail": 488, "pts_scored": 440, "average": "-0.65…", "inlier_pct": "90%",
            },
        ],
    },
    "Profit": {
        "items": [
            {
                "name":          "iCOS",
                "actual":        27.8, "green_thresh": 28, "yellow_thresh": 30, "higher": False,
                "actual_fmt":    "27.8%", "target_fmt": "≤ 28%",
                "pts_avail": 488, "pts_scored": 408, "average": "2.34%", "inlier_pct": "84%",
            },
            {
                "name":          "Labor Hours",
                "actual":        -1.8, "green_thresh": 0, "yellow_thresh": 2, "higher": False,
                "actual_fmt":    "-1.8%", "target_fmt": "≤ 0%",
                "pts_avail": 488, "pts_scored": 448, "average": "-3.2%", "inlier_pct": "92%",
            },
            {
                "name":          "Mgr Control vs. Budget",
                "actual":        98.2, "green_thresh": 100, "yellow_thresh": 97, "higher": True,
                "actual_fmt":    "-1.8%", "target_fmt": "≥ 100%",
                "pts_avail": 488, "pts_scored": 280, "average": "-1.6%", "inlier_pct": "57%",
            },
            {
                "name":          "R&M vs. Budget",
                "actual":        80.0, "green_thresh": 100, "yellow_thresh": 110, "higher": False,
                "actual_fmt":    "-20.0%", "target_fmt": "≤ 100%",
                "pts_avail": 488, "pts_scored": 376, "average": "-20.0%", "inlier_pct": "77%",
            },
        ],
    },
}

# ── Compute scores ────────────────────────────────────────────────────────────
for cat_name, cat in METRICS.items():
    for item in cat["items"]:
        item["_status"] = get_status(item["actual"], item["green_thresh"],
                                     item["yellow_thresh"], item["higher"])

all_scores = [score_from_status(item["_status"])
              for cat in METRICS.values() for item in cat["items"]]
overall_pct = int(round(sum(all_scores) / len(all_scores) * 100)) if all_scores else 0

if overall_pct >= 80:
    ov_color = "#27AE60"; ov_shadow = "rgba(39,174,96,0.4)"
elif overall_pct >= 60:
    ov_color = "#F39C12"; ov_shadow = "rgba(243,156,18,0.4)"
else:
    ov_color = "#E74C3C"; ov_shadow = "rgba(231,76,60,0.4)"

# ── Overall score row ─────────────────────────────────────────────────────────
st.markdown(f"""
<div class="overall-wrap">
    <div class="overall-bubble" style="background:{ov_color};box-shadow:0 4px 18px {ov_shadow};">
        BSC
    </div>
    <div class="overall-text">{overall_pct}%</div>
    <div class="overall-arrow">→</div>
</div>
""", unsafe_allow_html=True)

# ── Category columns ──────────────────────────────────────────────────────────
CATEGORY_COLORS = {
    "People":   "#2563b0",
    "Customer": "#059669",
    "Sales":    "#7c3aed",
    "Profit":   "#C41230",
}

cols = st.columns(4)

for col, (cat_name, cat) in zip(cols, METRICS.items()):
    items = cat["items"]
    cat_scores = [score_from_status(it["_status"]) for it in items]
    cat_pct = int(round(sum(cat_scores) / len(cat_scores) * 100))
    cat_color = "#27AE60" if cat_pct >= 80 else ("#F39C12" if cat_pct >= 60 else "#E74C3C")
    accent = CATEGORY_COLORS[cat_name]

    with col:
        # ── Category header card ──
        st.markdown(f"""
        <div class="cat-header" style="border-left: 4px solid {accent};">
            <div class="cat-left">
                <span class="cat-pct" style="color:{cat_color};">{cat_pct}%</span>
                <span class="cat-name">{cat_name}</span>
            </div>
            <span class="cat-arrow">→</span>
        </div>
        """, unsafe_allow_html=True)

        # ── Metric cards ──
        for item in items:
            hb = harvey_html(item["_status"])
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-top">
                    {hb}
                    <div class="metric-name-row">
                        <span class="metric-name">{item['name']}</span>
                        <span class="metric-arrow">→</span>
                    </div>
                </div>
                <div class="stats-row">
                    <div class="stat-cell">
                        <div class="stat-val">{item['pts_avail']}</div>
                        <div class="stat-lbl">Pts Avail</div>
                    </div>
                    <div class="stat-cell">
                        <div class="stat-val">{item['pts_scored']}</div>
                        <div class="stat-lbl">Pts Scored</div>
                    </div>
                    <div class="stat-cell">
                        <div class="stat-val">{item['average']}</div>
                        <div class="stat-lbl">Average</div>
                    </div>
                    <div class="stat-cell">
                        <div class="stat-val">{item['inlier_pct']}</div>
                        <div class="stat-lbl">Inlier %</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ── Legend ────────────────────────────────────────────────────────────────────
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
st.markdown("""
<div class="legend-bar">
    <div class="legend-item">
        <span class="legend-dot" style="background:#27AE60;"></span> At or above target
    </div>
    <div class="legend-item">
        <span class="legend-dot" style="background:#F39C12;"></span> Near target
    </div>
    <div class="legend-item">
        <span class="legend-dot" style="background:#E74C3C;"></span> Below target
    </div>
</div>
""", unsafe_allow_html=True)
