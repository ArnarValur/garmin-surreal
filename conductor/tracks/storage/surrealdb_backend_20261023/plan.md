# Plan — surrealdb_backend_20261023

> Spec: [../../../docs/garmin-surreal-handoff.md](../../../docs/garmin-surreal-handoff.md)
> Goal: replace InfluxDB with SurrealDB (`health/garmin`) as the only backend; bench on PlutoII, then deploy to Saturn on Arnar's go.
> Arnar, 2026-10-23: the most important goal is to get the data — everything we can dig from Garmin.

## Phase 1 — Discover

- [x] Read owui-surrealdb-adapter conventions (SurrealDB 3.2.4, `ws://<host>:8000/rpc`, SDK 2.0.0, `SURREALDB_URI/NS/DB/USER/PASS`)
- [x] Fork `arpanghosh8453/garmin-grafana` → `ArnarValur/garmin-surreal`, clone at `895bfa7`
- [x] Audit every measurement: time format, tags, which tags make a point unique (static T3, 5 auditors + 5 skeptics)
- [x] Audit Garmin data upstream does not fetch yet → [garmin-coverage.md](./garmin-coverage.md)

## Phase 2 — Build

- [x] `surreal_store.py` + tests (T1) — DB tests run on a throwaway SurrealDB 3.2.4 container; `mem://` kept as a smoke test only
- [x] 4 touch points in `garmin_fetch.py`
- [x] Deps (`surrealdb==2.0.0`, `pytz` pinned, influx + pandas dropped), `influxdb_exporter.py` removed, compose + `.env.example` + `init.surql.example`, README section
- [x] Independent review: 18 confirmed findings fixed (commit `9f3c32c`)

## Phase 3 — Bench on PlutoII

- [x] T2 integration against local SurrealDB with the dedicated user (`garmin_writer`)
- [ ] Garmin login (`src/garmin_grafana/garmin_login.py`) — **blocked: account email change pending at Garmin support**
- [ ] Capability probe (`scripts/garmin_capability_probe.py`)
- [ ] T4 live: 7-day fetch, 2–3 update cycles, stable counts on re-fetch
- [ ] T3 uniqueness on real data (`Collision` warnings in the logs)
- [ ] T5 ~30-day backfill, per-table counts, spot-checks against the Connect app

## Phase 4 — Saturn (after Arnar's go)

- [ ] Decide storage instance (ADR candidate: dedicated `health-surrealdb`, port 8087, vs `owui-surrealdb`)
- [ ] Image build (arm64), `health/garmin` + dedicated user, compose service, interactive login, full backfill

## Deviations from the spec

- **D1 Env names** follow owui-surrealdb-adapter (`SURREALDB_URI/NS/DB/USER/PASS`), not the spec's `SURREALDB_URL/NAMESPACE/DATABASE/PASSWORD` (Arnar asked to reuse the adapter's conventions).
- **D2 Record key**: `KEY_TAGS = ActivityID, ExerciseCategory, ExerciseLabel, Source, SourceType, behavior` plus `KEY_FIELDS` (`Index` for ActivityLap/Length/Session, `SetOrder` for StrengthExerciseSet). Dropped from the spec's list: `ActivitySelector` (drifts when an activity type is edited), `Activity_ID`/`Index`/`SleepStageLevel` (they are fields, not tags). Added `behavior` (LifestyleJournal lost all but one behavior per day), `SourceType`/`Source` (same-second readings from two sources).
- **D3 Failed writes** raise and the date is retried every 2 min (upstream logged and skipped → permanent gap). `meta:sync.pending_from` lets a crash resume its range.
- **D4 Small upstream fixes** that would lose data: strength sets replaced only by a complete snapshot (null reps aborted the loop), ActivitySummary END marker ≥ 1 s after start.
- **D5 FETCH_SELECTION** leaves out `solar_intensity`: on a non-solar watch Garmin raises and the rest of that day is skipped.
- **D6 Extra files**: `garmin_login.py` (hidden-password login helper), `scripts/garmin_capability_probe.py`, `init.surql.example`, tests.

## Known upstream issues (left as-is, minimal diff)

- `fit_activity_importer.py` END marker can share the start second; `fetch_activity_GPS` does `return []` instead of `continue` when FORCE_REPROCESS_ACTIVITIES=False.
- LactateThreshold time uses the host's local TZ (run locally with `TZ=UTC`; containers are UTC).
- SleepSummary/SleepIntraday IDs move when a sleep window is edited → orphan rows (InfluxDB had the same).
- Naps, sleep sub-scores, HRV summary and many daily-stats fields are not stored (see garmin-coverage.md).
