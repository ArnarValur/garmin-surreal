# Technical rules — garmin-surreal

> Graduated lessons about the code, stack and tooling. Cap 15 rules; replace in place when superseded.

1. **Test against real SurrealDB 3.x.** The SDK's `mem://` engine (surrealdb 2.0.0) is SurrealDB 2.0: ID ranges and missing tables behave differently. `tests/conftest.py` starts a throwaway `surrealdb/surrealdb:v3.2.4` container or uses `TEST_SURREALDB_URI`.
2. **Check every statement.** `db.query()` only raises for the first statement; use `query_raw` and check `error` plus each `result[i].status` (done in `surreal_store._query_once`).
3. **Database-level users** sign in with `{"namespace", "database", "username", "password"}` (lowercase `ns`/`db` fail). `DEFINE USER ... PASSWORD` needs a string literal, not a `$param`.
4. **SurrealDB 3.x errors on SELECT/DELETE of a missing table** ("does not exist") — treat it as empty where that is meant.
5. **Ints beyond int64 wrap silently** in SurrealDB; `surreal_store` turns them into floats.
6. **Never add a drifting tag to the record key** (Device, ActivitySelector, User_ID, ActivityName): a changed value makes a second row. A tag that tells same-time points apart must be in the key, or points merge silently — log line `Collision`.
7. **Run fetches locally with `TZ=UTC`** to match the container (LactateThreshold time depends on the host zone).
8. **`solar_intensity` on a non-solar watch** raises inside `daily_fetch_write` and skips the rest of that day — keep it out of `FETCH_SELECTION`.
