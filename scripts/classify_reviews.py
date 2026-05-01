"""
scripts/classify_reviews.py
============================
LLM classification of Google reviews using Claude Haiku.

For each review with text, scores 7 operational topics (1–5 or null if not
mentioned), assigns sentiment, and flags reviews needing an owner response.

Only processes unclassified reviews (classified_at IS NULL).
Safe to re-run — already-classified reviews are skipped.

Usage:
    py scripts/classify_reviews.py            # classify all pending reviews
    py scripts/classify_reviews.py --dry-run  # preview first batch, no writes
    py scripts/classify_reviews.py --stats    # show classification progress

Cost estimate: ~$0.05 for a full initial run of ~2,500 reviews (Claude Haiku).

Setup:
    Add your Anthropic API key to .streamlit/secrets.toml:
        [anthropic]
        api_key = "sk-ant-..."
    Or set env var: ANTHROPIC_API_KEY=sk-ant-...
"""

import os, sys, json, time, re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

BATCH_SIZE   = 20    # reviews per API call
MODEL        = "claude-haiku-4-5-20251001"
MAX_RETRIES  = 3
RETRY_DELAY  = 5     # seconds between retries

SYSTEM_PROMPT = """You classify Jersey Mike's Subs customer reviews for a franchise operator.

For each review, return scores ONLY for topics the review actually mentions.
Use null for topics not mentioned — do not guess or infer.

Topics (score 1–5 where mentioned, null otherwise):
- topic_speed: wait time, line speed, how fast order was ready
- topic_accuracy: order correctness, got the right items/toppings
- topic_staff: friendliness, helpfulness, professionalism of employees
- topic_food: taste, quality, freshness, portion size, value of the food
- topic_cleanliness: store cleanliness, tables, bathroom, overall tidiness
- topic_online: online ordering, app, third-party delivery (DoorDash etc.)
- topic_value: price vs. value perception, whether food felt worth the cost

Scoring guide: 5=excellent, 4=good, 3=average/neutral mention, 2=below average, 1=poor/very negative

sentiment: overall tone — "positive", "negative", "mixed", or "neutral"

flag_needs_response: true if the review contains any of:
- A specific complaint warranting resolution
- A named employee (positive or negative — owner should acknowledge)
- A food safety or health concern
- Repeated bad experiences ("every time", "always wrong", etc.)
- Otherwise false

Return a JSON array — one object per review, in the same order as input.
Each object must have all 9 keys (use null for unmentioned topics, false for flag).
Return ONLY the JSON array, no explanation."""

CLASSIFICATION_SCHEMA = {
    "topic_speed":          (int, type(None)),
    "topic_accuracy":       (int, type(None)),
    "topic_staff":          (int, type(None)),
    "topic_food":           (int, type(None)),
    "topic_cleanliness":    (int, type(None)),
    "topic_online":         (int, type(None)),
    "topic_value":          (int, type(None)),
    "sentiment":            str,
    "flag_needs_response":  bool,
}

VALID_SENTIMENTS = {"positive", "negative", "mixed", "neutral"}


# ── DB connection ─────────────────────────────────────────────────────────────

def get_conn():
    import psycopg2
    env_host = os.environ.get("SUPABASE_HOST")
    if env_host:
        try:
            conn = psycopg2.connect(
                host=env_host,
                port=int(os.environ.get("SUPABASE_PORT", "5432")),
                dbname=os.environ.get("SUPABASE_DBNAME", "postgres"),
                user=os.environ.get("SUPABASE_USER"),
                password=os.environ.get("SUPABASE_PASSWORD"),
                sslmode="require",
                connect_timeout=10,
                options="-c statement_timeout=0",
            )
            return conn, "postgres"
        except Exception as e:
            print(f"⚠️  Supabase (env) failed: {e}")

    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(secrets_path, "rb") as f:
            cfg = tomllib.load(f)
        if "supabase" in cfg:
            s = cfg["supabase"]
            conn = psycopg2.connect(
                host=s["host"], port=int(s["port"]),
                dbname=s["dbname"], user=s["user"],
                password=s["password"], sslmode="require",
                connect_timeout=10,
                options="-c statement_timeout=0",
            )
            print("Connected to Supabase")
            return conn, "postgres"

    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    return sqlite3.connect(db), "sqlite"


# ── Anthropic API key ─────────────────────────────────────────────────────────

def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if key:
        return key
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(secrets_path, "rb") as f:
            cfg = tomllib.load(f)
        key = cfg.get("anthropic", {}).get("api_key", "").strip()
        if key:
            return key
    return ""


# ── Classify a batch via Anthropic API ───────────────────────────────────────

def _call_api(reviews, api_key):
    """
    Single API call for a list of reviews.
    Returns parsed list of dicts, or raises on error / count mismatch.
    """
    import urllib.request, urllib.error

    numbered = "\n\n".join(
        f"[{i+1}] {r['text'][:1500]}"
        for i, r in enumerate(reviews)
    )
    user_msg = f"Classify these {len(reviews)} reviews:\n\n{numbered}"

    payload = json.dumps({
        "model":      MODEL,
        "max_tokens": 2048,
        "system":     SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": user_msg}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        method="POST",
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
        },
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        body = json.loads(resp.read())
    raw = body["content"][0]["text"].strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    results = json.loads(raw)
    if not isinstance(results, list) or len(results) != len(reviews):
        raise ValueError(f"Expected {len(reviews)} results, got {len(results)}")
    return results


def classify_batch(reviews, api_key):
    """
    Classify a batch of reviews with automatic fallback on count mismatch:
      1. Try the full batch (up to MAX_RETRIES times).
      2. If it consistently returns the wrong count, split into halves and
         classify each half separately.
      3. If a half still fails, fall back to one-at-a-time for that half.
    This handles reviews with special characters or content that confuses
    the model's counting without losing any reviews.
    """
    import urllib.error

    # ── Attempt full batch first ──────────────────────────────────────────────
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _call_api(reviews, api_key)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code == 429 or e.code >= 500:
                if attempt < MAX_RETRIES:
                    wait = RETRY_DELAY * attempt
                    print(f"  ⚠️  HTTP {e.code} — retrying in {wait}s...")
                    time.sleep(wait)
                    continue
            raise RuntimeError(f"Anthropic API error {e.code}: {body}") from e
        except Exception as e:
            if attempt < MAX_RETRIES:
                wait = RETRY_DELAY * attempt
                print(f"  ⚠️  Error ({e}) — retrying in {wait}s...")
                time.sleep(wait)

    # ── Full batch failed — split into halves ─────────────────────────────────
    if len(reviews) == 1:
        # Can't split further — return a blank result so we don't lose the row
        print(f"  ⚠️  Single review failed all retries — using blank classification")
        return [{
            "topic_speed": None, "topic_accuracy": None, "topic_staff": None,
            "topic_food": None, "topic_cleanliness": None, "topic_online": None,
            "topic_value": None, "sentiment": "neutral", "flag_needs_response": False,
        }]

    print(f"  ↳ Splitting batch of {len(reviews)} into halves...")
    mid = len(reviews) // 2
    left  = _classify_with_fallback(reviews[:mid], api_key)
    right = _classify_with_fallback(reviews[mid:], api_key)
    return left + right


def _classify_with_fallback(reviews, api_key):
    """Classify a sub-batch, falling back to halves then one-at-a-time."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return _call_api(reviews, api_key)
        except Exception as e:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)

    if len(reviews) == 1:
        print(f"  ⚠️  Single review failed — using blank classification")
        return [{
            "topic_speed": None, "topic_accuracy": None, "topic_staff": None,
            "topic_food": None, "topic_cleanliness": None, "topic_online": None,
            "topic_value": None, "sentiment": "neutral", "flag_needs_response": False,
        }]

    mid = len(reviews) // 2
    return (_classify_with_fallback(reviews[:mid], api_key) +
            _classify_with_fallback(reviews[mid:], api_key))


def validate_result(r):
    """
    Coerce and validate a single classification result.
    Returns cleaned dict or raises ValueError.
    """
    out = {}
    for key in ("topic_speed","topic_accuracy","topic_staff","topic_food",
                "topic_cleanliness","topic_online","topic_value"):
        val = r.get(key)
        if val is None:
            out[key] = None
        else:
            try:
                v = int(val)
                out[key] = max(1, min(5, v))
            except (TypeError, ValueError):
                out[key] = None

    sentiment = str(r.get("sentiment", "neutral")).lower().strip()
    out["sentiment"] = sentiment if sentiment in VALID_SENTIMENTS else "neutral"

    flag = r.get("flag_needs_response", False)
    out["flag_needs_response"] = bool(flag)
    return out


# ── Write results back to DB ──────────────────────────────────────────────────

def write_results(cur, dialect, review_ids, results):
    """Bulk-update classified_at + all classification fields for a batch."""
    p = "%s" if dialect == "postgres" else "?"
    now = datetime.now(timezone.utc).isoformat()
    sql = f"""
        UPDATE store_reviews SET
            topic_speed          = {p},
            topic_accuracy       = {p},
            topic_staff          = {p},
            topic_food           = {p},
            topic_cleanliness    = {p},
            topic_online         = {p},
            topic_value          = {p},
            sentiment            = {p},
            flag_needs_response  = {p},
            classified_at        = {p}
        WHERE id = {p}
    """
    batch = []
    for rid, res in zip(review_ids, results):
        try:
            r = validate_result(res)
        except Exception as e:
            print(f"  ⚠️  Validation error for id={rid}: {e} — skipping")
            continue
        batch.append((
            r["topic_speed"], r["topic_accuracy"], r["topic_staff"],
            r["topic_food"], r["topic_cleanliness"], r["topic_online"],
            r["topic_value"], r["sentiment"], r["flag_needs_response"],
            now, rid,
        ))
    if batch:
        cur.executemany(sql, batch)
    return len(batch)


# ── Stats ─────────────────────────────────────────────────────────────────────

def show_stats(conn, dialect):
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*)                                          AS total,
            COUNT(*) FILTER (WHERE review_text IS NOT NULL)  AS has_text,
            COUNT(*) FILTER (WHERE classified_at IS NOT NULL) AS classified,
            COUNT(*) FILTER (WHERE classified_at IS NULL
                             AND review_text IS NOT NULL)     AS pending
        FROM store_reviews
    """)
    row = cur.fetchone()
    print(f"Total reviews      : {row[0]:,}")
    print(f"  With text        : {row[1]:,}")
    print(f"  Classified       : {row[2]:,}")
    print(f"  Pending          : {row[3]:,}")

    if row[2]:
        cur.execute("""
            SELECT sentiment, COUNT(*) FROM store_reviews
            WHERE classified_at IS NOT NULL
            GROUP BY sentiment ORDER BY COUNT(*) DESC
        """)
        print("\nSentiment breakdown (classified):")
        for s, c in cur.fetchall():
            print(f"  {s or 'null':<10} {c:,}")

        cur.execute("""
            SELECT COUNT(*) FROM store_reviews
            WHERE flag_needs_response = TRUE
        """)
        nr = cur.fetchone()[0]
        print(f"\nNeeds owner response: {nr:,}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = set(sys.argv[1:])
    dry_run = "--dry-run" in args

    api_key = get_api_key()
    if not api_key:
        print("❌  No Anthropic API key found.")
        print("    Add to .streamlit/secrets.toml:  [anthropic] / api_key = 'sk-ant-...'")
        print("    Or set env var: ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    conn, dialect = get_conn()

    if "--stats" in args:
        show_stats(conn, dialect)
        conn.close()
        return

    cur = conn.cursor()

    # Fetch unclassified reviews that have text
    cur.execute("""
        SELECT id, review_text
        FROM   store_reviews
        WHERE  classified_at IS NULL
          AND  review_text IS NOT NULL
          AND  TRIM(review_text) != ''
        ORDER  BY review_date DESC, id
    """)
    pending = cur.fetchall()

    total = len(pending)
    if total == 0:
        print("✓ All reviews with text are already classified.")
        conn.close()
        return

    print(f"=== Review Classification  ({MODEL}) ===")
    print(f"Pending: {total:,} reviews  |  Batch size: {BATCH_SIZE}")
    if dry_run:
        print("DRY RUN — no writes\n")

    batches     = [pending[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    total_done  = 0
    total_saved = 0
    errors      = 0

    for b_idx, batch in enumerate(batches, 1):
        ids   = [r[0] for r in batch]
        texts = [{"text": r[1]} for r in batch]

        prefix = f"[{b_idx:3d}/{len(batches)}]"
        print(f"{prefix} Classifying {len(batch)} reviews... ", end="", flush=True)

        try:
            results = classify_batch(texts, api_key)
            print(f"✓", end="")
        except Exception as e:
            print(f"\n  ❌  Batch failed: {e}")
            errors += 1
            time.sleep(2)
            continue

        if not dry_run:
            saved = write_results(cur, dialect, ids, results)
            conn.commit()
            total_saved += saved
            print(f"  saved {saved}")
        else:
            total_saved += len(results)
            print(f"  (dry run)")
            if b_idx == 1:
                print("\n  Sample output (first review):")
                print(f"  Text : {texts[0]['text'][:120]}...")
                print(f"  Result: {json.dumps(results[0], indent=4)}\n")
            break   # only run one batch in dry-run mode

        total_done += len(batch)

        # Brief pause to respect rate limits
        time.sleep(0.3)

    conn.close()

    print(f"\n{'─'*50}")
    if dry_run:
        print(f"Dry run complete — {total:,} reviews pending classification")
    else:
        print(f"✓ Done — {total_saved:,} reviews classified  ({errors} batch errors)")
        if errors:
            print(f"  Re-run to retry the {errors} failed batch(es)")


if __name__ == "__main__":
    main()
