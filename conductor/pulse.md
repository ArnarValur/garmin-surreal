# Pulse — garmin-surreal

> **Updated:** 2026-10-23 19:05 by checkpoint
> State only, cap ~60 lines. Rewritten from scratch at every checkpoint —
> if you are appending to this file, you are doing it wrong.

## 📍 Now — what runs where

- Repo `~/Projects/garmin-surreal`, `main`; fork of upstream `895bfa7` at `github.com/ArnarValur/garmin-surreal` (remote `upstream` = arpanghosh8453/garmin-grafana).
- SurrealDB backend done: `src/garmin_grafana/surreal_store.py` + 4 touch points in `garmin_fetch.py` (+ date retry, resume marker, strength-set and END fixes). 48 tests pass (`uv run --with pytest pytest tests -q`), on a throwaway SurrealDB 3.2.4 container and on the PlutoII bench.
- PlutoII bench SurrealDB (`pluto-surrealdb` 3.2.4, port 8000): namespace `health`, db `garmin`, user `garmin_writer` (EDITOR). Holds only `meta`. Password in the repo's git-ignored `.env`.
- No fetcher running anywhere. Nothing deployed to Saturn.
- Local `.env` (600, git-ignored) sets `TZ=UTC`, token dir `./garminconnect-tokens`, FIT files `./fit-files`.

## 🚀 Active tracks

- surrealdb_backend_20261023 → tracks/storage/surrealdb_backend_20261023/plan.md

## ⚠️ Blockers

- Garmin login: the account is on an old email Arnar can't reach; Garmin support is changing it (expected next week). Blocks T3/T4/T5 and the capability probe.

## 📋 Next queue

1. Once the email is changed: `.venv/bin/python src/garmin_grafana/garmin_login.py` (with `.env` sourced) on PlutoII.
2. Run `scripts/garmin_capability_probe.py` (output outside the repo) — which endpoints return data for the Venu 2 Plus + scale.
3. T4: run `garmin_fetch.py` (7-day default), 2–3 update cycles, re-fetch → row counts stable; grep logs for `Collision`.
4. T5: ~30-day backfill, per-table counts, spot-check a weigh-in and a sleep night against the Connect app.
5. ADR candidate (deferred): Saturn storage — new `health-surrealdb` on saturn-net, host port 8087 (respects Saturn ADR-0014: owui-surrealdb is OWUI-only) vs the spec's `owui-surrealdb`. Ask Arnar before deploying.
6. Saturn deploy prep → wait for Arnar's go.
7. "Dig everything": raw-JSON mirror of every Garmin response + extra endpoints (SpO2, Body Battery events, sleep sub-scores, …) — see the track's garmin-coverage.md.

## 📌 Parked

- Upstream bugs left as-is (minimal diff): fit_activity_importer END marker < 1 s, `return []` with FORCE_REPROCESS_ACTIVITIES=False, LactateThreshold time depends on host TZ, SleepSummary ID moves when a sleep window is edited, naps not stored → plan.md "Known upstream issues".
