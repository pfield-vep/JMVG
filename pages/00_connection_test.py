"""
pages/00_connection_test.py — Temporary Snowflake connection test
DELETE THIS FILE once the connection is confirmed working.
"""
import base64
import streamlit as st

st.set_page_config(page_title="Snowflake Connection Test", page_icon="❄️")
st.title("❄️ Snowflake Connection Test")
st.caption("Temporary page — delete after confirming the connection works.")
st.write("---")

# ── Step 1: Import ────────────────────────────────────────────────────────────
st.subheader("Step 1: Import snowflake.connector")
try:
    import snowflake.connector
    st.success("✅ Package available.")
except ImportError as e:
    st.error("❌ Package not installed — the build may have failed.")
    st.code(str(e))
    st.stop()

# ── Step 2: Read secrets ──────────────────────────────────────────────────────
st.subheader("Step 2: Read secrets")
try:
    cfg = st.secrets["connections"]["snowflake"]
    st.success(f"✅ Secrets found. account=`{cfg['account']}` user=`{cfg['user']}`")
except Exception as e:
    st.error("❌ Could not read secrets.")
    st.code(str(e))
    st.stop()

# ── Step 3: Decode private key ────────────────────────────────────────────────
st.subheader("Step 3: Decode private key")
try:
    private_key_bytes = base64.b64decode(cfg["private_key"])
    st.success(f"✅ Private key decoded ({len(private_key_bytes)} bytes).")
except Exception as e:
    st.error("❌ Private key decode failed.")
    st.code(str(e))
    st.stop()

# ── Step 4: Connect and query ─────────────────────────────────────────────────
st.subheader("Step 4: Connect to Snowflake")
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
    cs = conn.cursor()
    cs.execute("SELECT CURRENT_TIMESTAMP(), CURRENT_USER(), CURRENT_WAREHOUSE()")
    row = cs.fetchone()
    conn.close()
    st.success("✅ Connected and queried successfully!")
    st.write(f"**Timestamp:** {row[0]}  |  **User:** {row[1]}  |  **Warehouse:** {row[2]}")
except Exception as e:
    st.error("❌ Connection failed:")
    st.code(str(e))
    st.markdown("""
**Common fixes:**
- Account format wrong → try `host = "vantagedata.eu-west-1.snowflakecomputing.com"` instead of `account` in Cloud Secrets
- JWT invalid → public key not yet registered on the Snowflake user
- Warehouse/database name wrong
""")
