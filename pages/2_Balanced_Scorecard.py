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
    initial_sidebar_state="auto",
)

SAN_DIEGO_STORE_IDS = ['20071','20091','20171','20177','20291','20292','20300']

STORE_NAMES = {
    '20156':'North Hollywood','20218':'Mission Hills','20267':'Balboa',
    '20294':'Toluca','20026':'Tampa','20311':'Porter Ranch',
    '20352':'San Fernando','20363':'Warner Center','20273':'Big Bear',
    '20366':'Burbank North','20011':'Westlake','20255':'Arboles',
    '20048':'Janss','20245':'Wendy','20381':'Sylmar',
    '20116':'Encino','20388':'Lake Arrowhead','20075':'Isla Vista',
    '20335':'Goleta','20360':'Santa Barbara','20424':'Studio City',
    '20177':'SD1','20171':'SD2','20091':'SD3',
    '20071':'SD4','20300':'SD5','20292':'SD6',
    '20291':'SD7','20013':'Buellton',
}

_LOGO = "data:image/avif;base64,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"

def get_db_connection():
    try:
        import psycopg2
        s = st.secrets["supabase"]
        return psycopg2.connect(
            host=s["host"], port=int(s["port"]),
            dbname=s["dbname"], user=s["user"],
            password=s["password"], sslmode="require"
        )
    except Exception:
        return None

@st.cache_data(ttl=300)
def load_stores():
    conn = get_db_connection()
    if conn is None:
        return None
    try:
        df = pd.read_sql("SELECT store_id, city, co_op FROM stores", conn)
        df["co_op"] = df["co_op"].str.replace("\n"," ").str.strip()
        return df
    except Exception:
        return None

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>[  /* No horizontal page scroll on mobile */
  html, body, .stApp {{ overflow-x: hidden !important; max-width: 100vw !important; }}
data-testid="stAppViewContainer"] { background:#F5F6F8; }
    footer { visibility:hidden; }
    #MainMenu { visibility:hidden; }
    header { visibility:hidden; }
    [data-testid="stToolbar"] { visibility: visible !important; }
    [data-testid="stExpandSidebarButton"],
    [data-testid="stExpandSidebarButton"] * { visibility: visible !important; }
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapseButton"] * { visibility: visible !important; }

    /* Full width — remove Streamlit's default side padding */
    .block-container {
        padding: 0.75rem 1.25rem 1.5rem !important;
        max-width: 100% !important;
    }

    /* ── Top-align all columns ── */
    div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
        vertical-align: top !important;
        align-self: flex-start !important;
    }

    /* ── Overall score strip ── */
    .overall-strip {
        display:flex; align-items:center; justify-content:center; gap:14px;
        background:#FFFFFF; border:1.5px solid #E0E3E8; border-radius:10px;
        padding:10px 24px; margin-bottom:14px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.06);
    }
    .overall-bubble {
        width:48px; height:48px; border-radius:50%;
        display:flex; align-items:center; justify-content:center;
        font-size:11px; font-weight:900; color:#FFFFFF;
        text-transform:uppercase; letter-spacing:0.5px; font-family:Arial,sans-serif;
    }
    .overall-pct {
        font-size:2.2em; font-weight:900; color:#1a1a2e;
        font-family:Arial,sans-serif; line-height:1;
    }
    .overall-label {
        font-size:11px; font-weight:700; color:#6B7280;
        font-family:Arial,sans-serif; letter-spacing:1.5px; text-transform:uppercase;
    }

    /* ── Category header card ── */
    .cat-header {
        background: #134A7C;
        border-radius: 10px 10px 0 0;
        padding: 14px 16px;
        display: flex; align-items: center; justify-content: space-between;
        box-sizing: border-box;
    }
    .cat-left { display:flex; align-items:center; gap:10px; }
    .cat-bubble {
        width:34px; height:34px; border-radius:50%;
        display:flex; align-items:center; justify-content:center;
        font-size:14px; font-weight:900; color:#FFFFFF;
        box-shadow: 0 0 8px rgba(0,0,0,0.3);
        flex-shrink: 0;
    }
    .cat-name {
        font-size:15px; font-weight:800; color:#FFFFFF;
        font-family:Arial,sans-serif; letter-spacing:0.5px;
    }
    .cat-pct {
        font-size:20px; font-weight:900; color:#FFFFFF;
        font-family:Arial,sans-serif;
    }

    /* ── Metric card (white, colored left border) ── */
    .metric-card {
        background: #FFFFFF;
        border: 1px solid #E0E3E8;
        border-radius: 0;
        padding: 10px 14px;
        margin-bottom: 0;
        box-sizing: border-box;
        border-top: none;
    }
    .metric-card:last-child {
        border-radius: 0 0 10px 10px;
        margin-bottom: 12px;
    }
    .metric-top {
        display:flex; align-items:center; gap:10px; margin-bottom:8px;
    }
    .harvey-ball {
        width:28px; height:28px; border-radius:50%; flex-shrink:0;
        display:flex; align-items:center; justify-content:center;
        font-size:13px; font-weight:900; color:#FFFFFF;
    }
    .hb-green  { background:#27AE60; box-shadow:0 0 6px rgba(39,174,96,0.4); }
    .hb-yellow { background:#F39C12; box-shadow:0 0 6px rgba(243,156,18,0.4); }
    .hb-red    { background:#E74C3C; box-shadow:0 0 6px rgba(231,76,60,0.4); }
    .hb-grey   { background:#9CA3AF; }
    .metric-name-row {
        display:flex; align-items:center; justify-content:space-between; flex-grow:1;
    }
    .metric-name {
        font-size:13px; font-weight:700; color:#1a1a2e; font-family:Arial,sans-serif;
    }
    .stats-row {
        display:flex; gap:0; border-top:1px solid #E0E3E8; padding-top:8px;
    }
    .stat-cell { flex:1; text-align:center; }
    .stat-cell + .stat-cell { border-left: 1px solid #E0E3E8; }
    .stat-val {
        font-size:13px; font-weight:700; color:#1a1a2e;
        font-family:Arial,sans-serif; line-height:1;
    }
    .stat-lbl {
        font-size:10px; color:#6B7280; text-transform:uppercase;
        letter-spacing:0.5px; margin-top:3px; font-family:Arial,sans-serif;
    }

    /* ── Legend ── */
    .legend-bar {
        display:flex; gap:24px; justify-content:center; align-items:center;
        padding:8px 16px; background:#FFFFFF; border-radius:8px;
        border:1px solid #E0E3E8; font-family:Arial,sans-serif; margin-top:12px;
    }
    .legend-item {
        display:flex; align-items:center; gap:7px;
        font-size:12px; color:#444; font-weight:600;
    }
    .legend-dot { width:11px; height:11px; border-radius:50%; display:inline-block; }
</style>
""", unsafe_allow_html=True)

# ── Helpers ──────────────────────────────────────────────────────────────────
def get_status(actual, green_thresh, yellow_thresh, higher=True):
    if actual is None: return "grey"
    if higher:
        return "green" if actual>=green_thresh else ("yellow" if actual>=yellow_thresh else "red")
    else:
        return "green" if actual<=green_thresh else ("yellow" if actual<=yellow_thresh else "red")

def score_from_status(s):
    return {"green":1.0,"yellow":0.5,"red":0.0,"grey":0.0}[s]

def harvey_html(status):
    sym = {"green":"✓","yellow":"!","red":"✗","grey":"–"}[status]
    return f'<div class="harvey-ball hb-{status}">{sym}</div>'

# ── Load stores ───────────────────────────────────────────────────────────────
stores_df = load_stores()
markets = (["All Markets"]+sorted(stores_df["co_op"].dropna().unique().tolist())
           if stores_df is not None else ["All Markets","Los Angeles","Santa Barbara","San Diego"])

# ── HEADER ROW: logo | period | market | store | home ─────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;
            background:#134A7C;border-radius:10px;padding:12px 20px;
            margin-bottom:14px;">
    <img src="{_LOGO}" style="height:44px;width:auto;flex-shrink:0;"/>
    <div style="font-size:13px;font-weight:800;color:#FFFFFF;letter-spacing:2px;
                text-transform:uppercase;font-family:Arial,sans-serif;margin-right:16px;">
        Balanced Scorecard
    </div>
</div>
""", unsafe_allow_html=True)

ctrl_col1, ctrl_col2, ctrl_col3, ctrl_col4 = st.columns([1.2, 1.5, 2.5, 0.8])
with ctrl_col1:
    selected_period = st.selectbox("Period", ["2026-02","2026-01","2025-12","2025-11"])
with ctrl_col2:
    selected_market = st.selectbox("Market", markets)
with ctrl_col3:
    if stores_df is not None:
        filtered = stores_df.copy()
        if selected_market != "All Markets":
            filtered = filtered[filtered["co_op"]==selected_market]
        store_opts = {"All Stores":None}
        for _, r in filtered.sort_values("store_id").iterrows():
            sid = r["store_id"]
            store_opts[f"{sid} — {STORE_NAMES.get(sid, r['city'])}"] = sid
    else:
        store_opts = {"All Stores":None}
    selected_store_label = st.selectbox("Store", list(store_opts.keys()))
    selected_store = store_opts.get(selected_store_label)
with ctrl_col4:
    st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
    if st.button("⌂  Home", key="home_btn"):
        st.switch_page("app.py")

# ── Scorecard data ────────────────────────────────────────────────────────────
METRICS = {
    "People":{
        "bg":"#134A7C",
        "items":[
            {"name":"Certified Managers",    "actual":94.2,"green_thresh":90, "yellow_thresh":85, "higher":True,
              "pts_avail":488,"pts_scored":464,"average":"94.2%","inlier_pct":"95%"},
            {"name":"Team & Shift Turnover", "actual":88.0,"green_thresh":100,"yellow_thresh":120,"higher":False,
              "pts_avail":488,"pts_scored":352,"average":"103%", "inlier_pct":"72%"},
            {"name":"Staffing vs. Benchmark","actual":100.0,"green_thresh":100,"yellow_thresh":95, "higher":False,
              "pts_avail":488,"pts_scored":488,"average":"100%", "inlier_pct":"100%"},
        ],
    },
    "Customer":{
        "bg":"#134A7C",
        "items":[
            {"name":"Speed (OTD)",   "actual":208, "green_thresh":210,"yellow_thresh":240,"higher":False,
              "pts_avail":488,"pts_scored":352,"average":"3:25","inlier_pct":"72%"},
            {"name":"Supreme Rating","actual":4.1, "green_thresh":4.0,"yellow_thresh":3.8,"higher":True,
              "pts_avail":488,"pts_scored":440,"average":"4.1", "inlier_pct":"90%"},
            {"name":"Complaints",   "actual":7,   "green_thresh":5,  "yellow_thresh":8,  "higher":False,
              "pts_avail":488,"pts_scored":232,"average":"9.5", "inlier_pct":"48%"},
            {"name":"Core OPS, F/S","actual":98.0,"green_thresh":98, "yellow_thresh":95, "higher":True,
              "pts_avail":488,"pts_scored":478,"average":"98%", "inlier_pct":"98%"},
        ],
    },
    "Sales":{
        "bg":"#134A7C",
        "items":[
            {"name":"Sales vs. Budget",        "actual":102.3,"green_thresh":100,"yellow_thresh":97,"higher":True,
              "pts_avail":488,"pts_scored":376,"average":"2.7%", "inlier_pct":"77%"},
            {"name":"Transactions vs. Budget", "actual":99.1, "green_thresh":100,"yellow_thresh":97,"higher":True,
              "pts_avail":488,"pts_scored":384,"average":"2.8%", "inlier_pct":"79%"},
            {"name":"Hours of Operation",      "actual":99.0, "green_thresh":100,"yellow_thresh":98,"higher":True,
              "pts_avail":488,"pts_scored":440,"average":"-0.6%","inlier_pct":"90%"},
        ],
    },
    "Profit":{
        "bg":"#134A7C",
        "items":[
            {"name":"iCOS",                   "actual":27.8,"green_thresh":28, "yellow_thresh":30, "higher":False,
              "pts_avail":488,"pts_scored":408,"average":"2.34%","inlier_pct":"84%"},
            {"name":"Labor Hours",            "actual":-1.8,"green_thresh":0,  "yellow_thresh":2,  "higher":False,
              "pts_avail":488,"pts_scored":448,"average":"-3.2%","inlier_pct":"92%"},
            {"name":"Mgr Control vs. Budget", "actual":98.2,"green_thresh":100,"yellow_thresh":97, "higher":True,
              "pts_avail":488,"pts_scored":280,"average":"-1.6%","inlier_pct":"57%"},
            {"name":"R&M vs. Budget",         "actual":80.0,"green_thresh":100,"yellow_thresh":110,"higher":False,
              "pts_avail":488,"pts_scored":376,"average":"-20%","inlier_pct":"77%"},
        ],
    },
}

# Compute scores
for cat in METRICS.values():
    for item in cat["items"]:
        item["_status"] = get_status(item["actual"],item["green_thresh"],item["yellow_thresh"],item["higher"])

all_scores = [score_from_status(it["_status"]) for cat in METRICS.values() for it in cat["items"]]
overall_pct = int(round(sum(all_scores)/len(all_scores)*100)) if all_scores else 0
ov_color = "#27AE60" if overall_pct>=80 else ("#F39C12" if overall_pct>=60 else "#E74C3C")
ov_shadow = "rgba(39,174,96,0.3)" if overall_pct>=80 else ("rgba(243,156,18,0.3)" if overall_pct>=60 else "rgba(231,76,60,0.3)")

# ── Overall score strip ───────────────────────────────────────────────────────
st.markdown(f'''
<div class="overall-strip">
    <div class="overall-bubble" style="background:{ov_color};box-shadow:0 3px 12px {ov_shadow};">BSC</div>
    <div>
        <div class="overall-pct">{overall_pct}%</div>
        <div class="overall-label">Overall Score</div>
    </div>
</div>
''', unsafe_allow_html=True)

# ── Category columns ──────────────────────────────────────────────────────────
cols = st.columns(4)

for col,(cat_name,cat) in zip(cols,METRICS.items()):
    items = cat["items"]
    cat_scores = [score_from_status(it["_status"]) for it in items]
    cat_pct = int(round(sum(cat_scores)/len(cat_scores)*100))
    cb_color = "#27AE60" if cat_pct>=80 else ("#F39C12" if cat_pct>=60 else "#E74C3C")
    sym = "✓" if cat_pct>=80 else ("!" if cat_pct>=60 else "✗")
    cat_bg = cat["bg"]

    with col:
        st.markdown(f'''
        <div class="cat-header" style="background:{cat_bg};">
            <div class="cat-left">
                <div class="cat-bubble" style="background:{cb_color};">{sym}</div>
                <span class="cat-name">{cat_name}</span>
            </div>
            <span class="cat-pct">{cat_pct}%</span>
        </div>
        ''', unsafe_allow_html=True)

        for idx, item in enumerate(items):
            hb     = harvey_html(item["_status"])
            iname  = item["name"]
            iavail = item["pts_avail"]
            iscored= item["pts_scored"]
            iavg   = item["average"]
            iinlier= item["inlier_pct"]
            is_last = idx == len(items) - 1
            extra_cls = " last-card" if is_last else ""
            # Left border color matches status
            border_colors = {"green":"#27AE60","yellow":"#F39C12","red":"#E74C3C","grey":"#9CA3AF"}
            left_border = border_colors.get(item["_status"], "#9CA3AF")
            radius = "border-radius:0 0 10px 10px;" if is_last else ""
            mb = "margin-bottom:12px;" if is_last else ""
            st.markdown(f'''
            <div class="metric-card" style="border-left:4px solid {left_border};{radius}{mb}">
                <div class="metric-top">
                    {hb}
                    <div class="metric-name-row">
                        <span class="metric-name">{iname}</span>
                    </div>
                </div>
                <div class="stats-row">
                    <div class="stat-cell">
                        <div class="stat-val">{iavail}</div>
                        <div class="stat-lbl">Pts Avail</div>
                    </div>
                    <div class="stat-cell">
                        <div class="stat-val">{iscored}</div>
                        <div class="stat-lbl">Pts Scored</div>
                    </div>
                    <div class="stat-cell">
                        <div class="stat-val">{iavg}</div>
                        <div class="stat-lbl">Average</div>
                    </div>
                    <div class="stat-cell">
                        <div class="stat-val">{iinlier}</div>
                        <div class="stat-lbl">Inlier %</div>
                    </div>
                </div>
            </div>
            ''', unsafe_allow_html=True)

# ── Legend ────────────────────────────────────────────────────────────────────
st.markdown('''
<div class="legend-bar">
    <div class="legend-item"><span class="legend-dot" style="background:#27AE60;"></span> At or above target</div>
    <div class="legend-item"><span class="legend-dot" style="background:#F39C12;"></span> Near target</div>
    <div class="legend-item"><span class="legend-dot" style="background:#E74C3C;"></span> Below target</div>
</div>
''', unsafe_allow_html=True)
