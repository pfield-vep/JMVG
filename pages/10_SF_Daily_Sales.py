"""
pages/10_SF_Daily_Sales.py — Snowflake Daily Sales (Test Version)
Runs parallel to 5_Daily_Sales.py for validation before cutover.
Pulls live from Snowflake RPT_DAILY_SALES.

NOT YET INCLUDED vs old dashboard (see SNOWFLAKE_MIGRATION_GAPS.md):
  - Lunch / dinner / morning daypart split
  - Weather × SSS attribution panel
  - BlakeWard benchmark tab
  - DM names (grouped by District instead)
"""

import base64
from datetime import date
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import snowflake.connector

st.set_page_config(
    page_title="SF Daily Sales | JM Valley Group",
    page_icon="❄️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Brand colors ──────────────────────────────────────────────────────────────
RED    = "#EE3227"
BLUE   = "#134A7C"
GOLD   = "#D4AF37"
WHITE  = "#FFFFFF"
LIGHT  = "#F5F6F8"
BORDER = "#E0E3E8"
GREEN  = "#16a34a"
DANGER = "#dc2626"
AMBER  = "#d97706"
MUTED  = "#6B7280"

# ── Snowflake connection ──────────────────────────────────────────────────────
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

@st.cache_data(ttl=300)
def load_snapshot():
    """
    Load the latest day's row per store from RPT_DAILY_SALES.
    All WTD/MTD/QTD/YTD columns are pre-computed by Snowflake as of that date.
    """
    cs = _get_conn().cursor()
    cs.execute("SELECT MAX(DATE_OF_BUSINESS) FROM REPORTING.RPT_DAILY_SALES")
    latest = cs.fetchone()[0]

    cs.execute(f"""
        SELECT
            SITE_ID, STORE_NAME, REGION, DISTRICT, STATE,
            DATE_OF_BUSINESS, FIRST_SALES_DATE,
            -- Core daily
            NET_SALES, TOTAL_TRANSACTIONS, AVERAGE_CHECK,
            WALK_IN_SALES, ONLINE_SALES, THIRD_PARTY_SALES,
            BREAD_COUNT,
            -- Channel WTD (for mix %)
            WALK_IN_SALES_WTD, ONLINE_SALES_WTD, THIRD_PARTY_SALES_WTD,
            THIRD_PARTY_SALES_MTD, THIRD_PARTY_SALES_QTD,
            -- Net Sales all periods
            NET_SALES_WTD,  NET_SALES_PY_WTD,
            NET_SALES_MTD,  NET_SALES_PY_MTD,
            NET_SALES_QTD,  NET_SALES_PY_QTD,
            NET_SALES_YTD,  NET_SALES_PY_YTD,
            -- Transactions all periods
            TOTAL_TRANSACTIONS_WTD,  TOTAL_TRANSACTIONS_PY_WTD,
            TOTAL_TRANSACTIONS_MTD,  TOTAL_TRANSACTIONS_PY_MTD,
            TOTAL_TRANSACTIONS_QTD,  TOTAL_TRANSACTIONS_PY_QTD,
            TOTAL_TRANSACTIONS_YTD,  TOTAL_TRANSACTIONS_PY_YTD,
            -- Bread all periods
            BREAD_COUNT_WTD,  BREAD_COUNT_PY_WTD,
            BREAD_COUNT_MTD,  BREAD_COUNT_PY_MTD,
            BREAD_COUNT_QTD,  BREAD_COUNT_PY_QTD,
            BREAD_COUNT_YTD,  BREAD_COUNT_PY_YTD,
            -- DoorDash
            THIRD_PARTY_DOORDASH_NET_SALES,       THIRD_PARTY_DOORDASH_NET_SALES_PY,
            THIRD_PARTY_DOORDASH_NET_SALES_WTD,   THIRD_PARTY_DOORDASH_NET_SALES_PY_WTD,
            THIRD_PARTY_DOORDASH_NET_SALES_MTD,   THIRD_PARTY_DOORDASH_NET_SALES_PY_MTD,
            THIRD_PARTY_DOORDASH_NET_SALES_QTD,   THIRD_PARTY_DOORDASH_NET_SALES_PY_QTD,
            THIRD_PARTY_DOORDASH_NET_SALES_YTD,   THIRD_PARTY_DOORDASH_NET_SALES_PY_YTD,
            THIRD_PARTY_DOORDASH_TRANSACTION_COUNT, THIRD_PARTY_DOORDASH_TRANSACTION_COUNT_PY,
            -- UberEats
            THIRD_PARTY_UBEREATS_NET_SALES,       THIRD_PARTY_UBEREATS_NET_SALES_PY,
            THIRD_PARTY_UBEREATS_NET_SALES_WTD,   THIRD_PARTY_UBEREATS_NET_SALES_PY_WTD,
            THIRD_PARTY_UBEREATS_NET_SALES_MTD,   THIRD_PARTY_UBEREATS_NET_SALES_PY_MTD,
            THIRD_PARTY_UBEREATS_NET_SALES_QTD,   THIRD_PARTY_UBEREATS_NET_SALES_PY_QTD,
            THIRD_PARTY_UBEREATS_NET_SALES_YTD,   THIRD_PARTY_UBEREATS_NET_SALES_PY_YTD,
            THIRD_PARTY_UBEREATS_TRANSACTION_COUNT, THIRD_PARTY_UBEREATS_TRANSACTION_COUNT_PY,
            -- Grubhub
            THIRD_PARTY_GRUBHUB_NET_SALES,        THIRD_PARTY_GRUBHUB_NET_SALES_PY,
            THIRD_PARTY_GRUBHUB_NET_SALES_WTD,    THIRD_PARTY_GRUBHUB_NET_SALES_PY_WTD,
            THIRD_PARTY_GRUBHUB_NET_SALES_MTD,    THIRD_PARTY_GRUBHUB_NET_SALES_PY_MTD,
            THIRD_PARTY_GRUBHUB_NET_SALES_QTD,    THIRD_PARTY_GRUBHUB_NET_SALES_PY_QTD,
            THIRD_PARTY_GRUBHUB_NET_SALES_YTD,    THIRD_PARTY_GRUBHUB_NET_SALES_PY_YTD,
            THIRD_PARTY_GRUBHUB_TRANSACTION_COUNT,  THIRD_PARTY_GRUBHUB_TRANSACTION_COUNT_PY,
            -- Postmates
            THIRD_PARTY_POSTMATES_NET_SALES,      THIRD_PARTY_POSTMATES_NET_SALES_PY,
            THIRD_PARTY_POSTMATES_NET_SALES_WTD,  THIRD_PARTY_POSTMATES_NET_SALES_PY_WTD,
            THIRD_PARTY_POSTMATES_NET_SALES_MTD,  THIRD_PARTY_POSTMATES_NET_SALES_PY_MTD,
            THIRD_PARTY_POSTMATES_NET_SALES_QTD,  THIRD_PARTY_POSTMATES_NET_SALES_PY_QTD,
            THIRD_PARTY_POSTMATES_NET_SALES_YTD,  THIRD_PARTY_POSTMATES_NET_SALES_PY_YTD,
            THIRD_PARTY_POSTMATES_TRANSACTION_COUNT, THIRD_PARTY_POSTMATES_TRANSACTION_COUNT_PY,
            -- Catering
            CATERING_SALES,     CATERING_SALES_PY,
            CATERING_SALES_WTD, CATERING_SALES_PY_WTD,
            CATERING_SALES_MTD, CATERING_SALES_PY_MTD,
            CATERING_SALES_QTD, CATERING_SALES_PY_QTD,
            CATERING_SALES_YTD, CATERING_SALES_PY_YTD,
            CATERING_TICKETS,     CATERING_TICKETS_PY,
            CATERING_TICKETS_WTD, CATERING_TICKETS_PY_WTD,
            CATERING_TICKETS_MTD, CATERING_TICKETS_PY_MTD,
            CATERING_TICKETS_QTD, CATERING_TICKETS_PY_QTD,
            CATERING_TICKETS_YTD, CATERING_TICKETS_PY_YTD,
            EZCATER_COUNT,     EZCATER_TOTAL_AMOUNT,     EZCATER_FOOD_AMOUNT,
            EZCATER_COUNT_PY,  EZCATER_TOTAL_AMOUNT_PY,  EZCATER_FOOD_AMOUNT_PY
        FROM REPORTING.RPT_DAILY_SALES
        WHERE DATE_OF_BUSINESS = '{latest}'
    """)
    cols = [d[0] for d in cs.description]
    df = pd.DataFrame(cs.fetchall(), columns=cols)

    for c in ["DATE_OF_BUSINESS", "FIRST_SALES_DATE"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c]).dt.date

    num_cols = df.select_dtypes(include="number").columns
    df[num_cols] = df[num_cols].fillna(0)
    return df, latest


# ── Period helpers ────────────────────────────────────────────────────────────
PERIOD_COLS = {
    "WTD": {
        "sales":  ("NET_SALES_WTD",            "NET_SALES_PY_WTD"),
        "tx":     ("TOTAL_TRANSACTIONS_WTD",    "TOTAL_TRANSACTIONS_PY_WTD"),
        "bread":  ("BREAD_COUNT_WTD",           "BREAD_COUNT_PY_WTD"),
        "walkin": "WALK_IN_SALES_WTD",
        "online": "ONLINE_SALES_WTD",
        "thirdp": "THIRD_PARTY_SALES_WTD",
        "dd":     ("THIRD_PARTY_DOORDASH_NET_SALES_WTD",   "THIRD_PARTY_DOORDASH_NET_SALES_PY_WTD"),
        "ue":     ("THIRD_PARTY_UBEREATS_NET_SALES_WTD",   "THIRD_PARTY_UBEREATS_NET_SALES_PY_WTD"),
        "gh":     ("THIRD_PARTY_GRUBHUB_NET_SALES_WTD",    "THIRD_PARTY_GRUBHUB_NET_SALES_PY_WTD"),
        "pm":     ("THIRD_PARTY_POSTMATES_NET_SALES_WTD",  "THIRD_PARTY_POSTMATES_NET_SALES_PY_WTD"),
        "cat":    ("CATERING_SALES_WTD",  "CATERING_SALES_PY_WTD"),
        "tkt":    ("CATERING_TICKETS_WTD","CATERING_TICKETS_PY_WTD"),
    },
    "MTD": {
        "sales":  ("NET_SALES_MTD",            "NET_SALES_PY_MTD"),
        "tx":     ("TOTAL_TRANSACTIONS_MTD",    "TOTAL_TRANSACTIONS_PY_MTD"),
        "bread":  ("BREAD_COUNT_MTD",           "BREAD_COUNT_PY_MTD"),
        "walkin": "WALK_IN_SALES_WTD",   # fallback to WTD for mix %
        "online": "ONLINE_SALES_WTD",
        "thirdp": "THIRD_PARTY_SALES_MTD",
        "dd":     ("THIRD_PARTY_DOORDASH_NET_SALES_MTD",   "THIRD_PARTY_DOORDASH_NET_SALES_PY_MTD"),
        "ue":     ("THIRD_PARTY_UBEREATS_NET_SALES_MTD",   "THIRD_PARTY_UBEREATS_NET_SALES_PY_MTD"),
        "gh":     ("THIRD_PARTY_GRUBHUB_NET_SALES_MTD",    "THIRD_PARTY_GRUBHUB_NET_SALES_PY_MTD"),
        "pm":     ("THIRD_PARTY_POSTMATES_NET_SALES_MTD",  "THIRD_PARTY_POSTMATES_NET_SALES_PY_MTD"),
        "cat":    ("CATERING_SALES_MTD",  "CATERING_SALES_PY_MTD"),
        "tkt":    ("CATERING_TICKETS_MTD","CATERING_TICKETS_PY_MTD"),
    },
    "QTD": {
        "sales":  ("NET_SALES_QTD",            "NET_SALES_PY_QTD"),
        "tx":     ("TOTAL_TRANSACTIONS_QTD",    "TOTAL_TRANSACTIONS_PY_QTD"),
        "bread":  ("BREAD_COUNT_QTD",           "BREAD_COUNT_PY_QTD"),
        "walkin": "WALK_IN_SALES_WTD",
        "online": "ONLINE_SALES_WTD",
        "thirdp": "THIRD_PARTY_SALES_QTD",
        "dd":     ("THIRD_PARTY_DOORDASH_NET_SALES_QTD",   "THIRD_PARTY_DOORDASH_NET_SALES_PY_QTD"),
        "ue":     ("THIRD_PARTY_UBEREATS_NET_SALES_QTD",   "THIRD_PARTY_UBEREATS_NET_SALES_PY_QTD"),
        "gh":     ("THIRD_PARTY_GRUBHUB_NET_SALES_QTD",    "THIRD_PARTY_GRUBHUB_NET_SALES_PY_QTD"),
        "pm":     ("THIRD_PARTY_POSTMATES_NET_SALES_QTD",  "THIRD_PARTY_POSTMATES_NET_SALES_PY_QTD"),
        "cat":    ("CATERING_SALES_QTD",  "CATERING_SALES_PY_QTD"),
        "tkt":    ("CATERING_TICKETS_QTD","CATERING_TICKETS_PY_QTD"),
    },
    "YTD": {
        "sales":  ("NET_SALES_YTD",            "NET_SALES_PY_YTD"),
        "tx":     ("TOTAL_TRANSACTIONS_YTD",    "TOTAL_TRANSACTIONS_PY_YTD"),
        "bread":  ("BREAD_COUNT_YTD",           "BREAD_COUNT_PY_YTD"),
        "walkin": "WALK_IN_SALES_WTD",
        "online": "ONLINE_SALES_WTD",
        "thirdp": "THIRD_PARTY_SALES_WTD",
        "dd":     ("THIRD_PARTY_DOORDASH_NET_SALES_YTD",   "THIRD_PARTY_DOORDASH_NET_SALES_PY_YTD"),
        "ue":     ("THIRD_PARTY_UBEREATS_NET_SALES_YTD",   "THIRD_PARTY_UBEREATS_NET_SALES_PY_YTD"),
        "gh":     ("THIRD_PARTY_GRUBHUB_NET_SALES_YTD",    "THIRD_PARTY_GRUBHUB_NET_SALES_PY_YTD"),
        "pm":     ("THIRD_PARTY_POSTMATES_NET_SALES_YTD",  "THIRD_PARTY_POSTMATES_NET_SALES_PY_YTD"),
        "cat":    ("CATERING_SALES_YTD",  "CATERING_SALES_PY_YTD"),
        "tkt":    ("CATERING_TICKETS_YTD","CATERING_TICKETS_PY_YTD"),
    },
}

def comp_mask(df, py_col):
    """Comp-eligible = stores that had sales in the same period last year.
    Matches existing dashboard methodology: prior year sales > 0."""
    return df[py_col] > 0

def calc_sss(df, cy_col, py_col):
    mask = comp_mask(df, py_col)
    cy = df.loc[mask, cy_col].sum()
    py = df.loc[mask, py_col].sum()
    return (cy - py) / py * 100 if py > 0 else None

def fmt_pct(v):
    if v is None: return "—"
    return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"

def fmt_usd(v):
    if not v: return "—"
    if abs(v) >= 1_000_000: return f"${v/1_000_000:.2f}M"
    if abs(v) >= 1_000: return f"${v/1_000:.1f}K"
    return f"${v:,.0f}"

def pct_color(v):
    if v is None: return MUTED
    return GREEN if v >= 2 else (AMBER if v >= 0 else DANGER)

def yoy(cy, py):
    return (cy - py) / py * 100 if py and py > 0 else None

def tile_html(label, value, color, sub=""):
    return f"""
    <div style="background:{WHITE};border:1px solid {BORDER};border-radius:12px;
                padding:16px 20px;text-align:center;min-width:130px;flex:1;">
      <div style="font-size:11px;color:{MUTED};font-weight:600;
                  text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;">{label}</div>
      <div style="font-size:26px;font-weight:800;color:{color};margin:2px 0;">{value}</div>
      <div style="font-size:11px;color:{MUTED};">{sub}</div>
    </div>"""

def tiles_row(tiles):
    inner = "".join(tiles)
    return f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px;">{inner}</div>'


# ── Load data ─────────────────────────────────────────────────────────────────
try:
    df, latest = load_snapshot()
except Exception as e:
    st.error(f"Failed to load Snowflake data: {e}")
    st.stop()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
  .sf-table {{ width:100%;border-collapse:collapse;font-size:13px; }}
  .sf-table th {{ background:{BLUE};color:{WHITE};padding:8px 12px;
                  text-align:right;font-weight:600;font-size:11px; }}
  .sf-table th:first-child {{ text-align:left; }}
  .sf-table td {{ padding:7px 12px;border-bottom:1px solid {BORDER};
                  text-align:right;color:#1a1a2e; }}
  .sf-table td:first-child {{ text-align:left;font-weight:600; }}
  .sf-table tr:last-child td {{ font-weight:700;background:{LIGHT}; }}
  .sf-table tr:hover td {{ background:#f0f4fa; }}
  .sf-section {{ font-size:14px;font-weight:700;color:{BLUE};
                 margin:18px 0 8px 0;border-bottom:1px solid {BORDER};
                 padding-bottom:4px; }}
  [data-testid="stAppViewContainer"] {{ background:{LIGHT}; }}
  .block-container {{ padding-top:1rem; }}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:8px 0 14px 0;border-bottom:2px solid {BORDER};margin-bottom:16px;">
  <div>
    <span style="font-size:22px;font-weight:800;color:{BLUE};">Daily Sales</span>
    <span style="font-size:12px;color:{MUTED};margin-left:10px;">
      Snowflake · As of <b>{latest}</b>
    </span>
  </div>
  <span style="background:#dbeafe;color:{BLUE};border-radius:6px;
               padding:4px 10px;font-size:11px;font-weight:700;letter-spacing:.5px;">
    TEST — PARALLEL VERSION
  </span>
</div>
""", unsafe_allow_html=True)

# ── Period selector ───────────────────────────────────────────────────────────
period = st.radio("", ["WTD", "MTD", "QTD", "YTD"],
                  horizontal=True, index=0, label_visibility="collapsed")

pc       = PERIOD_COLS[period]
cy_s, py_s = pc["sales"]
cy_t, py_t = pc["tx"]
cy_b, py_b = pc["bread"]

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "By District", "3P Channels", "Catering"])


# ══════════════════════════════════════════════════════════════════════════════
with tab1:
# ══════════════════════════════════════════════════════════════════════════════
    sss_v  = calc_sss(df, cy_s, py_s)
    sst_v  = calc_sss(df, cy_t, py_t)
    bread_v = calc_sss(df, cy_b, py_b)

    total_cy = df[cy_s].sum()
    total_py = df[py_s].sum()
    total_tx_cy = df[cy_t].sum()
    comp_count  = comp_mask(df, py_s).sum()
    atc = total_cy / total_tx_cy if total_tx_cy else None

    # Channel mix — WTD columns used for %
    total_sales_wtd = df["NET_SALES_WTD"].sum() or 1
    walkin_pct = df["WALK_IN_SALES_WTD"].sum() / total_sales_wtd * 100
    online_pct = df["ONLINE_SALES_WTD"].sum()  / total_sales_wtd * 100
    thirdp_pct = df["THIRD_PARTY_SALES_WTD"].sum() / total_sales_wtd * 100

    st.markdown(tiles_row([
        tile_html("SSS%",      fmt_pct(sss_v),   pct_color(sss_v),
                  f"{comp_count} comp stores"),
        tile_html("SST%",      fmt_pct(sst_v),   pct_color(sst_v),
                  "Transactions"),
        tile_html("Bread SSS%",fmt_pct(bread_v), pct_color(bread_v),
                  "Sub count"),
        tile_html(f"Net Sales ({period})", fmt_usd(total_cy), BLUE,
                  fmt_pct(yoy(total_cy, total_py))),
        tile_html("Avg Check", f"${atc:.2f}" if atc else "—", BLUE,
                  f"{total_tx_cy:,.0f} transactions"),
    ]), unsafe_allow_html=True)

    # ── Channel mix tiles ─────────────────────────────────────────────────────
    st.markdown(tiles_row([
        tile_html("Walk-In",    f"{walkin_pct:.1f}%", BLUE,  "of WTD sales"),
        tile_html("Online",     f"{online_pct:.1f}%", BLUE,  "of WTD sales"),
        tile_html("3rd Party",  f"{thirdp_pct:.1f}%", BLUE,  "of WTD sales"),
    ]), unsafe_allow_html=True)

    # ── Market table ──────────────────────────────────────────────────────────
    st.markdown('<div class="sf-section">By Market (Region)</div>', unsafe_allow_html=True)

    rows = []
    for region, grp in sorted(df.groupby("REGION")):
        r_cy  = grp[cy_s].sum()
        r_py  = grp[py_s].sum()
        r_tx  = grp[cy_t].sum()
        r_sss = calc_sss(grp, cy_s, py_s)
        r_sst = calc_sss(grp, cy_t, py_t)
        rows.append(f"""<tr>
          <td>{region or "—"}</td>
          <td>{len(grp)}</td>
          <td>{fmt_usd(r_cy)}</td>
          <td style="color:{pct_color(r_sss)};font-weight:700">{fmt_pct(r_sss)}</td>
          <td style="color:{pct_color(r_sst)};font-weight:700">{fmt_pct(r_sst)}</td>
          <td>{r_tx:,.0f}</td>
        </tr>""")

    total_sss = calc_sss(df, cy_s, py_s)
    total_sst = calc_sss(df, cy_t, py_t)
    rows.append(f"""<tr>
      <td>TOTAL</td>
      <td>{len(df)}</td>
      <td>{fmt_usd(total_cy)}</td>
      <td style="color:{pct_color(total_sss)};font-weight:700">{fmt_pct(total_sss)}</td>
      <td style="color:{pct_color(total_sst)};font-weight:700">{fmt_pct(total_sst)}</td>
      <td>{total_tx_cy:,.0f}</td>
    </tr>""")

    st.markdown(f"""
    <div style="overflow-x:auto;">
    <table class="sf-table">
      <thead><tr>
        <th style="text-align:left">Market</th><th>Stores</th>
        <th>Net Sales</th><th>SSS%</th><th>SST%</th><th>Transactions</th>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table></div>""", unsafe_allow_html=True)

    # ── Store detail ──────────────────────────────────────────────────────────
    with st.expander("Store detail"):
        store_rows = []
        for _, r in df.sort_values("STORE_NAME").iterrows():
            cy_v = r[cy_s]; py_v = r[py_s]
            store_rows.append({
                "Store": r["STORE_NAME"] or r["SITE_ID"],
                "District": r["DISTRICT"],
                f"Sales ({period})": fmt_usd(cy_v),
                "vs PY": fmt_pct(yoy(cy_v, py_v)),
                "Transactions": f"{r[cy_t]:,.0f}",
                "Avg Check": f"${r['AVERAGE_CHECK']:.2f}" if r["AVERAGE_CHECK"] else "—",
            })
        st.dataframe(pd.DataFrame(store_rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
with tab2:
# ══════════════════════════════════════════════════════════════════════════════
    st.markdown(f'<div class="sf-section">SSS / SST by District — {period}</div>',
                unsafe_allow_html=True)
    st.caption("⚠️ DM names not yet in Snowflake — grouped by District. See SNOWFLAKE_MIGRATION_GAPS.md.")

    dist_rows = []
    for district, grp in sorted(df.groupby("DISTRICT")):
        d_cy   = grp[cy_s].sum()
        d_py   = grp[py_s].sum()
        d_tx   = grp[cy_t].sum()
        d_sss  = calc_sss(grp, cy_s, py_s)
        d_sst  = calc_sss(grp, cy_t, py_t)
        d_comp = comp_mask(grp, py_s).sum()
        dist_rows.append({
            "District": district or "—",
            "Stores": len(grp),
            "Comp": d_comp,
            f"Net Sales ({period})": fmt_usd(d_cy),
            "vs PY": fmt_pct(yoy(d_cy, d_py)),
            "SSS%": fmt_pct(d_sss),
            "SST%": fmt_pct(d_sst),
            "Transactions": f"{d_tx:,.0f}",
        })

    dist_rows.append({
        "District": "TOTAL",
        "Stores": len(df),
        "Comp": comp_mask(df, py_s).sum(),
        f"Net Sales ({period})": fmt_usd(df[cy_s].sum()),
        "vs PY": fmt_pct(yoy(df[cy_s].sum(), df[py_s].sum())),
        "SSS%": fmt_pct(calc_sss(df, cy_s, py_s)),
        "SST%": fmt_pct(calc_sss(df, cy_t, py_t)),
        "Transactions": f"{df[cy_t].sum():,.0f}",
    })

    st.dataframe(pd.DataFrame(dist_rows), use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
with tab3:
# ══════════════════════════════════════════════════════════════════════════════
    st.markdown(f'<div class="sf-section">3rd-Party Delivery by Provider — {period}</div>',
                unsafe_allow_html=True)
    st.caption("YOY = all stores. Comp-filtered 3P SSS is a future enhancement (see gaps log).")

    providers = [
        ("DoorDash",  pc["dd"]),
        ("UberEats",  pc["ue"]),
        ("Grubhub",   pc["gh"]),
        ("Postmates", pc["pm"]),
    ]

    tx_cols = {
        "DoorDash":  ("THIRD_PARTY_DOORDASH_TRANSACTION_COUNT",  "THIRD_PARTY_DOORDASH_TRANSACTION_COUNT_PY"),
        "UberEats":  ("THIRD_PARTY_UBEREATS_TRANSACTION_COUNT",  "THIRD_PARTY_UBEREATS_TRANSACTION_COUNT_PY"),
        "Grubhub":   ("THIRD_PARTY_GRUBHUB_TRANSACTION_COUNT",   "THIRD_PARTY_GRUBHUB_TRANSACTION_COUNT_PY"),
        "Postmates": ("THIRD_PARTY_POSTMATES_TRANSACTION_COUNT", "THIRD_PARTY_POSTMATES_TRANSACTION_COUNT_PY"),
    }

    total_thirdp_cy = df[pc["thirdp"]].sum() or 1
    p3_rows = []
    chart_labels, chart_cy, chart_py = [], [], []

    for name, (cy_col, py_col) in providers:
        cy_v = df[cy_col].sum()
        py_v = df[py_col].sum()
        tc_cy, tc_py = tx_cols[name]
        tx_cy_v = df[tc_cy].sum()
        tx_py_v = df[tc_py].sum()
        share = cy_v / total_thirdp_cy * 100

        p3_rows.append({
            "Provider": name,
            f"Sales ({period})": fmt_usd(cy_v),
            "vs PY": fmt_pct(yoy(cy_v, py_v)),
            "% of 3P": f"{share:.1f}%",
            "Orders": f"{tx_cy_v:,.0f}",
            "Orders vs PY": fmt_pct(yoy(tx_cy_v, tx_py_v)),
        })
        chart_labels.append(name)
        chart_cy.append(cy_v)
        chart_py.append(py_v)

    st.dataframe(pd.DataFrame(p3_rows), use_container_width=True, hide_index=True)

    # ── Bar chart CY vs PY ────────────────────────────────────────────────────
    if sum(chart_cy) > 0:
        fig = go.Figure()
        fig.add_bar(name=f"CY ({period})", x=chart_labels, y=chart_cy,
                    marker_color=BLUE)
        fig.add_bar(name="PY",             x=chart_labels, y=chart_py,
                    marker_color=BORDER)
        fig.update_layout(
            barmode="group", height=300,
            margin=dict(t=20, b=20, l=40, r=20),
            plot_bgcolor=WHITE, paper_bgcolor=WHITE,
            yaxis=dict(tickprefix="$", tickformat=",.0f"),
            legend=dict(orientation="h", y=-0.25),
            dragmode=False,
        )
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(fixedrange=True)
        st.plotly_chart(fig, use_container_width=True)

    # ── Pie share ─────────────────────────────────────────────────────────────
    if sum(chart_cy) > 0:
        fig2 = go.Figure(go.Pie(
            labels=chart_labels, values=chart_cy, hole=0.5,
            marker_colors=[RED, "#F97316", BLUE, GOLD],
        ))
        fig2.update_layout(
            height=260, margin=dict(t=10, b=10, l=10, r=10),
            showlegend=True, plot_bgcolor=WHITE, paper_bgcolor=WHITE,
        )
        st.plotly_chart(fig2, use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
with tab4:
# ══════════════════════════════════════════════════════════════════════════════
    st.markdown(f'<div class="sf-section">Catering — {period}</div>',
                unsafe_allow_html=True)

    cat_cy_col, cat_py_col = pc["cat"]
    tkt_cy_col, tkt_py_col = pc["tkt"]

    total_cat_cy  = df[cat_cy_col].sum()
    total_cat_py  = df[cat_py_col].sum()
    total_tkt_cy  = df[tkt_cy_col].sum()
    total_tkt_py  = df[tkt_py_col].sum()
    ezcater_cy    = df["EZCATER_TOTAL_AMOUNT"].sum()
    ezcater_py    = df["EZCATER_TOTAL_AMOUNT_PY"].sum()
    ez_cnt_cy     = df["EZCATER_COUNT"].sum()
    ez_cnt_py     = df["EZCATER_COUNT_PY"].sum()

    cat_share = total_cat_cy / df[cy_s].sum() * 100 if df[cy_s].sum() else None

    st.markdown(tiles_row([
        tile_html(f"Catering Sales ({period})", fmt_usd(total_cat_cy),
                  BLUE, fmt_pct(yoy(total_cat_cy, total_cat_py))),
        tile_html("vs Prior Year",
                  fmt_pct(yoy(total_cat_cy, total_cat_py)),
                  pct_color(yoy(total_cat_cy, total_cat_py)),
                  "YOY all stores"),
        tile_html("Catering Tickets", f"{total_tkt_cy:,.0f}",
                  BLUE, fmt_pct(yoy(total_tkt_cy, total_tkt_py))),
        tile_html("ezCater Sales", fmt_usd(ezcater_cy),
                  GOLD, fmt_pct(yoy(ezcater_cy, ezcater_py))),
        tile_html("ezCater Orders", f"{int(ez_cnt_cy):,}",
                  GOLD, f"PY: {int(ez_cnt_py):,}"),
        tile_html("% of Total Sales", f"{cat_share:.1f}%" if cat_share else "—",
                  MUTED, period),
    ]), unsafe_allow_html=True)

    # ── Store breakdown ───────────────────────────────────────────────────────
    st.markdown('<div class="sf-section">By Store</div>', unsafe_allow_html=True)
    cat_store = []
    for _, r in df.sort_values(cat_cy_col, ascending=False).iterrows():
        cy_v = r[cat_cy_col]
        py_v = r[cat_py_col]
        if cy_v > 0 or py_v > 0:
            cat_store.append({
                "Store": r["STORE_NAME"] or r["SITE_ID"],
                "District": r["DISTRICT"],
                f"Catering ({period})": fmt_usd(cy_v),
                "vs PY": fmt_pct(yoy(cy_v, py_v)),
                "Tickets": f"{r[tkt_cy_col]:,.0f}",
                "ezCater $": fmt_usd(r["EZCATER_TOTAL_AMOUNT"]),
                "ezCater Orders": f"{int(r.get('EZCATER_COUNT') or 0):,}",
            })

    if cat_store:
        st.dataframe(pd.DataFrame(cat_store), use_container_width=True, hide_index=True)
    else:
        st.info("No catering data available for this period.")
