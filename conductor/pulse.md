# Pulse — garmin-surreal

> **Updated:** 2026-10-23 19:50 by checkpoint
> State only, cap ~60 lines. Rewritten from scratch at every checkpoint —
> if you are appending to this file, you are doing it wrong.

## 📍 Now — what runs where

- **Saturn (production):** `/srv/saturn-docker/garmin/` — `garmin-fetch` (image `garmin-surreal:surreal-v0.1.0`, loop every 300 s, `restart: unless-stopped`, raw + extras on) + `health-surrealdb` (SurrealDB 3.2.4, saturn-net, port 8087). Namespace `health`, db `garmin`, user `garmin_writer`. `.env` 640 claude:docker; tokens in `garminconnect-tokens/` (600, uid 1000); raw FIT files in `fit-files/`. Run `docker compose` there as `claude`.
- **Saturn backfill:** container `garmin-backfill`, 2025-10-23 → 2026-10-15 with `REQUEST_INTRADAY_DATA_REFRESH=True`; 30/357 days done at 19:45 (~14 s/day). Check: `docker logs garmin-backfill | grep -E "Bulk update success|Traceback|DENIED"`; `docker rm garmin-backfill` when done.
- **Backups (all Saturn SurrealDBs):** `surrealdb-backup.timer` 03:30 nightly → `/srv/backups/surrealdb/<server>/<date>/` (14 daily + 12 monthly). Script, restore test and README in `/srv/saturn-docker/surrealdb-backup/`. Restore-tested 2026-10-23 for owui, dittodatto and health. Same disk as the data.
- **Repo:** `~/Projects/garmin-surreal`, `main` = tag `surreal-v0.1.0` + conductor commits, pushed to `ArnarValur/garmin-surreal`. 62 tests pass.
- **PlutoII bench:** `pluto-surrealdb` `health/garmin` keeps the bench data. No fetcher runs on PlutoII.

## 🚀 Active tracks

- surrealdb_backend_20261023 → tracks/storage/surrealdb_backend_20261023/plan.md

## ⚠️ Blockers

- None.

## 📋 Next queue

1. When `garmin-backfill` finishes: per-table counts on Saturn, spot-check an old day, `docker rm garmin-backfill`.
2. Watch the Saturn loop for a few days (`docker logs garmin-fetch | grep -E "ERROR|Collision|Skipped"`).
3. Oslo DST ends 2026-10-25: upstream computes the UTC offset once at start — restart `garmin-fetch` after that.
4. Off-machine copy of `/srv/backups/surrealdb` (backups share Saturn's disk).
5. Dashboard — Arnar starts it in its own session.
6. Read useful raw tables out (sleep sub-scores, SpO2, floors, weather, PRs); later per spec §9: aggregates, MCP/Hermes read tool.

## 📌 Parked

- Upstream bugs left as-is (minimal diff) → plan.md "Known upstream issues".
- Garmin account email change still pending at support (login works with the old address).
