# Snowflake Migration — Gaps Log

Items in the current dashboard that are **not yet available** in the Snowflake test version.
Bring this list when talking to the Snowflake admin or JM tech team.

---

## 1. Lunch / Dinner / Morning Daypart Split
**Where it appears:** Daily Sales → Overview tiles and channel mix  
**What's missing:** `RPT_DAILY_SALES` has no daypart (lunch/dinner/morning) breakdown.  
**Ask:** Request a `LUNCH_NET_SALES`, `DINNER_NET_SALES` column be added to `RPT_DAILY_SALES`,
or access to the underlying hourly/daypart transaction table.

---

## 2. Weather × SSS Attribution Panel
**Where it appears:** Daily Sales → Overview → bottom panel  
**What's missing:** Weather data (`store_daily_weather` table) lives in Supabase, not Snowflake.  
**Ask:** Either keep pulling weather from the existing source and join it client-side,
or request a weather table be added to the Snowflake reporting environment.

---

## 3. BlakeWard Peer Benchmark Tab
**Where it appears:** Daily Sales → Benchmark tab (4th tab)  
**What's missing:** BlakeWard comparison data comes from PDF-parsed `weekly_benchmark` table in Supabase.
There is no equivalent in Snowflake.  
**Ask:** This likely stays as a manual PDF import process. No Snowflake fix needed — just keep
the current pipeline running and wire the benchmark tab back in manually.

---

## 4. District Manager (DM) Names
**Where it appears:** Daily Sales → "By District Manager" tab — tree grouped by DM name  
**What's missing:** `RPT_DAILY_SALES` has `DISTRICT` and `REGION` but not individual DM names.
The current dashboard pulls DM names from the `stores` table in Supabase.  
**Ask (option A):** Add `DM_NAME` column to `RPT_DAILY_SALES` in Snowflake.  
**Ask (option B):** Join `RPT_DAILY_LABOR.DM_REPORT` on `SITE_ID + DATE` to get DM names
(available now — no new data needed, just an extra join).

---

## 5. True SSS by 3P Channel (DoorDash, UberEats, etc.)
**Where it appears:** Daily Sales → 3P Channels tab (new feature)  
**What's missing:** No pre-filtered SSS columns for individual 3P providers
(e.g. no `SSS_DOORDASH_NET_SALES`). Current test uses YOY all-stores comparison.  
**Ask:** Either accept the YOY approach as sufficient, or request comp-filtered 3P columns
be added to `RPT_DAILY_SALES`.

---

## 6. Hourly Heatmap
**Where it appears:** Hourly Heatmap page  
**What's missing:** None of the 5 Snowflake views have hourly breakdowns.
All data is daily-level.  
**Ask:** Request access to an hourly sales table or view, OR confirm whether the
Snowflake instance has one in STAGING that this user can be granted access to.

---

## Not a Gap — Items That Are Better in Snowflake
- Pre-built WTD / MTD / QTD / YTD / PTD comparisons (vs manual aggregation today)
- Prior year comparisons built in for every metric
- Labor data (`RPT_DAILY_LABOR`) — not in current dashboard at all
- COGS / inventory variance (`RPT_WEEKLY_COGS`) — not in current dashboard at all
- Catering breakdown by channel including ezCater — not in current dashboard at all
- 3P provider detail by DoorDash / UberEats / Grubhub / Postmates — not in current dashboard
- Google reviews data (`RPT_DAILY_REVIEWS`) via Snowflake instead of Google API scraping
