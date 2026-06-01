"""
pages/00_connection_test.py — Snowflake data explorer (temporary)
DELETE THIS FILE once you've confirmed what data is available.
"""
import base64
import streamlit as st
import snowflake.connector

st.set_page_config(page_title="Snowflake Explorer", page_icon="❄️")
st.title("❄️ Snowflake Data Explorer")
st.caption("Temporary page — delete after confirming available tables.")
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

try:
    conn = get_conn()
    cs = conn.cursor()

    # ── What database/schema are we in? ──────────────────────────────────────
    cs.execute("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_WAREHOUSE()")
    row = cs.fetchone()
    st.success(f"✅ Connected — Database: `{row[0]}` | Schema: `{row[1]}` | Warehouse: `{row[2]}`")
    st.write("---")

    # ── All schemas in the database ───────────────────────────────────────────
    st.subheader("Schemas in this database")
    cs.execute("SHOW SCHEMAS")
    schemas = cs.fetchall()
    schema_names = [r[1] for r in schemas]
    st.write(schema_names)
    st.write("---")

    # ── Tables in REPORTING schema ────────────────────────────────────────────
    st.subheader("Tables in REPORTING schema")
    cs.execute("SHOW TABLES IN SCHEMA REPORTING")
    tables = cs.fetchall()
    if tables:
        for t in tables:
            st.write(f"**{t[1]}** — {t[5]} rows (estimated)")
    else:
        st.warning("No tables found in REPORTING schema.")
    st.write("---")

    # ── Preview any table ─────────────────────────────────────────────────────
    if tables:
        st.subheader("Preview a table")
        table_names = [t[1] for t in tables]
        selected = st.selectbox("Pick a table", table_names)
        if selected:
            cs.execute(f"SELECT * FROM REPORTING.{selected} LIMIT 20")
            cols = [desc[0] for desc in cs.description]
            rows = cs.fetchall()
            import pandas as pd
            df = pd.DataFrame(rows, columns=cols)
            st.dataframe(df)

except Exception as e:
    st.error("Connection failed:")
    st.code(str(e))
