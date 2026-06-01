"""
pages/00_connection_test.py — Snowflake schema explorer (temporary)
"""
import base64
import pandas as pd
import streamlit as st
import snowflake.connector

st.set_page_config(page_title="Snowflake Schema", page_icon="❄️")
st.title("❄️ Snowflake — Schema & Sample Data")
st.write("---")

@st.cache_resource
def get_conn():
    cfg = st.secrets["connections"]["snowflake"]
    return snowflake.connector.connect(
        account=cfg["account"],
        user=cfg["user"],
        authenticator="snowflake_jwt",
        private_key=base64.b64decode(cfg["private_key"]),
        warehouse=cfg.get("warehouse", ""),
        database=cfg.get("database", ""),
        schema=cfg.get("schema", ""),
    )

def run(sql):
    cs = get_conn().cursor()
    cs.execute(sql)
    cols = [d[0] for d in cs.description]
    return pd.DataFrame(cs.fetchall(), columns=cols)

VIEWS = [
    "RPT_DAILY_DISCOUNTS",
    "RPT_DAILY_LABOR",
    "RPT_DAILY_REVIEWS",
    "RPT_DAILY_SALES",
    "RPT_WEEKLY_COGS",
]

try:
    for view in VIEWS:
        st.subheader(f"📋 {view}")

        # Column list
        df_cols = run(f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'REPORTING' AND table_name = '{view}'
            ORDER BY ordinal_position
        """)
        st.write(f"**{len(df_cols)} columns:**")
        st.dataframe(df_cols, use_container_width=True, hide_index=True)

        # Sample rows
        with st.expander("Show 5 sample rows"):
            df_sample = run(f"SELECT * FROM REPORTING.{view} LIMIT 5")
            st.dataframe(df_sample, use_container_width=True, hide_index=True)

        st.write("---")

except Exception as e:
    st.error("Error:")
    st.code(str(e))
