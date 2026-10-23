# Pulse — garmin-surreal

> **Updated:** 2026-10-23 19:45 by checkpoint
> State only, cap ~60 lines. Rewritten from scratch at every checkpoint —
> if you are appending to this file, you are doing it wrong.

## 📍 Now — what runs where

- **Saturn (production):** `/srv/saturn-docker/garmin/` — `garmin-fetch` (image `garmin-surreal:surreal-v0.1.0`, update loop every 300 s, `restart: unless-stopped`) + `health-surrealdb` (SurrealDB 3.2.4, saturn-net, port 8087). Namespace `health`, db `garmin`, user `garmin_writer`. `.env` 640 claude:docker; Garmin tokens in `garminconnect-tokens/` (copied from PlutoII, 600 uid 1000); raw FIT files in `fit-files/`. Run `docker compose` there as `claude` (docker group).
- **Saturn backfill:** container `garmin-backfill` (`docker compose run -d`), 2025-10-23 → 2026-10-15, `REQUEST_INTRADAY_DATA_REFRESH=True` (Garmin restores offloaded intraday data; a DENIED reply pauses it 24 h). Check: `docker logs garmin-backfill | grep -E "Bulk update success|Traceback|DENIED"`; remove the container when done.
- **Repo:** `~/Projects/garmin-surreal`, `main` = tag `surreal-v0.1.0` (pushed to `ArnarValur/garmin-surreal`). 62 tests pass. Upstream tags `v0.x` are upstream's — the fork tags `surreal-v*`.
- **PlutoII bench:** `pluto-surrealdb` `health/garmin` holds 30 days + raw tables from the bench runs. No fetcher running on PlutoII anymore.

## 🚀 Active tracks

- surrealdb_backend_20261023 → tracks/storage/surrealdb_backend_20261023/plan.md

## ⚠️ Blockers

- None.

## 📋 Next queue

1. When `garmin-backfill` finishes: per-table counts on Saturn, spot-check an old day (intraday restored?), `docker rm garmin-backfill`.
2. Watch the first days of the Saturn loop (`docker logs garmin-fetch | grep -E "ERROR|Collision|Skipped"`).
3. After the US DST change / Oslo DST (25 Oct): upstream computes the UTC offset once at start — restart `garmin-fetch` or confirm dates still line up.
4. Backups for `health-surrealdb-data` (not set up).
5. Parse useful raw tables into views (sleep sub-scores, SpO2, floors, weather) — track later.
6. Later per spec §9: aggregate tables, own dashboard, MCP/Hermes read tool over `health/garmin`.

## 📌 Parked

- Upstream bugs left as-is (minimal diff) → plan.md "Known upstream issues".
- Garmin account email change still pending at support (login works with the old address).
