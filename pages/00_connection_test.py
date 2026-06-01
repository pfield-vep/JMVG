"""
pages/00_connection_test.py — Snowflake data explorer (temporary)
DELETE THIS FILE once you've confirmed what data is available.
"""
import base64
import pandas as pd
import streamlit as st
import snowflake.connector

st.set_page_config(page_title="Snowflake Explorer", page_icon="❄️")
st.title("❄️ Snowflake Data Explorer")
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

def query(sql):
    cs = get_conn().cursor()
    cs.execute(sql)
    cols = [d[0] for d in cs.description]
    return pd.DataFrame(cs.fetchall(), columns=cols)

try:
    conn = get_conn()
    cs = conn.cursor()

    # ── Current context ───────────────────────────────────────────────────────
    cs.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE(), CURRENT_ROLE()")
    row = cs.fetchone()
    st.success(f"✅ Connected")
    st.write(f"**Database:** `{row[0]}` | **Schema:** `{row[1]}` | **Warehouse:** `{row[2]}` | **Role:** `{row[3]}`")
    st.write("---")

    # ── All tables this user can see (across all schemas) ─────────────────────
    st.subheader("All tables visible to this user")
    df_tables = query("""
        SELECT table_schema, table_name, table_type, row_count
        FROM information_schema.tables
        WHERE table_schema NOT IN ('INFORMATION_SCHEMA')
        ORDER BY table_schema, table_name
    """)
    if df_tables.empty:
        st.warning("No tables visible. The user may lack SELECT grants on any table.")
    else:
        st.dataframe(df_tables, use_container_width=True)
    st.write("---")

    # ── Preview a table ───────────────────────────────────────────────────────
    st.subheader("Preview a table")
    if not df_tables.empty:
        options = [f"{r['TABLE_SCHEMA']}.{r['TABLE_NAME']}" for _, r in df_tables.iterrows()]
        selected = st.selectbox("Pick a table", options)
        if selected:
            df_preview = query(f"SELECT * FROM {selected} LIMIT 50")
            st.write(f"{len(df_preview)} rows shown (max 50)")
            st.dataframe(df_preview, use_container_width=True)
    else:
        st.info("No tables to preview.")

except Exception as e:
    st.error("Error:")
    st.code(str(e))
