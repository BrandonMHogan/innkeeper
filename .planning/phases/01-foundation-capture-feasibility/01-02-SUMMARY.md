---
phase: 01-foundation-capture-feasibility
plan: 02
subsystem: infra/capture
tags: [docker-compose, scapy, timescaledb, lima, networking]

requires:
  - phase: 01-foundation-capture-feasibility
    provides: backend (FastAPI auth + capture-ingest routes), frontend (SvelteKit SPA)
provides:
  - "Scapy ARP-capture proof-of-concept service (capture/)"
  - "Final 4-service docker-compose.yml topology (db, api, frontend, capture)"
  - "Confirmed go/no-go: real LAN ARP capture into PostgreSQL works end-to-end"
affects: [phase-02-discovery, phase-03-bandwidth]

tech-stack:
  added: [scapy, httpx (capture service), Lima (macOS dev-only VM tooling)]
  patterns:
    - "Capture service: network_mode: host + cap_add [NET_RAW, NET_ADMIN], never --privileged"
    - "Same-origin frontend/API via nginx reverse-proxy (not cross-port + CORS) to avoid SameSite cookie issues"
    - "Runtime-detected trust boundary (default gateway via /proc/net/route) instead of hardcoded IPs, for Docker hairpin-NAT-aware loopback checks"

key-files:
  created:
    - capture/Dockerfile
    - capture/capture.py
    - capture/requirements.txt
    - docker-compose.yml
    - backend/tests/test_compose.py
    - lima/innkeeper.yaml
    - scripts/dev-vm.sh
  modified:
    - backend/alembic/versions/0001_initial.py
    - backend/src/routes/capture.py
    - frontend/src/lib/api.ts
    - frontend/nginx.conf
    - .env.example
    - .gitignore

key-decisions:
  - "macOS has no real Linux host to test D-05 against, and Docker Desktop's NAT isolation can't see real LAN ARP traffic — solved with a Lima VM using bridged (not shared/NAT) networking, giving a genuine LAN-routable IP. This is dev-only tooling; the real Linux deployment target needs none of it (documented in docs/dev/mac_setup.md and README.md)."
  - "Frontend and API are same-origin via an nginx /api/ reverse-proxy, not cross-port with CORS — SameSite=Lax session cookies are never sent on cross-site fetch() calls, which silently broke login (200 on /login, immediate 401 on /me). This also fixes a second latent bug: PUBLIC_API_URL was previously baked into the frontend as a literal IP at build time, breaking on any DHCP IP change."
  - "capture.py's loopback-only ingest check failed for the actual deployment topology: capture runs network_mode: host (required for real LAN access) while api runs on the Docker bridge network, so capture's loopback-originated traffic arrives at api hairpin-NATed to the bridge gateway IP, not 127.0.0.1. Fixed by detecting the gateway at runtime via /proc/net/route (never hardcoded) and trusting it alongside loopback — preserves the original security intent since genuine external LAN traffic's source IP is not NATed this way."
  - "create_hypertable() auto-creates an index that the migration then tried to create again — made idempotent with CREATE INDEX IF NOT EXISTS."

requirements-completed: [PLAT-01, PLAT-02, PLAT-03]

duration: ~3h (including live debugging across 3 follow-up quick tasks)
completed: 2026-06-18
---

# Phase 1: Capture + Compose Feasibility Spike Summary

**Full 4-service docker-compose stack (db/api/frontend/capture) verified live on a real bridged-network Linux VM — confirmed a genuine LAN ARP packet flows capture → API → PostgreSQL (D-05 go/no-go: PASS).**

## Performance

- **Duration:** ~3h total (Task 1 auto-execution + live verification + 3 bug-fix quick tasks discovered during real browser/network testing)
- **Tasks:** 2 (Task 1: capture service + compose topology; Task 2: human-verify checkpoint)
- **Files modified:** 13 across this plan and 3 follow-up quick tasks

## Accomplishments

- Scapy-based ARP capture service (`capture/capture.py`) with graceful SIGTERM shutdown — `docker compose down` completes in ~10s, never hangs
- Final 4-service `docker-compose.yml`: `db` (TimescaleDB), `api`, `frontend`, `capture` (network_mode: host, `cap_add: [NET_RAW, NET_ADMIN]`, never `--privileged`)
- **D-05 go/no-go gate: PASS** — verified with a real LAN ARP packet captured live (not simulated), confirmed via direct DB query
- Full browser-based UAT: setup → login → dashboard works end-to-end from a real browser against a real bridged LAN IP
- Lima VM dev tooling (`scripts/dev-vm.sh`) so any Mac can reproduce this exact verification without Docker Desktop's network limitations

## Task Commits

1. **Task 1: Capture service + docker-compose.yml topology** — `7a8ece6` (feat)
2. **Task 2: Human-verify checkpoint** — resolved via live debugging (see Issues Encountered), no single commit; see quick tasks below

**Follow-up fixes discovered during live verification** (each its own atomic quick task per project GSD workflow):
- `b6c0612` — fix: idempotent `bandwidth_metrics_time_idx` index creation (alembic migration collision)
- `0b6f8ec` — fix: same-origin nginx proxy for `/api/` (quick-260618-coa, Task 1)
- `455e8d4` — fix: `API_BASE` fallback defaults to empty string, not hardcoded `localhost:8000` (quick-260618-coa, Task 2 root-cause)
- `8054f07` — fix: capture ingest trusts runtime-detected Docker bridge gateway, not just literal loopback (quick-260618-dcc)
- `fefb67c`, `1b57771` — Lima VM dev tooling and its own bug fixes (quick-260618-bmk)

## Files Created/Modified

- `capture/capture.py` — Scapy ARP sniff loop, POSTs to `/api/capture/arp`, SIGTERM-safe shutdown
- `capture/Dockerfile`, `capture/requirements.txt` — capture service build
- `docker-compose.yml` — final 4-service topology
- `backend/tests/test_compose.py` — automated compose health test (requires Docker daemon; not runnable in this sandbox, covered by live verification instead)
- `backend/alembic/versions/0001_initial.py` — idempotent index creation fix
- `backend/src/routes/capture.py` — runtime gateway-detection trust boundary fix
- `frontend/src/lib/api.ts`, `frontend/nginx.conf` — same-origin API proxy fix
- `lima/innkeeper.yaml`, `scripts/dev-vm.sh` — macOS-only dev VM tooling (not part of production deployment)

## Decisions Made

See `key-decisions` in frontmatter — all four are substantive fixes that came directly out of attempting real (not simulated) verification, exactly the value this checkpoint type is designed to catch.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Idempotent migration index creation**
- **Found during:** First live `docker compose up` against a fresh TimescaleDB volume
- **Issue:** `create_hypertable()` auto-creates `bandwidth_metrics_time_idx`; the migration's explicit `op.create_index()` then collided with it (`DuplicateTableError`), crashing the `api` container on every fresh deploy
- **Fix:** Replaced with `CREATE INDEX IF NOT EXISTS`
- **Committed in:** `b6c0612`

**2. [Rule 1 - Bug] Cross-origin session cookie never persisted**
- **Found during:** Real browser login test — `/login` returned 200 with `Set-Cookie`, but the immediate `/me` check returned 401
- **Issue:** Frontend (port 9999) and API (port 8000) were different origins; `SessionMiddleware`'s `SameSite=Lax` cookie is never sent on cross-site `fetch()` calls (only top-level GET navigations) — invisible to unit tests since Starlette's `TestClient` doesn't enforce real browser cookie policy
- **Fix:** nginx reverse-proxies `/api/` to the `api` service, making frontend and API same-origin from the browser's perspective; also fixed the underlying `api.ts` fallback (`?? 'http://localhost:8000'`) which silently defeated even the empty-`PUBLIC_API_URL` config because SvelteKit excludes empty-valued `PUBLIC_` env vars from `import.meta.env` entirely
- **Committed in:** `0b6f8ec`, `455e8d4`

**3. [Rule 1 - Bug] Capture ingest always rejected with 403**
- **Found during:** Attempting the actual D-05 go/no-go test — capture's POST to `/api/capture/arp` always failed with `403 Forbidden`
- **Issue:** `capture` runs `network_mode: host` (required for real LAN access) while `api` runs on the Docker bridge network; Docker's hairpin NAT rewrites capture's loopback-originated traffic to the bridge gateway IP (e.g. `172.18.0.1`) by the time it reaches `api`, so the literal `127.0.0.1`/`::1` check never matched
- **Fix:** Detect the default gateway at runtime via `/proc/net/route` (never hardcoded — verified no literal subnet appears anywhere in the file) and trust it alongside loopback. Fails safe to loopback-only if the file can't be read/parsed. Two new regression tests added.
- **Committed in:** `8054f07`

---

**Total deviations:** 3 auto-fixed (all Rule 1 - real bugs blocking the checkpoint's actual verification, not scope creep)
**Impact on plan:** None of these were optional polish — each one silently broke the exact behavior the checkpoint exists to verify (a working compose stack with real browser auth and real ARP capture). Catching them required actually running the stack, which is precisely why this plan has a `checkpoint:human-verify` gate instead of relying on unit tests alone.

## Issues Encountered

- **Worktree infrastructure bug:** Early in phase execution, `isolation="worktree"` dispatch produced a worktree checked out from a completely unrelated commit history (no shared ancestor with `main`). Both affected executors correctly halted via the `worktree_branch_check` guard without making any changes. Recovered by disabling worktree isolation for the remainder of this session (sequential execution on the main tree).
- **Lima VM setup required several rounds of debugging** (chown/sudoers path requirements for `socket_vmnet`, a `{{.User}}` templating bug in the `message:` field, and a uid-1000 assumption that doesn't hold when Lima matches the host's real UID) — all fixed and documented in `docs/dev/mac_setup.md`.
- **`.env` heredoc paste corruption** during manual setup (leading whitespace from terminal indentation, unterminated heredoc) — recovered by having the user re-run cleanup commands; no secrets were exposed in this conversation.

## User Setup Required

None for production (a real Linux host just needs `docker compose up`). For macOS local development/testing, see `docs/dev/mac_setup.md` (Lima VM bridged-network setup, one-time `brew install lima socket_vmnet` plus sudoers configuration).

## Next Phase Readiness

- **D-05 go/no-go gate: PASS** — Phase 2 (discovery) can proceed; the chosen capture topology (network_mode: host + Scapy) is proven to see real LAN traffic.
- PLAT-01/02/03 all confirmed via live multi-device-equivalent testing (curl from outside the VM simulating a different LAN device, real browser UAT).
- No blockers carried forward beyond the existing Phase 2/3 concerns already tracked in STATE.md (MAC-randomization identity model, TimescaleDB schema decisions).

---
*Phase: 01-foundation-capture-feasibility*
*Completed: 2026-06-18*
