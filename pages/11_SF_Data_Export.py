"""
pages/11_SF_Data_Export.py — Snowflake Historical Data Export
Pull catering and 3P delivery history directly from Snowflake and download as Excel.
"""
import base64
import io
from datetime import date
import streamlit as st
import pandas as pd
import snowflake.connector

st.set_page_config(
    page_title="SF Data Export | JM Valley Group",
    page_icon="📥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BLUE   = "#134A7C"
BORDER = "#E0E3E8"
LIGHT  = "#F5F6F8"
MUTED  = "#6B7280"

@st.cache_resource
def _get_conn():
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

def run_query(sql):
    cs = _get_conn().cursor()
    cs.execute(sql)
    cols = [d[0] for d in cs.description]
    return pd.DataFrame(cs.fetchall(), columns=cols)

def to_excel_bytes(df):
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Data")
    return buf.getvalue()

st.markdown(f"""
<div style="padding:8px 0 20px 0;border-bottom:2px solid {BORDER};margin-bottom:24px;">
  <span style="font-size:22px;font-weight:800;color:{BLUE};">Snowflake Historical Export</span>
  <span style="font-size:12px;color:{MUTED};margin-left:10px;">
    Pull raw daily data from Snowflake · One Excel file per dataset
  </span>
</div>
""", unsafe_allow_html=True)

# ── Check available date range ────────────────────────────────────────────────
@st.cache_data(ttl=3600)
def get_date_range():
    df = run_query("SELECT MIN(DATE_OF_BUSINESS), MAX(DATE_OF_BUSINESS) FROM REPORTING.RPT_DAILY_SALES")
    return df.iloc[0, 0], df.iloc[0, 1]

try:
    min_date, max_date = get_date_range()
    st.info(f"📅 Data available: **{min_date}** through **{max_date}**")
except Exception as e:
    st.error(f"Could not connect to Snowflake: {e}")
    st.stop()

st.write("---")

# ══════════════════════════════════════════════════════════════════════════════
st.subheader("1 — Catering Sales by Store by Day")
st.caption("Includes total catering sales, tickets, and ezCater breakdown (sales, orders, food amount).")

if st.button("📥 Pull & Download Catering Data", type="primary", key="catering"):
    with st.spinner("Querying Snowflake... this may take 20–30 seconds for a large date range."):
        try:
            df_cat = run_query(f"""
                SELECT
                    DATE_OF_BUSINESS        AS Date,
                    SITE_ID                 AS Store_ID,
                    STORE_NAME              AS Store_Name,
                    REGION                  AS Region,
                    DISTRICT                AS District,
                    STATE                   AS State,
                    CATERING_SALES          AS Catering_Sales,
                    CATERING_TICKETS        AS Catering_Tickets,
                    CATERING_SALES_PY       AS Catering_Sales_PY,
                    CATERING_TICKETS_PY     AS Catering_Tickets_PY,
                    EZCATER_COUNT           AS ezCater_Orders,
                    EZCATER_TOTAL_AMOUNT    AS ezCater_Total_Amount,
                    EZCATER_FOOD_AMOUNT     AS ezCater_Food_Amount,
                    EZCATER_COUNT_PY        AS ezCater_Orders_PY,
                    EZCATER_TOTAL_AMOUNT_PY AS ezCater_Total_Amount_PY,
                    EZCATER_FOOD_AMOUNT_PY  AS ezCater_Food_Amount_PY
                FROM REPORTING.RPT_DAILY_SALES
                ORDER BY DATE_OF_BUSINESS, SITE_ID
            """)

            st.success(f"✅ {len(df_cat):,} rows pulled — {df_cat.iloc[:,0].min()} to {df_cat.iloc[:,0].max()}")
            st.dataframe(df_cat.head(10), use_container_width=True, hide_index=True)
            st.caption(f"Showing first 10 of {len(df_cat):,} rows. Download below for full dataset.")

            excel_bytes = to_excel_bytes(df_cat)
            st.download_button(
                label="💾 Download Catering Data (.xlsx)",
                data=excel_bytes,
                file_name=f"JMV_Catering_Daily_{df_cat.iloc[:,0].min()}_to_{df_cat.iloc[:,0].max()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_catering",
            )
        except Exception as e:
            st.error(f"Query failed: {e}")

st.write("---")

# ══════════════════════════════════════════════════════════════════════════════
st.subheader("2 — 3rd Party Delivery by Store by Day")
st.caption("DoorDash, UberEats, Grubhub, and Postmates — daily sales and transaction counts.")

if st.button("📥 Pull & Download 3P Delivery Data", type="primary", key="thirdparty"):
    with st.spinner("Querying Snowflake... this may take 20–30 seconds for a large date range."):
        try:
            df_3p = run_query(f"""
                SELECT
                    DATE_OF_BUSINESS                        AS Date,
                    SITE_ID                                 AS Store_ID,
                    STORE_NAME                              AS Store_Name,
                    REGION                                  AS Region,
                    DISTRICT                                AS District,
                    STATE                                   AS State,
                    -- DoorDash
                    THIRD_PARTY_DOORDASH_NET_SALES          AS DoorDash_Sales,
                    THIRD_PARTY_DOORDASH_TRANSACTION_COUNT  AS DoorDash_Transactions,
                    THIRD_PARTY_DOORDASH_NET_SALES_PY       AS DoorDash_Sales_PY,
                    THIRD_PARTY_DOORDASH_TRANSACTION_COUNT_PY AS DoorDash_Transactions_PY,
                    -- UberEats
                    THIRD_PARTY_UBEREATS_NET_SALES          AS UberEats_Sales,
                    THIRD_PARTY_UBEREATS_TRANSACTION_COUNT  AS UberEats_Transactions,
                    THIRD_PARTY_UBEREATS_NET_SALES_PY       AS UberEats_Sales_PY,
                    THIRD_PARTY_UBEREATS_TRANSACTION_COUNT_PY AS UberEats_Transactions_PY,
                    -- Grubhub
                    THIRD_PARTY_GRUBHUB_NET_SALES           AS Grubhub_Sales,
                    THIRD_PARTY_GRUBHUB_TRANSACTION_COUNT   AS Grubhub_Transactions,
                    THIRD_PARTY_GRUBHUB_NET_SALES_PY        AS Grubhub_Sales_PY,
                    THIRD_PARTY_GRUBHUB_TRANSACTION_COUNT_PY AS Grubhub_Transactions_PY,
                    -- Postmates
                    THIRD_PARTY_POSTMATES_NET_SALES         AS Postmates_Sales,
                    THIRD_PARTY_POSTMATES_TRANSACTION_COUNT AS Postmates_Transactions,
                    THIRD_PARTY_POSTMATES_NET_SALES_PY      AS Postmates_Sales_PY,
                    THIRD_PARTY_POSTMATES_TRANSACTION_COUNT_PY AS Postmates_Transactions_PY,
                    -- Total 3P
                    THIRD_PARTY_SALES                       AS Total_3P_Sales,
                    THIRD_PARTY_TRANSACTIONS                AS Total_3P_Transactions
                FROM REPORTING.RPT_DAILY_SALES
                ORDER BY DATE_OF_BUSINESS, SITE_ID
            """)

            st.success(f"✅ {len(df_3p):,} rows pulled — {df_3p.iloc[:,0].min()} to {df_3p.iloc[:,0].max()}")
            st.dataframe(df_3p.head(10), use_container_width=True, hide_index=True)
            st.caption(f"Showing first 10 of {len(df_3p):,} rows. Download below for full dataset.")

            excel_bytes = to_excel_bytes(df_3p)
            st.download_button(
                label="💾 Download 3P Delivery Data (.xlsx)",
                data=excel_bytes,
                file_name=f"JMV_3P_Delivery_Daily_{df_3p.iloc[:,0].min()}_to_{df_3p.iloc[:,0].max()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="dl_3p",
            )
        except Exception as e:
            st.error(f"Query failed: {e}")
