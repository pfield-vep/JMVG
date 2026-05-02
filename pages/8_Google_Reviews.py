"""
pages/8_Google_Reviews.py
JM Valley Group — Google Reviews Dashboard
Insights (default) · Store Scorecard · Needs Response · Trends
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json, os
from datetime import timedelta

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
    '20026':'Valley','20267':'Valley','20116':'Valley','20363':'Valley',
    '20156':'Valley','20424':'Valley','20366':'Valley','20294':'Valley',
    '20352':'Valley','20218':'Valley','20381':'Valley','20311':'Valley',
    '20011':'Conejo Valley','20048':'Conejo Valley',
    '20245':'Conejo Valley','20255':'Conejo Valley',
    '20273':'Mountains','20388':'Mountains',
    '20075':'Santa Barbara','20335':'Santa Barbara',
    '20360':'Santa Barbara','20013':'Santa Barbara',
    '20171':'Inland Riverside','20177':'Inland Riverside',
    '20291':'Inland Riverside','20091':'Inland Riverside',
    '20071':'Inland SD','20300':'Inland SD','20292':'Inland SD',
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
TOPICS        = list(TOPIC_LABELS.keys())
LABEL_TO_KEY  = {v: k for k, v in TOPIC_LABELS.items()}
SHORT_TO_KEY  = {k.replace('topic_',''):k for k in TOPICS}   # "accuracy" → "topic_accuracy"

# ── DB ─────────────────────────────────────────────────────────────────────────
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


@st.cache_data(ttl=300)
def load_reviews():
    conn, _ = get_conn()
    base_cols = """
        id, store_id, reviewer_name, rating, review_text,
        review_date, sentiment, flag_needs_response, classified_at,
        topic_speed, topic_accuracy, topic_staff, topic_food,
        topic_cleanliness, topic_online, topic_value
    """
    try:
        df = pd.read_sql_query(
            f"SELECT {base_cols}, complaint_tags, praise_tags, employee_mentioned "
            "FROM store_reviews ORDER BY review_date DESC NULLS LAST", conn)
        has_tags = df["complaint_tags"].notna().any()
    except Exception:
        # Postgres aborts the transaction on unknown column — roll back before retrying
        try:
            conn.rollback()
        except Exception:
            pass
        df = pd.read_sql_query(
            f"SELECT {base_cols} FROM store_reviews "
            "ORDER BY review_date DESC NULLS LAST", conn)
        df["complaint_tags"]     = None
        df["praise_tags"]        = None
        df["employee_mentioned"] = None
        has_tags = False
    finally:
        conn.close()

    df["store_id"]   = df["store_id"].astype(str)
    df["store_name"] = df["store_id"].map(STORE_NAMES).fillna(df["store_id"])
    df["subregion"]  = df["store_id"].map(SUBREGION_MAP).fillna("Other")
    df["review_date"] = pd.to_datetime(df["review_date"], errors="coerce")
    return df


@st.cache_data(ttl=300)
def load_store_ratings():
    conn, _ = get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT store_id, google_rating, google_review_count "
            "FROM stores WHERE google_place_id IS NOT NULL", conn)
    finally:
        conn.close()
    df["store_id"] = df["store_id"].astype(str)
    return df


# ── Helpers ────────────────────────────────────────────────────────────────────
def fmt_rating(v):
    return f"{float(v):.1f}" if v is not None and not pd.isna(v) else "—"

def stars(r):
    if r is None or pd.isna(r): return "—"
    f = round(float(r)); return "★"*f + "☆"*(5-f)

def sent_color(s):
    return {
        "positive": GREEN, "negative": DANGER,
        "mixed": AMBER, "neutral": MUTED
    }.get(s or "neutral", MUTED)

def parse_tags(raw, topic_short):
    """Parse complaint_tags/praise_tags JSON → list of phrases for a topic."""
    if not raw or pd.isna(raw):
        return []
    try:
        d = json.loads(raw) if isinstance(raw, str) else raw
        return d.get(topic_short, []) if isinstance(d, dict) else []
    except Exception:
        return []


# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
[data-testid="stAppViewContainer"] {{ background:{LIGHT}; }}
[data-testid="stHeader"] {{ background:transparent; }}
.kpi-card {{
    background:white; border-radius:10px; padding:16px 20px;
    border:1px solid {BORDER}; text-align:center;
}}
.kpi-label {{ font-size:12px; color:{MUTED}; font-weight:600;
              text-transform:uppercase; letter-spacing:.04em; margin-bottom:4px; }}
.kpi-value {{ font-size:28px; font-weight:700; color:{BLUE}; }}
.kpi-sub   {{ font-size:12px; color:{MUTED}; margin-top:2px; }}
.section-hdr {{
    font-size:14px; font-weight:700; color:{BLUE};
    border-bottom:1px solid {BORDER}; padding-bottom:7px; margin-bottom:12px;
}}
.filter-pill {{
    display:inline-flex; align-items:center; gap:6px;
    background:{BLUE}15; border:1px solid {BLUE}40;
    border-radius:20px; padding:5px 14px;
    font-size:13px; font-weight:600; color:{BLUE};
}}
.rev-card {{
    background:white; border:1px solid {BORDER};
    border-left:4px solid var(--lc);
    border-radius:8px; padding:14px 18px; margin-bottom:8px;
}}
</style>
""", unsafe_allow_html=True)


# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div style="background:linear-gradient(135deg,{BLUE},{BLUE}dd);
            border-radius:12px;padding:20px 28px;margin-bottom:20px;
            display:flex;align-items:center;gap:16px;">
  <span style="font-size:32px;">⭐</span>
  <div>
    <div style="color:white;font-size:22px;font-weight:800;">Google Reviews</div>
    <div style="color:rgba(255,255,255,.75);font-size:13px;margin-top:3px;">
      JM Valley Group — 29 stores
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── Load ───────────────────────────────────────────────────────────────────────
with st.spinner("Loading reviews…"):
    try:
        df_all    = load_reviews()
        df_stores = load_store_ratings()
    except Exception as e:
        st.error(f"Could not load review data: {e}")
        st.stop()

df_cls   = df_all[df_all["classified_at"].notna()].copy()
has_tags = (
    "complaint_tags" in df_cls.columns
    and df_cls["complaint_tags"].notna().any()
)


# ── KPI strip ──────────────────────────────────────────────────────────────────
total_reviews  = len(df_all)
classified_cnt = len(df_cls)
needs_resp_cnt = int(df_cls["flag_needs_response"].sum()) if len(df_cls) else 0
pct_pos        = (df_cls["sentiment"] == "positive").mean()*100 if len(df_cls) else None

valid_stores = df_stores.dropna(subset=["google_rating","google_review_count"])
portfolio_rating = (
    (valid_stores["google_rating"] * valid_stores["google_review_count"]).sum()
    / valid_stores["google_review_count"].sum()
    if len(valid_stores) else None
)

k1,k2,k3,k4,k5 = st.columns(5)
for col, label, val, sub, color in [
    (k1, "Portfolio Rating",   fmt_rating(portfolio_rating), "★ weighted avg", STAR),
    (k2, "Total Reviews",      f"{total_reviews:,}",         "across 29 stores", BLUE),
    (k3, "Classified",         f"{classified_cnt:,}",        f"of {total_reviews:,} with text", BLUE),
    (k4, "Positive Sentiment", f"{pct_pos:.0f}%" if pct_pos else "—", "of classified", GREEN),
    (k5, "Needs Response",     str(needs_resp_cnt),          "reviews flagged",
         DANGER if needs_resp_cnt > 0 else GREEN),
]:
    with col:
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value" style="color:{color};">{val}</div>
          <div class="kpi-sub">{sub}</div>
        </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────────
if "ins_topic"   not in st.session_state: st.session_state.ins_topic   = None
if "ins_mode"    not in st.session_state: st.session_state.ins_mode    = "complaint"
if "ins_phrase"  not in st.session_state: st.session_state.ins_phrase  = None


# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_ins, tab_sc, tab_nr, tab_tr = st.tabs([
    "🎯  Insights",
    "📋  Store Scorecard",
    f"🚩  Needs Response  ({needs_resp_cnt})",
    "📈  Trends",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
with tab_ins:

    if df_cls.empty:
        st.info("No classified reviews yet. Run `py scripts/classify_reviews.py` to classify.")
        st.stop()

    # ── Filters ────────────────────────────────────────────────────────────────
    rc1, rc2 = st.columns([2, 2])
    with rc1:
        ins_region = st.selectbox(
            "Region", ["All Regions"] + SUBREGION_ORDER, key="ins_region"
        )
    with rc2:
        PERIOD_OPTIONS = {
            "Last 30 days": 30, "Last 60 days": 60,
            "Last 90 days": 90, "All time": None,
        }
        ins_period = st.selectbox(
            "Time period", list(PERIOD_OPTIONS.keys()),
            index=0, key="ins_period"
        )
    days = PERIOD_OPTIONS[ins_period]

    df_ins = df_cls.copy()
    if ins_region != "All Regions":
        df_ins = df_ins[df_ins["subregion"] == ins_region]
    if days:
        cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
        df_ins = df_ins[df_ins["review_date"] >= cutoff]

    if df_ins.empty:
        st.info(f"No classified reviews in the last {days} days for this region.")
        st.stop()

    # ── Build topic complaint / praise counts ──────────────────────────────────
    complaint_counts, praise_counts, mention_counts = {}, {}, {}
    for t in TOPICS:
        label = TOPIC_LABELS[t]
        col   = df_ins[t].dropna()
        complaint_counts[label] = int((col <= 2).sum())
        praise_counts[label]    = int((col >= 4).sum())
        mention_counts[label]   = int(col.notna().sum())

    # Sort by complaint count descending
    sorted_labels  = sorted(complaint_counts, key=lambda x: complaint_counts[x], reverse=True)
    c_vals         = [complaint_counts[l] for l in sorted_labels]
    p_vals         = [praise_counts[l]    for l in sorted_labels]

    # ── Topic rows: bar + button inline ───────────────────────────────────────
    praise_sorted = sorted(praise_counts, key=lambda x: praise_counts[x], reverse=True)

    def _topic_rows(labels, counts, mode, bar_color):
        max_cnt = max(counts.values()) if any(counts.values()) else 1
        for label in labels:
            cnt = counts[label]
            pct = cnt / max_cnt * 100 if max_cnt > 0 else 0
            is_sel = (st.session_state.ins_topic == label
                      and st.session_state.ins_mode == mode)
            any_sel = st.session_state.ins_topic is not None

            bg      = f"{bar_color}12" if is_sel else "white"
            border  = f"1px solid {bar_color}80" if is_sel else f"1px solid {BORDER}"
            opacity = "1" if (is_sel or not any_sel) else "0.45"
            name_w  = "700" if is_sel else "500"

            row_l, row_r = st.columns([11, 1])
            with row_l:
                st.markdown(f"""
                <div style="background:{bg};border:{border};border-radius:8px;
                            padding:9px 14px;margin-bottom:2px;opacity:{opacity};">
                  <div style="display:flex;align-items:center;gap:12px;">
                    <div style="font-weight:{name_w};font-size:13px;color:{TEXT};
                                min-width:90px;white-space:nowrap;">{label}</div>
                    <div style="flex:1;background:#F3F4F6;border-radius:4px;height:9px;
                                overflow:hidden;">
                      <div style="width:{pct:.1f}%;background:{bar_color};
                                  height:9px;border-radius:4px;
                                  transition:width .3s;"></div>
                    </div>
                    <div style="font-weight:700;font-size:14px;color:{bar_color};
                                min-width:32px;text-align:right;">{cnt}</div>
                  </div>
                </div>
                """, unsafe_allow_html=True)
            with row_r:
                if st.button(
                    "✕" if is_sel else "→",
                    key=f"btn_{mode}_{label}",
                    type="primary" if is_sel else "secondary",
                    use_container_width=True,
                ):
                    if is_sel:
                        st.session_state.ins_topic  = None
                        st.session_state.ins_phrase = None
                    else:
                        st.session_state.ins_topic  = label
                        st.session_state.ins_mode   = mode
                        st.session_state.ins_phrase = None
                    st.rerun()

    ch1, ch2 = st.columns(2)
    with ch1:
        st.markdown(f"<div class='section-hdr'>🔴 Top Complaint Areas</div>",
                    unsafe_allow_html=True)
        _topic_rows(sorted_labels, complaint_counts, "complaint", DANGER)

    with ch2:
        st.markdown(f"<div class='section-hdr'>🟢 Top Praise Areas</div>",
                    unsafe_allow_html=True)
        _topic_rows(praise_sorted, praise_counts, "praise", GREEN)

    # ── Active filter banner ───────────────────────────────────────────────────
    sel_topic  = st.session_state.ins_topic
    sel_mode   = st.session_state.ins_mode
    sel_phrase = st.session_state.ins_phrase

    if sel_topic:
        topic_key   = LABEL_TO_KEY.get(sel_topic)
        topic_short = topic_key.replace("topic_","") if topic_key else ""
        mode_label  = "complaints" if sel_mode == "complaint" else "praise"
        threshold   = 2 if sel_mode == "complaint" else 4
        compare_op  = "le" if sel_mode == "complaint" else "ge"

        banner_col, clear_col = st.columns([6,1])
        with banner_col:
            phrase_part = f" → <b>{sel_phrase}</b>" if sel_phrase else ""
            st.markdown(
                f"<div class='filter-pill'>"
                f"{'🔴' if sel_mode=='complaint' else '🟢'} "
                f"<b>{sel_topic}</b> {mode_label}{phrase_part}"
                f"</div>",
                unsafe_allow_html=True
            )
        with clear_col:
            if st.button("✕ Clear", key="ins_clear"):
                st.session_state.ins_topic  = None
                st.session_state.ins_phrase = None
                st.rerun()

        # ── Specific issue breakdown (if tags available) ───────────────────────
        if has_tags and topic_key:
            tag_col = "complaint_tags" if sel_mode == "complaint" else "praise_tags"

            # Filter to reviews where this topic is mentioned at complaint/praise level
            if compare_op == "le":
                topic_revs = df_ins[df_ins[topic_key].notna() & (df_ins[topic_key] <= threshold)]
            else:
                topic_revs = df_ins[df_ins[topic_key].notna() & (df_ins[topic_key] >= threshold)]

            # Extract all phrases for this topic from tag column
            phrase_counts = {}
            for raw in topic_revs[tag_col].dropna():
                for phrase in parse_tags(raw, topic_short):
                    phrase = phrase.strip().lower()
                    if phrase:
                        phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

            if phrase_counts:
                top_phrases = sorted(phrase_counts, key=phrase_counts.get, reverse=True)[:15]
                top_vals    = [phrase_counts[p] for p in top_phrases]
                bar_col     = DANGER if sel_mode == "complaint" else GREEN

                st.markdown(
                    f"<div class='section-hdr' style='margin-top:16px;'>"
                    f"Specific {'Issues' if sel_mode=='complaint' else 'Highlights'}: "
                    f"{sel_topic}</div>",
                    unsafe_allow_html=True
                )

                # Phrase bar chart (visual)
                opacities = [
                    1.0 if sel_phrase is None or p == sel_phrase else 0.25
                    for p in top_phrases
                ]
                fig_phrases = go.Figure(go.Bar(
                    x=top_vals, y=top_phrases, orientation="h",
                    marker=dict(color=bar_col, opacity=opacities),
                    text=[str(v) for v in top_vals],
                    textposition="outside",
                    hovertemplate="%{y}: <b>%{x}</b> reviews<extra></extra>",
                ))
                fig_phrases.update_layout(
                    height=max(160, len(top_phrases)*28),
                    margin=dict(l=0, r=40, t=10, b=10),
                    plot_bgcolor="white", paper_bgcolor="white",
                    xaxis=dict(showgrid=False, showticklabels=False),
                    yaxis=dict(gridcolor=BORDER, autorange="reversed",
                               tickfont=dict(size=12)),
                    dragmode=False,
                )
                fig_phrases.update_layout(modebar_remove=[
                    "zoom2d","pan2d","select2d","lasso2d","autoScale2d","resetScale2d"
                ])
                st.plotly_chart(fig_phrases, use_container_width=True)

                # Phrase filter buttons — 4 per row
                st.caption("Filter to a specific issue:")
                phrase_rows = [top_phrases[i:i+4] for i in range(0, len(top_phrases), 4)]
                for row in phrase_rows:
                    pcols = st.columns(4)
                    for j, phrase in enumerate(row):
                        cnt = phrase_counts[phrase]
                        is_sel = (sel_phrase == phrase)
                        with pcols[j]:
                            if st.button(
                                f"{'✓ ' if is_sel else ''}{phrase} ({cnt})",
                                key=f"phrase_{phrase}",
                                type="primary" if is_sel else "secondary",
                                use_container_width=True,
                            ):
                                st.session_state.ins_phrase = None if is_sel else phrase
                                st.rerun()

            elif topic_revs.empty:
                pass
            else:
                st.caption(
                    f"Run `py scripts/extract_issues.py` to see specific "
                    f"{sel_topic.lower()} issues broken down."
                )

        elif not has_tags and sel_topic:
            st.info(
                f"💡 Run `py scripts/extract_issues.py` to see exactly what customers "
                f"complain about within {sel_topic} (e.g. 'wrong toppings', 'stale bread')."
            )

        # ── Filtered reviews ───────────────────────────────────────────────────
        st.markdown(
            f"<div class='section-hdr' style='margin-top:16px;'>Matching Reviews</div>",
            unsafe_allow_html=True
        )

        if topic_key:
            if compare_op == "le":
                df_filtered = df_ins[
                    df_ins[topic_key].notna() & (df_ins[topic_key] <= threshold)
                ].sort_values("review_date", ascending=False)
            else:
                df_filtered = df_ins[
                    df_ins[topic_key].notna() & (df_ins[topic_key] >= threshold)
                ].sort_values("review_date", ascending=False)

            # Further filter by phrase if selected
            if sel_phrase and has_tags:
                tag_col = "complaint_tags" if sel_mode == "complaint" else "praise_tags"
                def has_phrase(raw):
                    phrases = parse_tags(raw, topic_short)
                    return any(sel_phrase.lower() == p.strip().lower() for p in phrases)
                df_filtered = df_filtered[
                    df_filtered[tag_col].apply(has_phrase)
                ]

            st.caption(f"{len(df_filtered):,} reviews")

            lc = DANGER if sel_mode == "complaint" else GREEN
            for _, rev in df_filtered.head(50).iterrows():
                rating   = rev.get("rating")
                star_str = ("★"*int(rating) + "☆"*(5-int(rating))) if rating else "—"
                reviewer = rev.get("reviewer_name") or "Anonymous"
                rev_date = (rev["review_date"].strftime("%b %d, %Y")
                            if pd.notna(rev.get("review_date")) else "—")
                text     = (rev.get("review_text") or "")
                text_disp = (text[:300]+"…") if len(text)>300 else text
                sname    = rev.get("store_name","")
                sentiment = (rev.get("sentiment") or "neutral").lower()
                score    = rev.get(topic_key)
                score_str = f"{TOPIC_LABELS.get(topic_key,'')}: {score:.0f}/5" if score else ""

                st.markdown(f"""
                <div style="background:white;border:1px solid {BORDER};
                            border-left:4px solid {lc};
                            border-radius:8px;padding:12px 16px;margin-bottom:8px;">
                  <div style="display:flex;justify-content:space-between;
                              align-items:flex-start;flex-wrap:wrap;gap:4px;">
                    <div>
                      <span style="font-weight:700;font-size:13px;color:{BLUE};">{sname}</span>
                      <span style="color:{STAR};font-size:12px;margin-left:8px;">{star_str}</span>
                      <span style="color:{MUTED};font-size:11px;margin-left:6px;">
                        {reviewer} · {rev_date}
                      </span>
                    </div>
                    <div style="display:flex;gap:6px;align-items:center;">
                      {"<span style='background:"+lc+"20;color:"+lc+";border-radius:4px;"
                       "padding:2px 6px;font-size:11px;font-weight:700;'>"+score_str+"</span>"
                       if score_str else ""}
                      <span style="background:{sent_color(sentiment)}20;
                                   color:{sent_color(sentiment)};
                                   border-radius:4px;padding:2px 6px;
                                   font-size:11px;font-weight:600;">{sentiment}</span>
                    </div>
                  </div>
                  <div style="margin-top:7px;font-size:13px;color:#374151;line-height:1.5;">
                    {text_disp}
                  </div>
                </div>
                """, unsafe_allow_html=True)

            if len(df_filtered) > 50:
                st.caption(f"Showing first 50 of {len(df_filtered):,}. Apply region filter to narrow down.")

    else:
        # ── Default view: no topic selected — show quick summary ───────────────
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        sc1, sc2 = st.columns(2)

        with sc1:
            st.markdown(
                f"<div class='section-hdr'>🏪 Stores With Most Complaints</div>",
                unsafe_allow_html=True
            )
            store_complaints = (
                df_ins[df_ins["sentiment"].isin(["negative","mixed"])]
                .groupby("store_name")["id"].count()
                .sort_values(ascending=False)
                .head(10)
            )
            if not store_complaints.empty:
                fig_sc = go.Figure(go.Bar(
                    x=store_complaints.values,
                    y=store_complaints.index,
                    orientation="h",
                    marker_color=RED,
                    text=store_complaints.values,
                    textposition="outside",
                ))
                fig_sc.update_layout(
                    height=280, margin=dict(l=0, r=40, t=10, b=10),
                    plot_bgcolor="white", paper_bgcolor="white",
                    xaxis=dict(showgrid=False, showticklabels=False),
                    yaxis=dict(autorange="reversed"),
                    dragmode=False,
                )
                fig_sc.update_layout(modebar_remove=[
                    "zoom2d","pan2d","select2d","lasso2d","autoScale2d","resetScale2d"
                ])
                st.plotly_chart(fig_sc, use_container_width=True, key="store_complaints")

        with sc2:
            st.markdown(
                f"<div class='section-hdr'>📊 Sentiment Breakdown</div>",
                unsafe_allow_html=True
            )
            sent_counts = df_ins["sentiment"].value_counts()
            colors_map  = {"positive": GREEN, "negative": DANGER, "mixed": AMBER, "neutral": MUTED}
            fig_sent = go.Figure(go.Pie(
                labels=sent_counts.index,
                values=sent_counts.values,
                marker_colors=[colors_map.get(s, MUTED) for s in sent_counts.index],
                hole=0.55,
                textinfo="label+percent",
                hovertemplate="%{label}: <b>%{value}</b> reviews<extra></extra>",
            ))
            fig_sent.update_layout(
                height=280, margin=dict(l=0, r=0, t=10, b=10),
                paper_bgcolor="white",
                showlegend=False,
                dragmode=False,
            )
            fig_sent.update_layout(modebar_remove=[
                "zoom2d","pan2d","select2d","lasso2d","autoScale2d","resetScale2d"
            ])
            st.plotly_chart(fig_sent, use_container_width=True, key="sent_donut")

        st.markdown(
            f"<div style='text-align:center;color:{MUTED};font-size:13px;padding:8px 0;'>"
            f"👆 Click a bar in the charts above to drill into specific reviews</div>",
            unsafe_allow_html=True
        )


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — STORE SCORECARD
# ══════════════════════════════════════════════════════════════════════════════
with tab_sc:
    fc1, fc2, fc3 = st.columns([2,2,2])
    with fc1:
        sub_filter = st.selectbox("Region", ["All Regions"]+SUBREGION_ORDER, key="sc_sub")
    with fc2:
        sort_by = st.selectbox("Sort by", [
            "Rating (high→low)","Rating (low→high)",
            "Reviews (most)","Positive % (high→low)",
            "Needs Response (most)","Store Name"
        ], key="sc_sort")
    with fc3:
        min_rev = st.slider("Min reviews", 0, 50, 0, key="sc_minrev")

    store_df = df_stores.copy()
    store_df["store_name"] = store_df["store_id"].map(STORE_NAMES).fillna(store_df["store_id"])
    store_df["subregion"]  = store_df["store_id"].map(SUBREGION_MAP).fillna("Other")

    if not df_cls.empty:
        rev_agg = df_cls.groupby("store_id").agg(
            review_count_cls   = ("id","count"),
            pct_positive       = ("sentiment", lambda x: (x=="positive").mean()*100),
            pct_negative       = ("sentiment", lambda x: (x=="negative").mean()*100),
            pct_mixed          = ("sentiment", lambda x: (x=="mixed").mean()*100),
            needs_response_cnt = ("flag_needs_response","sum"),
        ).reset_index()
        for t in TOPICS:
            rev_agg = rev_agg.merge(
                df_cls.groupby("store_id")[t].mean().rename(f"avg_{t}").reset_index(),
                on="store_id", how="left"
            )
        store_df = store_df.merge(rev_agg, on="store_id", how="left")

    all_counts = df_all.groupby("store_id")["id"].count().rename("total_review_count").reset_index()
    store_df   = store_df.merge(all_counts, on="store_id", how="left")
    store_df["total_review_count"] = store_df["total_review_count"].fillna(0).astype(int)

    if sub_filter != "All Regions":
        store_df = store_df[store_df["subregion"] == sub_filter]
    store_df = store_df[store_df["total_review_count"] >= min_rev]

    if sort_by == "Rating (high→low)":     store_df = store_df.sort_values("google_rating", ascending=False)
    elif sort_by == "Rating (low→high)":   store_df = store_df.sort_values("google_rating")
    elif sort_by == "Reviews (most)":      store_df = store_df.sort_values("total_review_count", ascending=False)
    elif sort_by == "Positive % (high→low)": store_df = store_df.sort_values("pct_positive", ascending=False)
    elif sort_by == "Needs Response (most)": store_df = store_df.sort_values("needs_response_cnt", ascending=False)
    else: store_df = store_df.sort_values("store_name")

    current_region = None
    for _, row in store_df.iterrows():
        region = row.get("subregion","Other")
        if region != current_region:
            current_region = region
            st.markdown(
                f"<div style='font-size:12px;font-weight:700;color:{MUTED};"
                f"text-transform:uppercase;letter-spacing:.06em;"
                f"margin:18px 0 8px 2px;'>{region}</div>",
                unsafe_allow_html=True
            )

        sname    = row.get("store_name", row["store_id"])
        g_rating = row.get("google_rating")
        g_count  = row.get("google_review_count") or row.get("total_review_count",0)
        pct_pos  = row.get("pct_positive")
        pct_neg  = row.get("pct_negative")
        pct_mix  = row.get("pct_mixed")
        nr_cnt   = int(row.get("needs_response_cnt",0) or 0)

        rating_color = (
            DANGER if g_rating and g_rating < 3.5
            else AMBER if g_rating and g_rating < 4.2
            else GREEN
        ) if g_rating else MUTED

        topic_parts = []
        for t in TOPICS:
            v = row.get(f"avg_{t}")
            if v is not None and not pd.isna(v):
                c = DANGER if v<2.5 else AMBER if v<3.5 else GREEN if v>=4.0 else TEXT
                topic_parts.append(
                    f"<span style='margin-right:10px;font-size:12px;'>"
                    f"{TOPIC_LABELS[t]}: <strong style='color:{c}'>{v:.1f}</strong></span>"
                )

        p_pos = pct_pos if pct_pos and not pd.isna(pct_pos) else 0
        p_neg = pct_neg if pct_neg and not pd.isna(pct_neg) else 0
        p_mix = pct_mix if pct_mix and not pd.isna(pct_mix) else 0
        p_neu = max(0, 100 - p_pos - p_neg - p_mix)

        nr_badge = (
            f"<span style='background:#fef3c7;color:#92400e;border-radius:6px;"
            f"padding:2px 6px;font-size:11px;font-weight:700;margin-left:8px;'>"
            f"🚩 {nr_cnt}</span>" if nr_cnt > 0 else ""
        )

        st.markdown(f"""
        <div style="background:white;border:1px solid {BORDER};border-radius:10px;
                    padding:13px 18px;margin-bottom:7px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <span style="font-weight:700;font-size:14px;color:{TEXT};">
                {sname}{nr_badge}
              </span>
              <div style="font-size:11px;color:{MUTED};margin-top:2px;">
                {region} · {int(g_count or 0):,} Google reviews
              </div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:20px;font-weight:800;color:{rating_color};">
                {fmt_rating(g_rating)}
              </div>
              <div style="color:{STAR};font-size:13px;">{stars(g_rating)}</div>
            </div>
          </div>
          <div style="display:flex;height:5px;border-radius:3px;overflow:hidden;margin:9px 0 3px;">
            <div style="width:{p_pos:.1f}%;background:{GREEN};"></div>
            <div style="width:{p_mix:.1f}%;background:{AMBER};"></div>
            <div style="width:{p_neu:.1f}%;background:#D1D5DB;"></div>
            <div style="width:{p_neg:.1f}%;background:{DANGER};"></div>
          </div>
          <div style="font-size:10px;color:{MUTED};display:flex;gap:10px;margin-bottom:7px;">
            <span>✅ {p_pos:.0f}%</span><span>⚡ {p_mix:.0f}%</span>
            <span>❌ {p_neg:.0f}%</span>
          </div>
          <div>{"".join(topic_parts) or
               f"<span style='color:{MUTED};font-size:12px;'>No classified reviews</span>"}</div>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — NEEDS RESPONSE
# ══════════════════════════════════════════════════════════════════════════════
with tab_nr:
    df_nr = df_cls[df_cls["flag_needs_response"] == True].sort_values("review_date", ascending=False)

    if df_nr.empty:
        st.success("🎉 No reviews currently flagged for response.")
    else:
        nrc1, nrc2, nrc3 = st.columns([2,2,2])
        with nrc1:
            nr_store = st.selectbox(
                "Store", ["All Stores"]+sorted(df_nr["store_name"].unique().tolist()), key="nr_store"
            )
        with nrc2:
            nr_sent = st.selectbox(
                "Sentiment", ["All","negative","mixed","positive","neutral"], key="nr_sent"
            )
        with nrc3:
            nr_rating = st.selectbox("Rating", ["All","1 ★","2 ★","3 ★","4 ★","5 ★"], key="nr_rating")

        if nr_store != "All Stores":  df_nr = df_nr[df_nr["store_name"] == nr_store]
        if nr_sent  != "All":         df_nr = df_nr[df_nr["sentiment"]  == nr_sent]
        if nr_rating != "All":        df_nr = df_nr[df_nr["rating"]     == int(nr_rating[0])]

        st.caption(f"{len(df_nr):,} flagged reviews")

        for _, rev in df_nr.iterrows():
            sname    = rev.get("store_name","")
            rev_date = (rev["review_date"].strftime("%b %d, %Y")
                        if pd.notna(rev.get("review_date")) else "—")
            rating   = rev.get("rating")
            star_str = ("★"*int(rating)+"☆"*(5-int(rating))) if rating else "—"
            reviewer = rev.get("reviewer_name") or "Anonymous"
            text     = rev.get("review_text") or ""
            sentiment = (rev.get("sentiment") or "neutral").lower()
            sc = sent_color(sentiment)

            low_topics = []
            for t in TOPICS:
                v = rev.get(t)
                if v is not None and not pd.isna(v) and float(v) <= 2:
                    low_topics.append(
                        f"<span style='background:{DANGER}18;color:{DANGER};"
                        f"border-radius:4px;padding:2px 5px;font-size:11px;"
                        f"font-weight:600;margin-right:4px;'>"
                        f"{TOPIC_LABELS[t]} {v:.0f}</span>"
                    )

            st.markdown(f"""
            <div style="background:white;border:1px solid {BORDER};
                        border-left:4px solid {AMBER};
                        border-radius:8px;padding:14px 18px;margin-bottom:9px;">
              <div style="display:flex;justify-content:space-between;
                          align-items:flex-start;flex-wrap:wrap;gap:6px;">
                <div>
                  <span style="font-weight:700;font-size:14px;color:{BLUE};">{sname}</span>
                  <br/>
                  <span style="color:{STAR};font-size:13px;">{star_str}</span>
                  <span style="color:{MUTED};font-size:12px;margin-left:6px;">
                    {reviewer} · {rev_date}
                  </span>
                </div>
                <span style="background:{sc};color:white;border-radius:12px;
                             padding:3px 10px;font-size:11px;font-weight:600;
                             text-transform:capitalize;">{sentiment}</span>
              </div>
              <div style="margin-top:8px;font-size:13px;color:#374151;line-height:1.5;">
                {(text[:350]+"…") if len(text)>350 else text}
              </div>
              {"<div style='margin-top:8px;'>"+"".join(low_topics)+"</div>" if low_topics else ""}
            </div>
            """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — TRENDS
# ══════════════════════════════════════════════════════════════════════════════
with tab_tr:
    tr_c1, tr_c2 = st.columns([2,2])
    with tr_c1:
        tr_sub = st.selectbox("Region", ["All Regions"]+SUBREGION_ORDER, key="tr_sub")
    with tr_c2:
        tr_period = st.selectbox("Period", ["Last 12 months","Last 24 months","All time"], key="tr_period")

    df_t = df_all[df_all["review_date"].notna()].copy()
    if tr_sub != "All Regions":
        df_t = df_t[df_t["subregion"] == tr_sub]
    if tr_period == "Last 12 months":
        df_t = df_t[df_t["review_date"] >= pd.Timestamp.now() - pd.DateOffset(months=12)]
    elif tr_period == "Last 24 months":
        df_t = df_t[df_t["review_date"] >= pd.Timestamp.now() - pd.DateOffset(months=24)]

    if df_t.empty:
        st.info("No review data for the selected filters.")
    else:
        df_t["month"] = df_t["review_date"].dt.to_period("M")

        mrating = (
            df_t.groupby("month")
            .agg(avg_rating=("rating","mean"), review_count=("rating","count"))
            .reset_index()
        )
        mrating["month_dt"] = mrating["month"].dt.to_timestamp()

        # Monthly avg rating + volume
        st.markdown(f"<div class='section-hdr'>Monthly Average Rating</div>",
                    unsafe_allow_html=True)
        fig_r = go.Figure()
        fig_r.add_trace(go.Bar(
            x=mrating["month_dt"], y=mrating["review_count"],
            name="# Reviews", marker_color=BORDER, yaxis="y2", opacity=0.5,
        ))
        fig_r.add_trace(go.Scatter(
            x=mrating["month_dt"], y=mrating["avg_rating"],
            name="Avg Rating", mode="lines+markers",
            line=dict(color=STAR, width=3), marker=dict(size=7),
        ))
        fig_r.update_layout(
            height=290, margin=dict(l=0,r=0,t=10,b=50),
            plot_bgcolor="white", paper_bgcolor="white",
            yaxis=dict(title="Avg Rating", range=[1,5.2],
                       tickvals=[1,2,3,4,5], gridcolor=BORDER),
            yaxis2=dict(title="# Reviews", overlaying="y", side="right", showgrid=False),
            xaxis=dict(gridcolor=BORDER),
            legend=dict(orientation="h", y=-0.35, x=0),
            hovermode="x unified", dragmode=False,
        )
        fig_r.update_layout(modebar_remove=["zoom2d","pan2d","select2d","lasso2d",
                                            "autoScale2d","resetScale2d"])
        st.plotly_chart(fig_r, use_container_width=True)

        # Sentiment by month
        df_tc = df_t[df_t["classified_at"].notna()].copy()
        if not df_tc.empty:
            df_tc["month"] = df_tc["review_date"].dt.to_period("M")
            sent_m = df_tc.groupby(["month","sentiment"])["id"].count().reset_index()
            sent_m["month_dt"] = sent_m["month"].dt.to_timestamp()
            sp = sent_m.pivot_table(
                index="month_dt", columns="sentiment", values="id", fill_value=0
            ).reset_index()
            for s in ["positive","negative","mixed","neutral"]:
                if s not in sp.columns: sp[s] = 0
            tot = sp[["positive","negative","mixed","neutral"]].sum(axis=1).replace(0,1)
            for s in ["positive","negative","mixed","neutral"]:
                sp[f"pct_{s}"] = sp[s] / tot * 100

            st.markdown(f"<div class='section-hdr' style='margin-top:16px;'>Sentiment by Month</div>",
                        unsafe_allow_html=True)
            fig_s = go.Figure()
            for s, c in [("positive",GREEN),("mixed",AMBER),("neutral","#D1D5DB"),("negative",DANGER)]:
                fig_s.add_trace(go.Bar(x=sp["month_dt"], y=sp[f"pct_{s}"],
                                       name=s.capitalize(), marker_color=c))
            fig_s.update_layout(
                barmode="stack", height=260,
                margin=dict(l=0,r=0,t=10,b=50),
                plot_bgcolor="white", paper_bgcolor="white",
                yaxis=dict(title="% of Reviews", range=[0,100],
                           ticksuffix="%", gridcolor=BORDER),
                xaxis=dict(gridcolor=BORDER),
                legend=dict(orientation="h", y=-0.35, x=0),
                hovermode="x unified", dragmode=False,
            )
            fig_s.update_layout(modebar_remove=["zoom2d","pan2d","select2d","lasso2d",
                                                "autoScale2d","resetScale2d"])
            st.plotly_chart(fig_s, use_container_width=True)

        # Rating distribution
        st.markdown(f"<div class='section-hdr' style='margin-top:16px;'>Rating Distribution</div>",
                    unsafe_allow_html=True)
        dist = df_t["rating"].value_counts().sort_index(ascending=False).reset_index()
        dist.columns = ["rating","count"]
        fig_d = go.Figure(go.Bar(
            x=dist["count"], y=dist["rating"].apply(lambda r: "★"*int(r)),
            orientation="h",
            marker_color=dist["rating"].apply(
                lambda r: DANGER if r<=2 else AMBER if r==3 else GREEN
            ).tolist(),
            text=dist["count"].apply(lambda c: f"{c:,}"),
            textposition="outside",
        ))
        fig_d.update_layout(
            height=200, margin=dict(l=0,r=40,t=10,b=10),
            plot_bgcolor="white", paper_bgcolor="white",
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(autorange="reversed"),
            dragmode=False,
        )
        fig_d.update_layout(modebar_remove=["zoom2d","pan2d","select2d","lasso2d",
                                            "autoScale2d","resetScale2d"])
        st.plotly_chart(fig_d, use_container_width=True)
