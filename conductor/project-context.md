# Project Context — garmin-surreal

> Single identity + operational document for this project.
>
> **Created at init; user-edited thereafter — no command writes here.**
>
> Section order is deliberate: **identity-first (1–3), operational-second (4–8).**
> Agents partial-reading this file should see *what the product is* before *how to behave when working on it*.

---

## 1. Product Definition

- **Name:** garmin-surreal
- **Tagline:** Garmin Connect health data → SurrealDB, on a timer
- **Description:** Fork of `arpanghosh8453/garmin-grafana` with InfluxDB replaced by SurrealDB as the only storage backend. Pulls all Garmin Connect data (Venu 2 Plus watch + Garmin smart scale) and keeps it in its own namespace/database. Data only — no Grafana, no MCP yet. Full spec: [docs/garmin-surreal-handoff.md](./docs/garmin-surreal-handoff.md).
- **Target Audience:** Arnar's own health data on Saturn; later read by Hermes tools and an own dashboard
- **Key Differentiators:** Minimal diff over upstream (4 touch points + one new module), idempotent upsert-merge writes, time-first record IDs for fast range reads

---

## 2. Product Guidelines

- **Brand Voice:** Technical and precise
- **UX Principles:** Reliability-first — re-fetching any day must never change row counts or lose data
- **Accessibility:** Plain, short logs and docs

---

## 3. Tech Stack

- **Languages:** Python 3.13, SurrealQL
- **Frameworks:** `garminconnect` (Garmin API), `surrealdb` Python SDK 2.x
- **Databases:** SurrealDB 3.x (namespace `health`, database `garmin`)
- **Deployment Targets:** Docker (ARM64), self-hosted
- **Hosting:** Saturn (ASUS Ascent GX10); bench on PlutoII

---

## 4. Caution Levels

| Domain              | Level       | Notes                                   |
|---------------------|-------------|-----------------------------------------|
| `surreal_store.py` (record IDs, writes) | 🔴 Critical | A wrong key silently merges distinct points — data loss |
| Upstream files (`garmin_fetch.py`, importers) | 🟡 Careful | Touch only the 4 agreed points — keeps upstream rebases painless |
| Shared SurrealDB on Saturn | 🔴 Critical | Production for other apps — never touch other namespaces |
| Config / Build / compose | 🔴 Critical | Can break everything — verify before |
| Docs                | 🟢 Normal   | Low risk                                |
| conductor/ files    | 🟡 Careful  | Source of truth — don't corrupt         |

---

## 5. Domain Expertise

| Area                | Confidence  | Notes                                   |
|---------------------|-------------|-----------------------------------------|
| SurrealDB / SurrealQL | High      | Same server line as owui-surrealdb-adapter |
| surrealdb Python SDK | Medium     | 2.0.0 sync client; `mem://` for tests   |
| garminconnect       | Medium      | Upstream owns the Garmin API calls      |
| Docker              | High        | Primary deployment mechanism            |

---

## 6. Preferred Workflows

1. **Session Start Protocol:**
   - Boot with `/conductor` — it loads the hot set (pulse, last relay entry, tracks one-liners, workflow, behavioral rules, glossary) and nothing else
   - Warm-load track plans, ADRs, and technical rules only when work enters their domain

2. **Checkpoint Frequency:**
   - Checkpoint after every completed phase
   - Consider mid-phase checkpoints for long phases (>5 tasks)

3. **Decision Logging:**
   - Architectural decisions live in `conductor/adr/` — proposed and approved in-session, written at `/checkpoint`
   - Live state lives in `conductor/pulse.md`; the session story in `conductor/relay.md`; lessons in `conductor/agent-rules/`
   - Verify actual state on disk before proposing changes

4. **Debugging Protocol:**
   - Check legacy interference before blaming new code
   - If a fix fails twice, stop and escalate
   - Audit actual state vs documented state

---

## 7. Project-Specific Constraints

- Keep the upstream diff minimal: new logic goes in `src/garmin_grafana/surreal_store.py`; upstream files change only at the agreed touch points.
- Keep upstream's BSD-3-Clause `LICENSE` and copyright.
- Never commit secrets — Garmin and DB credentials live in a git-ignored `.env`.
- The DB user is dedicated to `health/garmin` and must not reach other namespaces.
- Bench on PlutoII first; deploy to Saturn only on Arnar's go.

---

## 8. Environment Notes

- Secrets: `.env` (git-ignored); template in `.env.example`.
- Garmin session tokens persist in the token directory (`TOKEN_DIR`, default `~/.garminconnect`) — never commit them.
