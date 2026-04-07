"""
pages/1_SSS_Dashboard.py
Runs the existing Jersey Mike's Same Store Sales dashboard.
"""
import os, sys, re

# Point to repo root so all imports in dashboard.py resolve correctly
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root)
os.chdir(root)

with open(os.path.join(root, "dashboard.py"), encoding="utf-8") as _f:
    code = _f.read()

# Remove st.set_page_config(...) — handled below with sidebar shown
code = re.sub(r'st\.set_page_config\([^)]*\)', '', code, flags=re.DOTALL)

import streamlit as st
st.set_page_config(
    page_title="Same Store Sales | JM Valley Group",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Logo + Home button header
_LOGO = "data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNjAgMTEwIiB3aWR0aD0iMjYwIiBoZWlnaHQ9IjExMCI+CiAgPCEtLSBXaGl0ZSBiYWNrZ3JvdW5kIC0tPgogIDxyZWN0IHdpZHRoPSIyNjAiIGhlaWdodD0iMTEwIiBmaWxsPSIjRkZGRkZGIiByeD0iNCIvPgoKICA8IS0tIFNJTkNFIDIwMTIgLS0+CiAgPHRleHQKICAgIHg9IjQyIiB5PSIyMiIKICAgIGZvbnQtZmFtaWx5PSJBcmlhbCwgSGVsdmV0aWNhLCBzYW5zLXNlcmlmIgogICAgZm9udC1zaXplPSI5IgogICAgZm9udC13ZWlnaHQ9IjYwMCIKICAgIGZpbGw9IiNDNDEyMzAiCiAgICBsZXR0ZXItc3BhY2luZz0iMi41IgogICAgdGV4dC1hbmNob3I9Im1pZGRsZSIKICA+U0lOQ0UgMjAxMjwvdGV4dD4KCiAgPCEtLSBKTSBWYWxsZXkg4oCUIGxhcmdlIHNjcmlwdC1zdHlsZSBib2xkIGl0YWxpYyAtLT4KICA8dGV4dAogICAgeD0iMTI1IiB5PSI3NiIKICAgIGZvbnQtZmFtaWx5PSJHZW9yZ2lhLCAnVGltZXMgTmV3IFJvbWFuJywgc2VyaWYiCiAgICBmb250LXNpemU9IjU0IgogICAgZm9udC13ZWlnaHQ9IjcwMCIKICAgIGZvbnQtc3R5bGU9Iml0YWxpYyIKICAgIGZpbGw9IiMxYTJmNWUiCiAgICB0ZXh0LWFuY2hvcj0ibWlkZGxlIgogICAgbGV0dGVyLXNwYWNpbmc9Ii0xIgogID5KTSBWYWxsZXk8L3RleHQ+CgogIDwhLS0gR1JPVVAgLS0+CiAgPHRleHQKICAgIHg9IjIxOCIgeT0iOTYiCiAgICBmb250LWZhbWlseT0iQXJpYWwsIEhlbHZldGljYSwgc2Fucy1zZXJpZiIKICAgIGZvbnQtc2l6ZT0iMTMiCiAgICBmb250LXdlaWdodD0iNzAwIgogICAgZmlsbD0iI0M0MTIzMCIKICAgIGxldHRlci1zcGFjaW5nPSIxLjUiCiAgICB0ZXh0LWFuY2hvcj0ibWlkZGxlIgogID5HUk9VUDwvdGV4dD4KPC9zdmc+Cg=="
logo_col, title_col, home_col = st.columns([2, 8, 1])
with logo_col:
    st.markdown(f'''<img src="{_LOGO}" style="height:54px;display:block;margin-top:2px;" alt="JM Valley Group"/>''',
                unsafe_allow_html=True)
with title_col:
    st.markdown("""<div style="padding-top:14px;font-size:1.35em;font-weight:800;
        color:#1a1a2e;font-family:Arial,sans-serif;">Same Store Sales Dashboard</div>""",
        unsafe_allow_html=True)
with home_col:
    if st.button("⌂  Home", key="home_btn"):
        st.switch_page("app.py")

exec(code, {"__name__": "__main__", "__file__": os.path.join(root, "dashboard.py")})
