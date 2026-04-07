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
        max-width: 300px;
        width: 100%;
        margin-bottom: 16px;
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
        font-size: 1.1em;
        color: #666666;
        margin-top: 8px;
        font-family: Arial, sans-serif;
    }
    .hub-divider {
        border: none;
        border-top: 2px solid #C41230;
        margin: 28px auto;
        width: 60%;
        opacity: 0.2;
    }
    .section-label {
        text-align: center;
        font-size: 0.88em;
        font-weight: 600;
        letter-spacing: 3px;
        color: #999999;
        text-transform: uppercase;
        margin-bottom: 32px;
        font-family: Arial, sans-serif;
    }

    /* ── Page-link cards ── */
    /* Target the anchor inside st.page_link */
    a[data-testid="stPageLink-NavLink"] {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        background: linear-gradient(135deg, #112240 0%, #1a3355 100%) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 20px !important;
        min-height: 260px !important;
        padding: 48px 36px !important;
        text-decoration: none !important;
        transition: all 0.3s ease !important;
        cursor: pointer !important;
        gap: 20px !important;
    }
    a[data-testid="stPageLink-NavLink"]:hover {
        border-color: rgba(196,18,48,0.5) !important;
        box-shadow: 0 20px 60px rgba(0,0,0,0.18),
                    0 0 30px rgba(196,18,48,0.12) !important;
        transform: translateY(-6px) !important;
        background: linear-gradient(135deg, #152b50 0%, #1e3d66 100%) !important;
    }
    /* The label text inside the link */
    a[data-testid="stPageLink-NavLink"] p {
        color: #FFFFFF !important;
        font-size: 2.0em !important;
        font-weight: 700 !important;
        text-align: center !important;
        font-family: Arial, sans-serif !important;
        margin: 0 !important;
        line-height: 1.3 !important;
    }

    /* ── Footer ── */
    .hub-footer {
        text-align: center;
        color: #aaaaaa;
        font-size: 0.78em;
        padding: 40px 0 20px 0;
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
        onerror="this.style.display='none'"
        alt="Jersey Mike's Subs"
    />
    <div class="hub-title">JM Valley Group</div>
    <div class="hub-subtitle">Franchise Performance Dashboards</div>
</div>
<hr class="hub-divider">
<div class="section-label">Select a Dashboard</div>
""", unsafe_allow_html=True)

# ── Cards ────────────────────────────────────────────────
_, col1, spacer, col2, _ = st.columns([1, 4, 0.5, 4, 1])

with col1:
    st.page_link(
        "pages/1_SSS_Dashboard.py",
        label="📊  Same Store Sales",
        use_container_width=True,
    )

with col2:
    st.page_link(
        "pages/2_Balanced_Scorecard.py",
        label="🎯  Balanced Scorecard",
        use_container_width=True,
    )

# ── Footer ───────────────────────────────────────────────
st.markdown("""
<div class="hub-footer">
    JM Valley Group · Franchise Intelligence
</div>
""", unsafe_allow_html=True)
