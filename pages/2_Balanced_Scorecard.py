"""
pages/2_Balanced_Scorecard.py
VantEdge Partners — Operational Balanced Scorecard
Placeholder data — connect live data source to activate.
"""

import streamlit as st
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="Balanced Scorecard | VantEdge",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ─────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    [data-testid="stAppViewContainer"] {
        background: #0b1929;
    }
    [data-testid="stSidebar"]       { display: none; }
    [data-testid="collapsedControl"]{ display: none; }
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
    .bsc-logo {
        background: linear-gradient(135deg,#1a4a8a,#2563b0);
        color:#fff;
        font-weight:900;
        font-size:1.3em;
        letter-spacing:3px;
        padding:7px 18px;
        border-radius:6px;
    }
    .bsc-title {
        font-size:1.55em;
        font-weight:800;
        color:#FFFFFF;
        letter-spacing:1px;
    }
    .bsc-period {
        font-size:0.85em;
        color:#4a6fa5;
        letter-spacing:1px;
    }

    /* ── Sample data banner ── */
    .sample-banner {
        background: rgba(245,158,11,0.12);
        border: 1px solid rgba(245,158,11,0.3);
        border-radius: 8px;
        padding: 8px 18px;
        color: #f59e0b;
        font-size: 0.82em;
        font-weight: 600;
        letter-spacing: 0.5px;
        text-align: center;
        margin-bottom: 18px;
    }

    /* ── Overall score ── */
    .overall-box {
        background: linear-gradient(135deg,#112240,#1a3355);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 14px;
        padding: 18px 28px;
        text-align: center;
        margin-bottom: 24px;
    }
    .overall-score {
        font-size: 2.8em;
        font-weight: 900;
        color: #27AE60;
    }
    .overall-label {
        font-size: 0.85em;
        color: #5a80a5;
        letter-spacing: 2px;
        text-transform: uppercase;
        margin-top: 2px;
    }

    /* ── Category column ── */
    .cat-header {
        border-radius: 10px 10px 0 0;
        padding: 14px 16px 12px 16px;
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
        color: rgba(255,255,255,0.85);
        letter-spacing: 1px;
        text-transform: uppercase;
        margin-top: 2px;
    }

    /* ── Metric card ── */
    .metric-card {
        background: #112240;
        border: 1px solid rgba(255,255,255,0.06);
        border-radius: 10px;
        padding: 14px 16px 12px 16px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .metric-card:hover {
        border-color: rgba(255,255,255,0.15);
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
    }
    .circle-green  { background: #27AE60; box-shadow: 0 0 10px rgba(39,174,96,0.4); }
    .circle-yellow { background: #F39C12; box-shadow: 0 0 10px rgba(243,156,18,0.4); }
    .circle-red    { background: #E74C3C; box-shadow: 0 0 10px rgba(231,76,60,0.4); }
    .circle-grey   { background: #4a5568; }

    .metric-body { flex-grow: 1; min-width: 0; }
    .metric-name {
        font-size: 0.92em;
        font-weight: 700;
        color: #d0e0f0;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
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
    }
    .stat-lbl {
        font-size: 0.65em;
        color: #4a6a8a;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        margin-top: 2px;
    }
    .metric-target {
        font-size: 0.72em;
        color: #3a5a7a;
        margin-top: 3px;
    }

    /* ── Back button ── */
    div[data-testid="stButton"] > button {
        background: rgba(37,99,176,0.2) !important;
        color: #5b9bd5 !important;
        border: 1px solid rgba(37,99,176,0.3) !important;
        border-radius: 8px !important;
        font-size: 0.85em !important;
        font-weight: 600 !important;
        padding: 6px 16px !important;
    }
    div[data-testid="stButton"] > button:hover {
        background: rgba(37,99,176,0.35) !important;
        color: #ffffff !important;
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
                "actual":           208,         # seconds
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
        "color": "#b45309",
        "bg":    "linear-gradient(135deg,#4a2200,#5a2c00)",
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
overall_color = "#27AE60" if overall_pct >= 80 else ("#F39C12" if overall_pct >= 60 else "#E74C3C")

# ── Top bar ──────────────────────────────────────────────────────────────────
back_col, title_col, period_col = st.columns([1, 6, 2])
with back_col:
    if st.button("← Home"):
        st.switch_page("app.py")
with title_col:
    st.markdown(f"""
    <div style="padding-top:8px;">
        <span class="bsc-logo">LVE</span>
        <span style="font-size:1.4em;font-weight:800;color:#fff;margin-left:14px;
                     vertical-align:middle;">Balanced Scorecard</span>
    </div>
    """, unsafe_allow_html=True)
with period_col:
    st.markdown(f"""
    <div style="text-align:right;padding-top:14px;color:#4a6fa5;font-size:0.85em;
                letter-spacing:1px;">PERIOD: {PERIOD}</div>
    """, unsafe_allow_html=True)

# Sample-data banner
st.markdown("""
<div class="sample-banner">
    ⚠️ &nbsp; SAMPLE DATA — Connect a live data source to display real metrics
</div>
""", unsafe_allow_html=True)

# ── Overall score bar ────────────────────────────────────────────────────────
oc1, oc2, oc3, oc4, oc5 = st.columns([2, 1, 1, 1, 2])
with oc3:
    st.markdown(f"""
    <div class="overall-box">
        <div class="overall-score" style="color:{overall_color};">{overall_pct}%</div>
        <div class="overall-label">Overall BSC</div>
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
            trend_color = "#27AE60" if item["vs_prior"].startswith("+") else (
                "#E74C3C" if item["vs_prior"].startswith("-") else "#7a99bb"
            )
            # For metrics where lower is better, reverse trend colors
            if not item["higher"]:
                trend_color = "#E74C3C" if item["vs_prior"].startswith("+") else (
                    "#27AE60" if item["vs_prior"].startswith("-") else "#7a99bb"
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
<div style="display:flex;gap:28px;justify-content:center;align-items:center;
            padding:14px;background:rgba(255,255,255,0.03);border-radius:10px;
            border:1px solid rgba(255,255,255,0.05);">
    <span style="display:flex;align-items:center;gap:8px;font-size:0.8em;color:#8a9bb0;">
        <span style="width:14px;height:14px;background:#27AE60;border-radius:50%;display:inline-block;"></span>
        At or above target
    </span>
    <span style="display:flex;align-items:center;gap:8px;font-size:0.8em;color:#8a9bb0;">
        <span style="width:14px;height:14px;background:#F39C12;border-radius:50%;display:inline-block;"></span>
        Near target (within threshold)
    </span>
    <span style="display:flex;align-items:center;gap:8px;font-size:0.8em;color:#8a9bb0;">
        <span style="width:14px;height:14px;background:#E74C3C;border-radius:50%;display:inline-block;"></span>
        Below target
    </span>
</div>
""", unsafe_allow_html=True)
