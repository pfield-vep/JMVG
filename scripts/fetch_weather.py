"""
scripts/fetch_weather.py
========================
Backfills (and incrementally updates) the weekly_weather table using the
free Open-Meteo historical-weather API — no API key required.

Run once to backfill all history, then weekly to stay current:
    python scripts/fetch_weather.py

Works against both SQLite (local) and Supabase/Postgres (production).
Supabase credentials are read from .streamlit/secrets.toml if present.
"""

import os, sys, time, json
from datetime import date, timedelta
from urllib.request import urlopen
from urllib.parse import urlencode

# ── repo root so dashboard imports work ──────────────────────────────────────
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
            import psycopg2
            s = cfg["supabase"]
            conn = psycopg2.connect(
                host=s["host"], port=int(s["port"]),
                dbname=s["dbname"], user=s["user"],
                password=s["password"], sslmode="require"
            )
            print("Connected to Supabase / Postgres")
            return conn, "postgres"
    import sqlite3
    db = os.path.join(ROOT, "jerseymikes.db")
    print(f"Connected to SQLite: {db}")
    return sqlite3.connect(db), "sqlite"


# ── Create weekly_weather table if absent ────────────────────────────────────
CREATE_SQL_SQLITE = """
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
)
"""

CREATE_SQL_PG = """
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
)
"""

def create_table(conn, dialect):
    cur = conn.cursor()
    cur.execute(CREATE_SQL_PG if dialect == "postgres" else CREATE_SQL_SQLITE)
    conn.commit()
    print("weekly_weather table ready")


# ── Open-Meteo fetch ─────────────────────────────────────────────────────────
def fetch_open_meteo(lat, lon, start_date: str, end_date: str) -> dict:
    """Returns daily arrays: time, temperature_2m_max, temperature_2m_min, precipitation_sum."""
    params = urlencode({
        "latitude":         lat,
        "longitude":        lon,
        "start_date":       start_date,
        "end_date":         end_date,
        "daily":            "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "timezone":         "America/Los_Angeles",
    })
    url = f"https://archive-api.open-meteo.com/v1/archive?{params}"
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read())


def aggregate_to_weekly(daily_data: dict, week_ending: str) -> dict:
    """Aggregate a 7-day daily window ending on week_ending into one row."""
    we = date.fromisoformat(week_ending)
    ws = we - timedelta(days=6)
    ws_str = ws.isoformat()

    times  = daily_data["daily"]["time"]
    t_max  = daily_data["daily"]["temperature_2m_max"]
    t_min  = daily_data["daily"]["temperature_2m_min"]
    precip = daily_data["daily"]["precipitation_sum"]

    days = [(t, h, l, p) for t, h, l, p in zip(times, t_max, t_min, precip)
            if ws_str <= t <= week_ending]

    if not days:
        return None

    highs  = [h for _, h, _, _ in days if h is not None]
    lows   = [l for _, _, l, _ in days if l is not None]
    precs  = [p for _, _, _, p in days if p is not None]

    avg_temp = round(sum((h + l) / 2 for h, l in zip(highs, lows)) / len(highs), 1) if highs else None
    max_temp = round(max(highs), 1) if highs else None
    min_temp = round(min(lows), 1)  if lows  else None
    total_p  = round(sum(precs), 2) if precs else 0.0
    rainy    = sum(1 for p in precs if p >= 0.1)   # days with ≥ 0.1 in rain
    cold     = sum(1 for h in highs if h < 60)      # days max temp below 60°F

    return {
        "avg_temp_f":      avg_temp,
        "max_temp_f":      max_temp,
        "min_temp_f":      min_temp,
        "total_precip_in": total_p,
        "rainy_days":      rainy,
        "cold_days":       cold,
    }


# ── Main backfill logic ───────────────────────────────────────────────────────
def backfill():
    conn, dialect = get_conn()
    create_table(conn, dialect)
    cur = conn.cursor()

    # Get all week_endings from both history tables
    cur.execute("""
        SELECT DISTINCT week_ending FROM weekly_store_history
        UNION
        SELECT DISTINCT week_ending FROM weekly_sales
        ORDER BY week_ending
    """)
    all_weeks = [r[0] for r in cur.fetchall()]

    if not all_weeks:
        print("No weeks found in database — nothing to backfill.")
        return

    # Find weeks already fetched (skip them)
    cur.execute("SELECT DISTINCT week_ending, market FROM weekly_weather")
    already = set(cur.fetchall())

    print(f"Total weeks in DB: {len(all_weeks)}  |  Already fetched: {len(already)}")

    p = "%s" if dialect == "postgres" else "?"
    upsert = f"""
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
    """ if dialect == "postgres" else f"""
        INSERT OR REPLACE INTO weekly_weather
            (week_ending, market, avg_temp_f, max_temp_f, min_temp_f,
             total_precip_in, rainy_days, cold_days)
        VALUES ({p},{p},{p},{p},{p},{p},{p},{p})
    """

    inserted = 0
    for market, (lat, lon) in MARKET_COORDS.items():
        missing = [w for w in all_weeks if (w, market) not in already]
        if not missing:
            print(f"  {market}: already up to date ✓")
            continue

        print(f"  {market}: fetching {len(missing)} weeks ({missing[0]} → {missing[-1]})…")

        # Fetch the full range in one API call
        try:
            data = fetch_open_meteo(lat, lon, missing[0], missing[-1])
        except Exception as e:
            print(f"    ⚠️  API error for {market}: {e}")
            time.sleep(2)
            continue

        for wk in missing:
            row = aggregate_to_weekly(data, wk)
            if row is None:
                continue
            cur.execute(upsert, (
                wk, market,
                row["avg_temp_f"], row["max_temp_f"], row["min_temp_f"],
                row["total_precip_in"], row["rainy_days"], row["cold_days"],
            ))
            inserted += 1

        conn.commit()
        time.sleep(0.5)   # be polite to the free API

    print(f"\nDone — {inserted} new rows written to weekly_weather.")
    conn.close()


if __name__ == "__main__":
    backfill()
