"""
pages/2_Balanced_Scorecard.py
JM Valley Group — Operational Balanced Scorecard
Placeholder data — connect live data source to activate.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Balanced Scorecard | JM Valley Group",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: #FFFFFF;
    }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }

    /* ── Top bar ── */
    .bsc-topbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 18px 0 6px 0;
        margin-bottom: 4px;
    }
    .bsc-title {
        font-size: 1.55em;
        font-weight: 800;
        color: #111111;
        letter-spacing: 1px;
        font-family: Arial, sans-serif;
    }
    .bsc-period {
        font-size: 0.85em;
        color: #888888;
        letter-spacing: 1px;
        font-family: Arial, sans-serif;
    }

    /* ── Sample data banner ── */
    .sample-banner {
        background: rgba(245,158,11,0.10);
        border: 1px solid rgba(245,158,11,0.35);
        border-radius: 8px;
        padding: 8px 18px;
        color: #b45309;
        font-size: 0.82em;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-align: center;
        margin-bottom: 18px;
        font-family: Arial, sans-serif;
    }

    /* ── Overall score bubble ── */
    .overall-wrap {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 28px;
    }
    .overall-bubble {
        width: 130px;
        height: 130px;
        border-radius: 50%;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        box-shadow: 0 6px 30px rgba(0,0,0,0.18);
    }
    .overall-score {
        font-size: 2.6em;
        font-weight: 900;
        color: #FFFFFF;
        line-height: 1;
    }
    .overall-label {
        font-size: 0.72em;
        color: rgba(255,255,255,0.85);
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-top: 4px;
        font-family: Arial, sans-serif;
        font-weight: 600;
    }

    /* ── Category column ── */
    .cat-header {
        border-radius: 12px 12px 0 0;
        padding: 16px 16px 14px 16px;
        text-align: center;
        margin-bottom: 2px;
    }
    .cat-pct {
        font-size: 1.8em;
        font-weight: 900;
        color: #FFFFFF;
    }
    .cat-name {
        font-size: 0.95em;
        font-weight: 700;
        color: rgba(255,255,255,0.90);
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-top: 2px;
        font-family: Arial, sans-serif;
    }

    /* ── Metric card ── */
    .metric-card {
        background: #112240;
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 10px;
        padding: 14px 16px 12px 16px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .metric-card:hover {
        border-color: rgba(255,255,255,0.20);
        background: #152a4e;
    }
    .status-circle {
        width: 36px;
        height: 36px;
        border-radius: 50%;
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1em;
        font-weight: 900;
        color: #FFFFFF;
    }
    .circle-green  { background: #27AE60; box-shadow: 0 0 10px rgba(39,174,96,0.4); }
    .circle-yellow { background: #F39C12; box-shadow: 0 0 10px rgba(243,156,18,0.4); }
    .circle-red    { background: #E74C3C; box-shadow: 0 0 10px rgba(231,76,60,0.4); }
    .circle-grey   { background: #4a5568; }

    .metric-body { flex-grow: 1; min-width: 0; }
    .metric-name {
        font-size: 0.92em;
        font-weight: 700;
        color: #FFFFFF;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-family: Arial, sans-serif;
    }
    .metric-stats {
        display: flex;
        gap: 18px;
        margin-top: 6px;
    }
    .stat-block { text-align: center; }
    .stat-val {
        font-size: 1.0em;
        font-weight: 700;
        color: #FFFFFF;
        line-height: 1;
        font-family: Arial, sans-serif;
    }
    .stat-lbl {
        font-size: 0.65em;
        color: rgba(255,255,255,0.55);
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-top: 2px;
        font-family: Arial, sans-serif;
    }
    .metric-target {
        font-size: 0.72em;
        color: rgba(255,255,255,0.45);
        margin-top: 3px;
        font-family: Arial, sans-serif;
    }

    /* ── Back / Home button ── */
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
        color: #ffffff !important;
    }

    /* ── Legend ── */
    .legend-bar {
        display: flex;
        gap: 28px;
        justify-content: center;
        align-items: center;
        padding: 14px;
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
        width: 14px;
        height: 14px;
        border-radius: 50%;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# ── Helper: determine status ─────────────────────────────────────────────────
def get_status(actual, green_thresh, yellow_thresh, higher_is_better=True):
    """Returns 'green', 'yellow', or 'red'."""
    if actual is None:
        return "grey"
    if higher_is_better:
        if actual >= green_thresh:
            return "green"
        elif actual >= yellow_thresh:
            return "yellow"
        else:
            return "red"
    else:
        if actual <= green_thresh:
            return "green"
        elif actual <= yellow_thresh:
            return "yellow"
        else:
            return "red"

def status_circle_html(status):
    label = {"green": "✓", "yellow": "!", "red": "✗", "grey": "–"}[status]
    return f'<div class="status-circle circle-{status}">{label}</div>'

def score_from_status(status):
    return {"green": 1.0, "yellow": 0.5, "red": 0.0, "grey": 0.0}[status]

# ── Placeholder Data ─────────────────────────────────────────────────────────
PERIOD = "2026-02"

METRICS = {
    "People": {
        "color": "#2563b0",
        "bg":    "linear-gradient(135deg,#1a3a6e,#1e4080)",
        "emoji": "👥",
        "items": [
            {
                "name":             "Certified Managers",
                "actual":           94.2,
                "actual_fmt":       "94.2%",
                "target_fmt":       "≥ 90%",
                "green_thresh":     90,
                "yellow_thresh":    85,
                "higher":           True,
                "stores":           "28 / 30",
                "vs_prior":         "+2.1%",
            },
            {
                "name":             "Team Turnover",
                "actual":           88.0,
                "actual_fmt":       "88%",
                "target_fmt":       "≤ 100%",
                "green_thresh":     100,
                "yellow_thresh":    120,
                "higher":           False,
                "stores":           "—",
                "vs_prior":         "-5.0%",
            },
        ],
    },
    "Customer": {
        "color": "#059669",
        "bg":    "linear-gradient(135deg,#0a4a30,#0d5a38)",
        "emoji": "⭐",
        "items": [
            {
                "name":             "Speed (OTD)",
                "actual":           208,
                "actual_fmt":       "3:28",
                "target_fmt":       "≤ 3:30",
                "green_thresh":     210,
                "yellow_thresh":    240,
                "higher":           False,
                "stores":           "27 / 30",
                "vs_prior":         "-0:04",
            },
            {
                "name":             "Accuracy",
                "actual":           97.8,
                "actual_fmt":       "97.8%",
                "target_fmt":       "≥ 98%",
                "green_thresh":     98,
                "yellow_thresh":    96,
                "higher":           True,
                "stores":           "24 / 30",
                "vs_prior":         "+0.3%",
            },
            {
                "name":             "Complaints",
                "actual":           7,
                "actual_fmt":       "7",
                "target_fmt":       "≤ 5",
                "green_thresh":     5,
                "yellow_thresh":    8,
                "higher":           False,
                "stores":           "—",
                "vs_prior":         "+2",
            },
        ],
    },
    "Sales": {
        "color": "#7c3aed",
        "bg":    "linear-gradient(135deg,#2d1a5e,#3b2070)",
        "emoji": "💰",
        "items": [
            {
                "name":             "Sales vs. Budget",
                "actual":           102.3,
                "actual_fmt":       "+2.3%",
                "target_fmt":       "≥ 100%",
                "green_thresh":     100,
                "yellow_thresh":    97,
                "higher":           True,
                "stores":           "22 / 30",
                "vs_prior":         "+1.1%",
            },
            {
                "name":             "Trans vs. Budget",
                "actual":           99.1,
                "actual_fmt":       "-0.9%",
                "target_fmt":       "≥ 100%",
                "green_thresh":     100,
                "yellow_thresh":    97,
                "higher":           True,
                "stores":           "18 / 30",
                "vs_prior":         "-0.5%",
            },
        ],
    },
    "Profit": {
        "color": "#C41230",
        "bg":    "linear-gradient(135deg,#8b0000,#C41230)",
        "emoji": "📈",
        "items": [
            {
                "name":             "COGS / Waste",
                "actual":           27.8,
                "actual_fmt":       "27.8%",
                "target_fmt":       "≤ 28%",
                "green_thresh":     28,
                "yellow_thresh":    30,
                "higher":           False,
                "stores":           "21 / 30",
                "vs_prior":         "-0.4%",
            },
            {
                "name":             "Labor Hours",
                "actual":           -1.8,
                "actual_fmt":       "-1.8%",
                "target_fmt":       "≤ 0%",
                "green_thresh":     0,
                "yellow_thresh":    2,
                "higher":           False,
                "stores":           "23 / 30",
                "vs_prior":         "-0.6%",
            },
            {
                "name":             "Ctrl Profit vs. Budget",
                "actual":           98.2,
                "actual_fmt":       "-1.8%",
                "target_fmt":       "≥ 100%",
                "green_thresh":     100,
                "yellow_thresh":    97,
                "higher":           True,
                "stores":           "16 / 30",
                "vs_prior":         "+1.2%",
            },
        ],
    },
}

# ── Compute overall score ────────────────────────────────────────────────────
all_statuses = []
for cat_data in METRICS.values():
    for item in cat_data["items"]:
        s = get_status(item["actual"], item["green_thresh"],
                       item["yellow_thresh"], item["higher"])
        all_statuses.append(score_from_status(s))

overall_pct = int(round(sum(all_statuses) / len(all_statuses) * 100)) if all_statuses else 0
if overall_pct >= 80:
    overall_color = "#27AE60"
    overall_shadow = "rgba(39,174,96,0.45)"
elif overall_pct >= 60:
    overall_color = "#F39C12"
    overall_shadow = "rgba(243,156,18,0.45)"
else:
    overall_color = "#E74C3C"
    overall_shadow = "rgba(231,76,60,0.45)"

# ── Top bar ──────────────────────────────────────────────────────────────────
back_col, title_col, period_col = st.columns([1, 6, 2])
with back_col:
    if st.button("← Home"):
        st.switch_page("app.py")
with title_col:
    st.markdown(f"""
    <div style="padding-top:8px;">
        <span style="font-size:1.5em;font-weight:800;color:#111111;
                     font-family:Arial,sans-serif;vertical-align:middle;">
            🎯 &nbsp;Balanced Scorecard
        </span>
        <span style="font-size:0.9em;color:#C41230;font-weight:700;
                     margin-left:12px;font-family:Arial,sans-serif;">
            JM Valley Group
        </span>
    </div>
    """, unsafe_allow_html=True)
with period_col:
    st.markdown(f"""
    <div style="text-align:right;padding-top:14px;color:#888888;font-size:0.85em;
                letter-spacing:1px;font-family:Arial,sans-serif;">PERIOD: {PERIOD}</div>
    """, unsafe_allow_html=True)

# Sample-data banner
st.markdown("""
<div class="sample-banner">
    ⚠️ &nbsp; SAMPLE DATA — Connect a live data source to display real metrics
</div>
""", unsafe_allow_html=True)

# ── Overall score bubble ─────────────────────────────────────────────────────
oc1, oc2, oc3, oc4, oc5 = st.columns([2, 1, 1, 1, 2])
with oc3:
    st.markdown(f"""
    <div class="overall-wrap">
        <div class="overall-bubble"
             style="background:{overall_color};
                    box-shadow:0 6px 30px {overall_shadow};">
            <div class="overall-score">{overall_pct}%</div>
            <div class="overall-label">Overall</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

# ── Category columns ─────────────────────────────────────────────────────────
cols = st.columns(4)

for col, (cat_name, cat_data) in zip(cols, METRICS.items()):
    items = cat_data["items"]

    # Category score
    cat_scores = [
        score_from_status(
            get_status(it["actual"], it["green_thresh"], it["yellow_thresh"], it["higher"])
        )
        for it in items
    ]
    cat_pct = int(round(sum(cat_scores) / len(cat_scores) * 100))
    cat_color = "#27AE60" if cat_pct >= 80 else ("#F39C12" if cat_pct >= 60 else "#E74C3C")

    with col:
        # Category header
        st.markdown(f"""
        <div class="cat-header" style="background:{cat_data['bg']};">
            <div style="font-size:1.5em;margin-bottom:4px;">{cat_data['emoji']}</div>
            <div class="cat-pct" style="color:{cat_color};">{cat_pct}%</div>
            <div class="cat-name">{cat_name}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Metric cards
        for item in items:
            status = get_status(
                item["actual"], item["green_thresh"],
                item["yellow_thresh"], item["higher"]
            )
            circle = status_circle_html(status)
            trend_color = "#5ef095" if item["vs_prior"].startswith("+") else (
                "#ff8080" if item["vs_prior"].startswith("-") else "#cccccc"
            )
            # For metrics where lower is better, reverse trend colors
            if not item["higher"]:
                trend_color = "#ff8080" if item["vs_prior"].startswith("+") else (
                    "#5ef095" if item["vs_prior"].startswith("-") else "#cccccc"
                )

            st.markdown(f"""
            <div class="metric-card">
                {circle}
                <div class="metric-body">
                    <div class="metric-name">{item['name']}</div>
                    <div class="metric-stats">
                        <div class="stat-block">
                            <div class="stat-val">{item['actual_fmt']}</div>
                            <div class="stat-lbl">Actual</div>
                        </div>
                        <div class="stat-block">
                            <div class="stat-val">{item['target_fmt']}</div>
                            <div class="stat-lbl">Target</div>
                        </div>
                        <div class="stat-block">
                            <div class="stat-val" style="color:{trend_color};">{item['vs_prior']}</div>
                            <div class="stat-lbl">vs Prior</div>
                        </div>
                    </div>
                    <div class="metric-target">Stores in range: {item['stores']}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# ── Legend ───────────────────────────────────────────────────────────────────
st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
st.markdown("""
<div class="legend-bar">
    <div class="legend-item">
        <span class="legend-dot" style="background:#27AE60;"></span>
        At or above target
    </div>
    <div class="legend-item">
        <span class="legend-dot" style="background:#F39C12;"></span>
        Near target
    </div>
    <div class="legend-item">
        <span class="legend-dot" style="background:#E74C3C;"></span>
        Below target
    </div>
</div>
""", unsafe_allow_html=True)
