"""
pages/00_connection_test.py — Temporary Snowflake connection test
DELETE THIS FILE once the connection is confirmed working.
"""

import base64
import streamlit as st
import snowflake.connector

st.set_page_config(page_title="Snowflake Connection Test", page_icon="❄️")
st.title("❄️ Snowflake Connection Test")
st.caption("Temporary page — delete after confirming the connection works.")
st.write("---")

# ── Step 1: Read secrets ──────────────────────────────────────────────────────
st.subheader("Step 1: Read secrets")
try:
    cfg = st.secrets["connections"]["snowflake"]
    st.success(f"✅ Secrets found. account=`{cfg['account']}` user=`{cfg['user']}`")
except Exception as e:
    st.error("❌ Could not read secrets — check that `[connections.snowflake]` block exists in Cloud Secrets.")
    st.code(str(e))
    st.stop()

# ── Step 2: Decode private key ────────────────────────────────────────────────
st.subheader("Step 2: Decode private key")
try:
    private_key_bytes = base64.b64decode(cfg["private_key"])
    st.success(f"✅ Private key decoded ({len(private_key_bytes)} bytes).")
except Exception as e:
    st.error("❌ Private key decode failed — the value in secrets is not valid base64.")
    st.code(str(e))
    st.stop()

# ── Step 3: Open Snowflake connection ─────────────────────────────────────────
st.subheader("Step 3: Connect to Snowflake")
try:
    conn = snowflake.connector.connect(
        account=cfg["account"],
        user=cfg["user"],
        authenticator="snowflake_jwt",
        private_key=private_key_bytes,
        warehouse=cfg.get("warehouse", ""),
        database=cfg.get("database", ""),
        schema=cfg.get("schema", ""),
    )
    st.success("✅ Connected to Snowflake!")
except Exception as e:
    st.error("❌ Connection failed. Full error:")
    st.code(str(e))
    st.markdown("""
**Common fixes:**
- `account` wrong → try `host = "vantagedata.eu-west-1.snowflakecomputing.com"` instead of `account`
- `JWT token invalid` → public key may not be registered on the Snowflake user
- `250001 / Failed to connect` → warehouse or database name is wrong
""")
    st.stop()

# ── Step 4: Run a query ───────────────────────────────────────────────────────
st.subheader("Step 4: Run a query")
try:
    cs = conn.cursor()
    cs.execute("SELECT CURRENT_TIMESTAMP() AS ts, CURRENT_USER() AS usr, CURRENT_WAREHOUSE() AS wh")
    row = cs.fetchone()
    st.success("✅ Query succeeded!")
    st.write(f"**Timestamp:** {row[0]}  |  **User:** {row[1]}  |  **Warehouse:** {row[2]}")
except Exception as e:
    st.error("❌ Query failed:")
    st.code(str(e))
finally:
    conn.close()
