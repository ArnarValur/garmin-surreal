# Relay — garmin-surreal Session Log

> One entry per session, ≤10 lines, plain language. Newest first.
> Say what happened and what it means for the human — then point, don't retell.

## 2026-10-23 (evening) — Live on Saturn, raw data, 1-year backfill

- **What happened:** Garmin login worked (old email, password remembered; Garmin rate-limited the guesses but the third login method got through). Bench T3–T5 passed: 7-day + 30-day fetch, re-fetch kept counts identical, weigh-in and sleep matched the Connect app, phone sync arrived within 5 min. Added `raw` (every Garmin response stored whole) and `extras` (endpoints upstream never calls) after a capability probe; reviewed (9 fixes). Fixed upstream's broken intraday refresh. Deployed to Saturn with its own SurrealDB.
- **Status:** Saturn loop live; 1-year backfill running in `garmin-backfill`.
- **Decisions:** ADR-0001 own SurrealDB on Saturn; backfill 1 year (Arnar), not full history.
- **Next:** check the backfill result, then backups and reading the raw tables.

## 2026-10-23 — SurrealDB backend built; waiting on Garmin login

- **What happened:** Forked upstream, swapped InfluxDB for SurrealDB (`surreal_store.py` + 4 touch points), audited every measurement's record key with agents (spec's key list would have lost LifestyleJournal rows and same-second strength sets/laps), and fixed 18 issues from an independent review (DB outages no longer leave gaps; crashes resume their range).
- **Status:** 48 tests pass; bench `health/garmin` + `garmin_writer` ready on PlutoII. Live fetch blocked — Garmin account email needs changing by support.
- **Decisions:** deviations from the spec are listed in the track plan (D1–D6); Saturn storage choice is a deferred ADR candidate (pulse).
- **Next:** Garmin login → capability probe → T4/T5 → Saturn deploy on Arnar's go.

## 2026-10-23 — Conductor initialized

- **What happened:** Conductor scaffolded for garmin-surreal — state files, workflow, and the boot/checkpoint commands are in place.
- **Status:** Ready for the first working session.
- **Decisions:** none
- **Next:** Create the first track and start working.
