"""
app.py — JM Valley Group Navigation Controller
Defines sidebar order and labels using st.navigation().
To add a page: add a st.Page() entry here AND add a button in pages/0_Home.py.
To remove a page: remove the st.Page() entry here AND remove the button in pages/0_Home.py.
"""

import streamlit as st

pg = st.navigation([
    st.Page("pages/0_Home.py",               title="Home",               icon="🏠", default=True),
    st.Page("pages/5_Daily_Sales.py",        title="Daily Sales",        icon="📊"),
    st.Page("pages/6_Weather_Impact.py",     title="Weather Impact",     icon="🌤️"),
    st.Page("pages/7_Hourly_Heatmap.py",    title="Hourly Heatmap",     icon="🕐"),
    st.Page("pages/8_Google_Reviews.py",    title="Google Reviews",     icon="⭐"),
    st.Page("pages/2_Balanced_Scorecard.py", title="Balanced Scorecard", icon="🎯"),
    st.Page("pages/1_SSS_Dashboard.py",      title="SSS Dashboard",      icon="📈"),
    st.Page("pages/3_Data_Export.py",        title="Data Export",        icon="📥"),
    st.Page("pages/4_Update_Data.py",        title="Update Data",        icon="🔄"),
])

pg.run()
