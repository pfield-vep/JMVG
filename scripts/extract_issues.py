"""
scripts/extract_issues.py
=========================
Second LLM pass: extract specific sub-issues and praises per topic.

For each classified review, this script pulls out WHAT EXACTLY was good or bad
within each topic — going beyond "Accuracy: 2" to tell you "wrong toppings",
"missing peppers", "got someone else's order", etc.

Also extracts any employee first names mentioned (positive or negative).

Output (per review, stored back in store_reviews):
  complaint_tags   — JSON object: {"accuracy": ["wrong toppings", "missing mayo"], ...}
  praise_tags      — JSON object: {"staff": ["super friendly", "remembered my order"], ...}
  employee_mentioned — TEXT: first name if mentioned, NULL otherwise

Only processes reviews that have been classified (classified_at IS NOT NULL)
and haven't had issues extracted yet (complaint_tags IS NULL).
Safe to re-run.

Usage:
    py scripts/extract_issues.py            # extract all pending
    py scripts/extract_issues.py --dry-run  # preview first batch, no writes
    py scripts/extract_issues.py --stats    # show extraction progress

Setup:
    Anthropic API key in .streamlit/secrets.toml or ANTHROPIC_API_KEY env var.
"""

import os, sys, json, time, re
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

BATCH_SIZE  = 15
MODEL       = "claude-haiku-4-5-20251001"
MAX_RETRIES = 3
RETRY_DELAY = 5

SYSTEM_PROMPT = """You extract specific issues and praise from Jersey Mike's Subs customer reviews.

For each review, return complaint_tags and praise_tags grouped by topic.
Only include a topic if the review actually mentions it with a specific detail.

Topics: accuracy, speed, staff, food, cleanliness, online, value

What counts as a specific issue (use 2-5 word phrases, lowercase):
- accuracy:    "wrong toppings", "missing peppers", "got wrong order", "extra charge not asked", "wrong bread type", "missing item", "wrong sauce"
- speed:       "waited 20+ min", "slow drive-thru", "long lunch line", "order not ready", "took forever", "45 min wait"
- staff:       "rude employee", "ignored customers", "attitude problem", "argued with customer", "unhelpful manager"
- food:        "stale bread", "cold meat", "small portions", "soggy bread", "dry meat", "wrong temperature", "old ingredients"
- cleanliness: "dirty tables", "messy bathroom", "trash overflowing", "dirty floors", "sticky counters"
- online:      "doordash wrong order", "app crashed", "pickup not ready", "wrong items delivered", "missing items online"
- value:       "price too high", "portions smaller than before", "not worth the price", "raised prices again"

For praise_tags, same structure — what was specifically good:
- staff:    "super friendly", "remembered my order", "went above and beyond", "great attitude"
- food:     "fresh bread", "perfect portions", "exactly right", "best in area"
- speed:    "fast service", "in and out quick", "ready when promised"
- accuracy: "order perfect", "exactly as requested"

employee_mentioned: first name ONLY if a specific employee is called out (good or bad). null if not.
Examples: "Mike was amazing" → "Mike". "The tall guy" → null. "Manager Sarah" → "Sarah".

Return a JSON array — one object per review, same order as input.
Each object: {"complaint_tags": {}, "praise_tags": {}, "employee_mentioned": null}
Only include topics that have actual specific phrases.
Return ONLY the JSON array, no explanation."""


# ── DB ─────────────────────────────────────────────────────────────────────────

def get_conn():
    import psycopg2
    env_host = os.environ.get("SUPABASE_HOST")
    if env_host:
        try:
            return psycopg2.connect(
                host=env_host,
                port=int(os.environ.get("SUPABASE_PORT","5432")),
                dbname=os.environ.get("SUPABASE_DBNAME","postgres"),
                user=os.environ.get("SUPABASE_USER"),
                password=os.environ.get("SUPABASE_PASSWORD"),
                sslmode="require", connect_timeout=10,
                options="-c statement_timeout=0",
            ), "postgres"
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
                connect_timeout=10, options="-c statement_timeout=0",
            )
            print("Connected to Supabase")
            return conn, "postgres"

    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    return sqlite3.connect(db), "sqlite"


def get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY","").strip()
    if key: return key
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(secrets_path, "rb") as f:
            cfg = tomllib.load(f)
        return cfg.get("anthropic",{}).get("api_key","").strip()
    return ""


# ── Schema migration ───────────────────────────────────────────────────────────

def ensure_columns(conn, dialect):
    cur = conn.cursor()
    if dialect == "postgres":
        for col in ("complaint_tags TEXT", "praise_tags TEXT", "employee_mentioned TEXT"):
            try:
                cur.execute(f"ALTER TABLE store_reviews ADD COLUMN IF NOT EXISTS {col}")
            except Exception:
                pass
    else:
        existing = {r[1] for r in cur.execute("PRAGMA table_info(store_reviews)").fetchall()}
        for col_name, col_def in [
            ("complaint_tags",   "TEXT"),
            ("praise_tags",      "TEXT"),
            ("employee_mentioned","TEXT"),
        ]:
            if col_name not in existing:
                try:
                    cur.execute(f"ALTER TABLE store_reviews ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass
    conn.commit()
    print("✓ Columns ready (complaint_tags, praise_tags, employee_mentioned)")


# ── API call ───────────────────────────────────────────────────────────────────

def _call_api(reviews, api_key):
    import urllib.request, urllib.error

    numbered = "\n\n".join(
        f"[{i+1}] {r['text'][:1200]}"
        for i, r in enumerate(reviews)
    )
    user_msg = f"Extract specific issues from these {len(reviews)} reviews:\n\n{numbered}"

    payload = json.dumps({
        "model":      MODEL,
        "max_tokens": 2048,
        "system":     SYSTEM_PROMPT,
        "messages":   [{"role":"user","content": user_msg}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload, method="POST",
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


def extract_batch(reviews, api_key):
    import urllib.error
    for attempt in range(1, MAX_RETRIES+1):
        try:
            return _call_api(reviews, api_key)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code == 429 or e.code >= 500:
                if attempt < MAX_RETRIES:
                    wait = RETRY_DELAY * attempt
                    print(f"  ⚠️  HTTP {e.code} — retrying in {wait}s…")
                    time.sleep(wait)
                    continue
            raise RuntimeError(f"API error {e.code}: {body}") from e
        except Exception as ex:
            if attempt < MAX_RETRIES:
                print(f"  ⚠️  Error ({ex}) — retrying in {RETRY_DELAY}s…")
                time.sleep(RETRY_DELAY)

    # Fallback: split batch
    if len(reviews) == 1:
        print("  ⚠️  Single review failed — returning empty tags")
        return [{"complaint_tags":{},"praise_tags":{},"employee_mentioned":None}]

    print(f"  ↳ Splitting {len(reviews)} → halves…")
    mid = len(reviews) // 2
    return (
        extract_batch(reviews[:mid], api_key) +
        extract_batch(reviews[mid:], api_key)
    )


def validate_result(r):
    complaint = {}
    praise    = {}
    for topic in ("accuracy","speed","staff","food","cleanliness","online","value"):
        ct = r.get("complaint_tags",{})
        pt = r.get("praise_tags",{})
        if isinstance(ct, dict) and topic in ct:
            complaint[topic] = [str(p).strip().lower() for p in ct[topic] if p][:6]
        if isinstance(pt, dict) and topic in pt:
            praise[topic]    = [str(p).strip().lower() for p in pt[topic] if p][:6]
    emp = r.get("employee_mentioned")
    emp = str(emp).strip() if emp and str(emp).strip().lower() not in ("null","none","") else None
    return complaint, praise, emp


# ── Write back ─────────────────────────────────────────────────────────────────

def write_results(cur, dialect, review_ids, results):
    p   = "%s" if dialect == "postgres" else "?"
    sql = (f"UPDATE store_reviews SET "
           f"complaint_tags={p}, praise_tags={p}, employee_mentioned={p} "
           f"WHERE id={p}")
    batch = []
    for rid, res in zip(review_ids, results):
        try:
            complaint, praise, emp = validate_result(res)
        except Exception as e:
            print(f"  ⚠️  Validation error id={rid}: {e}")
            continue
        batch.append((
            json.dumps(complaint) if complaint else None,
            json.dumps(praise)    if praise    else None,
            emp, rid,
        ))
    if batch:
        cur.executemany(sql, batch)
    return len(batch)


# ── Stats ──────────────────────────────────────────────────────────────────────

def show_stats(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE classified_at IS NOT NULL
                             AND review_text IS NOT NULL)    AS classified,
            COUNT(*) FILTER (WHERE complaint_tags IS NOT NULL) AS extracted,
            COUNT(*) FILTER (WHERE classified_at IS NOT NULL
                             AND review_text IS NOT NULL
                             AND complaint_tags IS NULL)     AS pending
        FROM store_reviews
    """)
    row = cur.fetchone()
    print(f"Classified reviews : {row[0]:,}")
    print(f"  Extracted        : {row[1]:,}")
    print(f"  Pending          : {row[2]:,}")

    if row[1]:
        # Top complaint phrases overall
        cur.execute("""
            SELECT complaint_tags FROM store_reviews
            WHERE complaint_tags IS NOT NULL AND complaint_tags != '{}'
            LIMIT 500
        """)
        from collections import Counter
        phrase_counts = Counter()
        for (raw,) in cur.fetchall():
            try:
                d = json.loads(raw) if raw else {}
                for phrases in d.values():
                    phrase_counts.update(phrases)
            except Exception:
                pass
        if phrase_counts:
            print("\nTop 15 complaint phrases:")
            for phrase, cnt in phrase_counts.most_common(15):
                print(f"  {cnt:3d}×  {phrase}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    args    = set(sys.argv[1:])
    dry_run = "--dry-run" in args

    api_key = get_api_key()
    if not api_key:
        print("❌  No Anthropic API key found.")
        sys.exit(1)

    conn, dialect = get_conn()

    if "--stats" in args:
        show_stats(conn)
        conn.close()
        return

    ensure_columns(conn, dialect)

    cur = conn.cursor()
    cur.execute("""
        SELECT id, review_text
        FROM   store_reviews
        WHERE  classified_at IS NOT NULL
          AND  review_text IS NOT NULL
          AND  TRIM(review_text) != ''
          AND  complaint_tags IS NULL
        ORDER  BY review_date DESC, id
    """)
    pending = cur.fetchall()

    total = len(pending)
    if total == 0:
        print("✓ All classified reviews already have issue extraction.")
        conn.close()
        return

    print(f"=== Issue Extraction  ({MODEL}) ===")
    print(f"Pending: {total:,} reviews  |  Batch size: {BATCH_SIZE}")
    if dry_run:
        print("DRY RUN — no writes\n")

    batches     = [pending[i:i+BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]
    total_saved = 0
    errors      = 0

    for b_idx, batch in enumerate(batches, 1):
        ids   = [r[0] for r in batch]
        texts = [{"text": r[1]} for r in batch]

        prefix = f"[{b_idx:3d}/{len(batches)}]"
        print(f"{prefix} Extracting {len(batch)} reviews… ", end="", flush=True)

        try:
            results = extract_batch(texts, api_key)
            print("✓", end="")
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
                print(f"  Text: {texts[0]['text'][:100]}…")
                print(f"  Result: {json.dumps(results[0], indent=4)}\n")
            break

        time.sleep(0.3)

    conn.close()
    print(f"\n{'─'*50}")
    if dry_run:
        print(f"Dry run — {total:,} reviews pending extraction")
    else:
        print(f"✓ Done — {total_saved:,} reviews extracted  ({errors} batch errors)")
        if errors:
            print("  Re-run to retry failed batches")


if __name__ == "__main__":
    main()
