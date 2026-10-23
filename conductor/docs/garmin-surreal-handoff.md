# Garmin → SurrealDB — handoff for Claude Code

> Copied verbatim from Arnar's handoff on 2026-10-23. This is the source spec for
> track `surrealdb_backend_20261023`. Where the build deviated, the track plan says so.

## Prompt (paste into Claude Code on PlutoII, with this file attached)

Read the attached spec `garmin-surreal-handoff.md` fully before doing anything. Goal: fork `arpanghosh8453/garmin-grafana` into my GitHub as `garmin-surreal`, clone it to `~/Projects/garmin-surreal`, and replace InfluxDB with my existing SurrealDB as the only storage backend — data only, no Grafana, no MCP yet. First, read `~/Projects/owui-surrealdb-adapter` to learn my SurrealDB server version, connection URL style and auth setup, and reuse those conventions. Tell me what you found before writing code. Then implement per the spec, keeping the upstream diff minimal. Bench everything on PlutoII against my local SurrealDB first (unit tests + a 7-day live fetch + a short backfill), show me the acceptance checks, and only then prepare the Saturn deploy and wait for my go. Set up the project's conductor folder the way you do for my other `~/Projects` repos and copy this spec into it. Never commit secrets; Garmin and DB credentials go in a git-ignored `.env`.

## 1. Goal and scope

* Pull all Garmin Connect data (Venu 2 Plus + Garmin smart scale) on a timer and store it in SurrealDB only, in its own namespace/database, on Saturn.
* In scope: the fetcher, history backfill, Docker image for ARM64, compose service on Saturn.
* Out of scope for now: Grafana/dashboards, MCP/AI tools, aggregate views, CSV exporter.

## 2. Upstream facts (verified 2026-10-23, upstream commit `895bfa7`)

* License BSD-3-Clause — forking and modifying is fine; keep the license file and copyright.
* Main code: `src/garmin_grafana/garmin_fetch.py` (~1800 lines). Python 3.13, deps in `pyproject.toml` + `uv.lock`, Garmin access via `garminconnect==0.3.7` (works with Garmin's March-2026 auth change).
* Every fetch function returns a list of points: `{"measurement", "time" (ISO string, UTC), "tags": {...}, "fields": {...}}`.
* All writes go through one function: `write_points_to_influxdb(points)`. The FIT importer (`fit_activity_importer.py`) and the Garmin-export bulk importer (`garmin_bulk_importer.py`, which mocks `garmin_obj` and reuses `garmin_fetch`) also write only through it.
* InfluxDB is touched in exactly these places in `garmin_fetch.py`:
   1. Module-level client creation + demo-point connection test (≈ lines 89–125).
   2. `write_points_to_influxdb` (≈ line 194).
   3. `purge_existing_strength_exercise_sets` (≈ line 753) — deletes `StrengthExerciseSet` rows by tag `ActivityID`.
   4. Last-sync lookup in `__main__` (≈ line 1779) — newest `HeartRateIntraday` time.
* `influxdb_exporter.py` is a standalone CSV exporter — drop it from the image/docs in this fork.
* 30 measurements, e.g. `HeartRateIntraday`, `StressIntraday`, `BodyBatteryIntraday`, `SleepIntraday`, `SleepSummary`, `HRV_Intraday`, `DailyStats`, `BodyComposition` (scale: weight, bmi, bodyFat, bodyWater, boneMass, muscleMass, physiqueRating, visceralFat), `ActivitySummary`, `ActivityGPS`, `ActivityLap`, `StrengthExerciseSet`, `TrainingReadiness`, `VO2`-related, `DeviceSync`, etc.
* Common tags: `Device`, `Database_Name` (on everything); per-table distinguishing tags include `ActivityID` / `Activity_ID`, `ActivitySelector`, `Index`, `SleepStageLevel`, `SourceType`, `ActivityName`.
* Upstream already builds multi-arch Docker images (amd64 + arm64) — the Dockerfile works on ARM64.

## 3. Storage design

Location: namespace `health`, database `garmin` (env-configurable). Use a dedicated DB user with access to only that database.
One SurrealDB table per measurement, table name = measurement name.
Record ID = array, time first: `Table:[time, ...key tag values]`

* `time` = SurrealDB `datetime` in UTC (convert from the ISO string).
* Key tags = a small explicit allow-list of tags that make a point unique within its measurement: `ActivityID`, `Activity_ID`, `ActivitySelector`, `Index`, `SleepStageLevel` (Claude Code: audit every measurement and adjust this list; see test T3).
* Exclude from the ID: `Database_Name` (meaningless here), `Device`, `User_ID`, `ActivityName`, `SourceType` — these can change over time (device auto-detect, renamed activities) and would create duplicates.
* Key tag values go in sorted-by-tag-name order, as strings.
* Why time first: ordered IDs let range queries read a time slice directly, e.g. `HeartRateIntraday:[d'2026-10-01T00:00:00Z']..[d'2026-10-24T00:00:00Z']`.

Record content: all non-null fields at top level + `time` (datetime) + `tags` (object with all tags except `Database_Name`). Drop `None` fields. Keep Garmin's raw units (e.g. weight arrives in grams) — no conversions in this phase.

Write semantics: upsert-merge (same as InfluxDB overwriting a point), so re-fetching a day is idempotent:

```
FOR $r IN $rows { UPSERT $r.id MERGE $r.content; };
```

* `$rows` = list of `{"id": RecordID(table, [datetime, ...]), "content": {...}}` passed as a query variable.
* Batch ~2000 rows per query (GPS-heavy activities produce large batches; tune if WS message size errors appear).
* Avoid version-specific functions like `type::thing` (renamed in 3.x); passing `RecordID` objects from the SDK sidesteps that.

Schema: start schemaless. Optional: `DEFINE INDEX` on `tags.ActivityID` for activity tables.

## 4. Code changes (minimal diff)

Put all SurrealDB logic in a new module `src/garmin_grafana/surreal_store.py`; in the upstream files change only the 4 touch points so upstream rebases stay painless.

`surreal_store.py` provides:

* `connect()` — `from surrealdb import Surreal, RecordID`; `Surreal(SURREALDB_URL)`, `signin`, `use(ns, db)`; a connection check that fails fast with a clear log line (replaces the demo point).
* `write_points(points)` — map points → rows (section 3), batch, upsert-merge; honours `TAG_MEASUREMENTS_WITH_USER_EMAIL` (add `User_ID` to tags as upstream does); logs counts; raises/logs like upstream on failure.
* `last_sync_time()` — `SELECT id, time FROM HeartRateIntraday ORDER BY id DESC LIMIT 1` → datetime or `None`.
* `purge_strength_sets(activity_id)` — `DELETE StrengthExerciseSet WHERE tags.ActivityID = $a`.

Touch points in `garmin_fetch.py`:

1. Replace the InfluxDB client block with `surreal_store.connect()`.
2. Make `write_points_to_influxdb(points)` a thin wrapper around `surreal_store.write_points(points)` (keep the name — the importers call it).
3. `purge_existing_strength_exercise_sets` → `surreal_store.purge_strength_sets`.
4. Last-sync lookup → `surreal_store.last_sync_time()`, keep the existing 7-day fallback when empty.

Also:

* `pyproject.toml` / `uv.lock`: remove `influxdb`, `influxdb3-python`; add `surrealdb==2.0.0` (ships aarch64 wheels, has a blocking WS/HTTP client and an embedded `mem://` mode for tests). Keep `pandas` only if still needed.
* Replace `INFLUXDB_*` env vars with: `SURREALDB_URL` (e.g. `ws://surrealdb:8000/rpc`), `SURREALDB_NAMESPACE` (default `health`), `SURREALDB_DATABASE` (default `garmin`), `SURREALDB_USER`, `SURREALDB_PASSWORD`. Keep the `Database_Name` tag value harmless (it's excluded from IDs and content).
* Remove `influxdb_exporter.py`, InfluxDB/Grafana services and provisioning from the fork's compose file; keep upstream's Garmin env vars (`GARMINCONNECT_*`, `UPDATE_INTERVAL_SECONDS`, `FETCH_SELECTION`, `USER_TIMEZONE`, `RATE_LIMIT_CALLS_SECONDS`, `MANUAL_START_DATE/END_DATE`, …).
* `FETCH_SELECTION`: enable everything the Venu 2 Plus supports, including the optional extras (`training_readiness`, `training_status`, `endurance_score`, `hill_score`, `hydration`, `lactate_threshold`) — empty results are harmless.
* `USER_TIMEZONE=Europe/Oslo` (update after the Sweden move: `Europe/Stockholm` — same zone).
* Short README section in the fork explaining the SurrealDB backend and env vars.

## 5. Verified prototype (run in a sandbox on 2026-10-23, SDK 2.0.0, embedded `mem://` engine)

Writing the same 9 heart-rate points twice → 9 rows (idempotent). Time-range slice on the record ID returned the correct 6 rows. `last_sync_time` query returned the newest row. `None` fields were dropped. Strength-set purge by `tags.ActivityID` → 0 rows left.

```python
from datetime import datetime, timezone
from surrealdb import Surreal, RecordID

KEY_TAGS = {"ActivityID", "Activity_ID", "ActivitySelector", "Index", "SleepStageLevel"}

def to_rows(points):
    rows = []
    for p in points:
        t = datetime.fromisoformat(p["time"]).astimezone(timezone.utc)
        tags = {k: v for k, v in p["tags"].items() if k != "Database_Name"}
        key = [t] + [str(tags[k]) for k in sorted(tags) if k in KEY_TAGS]
        fields = {k: v for k, v in p["fields"].items() if v is not None}
        rows.append({"id": RecordID(p["measurement"], key),
                     "content": {**fields, "time": t, "tags": tags}})
    return rows

UPSERT = "FOR $r IN $rows { UPSERT $r.id MERGE $r.content; };"
db = Surreal("mem://"); db.use("health", "garmin")
db.query(UPSERT, {"rows": to_rows(points)})
```

This exact snippet was also run: a `Device` tag change ("Unknown" → "Venu 2 Plus") on the same timestamp overwrote the row (1 row, not 2), and 3 strength sets sharing a timestamp stayed 3 rows via the `Index` key tag.

## 6. Test plan — bench on PlutoII first

* T1 unit (no server): `mem://` engine — mapping, idempotent double write, range query, last-sync, purge, `None` dropping, batching across the chunk boundary.
* T2 integration: against my local SurrealDB on PlutoII, `health/garmin` with the dedicated user.
* T3 uniqueness audit: for one real day per measurement, assert that no two points from a single fetch map to the same record ID (would mean silent data loss). Fix `KEY_TAGS` if any collide.
* T4 live: first Garmin login interactively (MFA prompt) with tokens persisted; run a 7-day fetch; then let the loop run 2–3 update cycles and confirm new rows arrive and counts stay stable on re-fetch.
* T5 backfill: `MANUAL_START_DATE`/`MANUAL_END_DATE` for ~30 days; check row counts per table and spot-check a scale weigh-in and a sleep night against the Connect app.

## 7. Deploy to Saturn (after my go)

* Saturn: ARM64 (ASUS Ascent GX10), user `arnar`, `ssh saturn`. My SurrealDB already runs there (production for the OWUI adapter).
* Build the image on Saturn (native arm64) or via buildx; no registry needed.
* Compose service `garmin-fetch`: `restart: unless-stopped`, on the same Docker network as SurrealDB, `.env` for secrets, token volume `./garminconnect-tokens:/home/appuser/.garminconnect` owned `1000:1000`.
* Create the `health` namespace, `garmin` database and dedicated user on Saturn's SurrealDB without touching the OWUI data.
* Do the interactive Garmin login once on Saturn, then start the service. Then run the full history backfill (API backfill with the default rate limit; it may take a while — keep it in the background).
* Optional later: Garmin's official full-account export + `garmin_bulk_importer.py` for faster deep history.

## 8. Acceptance criteria

* Service runs on Saturn, survives restarts, and new watch/scale data appears in SurrealDB within one update interval after a phone sync.
* Re-fetching any day does not change row counts.
* `BodyComposition`, `HeartRateIntraday`, `SleepSummary`, `DailyStats` and `ActivitySummary` hold correct data for a spot-checked date.
* No InfluxDB/Grafana containers or dependencies remain in the fork.
* Upstream diff is limited to the 4 touch points + deps + compose/docs + the new module.

## 9. Later (not now)

* Live aggregate tables in SurrealDB (`DEFINE TABLE … AS SELECT … GROUP BY`) for daily/weekly rollups (resting HR, weight trend).
* Own dashboard.
* MCP / Hermes read tool over `health/garmin`.
* Watch upstream for Garmin auth changes; rebase the fork when `garminconnect` is bumped.
