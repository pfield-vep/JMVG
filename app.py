"""
app.py — VantEdge Partners Dashboard Hub
Landing page with navigation to sub-dashboards.
"""

import streamlit as st

st.set_page_config(
    page_title="VantEdge Partners | Dashboard Hub",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* ── Base ── */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(160deg, #0a1628 0%, #0d1f3c 60%, #081220 100%);
        min-height: 100vh;
    }
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }

    /* ── Header ── */
    .hub-header {
        text-align: center;
        padding: 60px 0 10px 0;
    }
    .hub-logo {
        display: inline-block;
        background: linear-gradient(135deg, #1a4a8a 0%, #2563b0 100%);
        color: #FFFFFF;
        font-size: 2em;
        font-weight: 900;
        letter-spacing: 3px;
        padding: 12px 28px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .hub-title {
        font-size: 2.6em;
        font-weight: 800;
        color: #FFFFFF;
        letter-spacing: 1px;
        margin: 0;
    }
    .hub-subtitle {
        font-size: 1.1em;
        color: #7a99bb;
        margin-top: 8px;
        letter-spacing: 0.5px;
    }
    .hub-divider {
        border: none;
        border-top: 1px solid rgba(255,255,255,0.08);
        margin: 36px auto;
        width: 60%;
    }
    .section-label {
        text-align: center;
        font-size: 0.85em;
        font-weight: 600;
        letter-spacing: 3px;
        color: #4a6fa5;
        text-transform: uppercase;
        margin-bottom: 32px;
    }

    /* ── Dashboard Cards ── */
    .dash-card {
        background: linear-gradient(135deg, #112240 0%, #1a3355 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 44px 36px 36px 36px;
        height: 320px;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        transition: all 0.3s ease;
        margin: 0 12px;
    }
    .dash-card:hover {
        border-color: rgba(100,160,255,0.4);
        box-shadow: 0 20px 60px rgba(0,0,0,0.5), 0 0 30px rgba(37,99,176,0.15);
        transform: translateY(-6px);
    }
    .card-emoji {
        font-size: 3.2em;
        margin-bottom: 18px;
        line-height: 1;
    }
    .card-title {
        font-size: 1.5em;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 14px;
        line-height: 1.2;
    }
    .card-desc {
        font-size: 0.9em;
        color: #7a99bb;
        line-height: 1.7;
        flex-grow: 1;
    }
    .card-tag {
        display: inline-block;
        background: rgba(37,99,176,0.25);
        color: #5b9bd5;
        font-size: 0.72em;
        font-weight: 600;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        padding: 4px 12px;
        border-radius: 20px;
        margin-bottom: 10px;
        border: 1px solid rgba(37,99,176,0.3);
    }

    /* ── Buttons ── */
    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #1a4a8a 0%, #2563b0 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px !important;
        font-size: 0.95em !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        padding: 12px 24px !important;
        width: 100% !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
        margin-top: 8px;
    }
    div[data-testid="stButton"] > button:hover {
        background: linear-gradient(135deg, #2563b0 0%, #3b82d4 100%) !important;
        box-shadow: 0 4px 20px rgba(37,99,176,0.5) !important;
    }

    /* ── Footer ── */
    .hub-footer {
        text-align: center;
        color: #2a4060;
        font-size: 0.78em;
        padding: 40px 0 20px 0;
        letter-spacing: 0.5px;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────
st.markdown("""
<div class="hub-header">
    <div class="hub-logo">LVE</div>
    <div class="hub-title">VantEdge Partners</div>
    <div class="hub-subtitle">Multi-Unit Franchise Intelligence Platform</div>
</div>
<hr class="hub-divider">
<div class="section-label">Select a Dashboard</div>
""", unsafe_allow_html=True)

# ── Cards ────────────────────────────────────────────────
_, col1, spacer, col2, _ = st.columns([1, 4, 0.5, 4, 1])

with col1:
    st.markdown("""
    <div class="dash-card">
        <div class="card-tag">Weekly · Jersey Mike's</div>
        <div class="card-emoji">📊</div>
        <div class="card-title">Same Store Sales</div>
        <div class="card-desc">
            Weekly sales performance, SSS trends, bread &amp; ops metrics,
            loyalty data, and store-level deep dives across your
            Jersey Mike's Valley Group portfolio.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Open Dashboard  →", key="sss"):
        st.switch_page("pages/1_SSS_Dashboard.py")

with col2:
    st.markdown("""
    <div class="dash-card">
        <div class="card-tag">Operational · KPIs</div>
        <div class="card-emoji">🎯</div>
        <div class="card-title">Balanced Scorecard</div>
        <div class="card-desc">
            At-a-glance operational performance across People, Customer,
            Sales, and Profit pillars — with color-coded status indicators
            vs. targets.
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Open Scorecard  →", key="bsc"):
        st.switch_page("pages/2_Balanced_Scorecard.py")

# ── Footer ───────────────────────────────────────────────
st.markdown("""
<div class="hub-footer">
    VantEdge Partners · Confidential &amp; Proprietary
</div>
""", unsafe_allow_html=True)
