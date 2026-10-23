# Health data gets its own SurrealDB on Saturn

> **Recorded:** 2026-10-23 19:40
> **Status:** accepted

The spec put `health/garmin` inside OWUI's `owui-surrealdb`, but Saturn's ADR-0014 keeps that instance OWUI-only (separate credentials, backups and failure domain). Arnar chose a dedicated `health-surrealdb` (SurrealDB 3.2.4, saturn-net, host port 8087) in the `/srv/saturn-docker/garmin/` stack instead.

## Consequences

- Own root user (`health_root`) and writer user (`garmin_writer`, EDITOR on `health/garmin`); secrets only in `/srv/saturn-docker/garmin/.env`.
- Later readers (MCP / Hermes tools, dashboards) connect to `ws://health-surrealdb:8000/rpc` on saturn-net, or saturn:8087.
- Backups of health data are separate from OWUI's.
