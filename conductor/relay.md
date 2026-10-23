# Relay — garmin-surreal Session Log

> One entry per session, ≤10 lines, plain language. Newest first.
> Say what happened and what it means for the human — then point, don't retell.

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
