"""
scripts/delete_partial_day.py
=============================
Deletes a target date from daily_sales AND hourly_sales in Supabase.

Used when an upstream export accidentally includes a same-day partial row
(e.g. the Vantage Point email ran before the day was actually complete)
and that row has already landed in the dashboard DB.

Usage:
    py scripts/delete_partial_day.py                # defaults to today (PT)
    py scripts/delete_partial_day.py 2026-05-22     # specific date
    py scripts/delete_partial_day.py --dry-run      # show counts only, no delete

Connects via .streamlit/secrets.toml.  Prints row counts before and after
so you can confirm what was removed.
"""
import os, sys, argparse
from datetime import date, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)


def get_conn():
    import psycopg2

    env_host = os.environ.get("SUPABASE_HOST")
    if env_host:
        return psycopg2.connect(
            host=env_host,
            port=int(os.environ.get("SUPABASE_PORT", "5432")),
            dbname=os.environ.get("SUPABASE_DBNAME", "postgres"),
            user=os.environ.get("SUPABASE_USER"),
            password=os.environ.get("SUPABASE_PASSWORD"),
            sslmode="require",
        )

    secrets_path = os.path.join(ROOT, ".streamlit", "secrets.toml")
    if not os.path.exists(secrets_path):
        raise SystemExit("secrets.toml not found — need Supabase credentials.")
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib
    with open(secrets_path, "rb") as f:
        cfg = tomllib.load(f)
    s = cfg["supabase"]
    return psycopg2.connect(
        host=s["host"], port=int(s["port"]),
        dbname=s["dbname"], user=s["user"],
        password=s["password"], sslmode="require",
    )


def today_pt() -> date:
    """Today in America/Los_Angeles. Stores are CA-based; PT defines 'today'."""
    try:
        from zoneinfo import ZoneInfo
    except ImportError:
        from backports.zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Los_Angeles")).date()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target_date", nargs="?", default=None,
                    help="Date to delete (YYYY-MM-DD). Defaults to today in Pacific time.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Show row counts but don't delete.")
    args = ap.parse_args()

    if args.target_date:
        try:
            tgt = datetime.strptime(args.target_date, "%Y-%m-%d").date()
        except ValueError:
            raise SystemExit(f"Bad date format: {args.target_date}. Use YYYY-MM-DD.")
    else:
        tgt = today_pt()
        print(f"No date passed — defaulting to today (PT): {tgt}")

    print(f"Target date: {tgt}")
    print(f"Mode       : {'DRY RUN — no changes' if args.dry_run else 'LIVE DELETE'}")
    print()

    conn = get_conn()
    cur = conn.cursor()

    # Inspect what's there
    print(f"Rows currently dated {tgt}:")
    for table in ("daily_sales", "hourly_sales"):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE sale_date = %s", (tgt,))
            n = cur.fetchone()[0]
            print(f"  {table}: {n:,}")
        except Exception as e:
            conn.rollback()
            print(f"  {table}: query failed — {e}")

    if args.dry_run:
        conn.close()
        print("\nDry run — no rows deleted.")
        return

    confirm = input(f"\nDelete all rows for {tgt} from daily_sales and hourly_sales? [y/N] ").strip().lower()
    if confirm not in ("y", "yes"):
        print("Aborted.")
        conn.close()
        return

    deleted = {}
    for table in ("daily_sales", "hourly_sales"):
        try:
            cur.execute(f"DELETE FROM {table} WHERE sale_date = %s", (tgt,))
            deleted[table] = cur.rowcount
        except Exception as e:
            conn.rollback()
            print(f"  {table}: delete failed — {e}")
            deleted[table] = 0
    conn.commit()

    print()
    print("Deleted:")
    for table, n in deleted.items():
        print(f"  {table}: {n:,} rows")

    # Verify
    print("\nPost-delete row counts for that date:")
    for table in ("daily_sales", "hourly_sales"):
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table} WHERE sale_date = %s", (tgt,))
            print(f"  {table}: {cur.fetchone()[0]:,}")
        except Exception:
            pass

    conn.close()


if __name__ == "__main__":
    main()
