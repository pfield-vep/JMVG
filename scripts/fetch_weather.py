"""
scripts/fetch_weather.py
========================
Populates two weather tables using the free Open-Meteo historical API
(no API key required):

  weekly_weather   — one row per (week_ending, market) — feeds the weekly
                     SSS correlation charts already in the dashboard.

  daily_weather    — one row per (date, market) — raw daily data for future
                     daily-sales correlation and Y/Y delta analysis.

Run once to backfill all history, then it runs daily via scheduled task:
    py scripts/fetch_weather.py            # full backfill
    py scripts/fetch_weather.py --update   # fast daily update (last 7 days → today)

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
# JM Valley Group markets
MARKET_COORDS = {
    "Los Angeles":               (34.0522, -118.2437),
    "Santa Barbara":             (34.4208, -119.6982),
    "Santa Barbara / San Luis Ob": (35.2828, -120.6596),   # SLO airport
    "San Diego":                 (32.7157, -117.1611),
    "Tampa":                     (27.9506, -82.4572),
}

# BlakeWard benchmark regions — representative major metros per state/region
# Keys match the `region` codes in weekly_benchmark (FL, KC, KS, MO, NC, NY, SC)
BENCHMARK_COORDS = {
    "FL": (27.9506, -82.4572),   # Tampa, FL
    "KC": (39.0997, -94.5786),   # Kansas City, MO
    "KS": (37.6872, -97.3301),   # Wichita, KS
    "MO": (38.6270, -90.1994),   # St. Louis, MO
    "NC": (35.2271, -80.8431),   # Charlotte, NC
    "NY": (40.7128, -74.0060),   # New York City, NY
    "SC": (34.0007, -81.0348),   # Columbia, SC
}

# ── DB connection ─────────────────────────────────────────────────────────────
def get_conn():
    import psycopg2

    # 1. Environment variables (GitHub Actions / CI)
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
            )
            print("Connected to Supabase via environment variables")
            return conn, "postgres"
        except Exception as e:
            print(f"⚠️  Supabase (env) failed: {e}")

    # 2. .streamlit/secrets.toml (local / Streamlit Cloud)
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

    # ── Weekly scope: all weeks across all sales + benchmark tables ───────────
    cur.execute("""
        SELECT DISTINCT week_ending FROM weekly_store_history
        UNION
        SELECT DISTINCT week_ending FROM weekly_sales
        UNION
        SELECT DISTINCT week_ending FROM weekly_benchmark
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
        daily_end        = date.today()   # always fetch through today

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

    # ── Benchmark regions (weekly_weather only, no daily needed) ─────────────
    print("\nFetching benchmark region weather (FL, KC, KS, MO, NC, NY, SC)…")
    cur.execute("SELECT DISTINCT week_ending FROM weekly_benchmark ORDER BY week_ending")
    bmark_weeks = [r[0] for r in cur.fetchall()]
    cur.execute("SELECT DISTINCT week_ending, market FROM weekly_weather")
    weekly_done_now = set(cur.fetchall())

    for region, (lat, lon) in BENCHMARK_COORDS.items():
        missing = [w for w in bmark_weeks if (w, region) not in weekly_done_now]
        if not missing:
            print(f"  {region}: up to date ✓")
            continue
        earliest = (date.fromisoformat(missing[0]) - timedelta(days=7)).isoformat()
        latest   = date.fromisoformat(missing[-1]).isoformat()
        print(f"  {region}: fetching {earliest} → {latest} ({len(missing)} weeks)…")
        try:
            data = fetch_open_meteo(lat, lon, earliest, latest)
        except Exception as e:
            print(f"    ⚠️  API error for {region}: {e}")
            time.sleep(2)
            continue
        for wk in missing:
            row = aggregate_to_weekly(data, wk)
            if row:
                upsert_weekly(cur, dialect, wk, region, row)
                weekly_inserted += 1
        conn.commit()
        time.sleep(0.4)

    print(f"\nDone.")
    print(f"  Weekly rows written : {weekly_inserted}")
    print(f"  Daily  rows written : {daily_inserted}")
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# FAST DAILY UPDATE  (runs via scheduled task every morning)
# ══════════════════════════════════════════════════════════════════════════════

def update_to_today():
    """
    Lightweight daily refresh — fetches the last 10 days through today for
    every market.  Upserts both daily_weather and weekly_weather rows.
    Safe to run multiple times (upserts are idempotent).
    """
    conn, dialect = get_conn()
    create_tables(conn, dialect)
    cur = conn.cursor()

    today     = date.today()
    fetch_end = today.isoformat()

    # Find the furthest back we need to go per market (last covered date - 10 days)
    cur.execute("SELECT market, MAX(date) FROM daily_weather GROUP BY market")
    market_max = {r[0]: r[1] for r in cur.fetchall()}

    total_daily  = 0
    total_weekly = 0

    for market, (lat, lon) in MARKET_COORDS.items():
        if market in market_max:
            last_covered = date.fromisoformat(market_max[market])
            fetch_start  = (last_covered - timedelta(days=10)).isoformat()
        else:
            # No data yet for this market — go back 14 months
            fetch_start = (today - timedelta(days=425)).isoformat()

        print(f"  {market}: {fetch_start} → {fetch_end}")
        try:
            data = fetch_open_meteo(lat, lon, fetch_start, fetch_end)
        except Exception as e:
            print(f"    ⚠️  API error: {e}")
            time.sleep(2)
            continue

        # Daily rows
        daily_rows = build_daily_rows(data, market)
        upsert_daily_batch(cur, dialect, daily_rows)
        total_daily += len(daily_rows)

        # Weekly rows — derive week_ending dates covered by this fetch window
        start_d = date.fromisoformat(fetch_start)
        end_d   = today
        # Walk forward to find Sundays (week_ending = Sunday)
        d = start_d
        while d <= end_d:
            if d.weekday() == 6:   # Sunday
                row = aggregate_to_weekly(data, d.isoformat())
                if row:
                    upsert_weekly(cur, dialect, d.isoformat(), market, row)
                    total_weekly += 1
            d += timedelta(days=1)

        conn.commit()
        time.sleep(0.4)

    # ── Benchmark regions: update weekly_weather for last 2 weeks ────────────
    print("\nUpdating benchmark region weekly weather…")
    for region, (lat, lon) in BENCHMARK_COORDS.items():
        fetch_start_b = (today - timedelta(days=14)).isoformat()
        try:
            data = fetch_open_meteo(lat, lon, fetch_start_b, fetch_end)
        except Exception as e:
            print(f"  ⚠️  {region}: {e}")
            time.sleep(2)
            continue
        d = today - timedelta(days=14)
        while d <= today:
            if d.weekday() == 6:   # Sunday = week_ending
                row = aggregate_to_weekly(data, d.isoformat())
                if row:
                    upsert_weekly(cur, dialect, d.isoformat(), region, row)
                    total_weekly += 1
            d += timedelta(days=1)
        conn.commit()
        time.sleep(0.3)

    print(f"\nUpdate complete — {total_daily} daily rows, {total_weekly} weekly rows written.")
    conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# PER-STORE WEATHER  (Option A — exact lat/lon per store, hourly daypart data)
# ══════════════════════════════════════════════════════════════════════════════

CREATE_STORE_WEATHER_PG = """
CREATE TABLE IF NOT EXISTS store_daily_weather (
    id               SERIAL  PRIMARY KEY,
    date             DATE    NOT NULL,
    store_id         TEXT    NOT NULL,
    -- Daily aggregates
    temp_max_f       REAL,
    temp_min_f       REAL,
    avg_temp_f       REAL,
    precip_in        REAL,
    is_rainy         INTEGER,          -- 1 if precip_in >= 0.10
    is_cold          INTEGER,          -- 1 if temp_max_f < 60
    temp_spread_f    REAL,             -- max-min (fog proxy: spread < 12 = likely overcast)
    -- Lunch window  11 AM – 2 PM local
    lunch_temp_f     REAL,
    lunch_precip_in  REAL,
    lunch_is_rainy   INTEGER,          -- 1 if lunch_precip_in >= 0.05
    -- Dinner window 5 PM – 8 PM local
    dinner_temp_f    REAL,
    dinner_precip_in REAL,
    dinner_is_rainy  INTEGER,          -- 1 if dinner_precip_in >= 0.05
    UNIQUE (date, store_id)
)"""

CREATE_STORE_WEATHER_SQLITE = CREATE_STORE_WEATHER_PG.replace(
    "SERIAL  PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT"
)


def create_store_weather_table(conn, dialect):
    cur = conn.cursor()
    cur.execute(CREATE_STORE_WEATHER_PG if dialect == "postgres"
                else CREATE_STORE_WEATHER_SQLITE)
    conn.commit()
    print("store_daily_weather table ready")


def fetch_open_meteo_hourly(lat, lon, start_date: str, end_date: str) -> dict:
    """Fetch hourly temperature + precipitation from Open-Meteo archive (free)."""
    params = urlencode({
        "latitude":           lat,
        "longitude":          lon,
        "start_date":         start_date,
        "end_date":           end_date,
        "hourly":             "temperature_2m,precipitation",
        "temperature_unit":   "fahrenheit",
        "precipitation_unit": "inch",
        "timezone":           "America/Los_Angeles",
    })
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def process_store_hourly(data: dict, store_id: str) -> list:
    """
    Convert Open-Meteo hourly response into store_daily_weather rows.
    Computes daily aggregates and lunch (11am–2pm) / dinner (5pm–8pm) metrics.
    """
    from collections import defaultdict
    from datetime import datetime as dt

    times  = data["hourly"]["time"]
    temps  = data["hourly"]["temperature_2m"]
    precips = data["hourly"]["precipitation"]

    daily = defaultdict(lambda: {
        "t": [], "p": [],
        "lt": [], "lp": [],   # lunch
        "dt_": [], "dp": [],  # dinner
    })

    for t_str, temp, precip in zip(times, temps, precips):
        d = dt.strptime(t_str, "%Y-%m-%dT%H:%M")
        day  = d.strftime("%Y-%m-%d")
        hour = d.hour

        if temp   is not None: daily[day]["t"].append(temp)
        if precip is not None: daily[day]["p"].append(precip)

        if hour in (11, 12, 13):                      # 11 AM – 2 PM
            if temp   is not None: daily[day]["lt"].append(temp)
            if precip is not None: daily[day]["lp"].append(precip)

        if hour in (17, 18, 19):                      # 5 PM – 8 PM
            if temp   is not None: daily[day]["dt_"].append(temp)
            if precip is not None: daily[day]["dp"].append(precip)

    rows = []
    for day, d in sorted(daily.items()):
        t_max = max(d["t"]) if d["t"] else None
        t_min = min(d["t"]) if d["t"] else None
        t_avg = sum(d["t"]) / len(d["t"]) if d["t"] else None
        prec  = sum(d["p"]) if d["p"] else 0.0
        spread = round(t_max - t_min, 1) if t_max and t_min else None

        l_t = max(d["lt"]) if d["lt"] else None
        l_p = round(sum(d["lp"]), 3) if d["lp"] else 0.0
        dn_t = max(d["dt_"]) if d["dt_"] else None
        dn_p = round(sum(d["dp"]), 3) if d["dp"] else 0.0

        rows.append({
            "date":             day,
            "store_id":         store_id,
            "temp_max_f":       round(t_max, 1) if t_max else None,
            "temp_min_f":       round(t_min, 1) if t_min else None,
            "avg_temp_f":       round(t_avg, 1) if t_avg else None,
            "precip_in":        round(prec, 3),
            "is_rainy":         1 if prec  >= 0.10 else 0,
            "is_cold":          1 if t_max and t_max < 60 else 0,
            "temp_spread_f":    spread,
            "lunch_temp_f":     round(l_t, 1) if l_t else None,
            "lunch_precip_in":  l_p,
            "lunch_is_rainy":   1 if l_p  >= 0.05 else 0,
            "dinner_temp_f":    round(dn_t, 1) if dn_t else None,
            "dinner_precip_in": dn_p,
            "dinner_is_rainy":  1 if dn_p >= 0.05 else 0,
        })
    return rows


def upsert_store_weather(cur, dialect, rows):
    if not rows:
        return 0
    p = "%s" if dialect == "postgres" else "?"
    COLS = [
        "date","store_id","temp_max_f","temp_min_f","avg_temp_f",
        "precip_in","is_rainy","is_cold","temp_spread_f",
        "lunch_temp_f","lunch_precip_in","lunch_is_rainy",
        "dinner_temp_f","dinner_precip_in","dinner_is_rainy",
    ]
    ph = ",".join([p] * len(COLS))
    col_list = ",".join(COLS)
    if dialect == "postgres":
        update_set = ",".join(f"{c}=EXCLUDED.{c}" for c in COLS
                              if c not in ("date","store_id"))
        sql = (f"INSERT INTO store_daily_weather ({col_list}) VALUES ({ph}) "
               f"ON CONFLICT (date,store_id) DO UPDATE SET {update_set}")
    else:
        sql = f"INSERT OR REPLACE INTO store_daily_weather ({col_list}) VALUES ({ph})"
    cur.executemany(sql, [tuple(r[c] for c in COLS) for r in rows])
    return len(rows)


def get_store_locations(conn, dialect):
    """Return list of (store_id, lat, lon) from the stores table."""
    cur = conn.cursor()
    cur.execute("SELECT store_id, lat, lon FROM stores WHERE lat IS NOT NULL AND lon IS NOT NULL")
    return [(str(r[0]), float(r[1]), float(r[2])) for r in cur.fetchall()]


def backfill_store_weather():
    """
    Full historical backfill for store_daily_weather.
    Fetches hourly data from Jan 1 2024 → today for every store.
    One API call per store (Open-Meteo returns the whole range in one shot).
    """
    conn, dialect = get_conn()
    create_store_weather_table(conn, dialect)
    cur = conn.cursor()

    stores = get_store_locations(conn, dialect)
    start  = "2024-01-01"
    end    = date.today().isoformat()
    total  = 0

    print(f"Backfilling store weather: {len(stores)} stores, {start} → {end}")
    for store_id, lat, lon in stores:
        print(f"  {store_id} ({lat:.4f}, {lon:.4f})…")
        try:
            data = fetch_open_meteo_hourly(lat, lon, start, end)
            rows = process_store_hourly(data, store_id)
            n = upsert_store_weather(cur, dialect, rows)
            conn.commit()
            total += n
            print(f"    ✓ {n} days")
        except Exception as e:
            print(f"    ⚠️  {e}")
            conn.rollback()
        time.sleep(0.3)

    conn.close()
    print(f"\nDone — {total:,} store-day rows upserted.")


def update_store_weather():
    """
    Fast daily update: fetch last 10 days for every store.
    Runs automatically in the GitHub Actions weather workflow.
    """
    conn, dialect = get_conn()
    create_store_weather_table(conn, dialect)
    cur = conn.cursor()

    stores = get_store_locations(conn, dialect)
    end    = date.today().isoformat()
    start  = (date.today() - timedelta(days=10)).isoformat()
    total  = 0

    print(f"Updating store weather ({start} → {end}) for {len(stores)} stores…")
    for store_id, lat, lon in stores:
        try:
            data = fetch_open_meteo_hourly(lat, lon, start, end)
            rows = process_store_hourly(data, store_id)
            n = upsert_store_weather(cur, dialect, rows)
            conn.commit()
            total += n
        except Exception as e:
            print(f"  ⚠️  {store_id}: {e}")
            conn.rollback()
        time.sleep(0.2)

    conn.close()
    print(f"Store weather update done — {total:,} rows upserted.")


if __name__ == "__main__":
    import sys as _sys
    args = set(_sys.argv[1:])

    if "--backfill-stores" in args:
        print("=== Store Weather Full Backfill ===")
        backfill_store_weather()
    elif "--update" in args:
        print("=== Weather Daily Update ===")
        update_to_today()
        update_store_weather()   # also update per-store weather
    elif "--update-stores" in args:
        print("=== Store Weather Daily Update ===")
        update_store_weather()
    else:
        print("=== Weather Full Backfill ===")
        backfill()
        backfill_store_weather()
