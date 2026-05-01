"""
pages/8_Google_Reviews.py
JM Valley Group — Google Reviews Dashboard
Store Scorecard · Needs Response · Trends
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import date, timedelta

st.set_page_config(
    page_title="Google Reviews | JM Valley Group",
    page_icon="⭐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Brand colors ───────────────────────────────────────────────────────────────
RED    = "#EE3227"
BLUE   = "#134A7C"
GOLD   = "#D4AF37"
WHITE  = "#FFFFFF"
LIGHT  = "#F5F6F8"
BORDER = "#E0E3E8"
TEXT   = "#1a1a2e"
MUTED  = "#6B7280"
GREEN  = "#16a34a"
DANGER = "#dc2626"
AMBER  = "#d97706"
STAR   = "#F59E0B"

# ── Store metadata ─────────────────────────────────────────────────────────────
STORE_NAMES = {
    '20156':'North Hollywood','20218':'Mission Hills','20267':'Balboa',
    '20294':'Toluca','20026':'Tampa (Northridge)','20311':'Porter Ranch',
    '20352':'San Fernando','20363':'Warner Center','20273':'Big Bear',
    '20366':'Burbank North','20011':'Westlake','20255':'Arboles',
    '20048':'Janss','20245':'Newbury Park','20381':'Sylmar',
    '20116':'Encino','20388':'Lake Arrowhead','20075':'Isla Vista',
    '20335':'Goleta','20360':'Santa Barbara','20424':'Studio City',
    '20177':'Murrieta','20171':'Temecula Ynez','20091':'Temecula Pkwy',
    '20071':'Escondido Ctr','20300':'Escondido E','20292':'Ramona',
    '20291':'Temecula Ranch','20013':'Buellton',
}

SUBREGION_MAP = {
    '20026':'Valley', '20267':'Valley', '20116':'Valley', '20363':'Valley',
    '20156':'Valley', '20424':'Valley', '20366':'Valley', '20294':'Valley',
    '20352':'Valley', '20218':'Valley', '20381':'Valley', '20311':'Valley',
    '20011':'Conejo Valley', '20048':'Conejo Valley',
    '20245':'Conejo Valley', '20255':'Conejo Valley',
    '20273':'Mountains', '20388':'Mountains',
    '20075':'Santa Barbara', '20335':'Santa Barbara',
    '20360':'Santa Barbara', '20013':'Santa Barbara',
    '20171':'Inland Riverside', '20177':'Inland Riverside',
    '20291':'Inland Riverside', '20091':'Inland Riverside',
    '20071':'Inland SD', '20300':'Inland SD', '20292':'Inland SD',
}

SUBREGION_ORDER = ['Valley','Conejo Valley','Mountains','Santa Barbara',
                   'Inland Riverside','Inland SD']

TOPIC_LABELS = {
    'topic_speed':       'Speed',
    'topic_accuracy':    'Accuracy',
    'topic_staff':       'Staff',
    'topic_food':        'Food',
    'topic_cleanliness': 'Cleanliness',
    'topic_online':      'Online/App',
    'topic_value':       'Value',
}
TOPICS = list(TOPIC_LABELS.keys())

# ── DB connection ──────────────────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jerseymikes.db")

def get_conn():
    try:
        import psycopg2
        s = st.secrets["supabase"]
        return psycopg2.connect(
            host=s["host"], port=int(s["port"]),
            dbname=s["dbname"], user=s["user"],
            password=s["password"], sslmode="require"
        ), "postgres"
    except Exception:
        import sqlite3
        return sqlite3.connect(DB_PATH), "sqlite"


# ── Data loaders ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_reviews():
    """Load all store_reviews with store metadata."""
    conn, _ = get_conn()
    try:
        df = pd.read_sql_query("""
            SELECT
                r.id,
                r.store_id,
                r.reviewer_name,
                r.rating,
                r.review_text,
                r.review_date,
                r.sentiment,
                r.flag_needs_response,
                r.classified_at,
                r.topic_speed,
                r.topic_accuracy,
                r.topic_staff,
                r.topic_food,
                r.topic_cleanliness,
                r.topic_online,
                r.topic_value
            FROM store_reviews r
            ORDER BY r.review_date DESC NULLS LAST
        """, conn)
    finally:
        conn.close()

    df["store_id"] = df["store_id"].astype(str)
    df["store_name"] = df["store_id"].map(STORE_NAMES).fillna(df["store_id"])
    df["subregion"]  = df["store_id"].map(SUBREGION_MAP).fillna("Other")
    df["review_date"] = pd.to_datetime(df["review_date"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def load_store_ratings():
    """Load google_rating and google_review_count from stores table."""
    conn, _ = get_conn()
    try:
        df = pd.read_sql_query("""
            SELECT store_id, google_rating, google_review_count
            FROM stores
            WHERE google_place_id IS NOT NULL
        """, conn)
    finally:
        conn.close()
    df["store_id"] = df["store_id"].astype(str)
    return df


# ── Helper: star string ────────────────────────────────────────────────────────

def stars(rating, max_stars=5):
    """Return filled/empty star Unicode string."""
    if rating is None or pd.isna(rating):
        return "—"
    filled = round(float(rating))
    return "★" * filled + "☆" * (max_stars - filled)


def fmt_rating(val):
    if val is None or pd.isna(val):
        return "—"
    return f"{float(val):.1f}"


def sentiment_badge(s):
    color_map = {
        "positive": GREEN,
        "negative": DANGER,
        "mixed":    AMBER,
        "neutral":  MUTED,
    }
    return color_map.get(s, MUTED)


# ── CSS ────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
/* Page background */
[data-testid="stAppViewContainer"] { background: #F5F6F8; }
[data-testid="stHeader"] { background: transparent; }

/* Metric cards */
.kpi-card {
    background: white;
    border-radius: 10px;
    padding: 16px 20px;
    border: 1px solid #E0E3E8;
    text-align: center;
}
.kpi-label { font-size: 12px; color: #6B7280; font-weight: 600;
             text-transform: uppercase; letter-spacing: .04em; margin-bottom: 4px; }
.kpi-value { font-size: 28px; font-weight: 700; color: #134A7C; }
.kpi-sub   { font-size: 12px; color: #6B7280; margin-top: 2px; }

/* Section card */
.section-card {
    background: white;
    border-radius: 10px;
    padding: 20px 24px;
    border: 1px solid #E0E3E8;
    margin-bottom: 16px;
}
.section-title {
    font-size: 15px; font-weight: 700; color: #134A7C;
    margin-bottom: 14px; border-bottom: 1px solid #E0E3E8; padding-bottom: 8px;
}

/* Sentiment pill */
.pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    color: white;
}
.pill-positive  { background: #16a34a; }
.pill-negative  { background: #dc2626; }
.pill-mixed     { background: #d97706; }
.pill-neutral   { background: #6B7280; }

/* Star color */
.star-gold { color: #F59E0B; font-size: 15px; }
.flag-badge { background:#fef3c7; color:#92400e; border-radius:6px;
              padding:2px 6px; font-size:11px; font-weight:700; }

/* Needs response review card */
.review-card {
    background: white;
    border: 1px solid #E0E3E8;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 10px;
}
.review-card.needs-response { border-left: 4px solid #d97706; }
.review-header { display:flex; justify-content:space-between; align-items:flex-start; }
.review-store { font-weight:700; color:#134A7C; font-size:13px; }
.review-meta  { font-size:12px; color:#6B7280; margin-top:2px; }
.review-text  { font-size:13px; color:#374151; margin-top:8px; line-height:1.5; }

/* Responsive table */
.stDataFrame { border-radius: 8px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)


# ── Page header ────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,{BLUE},{BLUE}dd);
            border-radius:12px;padding:20px 28px;margin-bottom:20px;
            display:flex;align-items:center;gap:16px;">
  <span style="font-size:32px;">⭐</span>
  <div>
    <div style="color:white;font-size:22px;font-weight:800;line-height:1.1;">
      Google Reviews
    </div>
    <div style="color:rgba(255,255,255,.75);font-size:13px;margin-top:3px;">
      JM Valley Group — 29 stores
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Load data ──────────────────────────────────────────────────────────────────
with st.spinner("Loading reviews…"):
    try:
        df_all    = load_reviews()
        df_stores = load_store_ratings()
        load_ok   = True
    except Exception as e:
        st.error(f"Could not load review data: {e}")
        st.stop()

# Only classified reviews for analytics
df_cls = df_all[df_all["classified_at"].notna()].copy()

# ── Top-line KPI strip ─────────────────────────────────────────────────────────
total_reviews  = len(df_all)
classified_cnt = len(df_cls)
needs_resp_cnt = int(df_cls["flag_needs_response"].sum()) if not df_cls.empty else 0

# Portfolio-level weighted avg rating
if not df_stores.empty and df_stores["google_rating"].notna().any():
    # Weight by review count
    valid = df_stores.dropna(subset=["google_rating","google_review_count"])
    if len(valid):
        portfolio_rating = (
            (valid["google_rating"] * valid["google_review_count"]).sum()
            / valid["google_review_count"].sum()
        )
    else:
        portfolio_rating = None
else:
    portfolio_rating = None

pct_positive = (
    (df_cls["sentiment"] == "positive").sum() / len(df_cls) * 100
    if len(df_cls) else None
)

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">Portfolio Rating</div>
      <div class="kpi-value" style="color:#F59E0B;">
        {fmt_rating(portfolio_rating)}
      </div>
      <div class="kpi-sub">★ weighted avg</div>
    </div>""", unsafe_allow_html=True)
with k2:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">Total Reviews</div>
      <div class="kpi-value">{total_reviews:,}</div>
      <div class="kpi-sub">across 29 stores</div>
    </div>""", unsafe_allow_html=True)
with k3:
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">Classified</div>
      <div class="kpi-value">{classified_cnt:,}</div>
      <div class="kpi-sub">of {total_reviews:,} with text</div>
    </div>""", unsafe_allow_html=True)
with k4:
    pct_str = f"{pct_positive:.0f}%" if pct_positive is not None else "—"
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">Positive Sentiment</div>
      <div class="kpi-value" style="color:{GREEN};">{pct_str}</div>
      <div class="kpi-sub">of classified reviews</div>
    </div>""", unsafe_allow_html=True)
with k5:
    badge_color = DANGER if needs_resp_cnt > 0 else GREEN
    st.markdown(f"""
    <div class="kpi-card">
      <div class="kpi-label">Needs Response</div>
      <div class="kpi-value" style="color:{badge_color};">{needs_resp_cnt}</div>
      <div class="kpi-sub">reviews flagged</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_scorecard, tab_response, tab_trends = st.tabs([
    "📋  Store Scorecard",
    f"🚩  Needs Response  ({needs_resp_cnt})",
    "📈  Trends",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — STORE SCORECARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_scorecard:

    # Filters row
    fc1, fc2, fc3 = st.columns([2, 2, 2])
    with fc1:
        sub_opts = ["All Regions"] + SUBREGION_ORDER
        sub_filter = st.selectbox("Region", sub_opts, key="sc_sub")
    with fc2:
        sort_opts = ["Rating (high→low)", "Rating (low→high)",
                     "Reviews (most)", "Positive % (high→low)",
                     "Needs Response (most)", "Store Name"]
        sort_by = st.selectbox("Sort by", sort_opts, key="sc_sort")
    with fc3:
        min_reviews = st.slider("Min reviews to show", 0, 50, 0, key="sc_minrev")

    # ── Build per-store summary ────────────────────────────────────────────────
    # Start from stores with ratings
    store_df = df_stores.copy()
    store_df["store_name"] = store_df["store_id"].map(STORE_NAMES).fillna(store_df["store_id"])
    store_df["subregion"]  = store_df["store_id"].map(SUBREGION_MAP).fillna("Other")

    # Add review counts and sentiment from classified reviews
    if not df_cls.empty:
        rev_agg = df_cls.groupby("store_id").agg(
            review_count_cls   = ("id", "count"),
            pct_positive       = ("sentiment", lambda x: (x == "positive").mean() * 100),
            pct_negative       = ("sentiment", lambda x: (x == "negative").mean() * 100),
            pct_mixed          = ("sentiment", lambda x: (x == "mixed").mean() * 100),
            needs_response_cnt = ("flag_needs_response", "sum"),
            latest_review_date = ("review_date", "max"),
        ).reset_index()
        for t in TOPICS:
            topic_avg = df_cls.groupby("store_id")[t].mean()
            rev_agg = rev_agg.merge(
                topic_avg.rename(f"avg_{t}").reset_index(),
                on="store_id", how="left"
            )
        store_df = store_df.merge(rev_agg, on="store_id", how="left")
    else:
        store_df["review_count_cls"] = 0
        store_df["needs_response_cnt"] = 0

    # Also count ALL reviews (including unclassified) per store
    all_counts = df_all.groupby("store_id")["id"].count().rename("total_review_count").reset_index()
    store_df = store_df.merge(all_counts, on="store_id", how="left")
    store_df["total_review_count"] = store_df["total_review_count"].fillna(0).astype(int)

    # Apply filters
    if sub_filter != "All Regions":
        store_df = store_df[store_df["subregion"] == sub_filter]
    store_df = store_df[store_df["total_review_count"] >= min_reviews]

    # Apply sort
    if sort_by == "Rating (high→low)":
        store_df = store_df.sort_values("google_rating", ascending=False)
    elif sort_by == "Rating (low→high)":
        store_df = store_df.sort_values("google_rating", ascending=True)
    elif sort_by == "Reviews (most)":
        store_df = store_df.sort_values("total_review_count", ascending=False)
    elif sort_by == "Positive % (high→low)":
        store_df = store_df.sort_values("pct_positive", ascending=False)
    elif sort_by == "Needs Response (most)":
        store_df = store_df.sort_values("needs_response_cnt", ascending=False)
    else:
        store_df = store_df.sort_values("store_name")

    if store_df.empty:
        st.info("No stores match the current filters.")
    else:
        # ── Render scorecard cards by subregion ───────────────────────────────
        current_region = None

        for _, row in store_df.iterrows():
            region = row.get("subregion", "Other")
            if region != current_region:
                current_region = region
                st.markdown(
                    f"<div style='font-size:13px;font-weight:700;color:{MUTED};"
                    f"text-transform:uppercase;letter-spacing:.06em;"
                    f"margin:18px 0 8px 2px;'>{region}</div>",
                    unsafe_allow_html=True
                )

            store_name = row.get("store_name", row["store_id"])
            g_rating   = row.get("google_rating")
            g_count    = row.get("google_review_count", 0) or row.get("total_review_count", 0)
            pct_pos    = row.get("pct_positive")
            pct_neg    = row.get("pct_negative")
            pct_mix    = row.get("pct_mixed")
            nr_cnt     = int(row.get("needs_response_cnt", 0) or 0)
            rev_cls    = int(row.get("review_count_cls", 0) or 0)

            # Rating display
            rating_str = fmt_rating(g_rating)
            stars_str  = stars(round(g_rating) if g_rating else None)
            rating_color = (
                DANGER if g_rating and g_rating < 3.5
                else AMBER if g_rating and g_rating < 4.2
                else GREEN
            ) if g_rating else MUTED

            # Sentiment bar widths
            def pct_str(v):
                return f"{v:.0f}%" if v is not None and not pd.isna(v) else "0%"

            # Topic scores — show only topics with data
            topic_parts = []
            for t in TOPICS:
                avg_val = row.get(f"avg_{t}")
                if avg_val is not None and not pd.isna(avg_val):
                    label = TOPIC_LABELS[t]
                    color = (
                        DANGER if avg_val < 2.5
                        else AMBER if avg_val < 3.5
                        else GREEN if avg_val >= 4.0
                        else TEXT
                    )
                    topic_parts.append(
                        f"<span style='margin-right:12px;font-size:12px;'>"
                        f"{label}: <strong style='color:{color}'>{avg_val:.1f}</strong></span>"
                    )

            topics_html = "".join(topic_parts) if topic_parts else (
                f"<span style='color:{MUTED};font-size:12px;'>No classified reviews</span>"
            )

            nr_badge = (
                f"<span style='background:#fef3c7;color:#92400e;"
                f"border-radius:6px;padding:2px 7px;"
                f"font-size:11px;font-weight:700;margin-left:8px;'>"
                f"🚩 {nr_cnt} need response</span>"
                if nr_cnt > 0 else ""
            )

            pct_pos_v = pct_pos if pct_pos is not None and not pd.isna(pct_pos) else 0
            pct_neg_v = pct_neg if pct_neg is not None and not pd.isna(pct_neg) else 0
            pct_mix_v = pct_mix if pct_mix is not None and not pd.isna(pct_mix) else 0
            pct_neu_v = 100 - pct_pos_v - pct_neg_v - pct_mix_v

            sentiment_bar = f"""
            <div style="display:flex;height:6px;border-radius:3px;overflow:hidden;margin:4px 0 2px;">
              <div style="width:{pct_pos_v:.1f}%;background:{GREEN};"></div>
              <div style="width:{pct_mix_v:.1f}%;background:{AMBER};"></div>
              <div style="width:{max(0,pct_neu_v):.1f}%;background:#D1D5DB;"></div>
              <div style="width:{pct_neg_v:.1f}%;background:{DANGER};"></div>
            </div>
            <div style="font-size:10px;color:{MUTED};display:flex;gap:10px;">
              <span>✅ {pct_str(pct_pos)}</span>
              <span>⚡ {pct_str(pct_mix)}</span>
              <span>❌ {pct_str(pct_neg)}</span>
            </div>
            """ if rev_cls > 0 else f"<div style='font-size:11px;color:{MUTED};'>No classified reviews</div>"

            st.markdown(f"""
            <div style="background:white;border:1px solid {BORDER};border-radius:10px;
                        padding:14px 18px;margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
                <div>
                  <div style="font-weight:700;font-size:15px;color:{TEXT};">
                    {store_name}{nr_badge}
                  </div>
                  <div style="font-size:12px;color:{MUTED};margin-top:1px;">
                    {region} · {int(g_count or 0):,} Google reviews
                  </div>
                </div>
                <div style="text-align:right;">
                  <div style="font-size:22px;font-weight:800;color:{rating_color};">
                    {rating_str}
                  </div>
                  <div style="color:{STAR};font-size:14px;line-height:1;">{stars_str}</div>
                </div>
              </div>
              <div style="margin-top:10px;">{sentiment_bar}</div>
              <div style="margin-top:8px;">{topics_html}</div>
            </div>
            """, unsafe_allow_html=True)

        # ── Summary table ──────────────────────────────────────────────────────
        with st.expander("📊  View as table"):
            tbl_cols = {
                "store_name":        "Store",
                "subregion":         "Region",
                "google_rating":     "G Rating",
                "total_review_count":"# Reviews",
                "pct_positive":      "% Positive",
                "pct_negative":      "% Negative",
                "needs_response_cnt":"Needs Resp",
            }
            tbl = store_df[list(tbl_cols.keys())].rename(columns=tbl_cols).copy()
            tbl["G Rating"]   = tbl["G Rating"].apply(fmt_rating)
            tbl["% Positive"] = tbl["% Positive"].apply(
                lambda x: f"{x:.0f}%" if x is not None and not pd.isna(x) else "—"
            )
            tbl["% Negative"] = tbl["% Negative"].apply(
                lambda x: f"{x:.0f}%" if x is not None and not pd.isna(x) else "—"
            )
            tbl["Needs Resp"]  = tbl["Needs Resp"].fillna(0).astype(int)
            st.dataframe(tbl, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — NEEDS RESPONSE
# ══════════════════════════════════════════════════════════════════════════════
with tab_response:

    df_nr = df_cls[df_cls["flag_needs_response"] == True].copy()
    df_nr = df_nr.sort_values("review_date", ascending=False)

    if df_nr.empty:
        st.success("🎉  No reviews currently flagged for response.")
    else:
        # Filter controls
        nrc1, nrc2, nrc3 = st.columns([2, 2, 2])
        with nrc1:
            store_opts = ["All Stores"] + sorted(df_nr["store_name"].unique().tolist())
            nr_store = st.selectbox("Store", store_opts, key="nr_store")
        with nrc2:
            sent_opts = ["All Sentiments", "negative", "mixed", "positive", "neutral"]
            nr_sent = st.selectbox("Sentiment", sent_opts, key="nr_sent")
        with nrc3:
            nr_rating = st.selectbox("Rating", ["All", "1 ★", "2 ★", "3 ★", "4 ★", "5 ★"],
                                     key="nr_rating")

        if nr_store != "All Stores":
            df_nr = df_nr[df_nr["store_name"] == nr_store]
        if nr_sent != "All Sentiments":
            df_nr = df_nr[df_nr["sentiment"] == nr_sent]
        if nr_rating != "All":
            nr_val = int(nr_rating[0])
            df_nr = df_nr[df_nr["rating"] == nr_val]

        st.markdown(
            f"<div style='font-size:13px;color:{MUTED};margin-bottom:12px;'>"
            f"Showing {len(df_nr):,} flagged reviews</div>",
            unsafe_allow_html=True
        )

        for _, rev in df_nr.iterrows():
            store_nm  = rev.get("store_name", rev["store_id"])
            rev_date  = rev["review_date"].strftime("%b %d, %Y") if pd.notna(rev["review_date"]) else "—"
            rating    = rev.get("rating")
            reviewer  = rev.get("reviewer_name") or "Anonymous"
            text      = rev.get("review_text") or ""
            sentiment = (rev.get("sentiment") or "neutral").lower()
            region    = rev.get("subregion", "")

            star_str  = "★" * int(rating) + "☆" * (5 - int(rating)) if rating else "—"
            sent_color = sentiment_badge(sentiment)

            # Which topics are scored (and low)?
            flagged_topics = []
            for t in TOPICS:
                val = rev.get(t)
                if val is not None and not pd.isna(val):
                    label = TOPIC_LABELS[t]
                    if float(val) <= 2:
                        flagged_topics.append(
                            f"<span style='background:{DANGER}20;color:{DANGER};"
                            f"border-radius:4px;padding:1px 5px;font-size:10px;"
                            f"font-weight:600;margin-right:4px;'>{label} {val:.0f}</span>"
                        )
                    else:
                        flagged_topics.append(
                            f"<span style='background:{LIGHT};color:{MUTED};"
                            f"border-radius:4px;padding:1px 5px;font-size:10px;"
                            f"margin-right:4px;'>{label} {val:.0f}</span>"
                        )

            topics_row = " ".join(flagged_topics)

            # Truncate review text
            display_text = (text[:350] + "…") if len(text) > 350 else text

            st.markdown(f"""
            <div style="background:white;border:1px solid {BORDER};
                        border-left:4px solid {AMBER};
                        border-radius:8px;padding:14px 18px;margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;
                          align-items:flex-start;flex-wrap:wrap;gap:6px;">
                <div>
                  <span style="font-weight:700;font-size:14px;color:{BLUE};">{store_nm}</span>
                  <span style="color:{MUTED};font-size:12px;margin-left:8px;">{region}</span>
                  <br/>
                  <span style="color:{STAR};font-size:13px;">{star_str}</span>
                  <span style="color:{MUTED};font-size:12px;margin-left:6px;">{reviewer} · {rev_date}</span>
                </div>
                <span style="background:{sent_color};color:white;border-radius:12px;
                             padding:3px 10px;font-size:11px;font-weight:600;
                             text-transform:capitalize;">{sentiment}</span>
              </div>
              <div style="margin-top:8px;font-size:13px;color:#374151;line-height:1.5;">
                {display_text}
              </div>
              {"<div style='margin-top:8px;'>" + topics_row + "</div>" if flagged_topics else ""}
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — TRENDS
# ══════════════════════════════════════════════════════════════════════════════
with tab_trends:

    tr_c1, tr_c2 = st.columns([2, 2])
    with tr_c1:
        tr_sub_opts = ["All Regions"] + SUBREGION_ORDER
        tr_sub = st.selectbox("Region", tr_sub_opts, key="tr_sub")
    with tr_c2:
        period_opts = ["Last 12 months", "Last 24 months", "All time"]
        tr_period = st.selectbox("Period", period_opts, key="tr_period")

    # Filter data for trends
    df_t = df_all.copy()
    if tr_sub != "All Regions":
        df_t = df_t[df_t["subregion"] == tr_sub]

    df_t = df_t[df_t["review_date"].notna()]

    if tr_period == "Last 12 months":
        cutoff = pd.Timestamp.now() - pd.DateOffset(months=12)
        df_t = df_t[df_t["review_date"] >= cutoff]
    elif tr_period == "Last 24 months":
        cutoff = pd.Timestamp.now() - pd.DateOffset(months=24)
        df_t = df_t[df_t["review_date"] >= cutoff]

    if df_t.empty:
        st.info("No review data for the selected filters.")
    else:
        # Monthly aggregation
        df_t["month"] = df_t["review_date"].dt.to_period("M")
        monthly_rating = df_t.groupby("month").agg(
            avg_rating    = ("rating", "mean"),
            review_count  = ("rating", "count"),
        ).reset_index()
        monthly_rating["month_dt"] = monthly_rating["month"].dt.to_timestamp()
        monthly_rating = monthly_rating.sort_values("month_dt")

        # Monthly sentiment (classified only)
        df_tc = df_t[df_t["classified_at"].notna()].copy()
        if not df_tc.empty:
            df_tc["month"] = df_tc["review_date"].dt.to_period("M")
            sent_monthly = df_tc.groupby(["month","sentiment"])["id"].count().reset_index()
            sent_monthly["month_dt"] = sent_monthly["month"].dt.to_timestamp()
            sent_pivot = sent_monthly.pivot_table(
                index="month_dt", columns="sentiment", values="id", fill_value=0
            ).reset_index()
            for s in ["positive","negative","mixed","neutral"]:
                if s not in sent_pivot.columns:
                    sent_pivot[s] = 0
            sent_pivot["total"] = (
                sent_pivot["positive"] + sent_pivot["negative"] +
                sent_pivot["mixed"] + sent_pivot["neutral"]
            )
            for s in ["positive","negative","mixed","neutral"]:
                sent_pivot[f"pct_{s}"] = sent_pivot[s] / sent_pivot["total"].replace(0,1) * 100
        else:
            sent_pivot = pd.DataFrame()

        # ── Chart 1: Monthly Average Rating ───────────────────────────────────
        st.markdown(
            f"<div class='section-title' style='font-weight:700;font-size:14px;"
            f"color:{BLUE};margin-bottom:8px;'>Monthly Average Rating</div>",
            unsafe_allow_html=True
        )

        fig_rating = go.Figure()
        fig_rating.add_trace(go.Bar(
            x=monthly_rating["month_dt"],
            y=monthly_rating["review_count"],
            name="# Reviews",
            marker_color=BORDER,
            yaxis="y2",
            showlegend=True,
            opacity=0.5,
        ))
        fig_rating.add_trace(go.Scatter(
            x=monthly_rating["month_dt"],
            y=monthly_rating["avg_rating"],
            name="Avg Rating",
            mode="lines+markers",
            line=dict(color=STAR, width=3),
            marker=dict(size=7, color=STAR),
            yaxis="y",
        ))
        fig_rating.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=10, b=50),
            plot_bgcolor="white",
            paper_bgcolor="white",
            yaxis=dict(
                title="Avg Rating",
                range=[1, 5.2],
                tickvals=[1,2,3,4,5],
                gridcolor=BORDER,
                side="left",
            ),
            yaxis2=dict(
                title="# Reviews",
                overlaying="y",
                side="right",
                showgrid=False,
            ),
            xaxis=dict(gridcolor=BORDER),
            legend=dict(orientation="h", y=-0.35, x=0),
            hovermode="x unified",
            dragmode=False,
        )
        fig_rating.update_layout(
            modebar_remove=["zoom2d","pan2d","select2d","lasso2d",
                            "autoScale2d","resetScale2d"],
        )
        st.plotly_chart(fig_rating, use_container_width=True)

        # ── Chart 2: Sentiment breakdown by month ─────────────────────────────
        if not sent_pivot.empty:
            st.markdown(
                f"<div class='section-title' style='font-weight:700;font-size:14px;"
                f"color:{BLUE};margin-bottom:8px;margin-top:16px;'>Sentiment by Month</div>",
                unsafe_allow_html=True
            )

            fig_sent = go.Figure()
            fig_sent.add_trace(go.Bar(
                x=sent_pivot["month_dt"],
                y=sent_pivot["pct_positive"],
                name="Positive",
                marker_color=GREEN,
            ))
            fig_sent.add_trace(go.Bar(
                x=sent_pivot["month_dt"],
                y=sent_pivot["pct_mixed"],
                name="Mixed",
                marker_color=AMBER,
            ))
            fig_sent.add_trace(go.Bar(
                x=sent_pivot["month_dt"],
                y=sent_pivot["pct_neutral"],
                name="Neutral",
                marker_color="#D1D5DB",
            ))
            fig_sent.add_trace(go.Bar(
                x=sent_pivot["month_dt"],
                y=sent_pivot["pct_negative"],
                name="Negative",
                marker_color=DANGER,
            ))
            fig_sent.update_layout(
                barmode="stack",
                height=280,
                margin=dict(l=0, r=0, t=10, b=50),
                plot_bgcolor="white",
                paper_bgcolor="white",
                yaxis=dict(
                    title="% of Reviews",
                    range=[0,100],
                    ticksuffix="%",
                    gridcolor=BORDER,
                ),
                xaxis=dict(gridcolor=BORDER),
                legend=dict(orientation="h", y=-0.35, x=0),
                hovermode="x unified",
                dragmode=False,
            )
            fig_sent.update_layout(
                modebar_remove=["zoom2d","pan2d","select2d","lasso2d",
                                "autoScale2d","resetScale2d"],
            )
            st.plotly_chart(fig_sent, use_container_width=True)

        # ── Chart 3: Topic Score Trends ────────────────────────────────────────
        if not df_tc.empty:
            st.markdown(
                f"<div class='section-title' style='font-weight:700;font-size:14px;"
                f"color:{BLUE};margin-bottom:8px;margin-top:16px;'>Topic Score Trends</div>",
                unsafe_allow_html=True
            )

            topic_filter = st.multiselect(
                "Topics to display",
                options=list(TOPIC_LABELS.values()),
                default=["Staff", "Food", "Speed", "Accuracy"],
                key="tr_topics"
            )
            label_to_key = {v: k for k, v in TOPIC_LABELS.items()}

            df_tc2 = df_tc.copy()
            df_tc2["month_dt"] = df_tc2["review_date"].dt.to_period("M").dt.to_timestamp()

            topic_colors = [BLUE, RED, GREEN, GOLD, AMBER, "#8B5CF6", "#EC4899"]

            fig_topics = go.Figure()
            for i, label in enumerate(topic_filter):
                tkey = label_to_key.get(label)
                if tkey and tkey in df_tc2.columns:
                    tmonth = (
                        df_tc2.dropna(subset=[tkey])
                        .groupby("month_dt")[tkey]
                        .mean()
                        .reset_index()
                        .rename(columns={tkey: "score"})
                    )
                    if not tmonth.empty:
                        fig_topics.add_trace(go.Scatter(
                            x=tmonth["month_dt"],
                            y=tmonth["score"],
                            name=label,
                            mode="lines+markers",
                            line=dict(color=topic_colors[i % len(topic_colors)], width=2),
                            marker=dict(size=5),
                        ))

            fig_topics.update_layout(
                height=280,
                margin=dict(l=0, r=0, t=10, b=50),
                plot_bgcolor="white",
                paper_bgcolor="white",
                yaxis=dict(
                    title="Avg Score (1–5)",
                    range=[1, 5.2],
                    tickvals=[1,2,3,4,5],
                    gridcolor=BORDER,
                ),
                xaxis=dict(gridcolor=BORDER),
                legend=dict(orientation="h", y=-0.35, x=0),
                hovermode="x unified",
                dragmode=False,
            )
            fig_topics.update_layout(
                modebar_remove=["zoom2d","pan2d","select2d","lasso2d",
                                "autoScale2d","resetScale2d"],
            )
            st.plotly_chart(fig_topics, use_container_width=True)

        # ── Rating distribution ────────────────────────────────────────────────
        st.markdown(
            f"<div class='section-title' style='font-weight:700;font-size:14px;"
            f"color:{BLUE};margin-bottom:8px;margin-top:16px;'>Rating Distribution</div>",
            unsafe_allow_html=True
        )
        dist = df_t["rating"].value_counts().sort_index(ascending=False).reset_index()
        dist.columns = ["rating", "count"]
        dist["label"] = dist["rating"].apply(lambda r: "★" * int(r))
        dist["color"] = dist["rating"].apply(
            lambda r: DANGER if r <= 2 else AMBER if r == 3 else GREEN
        )

        fig_dist = go.Figure(go.Bar(
            x=dist["count"],
            y=dist["label"],
            orientation="h",
            marker_color=dist["color"].tolist(),
            text=dist["count"].apply(lambda c: f"{c:,}"),
            textposition="outside",
        ))
        fig_dist.update_layout(
            height=200,
            margin=dict(l=0, r=40, t=10, b=10),
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(gridcolor=BORDER),
            dragmode=False,
        )
        fig_dist.update_layout(
            modebar_remove=["zoom2d","pan2d","select2d","lasso2d",
                            "autoScale2d","resetScale2d"],
        )
        st.plotly_chart(fig_dist, use_container_width=True)
