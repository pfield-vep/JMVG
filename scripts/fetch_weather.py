"""
scripts/fetch_weather.py
========================
Populates two weather tables using the free Open-Meteo historical API
(no API key required):

  weekly_weather   — one row per (week_ending, market) — feeds the weekly
                     SSS correlation charts already in the dashboard.

  daily_weather    — one row per (date, market) — raw daily data for future
                     daily-sales correlation and Y/Y delta analysis.

Run once to backfill all history, then weekly to stay current:
    py scripts/fetch_weather.py

Works against both SQLite (local) and Supabase/Postgres (production).
Supabase credentials are read from .streamlit/secrets.toml if present.
"""

import os, sys, time, json
from datetime import date, timedelta
from urllib.request import urlopen
from urllib.parse import urlencode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

# ── Market → GPS coordinates ──────────────────────────────────────────────────
MARKET_COORDS = {
    "Los Angeles":               (34.0522, -118.2437),
    "Santa Barbara":             (34.4208, -119.6982),
    "Santa Barbara / San Luis Ob": (35.2828, -120.6596),   # SLO airport
    "San Diego":                 (32.7157, -117.1611),
}

# ── DB connection ─────────────────────────────────────────────────────────────
def get_conn():
    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if os.path.exists(secrets_path):
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        with open(secrets_path, "rb") as f:
            cfg = tomllib.load(f)
        if "supabase" in cfg:
            try:
                import psycopg2
                s = cfg["supabase"]
                conn = psycopg2.connect(
                    host=s["host"], port=int(s["port"]),
                    dbname=s["dbname"], user=s["user"],
                    password=s["password"], sslmode="require"
                )
                print("Connected to Supabase / Postgres")
                return conn, "postgres"
            except Exception as e:
                print(f"⚠️  Supabase connection failed ({e})")
                print("   Falling back to local SQLite database…")
    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"


# ══════════════════════════════════════════════════════════════════════════════
# TABLE DEFINITIONS
# ══════════════════════════════════════════════════════════════════════════════

# ── weekly_weather ────────────────────────────────────────────────────────────
WEEKLY_SQLITE = """
CREATE TABLE IF NOT EXISTS weekly_weather (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    week_ending     TEXT    NOT NULL,
    market          TEXT    NOT NULL,
    avg_temp_f      REAL,
    max_temp_f      REAL,
    min_temp_f      REAL,
    total_precip_in REAL,
    rainy_days      INTEGER,
    cold_days       INTEGER,
    UNIQUE (week_ending, market)
)"""

WEEKLY_PG = """
CREATE TABLE IF NOT EXISTS weekly_weather (
    id              SERIAL  PRIMARY KEY,
    week_ending     TEXT    NOT NULL,
    market          TEXT    NOT NULL,
    avg_temp_f      REAL,
    max_temp_f      REAL,
    min_temp_f      REAL,
    total_precip_in REAL,
    rainy_days      INTEGER,
    cold_days       INTEGER,
    UNIQUE (week_ending, market)
)"""

# ── daily_weather ─────────────────────────────────────────────────────────────
# One row per calendar day per market.
# is_rainy  = 1 if precip_in >= 0.1 (measurable rain)
# is_cold   = 1 if temp_max_f < 60  (cold-day threshold)
# Used for:
#   • future daily-sales correlation
#   • Y/Y weather delta (same date 364 days prior, preserving weekday)
DAILY_SQLITE = """
CREATE TABLE IF NOT EXISTS daily_weather (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT    NOT NULL,
    market      TEXT    NOT NULL,
    temp_max_f  REAL,
    temp_min_f  REAL,
    avg_temp_f  REAL,
    precip_in   REAL,
    is_rainy    INTEGER,
    is_cold     INTEGER,
    UNIQUE (date, market)
)"""

DAILY_PG = """
CREATE TABLE IF NOT EXISTS daily_weather (
    id          SERIAL  PRIMARY KEY,
    date        TEXT    NOT NULL,
    market      TEXT    NOT NULL,
    temp_max_f  REAL,
    temp_min_f  REAL,
    avg_temp_f  REAL,
    precip_in   REAL,
    is_rainy    INTEGER,
    is_cold     INTEGER,
    UNIQUE (date, market)
)"""


def create_tables(conn, dialect):
    cur = conn.cursor()
    if dialect == "postgres":
        # weekly_weather: keep IF NOT EXISTS so existing data survives
        cur.execute(WEEKLY_PG)
        cur.execute(DAILY_PG)
    else:
        cur.execute(WEEKLY_SQLITE)
        cur.execute(DAILY_SQLITE)
    conn.commit()
    print("weekly_weather + daily_weather tables ready")


# ══════════════════════════════════════════════════════════════════════════════
# OPEN-METEO API
# ══════════════════════════════════════════════════════════════════════════════

def fetch_open_meteo(lat, lon, start_date: str, end_date: str) -> dict:
    """
    Returns daily arrays: time, temperature_2m_max, temperature_2m_min,
    precipitation_sum.  Uses the free archive endpoint — no key needed.
    """
    params = urlencode({
        "latitude":           lat,
        "longitude":          lon,
        "start_date":         start_date,
        "end_date":           end_date,
        "daily":              "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "temperature_unit":   "fahrenheit",
        "precipitation_unit": "inch",
        "timezone":           "America/Los_Angeles",
    })
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


# ══════════════════════════════════════════════════════════════════════════════
# DAILY ROW BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_daily_rows(daily_data: dict, market: str) -> list:
    """
    Convert raw Open-Meteo response into a list of daily_weather dicts.
    One dict per calendar day in the response.
    """
    times  = daily_data["daily"]["time"]
    t_max  = daily_data["daily"]["temperature_2m_max"]
    t_min  = daily_data["daily"]["temperature_2m_min"]
    precip = daily_data["daily"]["precipitation_sum"]

    rows = []
    for dt, hi, lo, pr in zip(times, t_max, t_min, precip):
        if hi is None and lo is None:
            continue
        avg = round((hi + lo) / 2, 1) if hi is not None and lo is not None else None
        pr  = pr if pr is not None else 0.0
        rows.append({
            "date":       dt,
            "market":     market,
            "temp_max_f": round(hi, 1) if hi is not None else None,
            "temp_min_f": round(lo, 1) if lo is not None else None,
            "avg_temp_f": avg,
            "precip_in":  round(pr, 2),
            "is_rainy":   1 if pr >= 0.1 else 0,
            "is_cold":    1 if (hi is not None and hi < 60) else 0,
        })
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# WEEKLY AGGREGATION (unchanged logic)
# ══════════════════════════════════════════════════════════════════════════════

def aggregate_to_weekly(daily_data: dict, week_ending: str) -> dict:
    """Aggregate a 7-day window ending on week_ending into one weekly row."""
    we     = date.fromisoformat(week_ending)
    ws_str = (we - timedelta(days=6)).isoformat()

    times  = daily_data["daily"]["time"]
    t_max  = daily_data["daily"]["temperature_2m_max"]
    t_min  = daily_data["daily"]["temperature_2m_min"]
    precip = daily_data["daily"]["precipitation_sum"]

    days = [(t, h, l, p) for t, h, l, p in zip(times, t_max, t_min, precip)
            if ws_str <= t <= week_ending]

    if not days:
        return None

    highs = [h for _, h, _, _ in days if h is not None]
    lows  = [l for _, _, l, _ in days if l is not None]
    precs = [p for _, _, _, p in days if p is not None]

    avg_temp = round(sum((h + l) / 2 for h, l in zip(highs, lows)) / len(highs), 1) if highs else None
    max_temp = round(max(highs), 1) if highs else None
    min_temp = round(min(lows),  1) if lows  else None
    total_p  = round(sum(precs), 2) if precs else 0.0
    rainy    = sum(1 for p in precs if p >= 0.1)
    cold     = sum(1 for h in highs if h < 60)

    return {
        "avg_temp_f":      avg_temp,
        "max_temp_f":      max_temp,
        "min_temp_f":      min_temp,
        "total_precip_in": total_p,
        "rainy_days":      rainy,
        "cold_days":       cold,
    }


# ══════════════════════════════════════════════════════════════════════════════
# UPSERT HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def upsert_weekly(cur, dialect, week_ending, market, row):
    p = "%s" if dialect == "postgres" else "?"
    if dialect == "postgres":
        sql = f"""
            INSERT INTO weekly_weather
                (week_ending, market, avg_temp_f, max_temp_f, min_temp_f,
                 total_precip_in, rainy_days, cold_days)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p})
            ON CONFLICT (week_ending, market) DO UPDATE SET
                avg_temp_f      = EXCLUDED.avg_temp_f,
                max_temp_f      = EXCLUDED.max_temp_f,
                min_temp_f      = EXCLUDED.min_temp_f,
                total_precip_in = EXCLUDED.total_precip_in,
                rainy_days      = EXCLUDED.rainy_days,
                cold_days       = EXCLUDED.cold_days
        """
    else:
        sql = f"""
            INSERT OR REPLACE INTO weekly_weather
                (week_ending, market, avg_temp_f, max_temp_f, min_temp_f,
                 total_precip_in, rainy_days, cold_days)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p})
        """
    cur.execute(sql, (
        week_ending, market,
        row["avg_temp_f"], row["max_temp_f"], row["min_temp_f"],
        row["total_precip_in"], row["rainy_days"], row["cold_days"],
    ))


def upsert_daily_batch(cur, dialect, rows):
    if not rows:
        return
    p = "%s" if dialect == "postgres" else "?"
    if dialect == "postgres":
        sql = f"""
            INSERT INTO daily_weather
                (date, market, temp_max_f, temp_min_f, avg_temp_f,
                 precip_in, is_rainy, is_cold)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p})
            ON CONFLICT (date, market) DO UPDATE SET
                temp_max_f = EXCLUDED.temp_max_f,
                temp_min_f = EXCLUDED.temp_min_f,
                avg_temp_f = EXCLUDED.avg_temp_f,
                precip_in  = EXCLUDED.precip_in,
                is_rainy   = EXCLUDED.is_rainy,
                is_cold    = EXCLUDED.is_cold
        """
    else:
        sql = f"""
            INSERT OR REPLACE INTO daily_weather
                (date, market, temp_max_f, temp_min_f, avg_temp_f,
                 precip_in, is_rainy, is_cold)
            VALUES ({p},{p},{p},{p},{p},{p},{p},{p})
        """
    for r in rows:
        cur.execute(sql, (
            r["date"], r["market"], r["temp_max_f"], r["temp_min_f"],
            r["avg_temp_f"], r["precip_in"], r["is_rainy"], r["is_cold"],
        ))


# ══════════════════════════════════════════════════════════════════════════════
# MAIN BACKFILL
# ══════════════════════════════════════════════════════════════════════════════

def backfill():
    conn, dialect = get_conn()
    create_tables(conn, dialect)
    cur = conn.cursor()

    # ── Weekly scope: all weeks present in sales tables ───────────────────────
    cur.execute("""
        SELECT DISTINCT week_ending FROM weekly_store_history
        UNION
        SELECT DISTINCT week_ending FROM weekly_sales
        ORDER BY week_ending
    """)
    all_weeks = [r[0] for r in cur.fetchall()]

    if not all_weeks:
        print("No weeks found in database — nothing to backfill.")
        conn.close()
        return

    # Already-fetched weekly rows (skip)
    cur.execute("SELECT DISTINCT week_ending, market FROM weekly_weather")
    weekly_done = set(cur.fetchall())

    # Already-fetched daily rows: just track which (market, earliest_date) pairs exist
    # to avoid re-fetching huge ranges unnecessarily
    cur.execute("SELECT market, MIN(date), MAX(date) FROM daily_weather GROUP BY market")
    daily_coverage = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

    print(f"Weekly scope: {len(all_weeks)} weeks  |  Weekly already done: {len(weekly_done)}")

    weekly_inserted = 0
    daily_inserted  = 0

    for market, (lat, lon) in MARKET_COORDS.items():
        missing_weekly = [w for w in all_weeks if (w, market) not in weekly_done]

        # For daily: fetch from 1 year before first sales week (for Y/Y delta)
        # through the last sales week.  If already covered, only fetch new dates.
        first_sales_week = date.fromisoformat(all_weeks[0])
        last_sales_week  = date.fromisoformat(all_weeks[-1])
        daily_start      = first_sales_week - timedelta(days=365)  # 1 yr lookback
        daily_end        = last_sales_week

        if market in daily_coverage:
            cov_min, cov_max = daily_coverage[market]
            # Only need to fetch dates not yet covered
            # (we refetch a small buffer to catch any gaps)
            daily_start = date.fromisoformat(cov_max) - timedelta(days=7)

        if not missing_weekly and market in daily_coverage:
            cov_min, cov_max = daily_coverage[market]
            if date.fromisoformat(cov_max) >= daily_end:
                print(f"  {market}: fully up to date ✓")
                continue

        fetch_start = min(daily_start, date.fromisoformat(missing_weekly[0]) if missing_weekly
                          else daily_start).isoformat()
        fetch_end   = daily_end.isoformat()

        print(f"  {market}: fetching {fetch_start} → {fetch_end}…")

        try:
            data = fetch_open_meteo(lat, lon, fetch_start, fetch_end)
        except Exception as e:
            print(f"    ⚠️  API error for {market}: {e}")
            time.sleep(2)
            continue

        # ── Write daily rows ──────────────────────────────────────────────────
        daily_rows = build_daily_rows(data, market)
        upsert_daily_batch(cur, dialect, daily_rows)
        daily_inserted += len(daily_rows)

        # ── Write weekly rows ─────────────────────────────────────────────────
        for wk in missing_weekly:
            row = aggregate_to_weekly(data, wk)
            if row is None:
                continue
            upsert_weekly(cur, dialect, wk, market, row)
            weekly_inserted += 1

        conn.commit()
        time.sleep(0.5)   # be polite to the free API

    print(f"\nDone.")
    print(f"  Weekly rows written : {weekly_inserted}")
    print(f"  Daily  rows written : {daily_inserted}")
    conn.close()


if __name__ == "__main__":
    backfill()
