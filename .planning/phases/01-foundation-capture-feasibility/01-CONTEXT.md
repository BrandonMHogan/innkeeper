# Phase 1: Foundation + Capture Feasibility - Context

**Gathered:** 2026-06-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up a fully deployable Docker Compose stack (API, frontend, DB, capture service) that is password-protected, accessible from any device on the LAN, and has a proven end-to-end capture pipeline: a Linux container capturing ARP traffic and writing a record to PostgreSQL via the API. Everything downstream phases need to be safe to build.

</domain>

<decisions>
## Implementation Decisions

### Deployment Target
- **D-01:** Target is a Linux machine (bare metal or VM) — NOT macOS with Docker Desktop. The macOS Docker host-networking constraint documented in STATE.md and REQUIREMENTS.md PLAT-03 does not apply.
- **D-02:** PLAT-03 "native macOS agent fallback" is NOT needed. Linux host networking is the baseline — no alternative topology research required.

### Capture Service
- **D-03:** Capture runs as a Docker container with `network_mode: host` + `CAP_NET_RAW` + `CAP_NET_ADMIN` capabilities. Never `--privileged`.
- **D-04:** Phase 1 capture service is proof-of-concept only — it captures ARP packets and POSTs them to the FastAPI API (which writes to PostgreSQL). No real discovery pipeline in Phase 1; that lands in Phase 2.
- **D-05:** The spike success criteria: capture one real ARP packet from the LAN, POST it to the API, confirm one row written to PostgreSQL. This is the Phase 1 go/no-go gate.
- **D-06:** Capture service → data flows via POST to the FastAPI API (not direct DB writes). The API is the single point of truth for all data writes, enabling future validation and enrichment.

### Authentication
- **D-07:** Session persistence: httpOnly signed session cookie. No JWT in localStorage — XSS-safe by default, auto-sent with every request.
- **D-08:** First-run flow: all routes redirect to `/setup` if no password has been configured. User sets password → redirected to `/login` → enters dashboard. Hard to bypass.
- **D-09:** Password policy: any non-empty string. No minimum length or complexity rules — this is a self-hosted single-user tool.
- **D-10:** Sessions never expire automatically. A session is invalidated only when the user changes their password.

### Docker Compose Topology
- **D-11:** 4 services from day 1: `api` (FastAPI), `frontend` (SvelteKit static), `db` (PostgreSQL + TimescaleDB), `capture` (host-networked capture service). Final topology — no throwaway scaffolding.
- **D-12:** Dashboard accessible at port **9999** (HTTP, no TLS). No nginx reverse proxy in Phase 1 — browser talks directly to the frontend container on :9999.
- **D-13:** Browser fetches API at the host's IP on its own port (e.g., :8000 or as configured). Frontend calls API via the host's network address, not Docker-internal DNS.
- **D-14:** Config (DB password, session secret, ports) via `.env` file at repo root. Committed `.env.example` documents required variables. Standard 12-factor pattern.
- **D-15:** Alembic migrations run automatically on API container startup (`alembic upgrade head` before Uvicorn starts). No manual migration step required by the user.
- **D-16:** TimescaleDB hypertable created in a Phase 1 Alembic migration — even though traffic data doesn't land until Phase 3. Schema changes are expensive; locking this in now.
- **D-17:** Frontend: SvelteKit built with `adapter-static`, served from a lightweight nginx container on port 9999.
- **D-18:** Development workflow: `docker compose up` for everything. Source directories mounted as volumes so code changes reflect without full rebuilds.

### Dashboard Shell
- **D-19:** Phase 1 dashboard shell contains only: `/setup`, `/login`, and a protected empty `/dashboard`. No nav structure, no device list, no additional routes. Phase 2 adds real content.

### Claude's Discretion
- API port selection (internal to Docker Compose) — any available port is fine
- Health check configuration for each service — standard patterns acceptable
- Docker Compose network name and internal DNS names for services
- Session cookie signing implementation details (e.g., itsdangerous, PyJWT in cookie mode)
- Specific nginx config for the frontend container

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project Requirements & Roadmap
- `.planning/ROADMAP.md` — Phase 1 success criteria (5 items), requirements list (PLAT-01/02/03, AUTH-01/02/03), phase goal statement
- `.planning/REQUIREMENTS.md` — Full v1 requirements; PLAT-03 definition (capture engine isolation), AUTH requirements detail
- `.planning/PROJECT.md` — Key decisions table, constraints (portability, self-hosted, Docker Compose, router-agnostic core, data privacy)

### Technology Stack
- `CLAUDE.md` — Complete stack decisions: Python 3.13, FastAPI 0.136, Pydantic 2.13, Uvicorn, sse-starlette, PostgreSQL 17, TimescaleDB 2.27, SQLAlchemy 2.0 async, asyncpg, Alembic, Scapy 2.7, Svelte 5.56, SvelteKit 2.65, Vite 6, adapter-static deployment model

### State & Blockers
- `.planning/STATE.md` — Current blockers: TimescaleDB schema is expensive to change (settle in Phase 1); macOS/Docker capture gate (now resolved — Linux target confirmed)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — project is greenfield. `openspec/` directory scaffolded but empty.

### Established Patterns
- None yet — Phase 1 establishes all patterns. Follow stack decisions in CLAUDE.md exactly.

### Integration Points
- All services are net-new. The compose file is the first integration point — every subsequent phase adds to it.

</code_context>

<specifics>
## Specific Ideas

- Port 9999 specifically chosen by the user — use it in all examples, README snippets, and docker-compose.yml
- User confirmed "docker compose up for everything" as the dev workflow — mount source as volumes in compose for hot iteration
- Capture service is explicitly proof-of-concept in Phase 1 — do not over-engineer it; Phase 2 replaces it with real discovery logic

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 1 scope.

</deferred>

---

*Phase: 1-Foundation + Capture Feasibility*
*Context gathered: 2026-06-16*
