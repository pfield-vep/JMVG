"""
app.py — JM Valley Group Dashboard Hub
Landing page with navigation to sub-dashboards.
"""

import streamlit as st

st.set_page_config(
    page_title="JM Valley Group | Dashboard Hub",
    page_icon="🥖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    /* ── Base ── */
    [data-testid="stAppViewContainer"] {
        background: #FFFFFF;
        min-height: 100vh;
    }
    [data-testid="stSidebar"] { display: none; }
    [data-testid="collapsedControl"] { display: none; }
    footer { visibility: hidden; }
    #MainMenu { visibility: hidden; }

    /* ── Header ── */
    .hub-header {
        text-align: center;
        padding: 40px 0 10px 0;
    }
    .hub-logo-img {
        max-width: 320px;
        width: 100%;
        margin-bottom: 18px;
        display: block;
        margin-left: auto;
        margin-right: auto;
    }
    .hub-title {
        font-size: 2.4em;
        font-weight: 800;
        color: #C41230;
        letter-spacing: 1px;
        margin: 0;
        font-family: Arial, sans-serif;
    }
    .hub-subtitle {
        font-size: 1.15em;
        color: #666666;
        margin-top: 8px;
        letter-spacing: 0.5px;
        font-family: Arial, sans-serif;
    }
    .hub-divider {
        border: none;
        border-top: 2px solid #C41230;
        margin: 28px auto;
        width: 60%;
        opacity: 0.25;
    }
    .section-label {
        text-align: center;
        font-size: 0.9em;
        font-weight: 600;
        letter-spacing: 3px;
        color: #888888;
        text-transform: uppercase;
        margin-bottom: 32px;
        font-family: Arial, sans-serif;
    }

    /* ── Dashboard Cards ── */
    a.dash-card-link {
        text-decoration: none;
        display: block;
    }
    .dash-card {
        background: linear-gradient(135deg, #112240 0%, #1a3355 100%);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 20px;
        padding: 44px 36px 40px 36px;
        height: 360px;
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        transition: all 0.3s ease;
        margin: 0 12px;
        cursor: pointer;
    }
    .dash-card:hover {
        border-color: rgba(196,18,48,0.5);
        box-shadow: 0 20px 60px rgba(0,0,0,0.15), 0 0 30px rgba(196,18,48,0.12);
        transform: translateY(-6px);
    }
    .card-emoji {
        font-size: 3.5em;
        margin-bottom: 18px;
        line-height: 1;
    }
    .card-title {
        font-size: 2.0em;
        font-weight: 700;
        color: #FFFFFF;
        margin-bottom: 16px;
        line-height: 1.2;
        font-family: Arial, sans-serif;
    }
    .card-desc {
        font-size: 1.35em;
        color: #a8c4dd;
        line-height: 1.7;
        flex-grow: 1;
        font-family: Arial, sans-serif;
    }
    .card-tag {
        display: inline-block;
        background: rgba(196,18,48,0.2);
        color: #e88090;
        font-size: 0.85em;
        font-weight: 600;
        letter-spacing: 1.5px;
        text-transform: uppercase;
        padding: 5px 14px;
        border-radius: 20px;
        margin-bottom: 12px;
        border: 1px solid rgba(196,18,48,0.35);
        font-family: Arial, sans-serif;
    }
    .card-arrow {
        margin-top: 18px;
        font-size: 1.4em;
        color: #C41230;
        font-weight: 700;
        letter-spacing: 2px;
    }

    /* ── Footer ── */
    .hub-footer {
        text-align: center;
        color: #aaaaaa;
        font-size: 0.78em;
        padding: 40px 0 20px 0;
        letter-spacing: 0.5px;
        font-family: Arial, sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ──────────────────────────────────────────────
st.markdown("""
<div class="hub-header">
    <img
        src="https://upload.wikimedia.org/wikipedia/en/thumb/3/39/Jersey_Mike%27s_Subs.svg/1200px-Jersey_Mike%27s_Subs.svg.png"
        class="hub-logo-img"
        onerror="this.style.display='none';document.getElementById('jm-text-logo').style.display='block';"
        alt="Jersey Mike's Subs"
    />
    <div id="jm-text-logo" style="display:none;font-size:2.8em;font-weight:900;color:#C41230;
         letter-spacing:2px;font-family:Arial,sans-serif;margin-bottom:12px;">
        Jersey Mike's
    </div>
    <div class="hub-title">JM Valley Group</div>
    <div class="hub-subtitle">Franchise Performance Dashboards</div>
</div>
<hr class="hub-divider">
<div class="section-label">Select a Dashboard</div>
""", unsafe_allow_html=True)

# ── Cards ────────────────────────────────────────────────
_, col1, spacer, col2, _ = st.columns([1, 4, 0.5, 4, 1])

with col1:
    st.markdown("""
    <a class="dash-card-link" href="/1_SSS_Dashboard">
    <div class="dash-card">
        <div class="card-tag">Weekly · Jersey Mike's</div>
        <div class="card-emoji">📊</div>
        <div class="card-title">Same Store Sales</div>
        <div class="card-desc">
            Weekly sales performance, SSS trends, bread &amp; ops metrics,
            loyalty data, and store-level deep dives across your
            JM Valley Group portfolio.
        </div>
        <div class="card-arrow">Open →</div>
    </div>
    </a>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <a class="dash-card-link" href="/2_Balanced_Scorecard">
    <div class="dash-card">
        <div class="card-tag">Operational · KPIs</div>
        <div class="card-emoji">🎯</div>
        <div class="card-title">Balanced Scorecard</div>
        <div class="card-desc">
            At-a-glance operational performance across People, Customer,
            Sales, and Profit pillars — with color-coded status indicators
            vs. targets.
        </div>
        <div class="card-arrow">Open →</div>
    </div>
    </a>
    """, unsafe_allow_html=True)

# ── Footer ───────────────────────────────────────────────
st.markdown("""
<div class="hub-footer">
    JM Valley Group · Franchise Intelligence
</div>
""", unsafe_allow_html=True)
