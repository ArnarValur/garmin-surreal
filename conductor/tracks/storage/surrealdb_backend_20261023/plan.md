# Plan — surrealdb_backend_20261023

> Spec: [../../../docs/garmin-surreal-handoff.md](../../../docs/garmin-surreal-handoff.md)
> Goal: replace InfluxDB with SurrealDB (`health/garmin`) as the only backend; bench on PlutoII, then deploy to Saturn on Arnar's go.
> Arnar, 2026-10-23: the most important goal is to get the data — everything we can dig from Garmin.

## Phase 1 — Discover

- [x] Read owui-surrealdb-adapter conventions (SurrealDB 3.2.4, `ws://<host>:8000/rpc`, SDK 2.0.0, `SURREALDB_URI/NS/DB/USER/PASS`)
- [x] Fork `arpanghosh8453/garmin-grafana` → `ArnarValur/garmin-surreal`, clone at `895bfa7`
- [ ] Audit every measurement: time format, tags, which tags make a point unique (static T3)
- [ ] Audit Garmin data upstream does not fetch yet

## Phase 2 — Build

- [ ] `surreal_store.py` + unit tests (T1, `mem://`)
- [ ] 4 touch points in `garmin_fetch.py`
- [ ] Deps (`surrealdb==2.0.0`, drop influx), drop `influxdb_exporter.py`, compose + `.env.example`, README section

## Phase 3 — Bench on PlutoII

- [ ] T2 integration against local SurrealDB with the dedicated user
- [ ] T4 live: interactive Garmin login, 7-day fetch, 2–3 update cycles, stable counts on re-fetch
- [ ] T3 uniqueness audit on real data
- [ ] T5 ~30-day backfill, per-table counts, spot-checks against the Connect app

## Phase 4 — Saturn (after Arnar's go)

- [ ] Image build (arm64), `health/garmin` + dedicated user, compose service, interactive login, full backfill
