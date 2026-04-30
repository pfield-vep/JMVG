"""
pages/0_Home.py — JM Valley Group Dashboard Hub
Landing page with navigation cards to all sub-dashboards.
"""

import streamlit as st

st.set_page_config(
    page_title="JM Valley Group | Dashboard Hub",
    page_icon="🥖",
    layout="wide",
    initial_sidebar_state="auto",
)

_LOGO = "data:image/avif;base64,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"

BLUE  = "#134A7C"
WHITE = "#FFFFFF"

st.markdown(f"""
<style>
    [data-testid="stAppViewContainer"] {{ background: {WHITE}; min-height: 100vh; }}
    [data-testid="stSidebar"] {{ display: none; }}
    [data-testid="collapsedControl"] {{ display: none; }}
    footer {{ visibility: hidden; }}
    #MainMenu {{ visibility: hidden; }}
    header {{ visibility: hidden; }}

    .top-bar {{
        display: flex; justify-content: flex-end; align-items: center;
        padding: 14px 8px 6px 8px;
    }}
    .top-bar img {{ height: 52px; width: auto; }}

    a[data-testid="stPageLink-NavLink"] {{
        display: flex !important; flex-direction: column !important;
        align-items: center !important; justify-content: center !important;
        background: {BLUE} !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 18px !important;
        min-height: 160px !important;
        padding: 28px 32px !important;
        text-decoration: none !important;
        transition: all 0.25s ease !important;
        cursor: pointer !important;
    }}
    a[data-testid="stPageLink-NavLink"]:hover {{
        border-color: rgba(238,50,39,0.5) !important;
        box-shadow: 0 12px 40px rgba(0,0,0,0.15), 0 0 20px rgba(238,50,39,0.1) !important;
        transform: translateY(-4px) !important;
        background: #0d3a5e !important;
    }}
    a[data-testid="stPageLink-NavLink"] p {{
        color: {WHITE} !important; font-size: 1.45em !important;
        font-weight: 700 !important; text-align: center !important;
        font-family: Arial, sans-serif !important;
        margin: 0 !important; line-height: 1.3 !important;
    }}
</style>

<div class="top-bar">
    <img src="{_LOGO}" alt="JM Valley Group" />
</div>
""", unsafe_allow_html=True)

# ── Row 1: Primary dashboards (4 across) ──────────────────────────────────────
_, c1, sp, c2, sp2, c3, sp3, c4, _ = st.columns([0.3, 3, 0.35, 3, 0.35, 3, 0.35, 3, 0.3])
with c1:
    st.page_link("pages/5_Daily_Sales.py",     label="📊  Daily Sales",     use_container_width=True)
with c2:
    st.page_link("pages/7_Hourly_Heatmap.py",  label="🕐  Hourly Heatmap",  use_container_width=True)
with c3:
    st.page_link("pages/6_Weather_Impact.py",  label="🌤️  Weather Impact",  use_container_width=True)
with c4:
    st.page_link("pages/2_Balanced_Scorecard.py", label="🎯  Balanced Scorecard", use_container_width=True)

st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

# ── Row 2: Supporting dashboards ──────────────────────────────────────────────
_, c5, sp4, c6, sp5, c7, _ = st.columns([0.5, 3, 0.4, 3, 0.4, 3, 0.5])
with c5:
    st.page_link("pages/1_SSS_Dashboard.py", label="📈  Same Store Sales",  use_container_width=True)
with c6:
    st.page_link("pages/3_Data_Export.py",   label="📥  Data Export",       use_container_width=True)
with c7:
    st.page_link("pages/4_Update_Data.py",   label="🔄  Update Weekly Data", use_container_width=True)
