"""
pages/00_connection_test.py — Temporary Snowflake connection test
DELETE THIS FILE once the connection is confirmed working.
"""

import streamlit as st

st.set_page_config(page_title="Snowflake Connection Test", page_icon="❄️")

st.title("❄️ Snowflake Connection Test")
st.caption("**Temporary page — delete after confirming the connection works.**")
st.write("---")

# ── Step 1: Create connection object ─────────────────────────────────────────
st.subheader("Step 1: Open connection")
try:
    conn = st.connection("snowflake")
    st.success("✅ Connection object created.")
except Exception as e:
    st.error("❌ **Failed to create connection object.** Full error:")
    st.code(str(e), language="text")
    st.markdown("""
**What this usually means:**
- The `[connections.snowflake]` block is missing or has a typo in Streamlit Cloud Secrets
- The `account` value is wrong — if you see an account/region error below, change
  `account = "vantagedata.eu-west-1"` to
  `host = "vantagedata.eu-west-1.snowflakecomputing.com"` in Cloud Secrets
- The private key PEM block has formatting issues (extra spaces, wrong line breaks)
""")
    st.stop()

# ── Step 2: Run a simple query ────────────────────────────────────────────────
st.subheader("Step 2: Run a simple query")
try:
    df = conn.query(
        "SELECT CURRENT_TIMESTAMP() AS connected_at, "
        "CURRENT_USER() AS user, "
        "CURRENT_WAREHOUSE() AS warehouse, "
        "CURRENT_DATABASE() AS database, "
        "CURRENT_SCHEMA() AS schema"
    )
    st.success("✅ Query succeeded — you are connected!")
    st.dataframe(df)
except Exception as e:
    st.error("❌ **Connection opened but query failed.** Full error:")
    st.code(str(e), language="text")
    st.stop()

# ── Step 3: Show tables in REPORTING schema ───────────────────────────────────
st.subheader("Step 3: SHOW TABLES IN SCHEMA REPORTING")
try:
    tables = conn.query("SHOW TABLES IN SCHEMA REPORTING")
    st.success(f"✅ Found {len(tables)} table(s) in the REPORTING schema.")
    st.dataframe(tables)
except Exception as e:
    st.warning("⚠️ SHOW TABLES failed — but Steps 1 and 2 passed, so the connection itself works.")
    st.markdown(
        "This may mean the `schema` or `database` in your secrets is wrong, "
        "or the user doesn't have SELECT privilege on REPORTING."
    )
    st.code(str(e), language="text")
