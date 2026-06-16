# Phase 1: Foundation + Capture Feasibility - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-16
**Phase:** 1-Foundation + Capture Feasibility
**Areas discussed:** Capture topology, Auth implementation, Docker service structure

---

## Capture Topology

| Option | Description | Selected |
|--------|-------------|----------|
| macOS Docker (original assumption) | Docker Desktop on macOS, native macOS agent fallback | |
| Linux machine (bare metal or VM) | Deployment target is Linux — Docker host networking works natively | ✓ |

**User's choice (freeform):** "we don't need it to be a docker macOS. its going to run on a linux distro. Either directly on a linux box of some kind, or on a PC using a linux virtual."

**Notes:** This fundamentally changed the Phase 1 premise. The macOS Docker host-networking constraint (listed as a HARD GATE in STATE.md) does not apply. Linux containers with `network_mode: host` work natively. PLAT-03 native macOS agent fallback is not needed.

---

| Option | Description | Selected |
|--------|-------------|----------|
| Container with host networking | Docker container with network_mode: host + CAP_NET_RAW/CAP_NET_ADMIN | ✓ |
| Host process (no Docker for capture) | Native process outside Docker | |
| You decide | Leave to researcher/planner | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Prove ARP broadcast visibility only | Spike confirms LAN ARP visibility | |
| Prove ARP + write one sample record to DB | End-to-end: capture ARP → write to PostgreSQL | ✓ |
| Skip formal spike, just scaffold the container | Linux networking is well-understood | |

**Notes:** User wants the spike to be a real end-to-end proof: capture → API → PostgreSQL row.

---

## Auth Implementation

| Option | Description | Selected |
|--------|-------------|----------|
| httpOnly cookie | Signed, XSS-safe, auto-sent | ✓ |
| JWT in localStorage | Stateless, exposed to XSS | |
| JWT in httpOnly cookie | Middle ground | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Redirect to /setup page | All routes redirect until password set | ✓ |
| Embedded modal on first visit | Dashboard loads, mandatory modal appears | |
| CLI setup before compose up | No in-UI wizard | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Any non-empty password | No minimum length or complexity | ✓ |
| Minimum 8 characters | Light enforcement | |
| You decide | Leave policy to implementor | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Never expire automatically | Invalidated only on password change | ✓ |
| Expire after 30 days of inactivity | Light expiry | |
| Expire after 24 hours (always) | Aggressive, overkill for home tool | |

---

## Docker Service Structure

| Option | Description | Selected |
|--------|-------------|----------|
| 4 services from day 1 | api, frontend, db, capture | ✓ |
| 3 services — skip capture | Add capture in Phase 2 | |
| 2 services — api + db only | Minimal skeleton | |

---

**Port selection (user freeform):** User said "can we use a custom port instead of 80 or 8080. like 445 or something" — noted that 445 is SMB. User selected 9999 ("all nines").

| Option | Description | Selected |
|--------|-------------|----------|
| 8888 | Common alt-HTTP port | |
| 9090 | Clean, Prometheus default | |
| 8444 | Evokes HTTPS without TLS | |
| 9999 (freeform) | All nines, memorable | ✓ |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Auth shell only | /setup, /login, empty /dashboard | ✓ |
| Full nav structure, empty pages | All routes scaffolded | |
| You decide | Leave to planner | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Frontend calls API via host port | Browser → host IP directly, no reverse proxy | ✓ |
| Nginx reverse proxy inside Docker | 5th service in Phase 1 | |
| FastAPI serves the frontend | Coupled deploy | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| .env file with docker compose | Standard 12-factor, .env.example committed | ✓ |
| Docker secrets | Requires Swarm mode, overkill | |
| Hardcoded defaults | Risk of secrets in images | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| API container runs Alembic on startup | `alembic upgrade head` before serving | ✓ |
| Separate migration container | Init container pattern, more complex | |
| Manual — user runs migrations | More control, more friction | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Proof-of-concept only | Captures ARP, writes to DB, done | ✓ |
| Scaffold full capture service interface | Final API surface with minimal logic | |
| You decide | Leave to planner | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic migration in Phase 1 (Recommended) | Create hypertable now, avoid later schema pain | ✓ |
| Phase 3 when traffic data lands | Add when needed | |
| You decide | Leave timing to planner | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| SvelteKit static build in lightweight container | adapter-static + nginx, port 9999 | ✓ |
| SvelteKit dev server in Docker | Not for production-like access | |
| FastAPI serves frontend | Coupled deploy | |

---

| Option | Description | Selected |
|--------|-------------|----------|
| Direct DB write | Capture → PostgreSQL directly | |
| POST to the API | Capture → FastAPI → PostgreSQL | ✓ |
| You decide | Leave IPC to researcher | |

**Notes:** User wants API as the single point of truth for all writes. Capture service POSTs to the API even in the Phase 1 spike.

---

| Option | Description | Selected |
|--------|-------------|----------|
| docker compose up for everything | Full stack via Docker, volumes for hot reload | ✓ |
| API and frontend run natively, DB in Docker | Faster iteration, more local setup | |
| Mix — DB in Docker, services native when working | Flexible but more context switching | |

---

## Claude's Discretion

- API port selection (internal to Docker Compose)
- Health check configuration for each service
- Docker Compose network name and internal service DNS names
- Session cookie signing implementation details
- Specific nginx config for the frontend container

## Deferred Ideas

None — discussion stayed within Phase 1 scope.
