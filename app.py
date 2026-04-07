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

_LOGO = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNjAgMTEwIiB3aWR0aD0iMjYwIiBoZWlnaHQ9IjExMCI+CiAgPCEtLSBXaGl0ZSBiYWNrZ3JvdW5kIC0tPgogIDxyZWN0IHdpZHRoPSIyNjAiIGhlaWdodD0iMTEwIiBmaWxsPSIjRkZGRkZGIiByeD0iNCIvPgoKICA8IS0tIFNJTkNFIDIwMTIgLS0+CiAgPHRleHQKICAgIHg9IjQyIiB5PSIyMiIKICAgIGZvbnQtZmFtaWx5PSJBcmlhbCwgSGVsdmV0aWNhLCBzYW5zLXNlcmlmIgogICAgZm9udC1zaXplPSI5IgogICAgZm9udC13ZWlnaHQ9IjYwMCIKICAgIGZpbGw9IiNDNDEyMzAiCiAgICBsZXR0ZXItc3BhY2luZz0iMi41IgogICAgdGV4dC1hbmNob3I9Im1pZGRsZSIKICA+U0lOQ0UgMjAxMjwvdGV4dD4KCiAgPCEtLSBKTSBWYWxsZXkg4oCUIGxhcmdlIHNjcmlwdC1zdHlsZSBib2xkIGl0YWxpYyAtLT4KICA8dGV4dAogICAgeD0iMTI1IiB5PSI3NiIKICAgIGZvbnQtZmFtaWx5PSJHZW9yZ2lhLCAnVGltZXMgTmV3IFJvbWFuJywgc2VyaWYiCiAgICBmb250LXNpemU9IjU0IgogICAgZm9udC13ZWlnaHQ9IjcwMCIKICAgIGZvbnQtc3R5bGU9Iml0YWxpYyIKICAgIGZpbGw9IiMxYTJmNWUiCiAgICB0ZXh0LWFuY2hvcj0ibWlkZGxlIgogICAgbGV0dGVyLXNwYWNpbmc9Ii0xIgogID5KTSBWYWxsZXk8L3RleHQ+CgogIDwhLS0gR1JPVVAgLS0+CiAgPHRleHQKICAgIHg9IjIxOCIgeT0iOTYiCiAgICBmb250LWZhbWlseT0iQXJpYWwsIEhlbHZldGljYSwgc2Fucy1zZXJpZiIKICAgIGZvbnQtc2l6ZT0iMTMiCiAgICBmb250LXdlaWdodD0iNzAwIgogICAgZmlsbD0iI0M0MTIzMCIKICAgIGxldHRlci1zcGFjaW5nPSIxLjUiCiAgICB0ZXh0LWFuY2hvcj0ibWlkZGxlIgogID5HUk9VUDwvdGV4dD4KPC9zdmc+Cg=="

st.markdown(f"""
<style>
    /* ── Base ── */
    [data-testid="stAppViewContainer"] {{
        background: #FFFFFF;
        min-height: 100vh;
    }}
    [data-testid="stSidebar"] {{ display: none; }}
    [data-testid="collapsedControl"] {{ display: none; }}
    footer {{ visibility: hidden; }}
    #MainMenu {{ visibility: hidden; }}

    /* ── Top bar: logo right, no padding waste ── */
    .top-bar {{
        display: flex;
        justify-content: flex-end;
        align-items: center;
        padding: 14px 8px 6px 8px;
    }}
    .top-bar img {{
        height: 52px;
        width: auto;
    }}

    /* ── Cards container: vertically centered ── */
    .cards-wrap {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 32px;
        padding: 20px 0 0 0;
        height: calc(100vh - 130px);
    }}

    /* ── Page-link cards ── */
    a[data-testid="stPageLink-NavLink"] {{
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        background: linear-gradient(135deg, #112240 0%, #1a3355 100%) !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        border-radius: 18px !important;
        min-height: 180px !important;
        padding: 32px 40px !important;
        text-decoration: none !important;
        transition: all 0.25s ease !important;
        cursor: pointer !important;
    }}
    a[data-testid="stPageLink-NavLink"]:hover {{
        border-color: rgba(196,18,48,0.5) !important;
        box-shadow: 0 12px 40px rgba(0,0,0,0.15),
                    0 0 20px rgba(196,18,48,0.1) !important;
        transform: translateY(-4px) !important;
        background: linear-gradient(135deg, #152b50 0%, #1e3d66 100%) !important;
    }}
    a[data-testid="stPageLink-NavLink"] p {{
        color: #FFFFFF !important;
        font-size: 1.6em !important;
        font-weight: 700 !important;
        text-align: center !important;
        font-family: Arial, sans-serif !important;
        margin: 0 !important;
        line-height: 1.3 !important;
    }}
</style>

<div class="top-bar">
    <img src="{_LOGO}" alt="JM Valley Group" />
</div>
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
