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
    initial_sidebar_state="collapsed",
)

# Home navigation is handled by the ⌂ Home link inside the blue filter bar

exec(code, {"__name__": "__main__", "__file__": os.path.join(root, "dashboard.py")})
