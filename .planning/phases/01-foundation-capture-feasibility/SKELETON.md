# Walking Skeleton — Innkeeper

**Phase:** 1
**Generated:** 2026-06-17

## Capability Proven End-to-End

A user can run `docker compose up`, set a dashboard password on first run, sign in, reach a protected empty dashboard from any device on the LAN — and a real ARP packet captured by an isolated, minimally-privileged container is persisted to PostgreSQL via the API.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Backend framework | FastAPI 0.137.1 + Uvicorn, Python 3.13 (Docker only) | Per CLAUDE.md stack; async-native; aiounifi (Phase 7) requires 3.13 |
| Data layer | PostgreSQL 17 + TimescaleDB 2.27 via SQLAlchemy 2.0 async + asyncpg + Alembic | D-16: hypertable schema locked in Phase 1 even though traffic data lands in Phase 3 — expensive to change later |
| Auth | Starlette `SessionMiddleware` (itsdangerous-signed httpOnly cookie), `hashlib.scrypt` password hashing, no expiry (D-07, D-09, D-10) | XSS-safe by default; single-user self-hosted tool needs no complexity rules or token refresh |
| Capture topology | Docker container, `network_mode: host`, `cap_add: [NET_RAW, NET_ADMIN]`, never `--privileged`, runs as root (Python raw-socket constraint) (D-01, D-03) | Linux deployment target confirmed by user — no macOS fallback needed |
| Capture data flow | Capture POSTs to FastAPI `/api/capture/arp`; API is sole DB writer (D-06) | Single point of truth for validation/enrichment in later phases |
| Frontend | SvelteKit 2.65 + Svelte 5.56, `adapter-static`, served by nginx on :9999 (D-17) | No SSR needed for a local-only dashboard; nginx serves static assets 10-100x faster than a Python server |
| Deployment target | Docker Compose, 4 services (`api`, `frontend`, `db`, `capture`), `.env`-driven config, port 9999 (D-11, D-12, D-14) | Final topology from day one — no throwaway scaffolding per user decision |
| Directory layout | `backend/src/{models,routes}`, `backend/alembic/`, `frontend/src/{routes,lib}`, `capture/` — flat per-service top-level dirs | Mirrors the 4 Docker Compose services 1:1; each dir = one Dockerfile build context |

## Stack Touched in Phase 1

- [x] Project scaffold (FastAPI backend, SvelteKit frontend, Scapy capture service — build/lint per stack)
- [x] Routing — `/setup`, `/login`, `/dashboard` (SvelteKit SPA routes); `/api/auth/*`, `/api/capture/arp` (FastAPI routes)
- [x] Database — real read AND write: `app_settings` row written on `/api/auth/setup`, read on `/api/auth/login`; `arp_events` row written by capture ingest
- [x] UI — interactive password form on `/setup` and `/login` wired to the real API via fetch with `credentials: 'include'`
- [x] Deployment — `docker compose up` brings up all 4 services; documented as the only required dev/run command

## Out of Scope (Deferred to Later Slices)

- Real device discovery / fingerprinting logic in the capture service — Phase 1 capture is proof-of-concept only (D-04); Phase 2 replaces it
- Any dashboard content beyond an empty protected shell — Phase 2 adds device list and nav
- Multi-user accounts, RBAC — v2 scope, out of project scope for v1 entirely
- TLS / reverse proxy — D-12 explicitly chose plain HTTP on :9999 for v1
- Traffic/bandwidth data actually populating `bandwidth_metrics` — table + hypertable created now (D-16), populated in Phase 3

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: Device Registry + Discovery — replaces capture PoC with real multi-source discovery (ARP + mDNS + DHCP), adds device registry CRUD and dashboard nav/content
- Phase 3: Live Traffic + Bandwidth — populates the `bandwidth_metrics` hypertable created in Phase 1, adds SSE live feed
- Phase 4: Security — port scans, security status, alerts
- Phase 5: Plugin System + Notifications — plugin contract, event bus, first-party notification plugin
- Phase 6: Dual-Mode + Control — travel mode, mode switcher, device blocking
- Phase 7: UniFi + Integrations — UniFi adapter (forces the Python 3.13 baseline laid down here), Pi-hole, Grafana
- Phase 8: Network Visualization — topology map, Wake-on-LAN
