<!-- GSD:project-start source:PROJECT.md -->

## Project

**Innkeeper**

Innkeeper is a self-hosted home network monitoring and management platform. It runs on a local server (Mac Mini or similar) and gives you full visibility into your network — connected devices, live traffic, bandwidth usage per device, and security issues. It operates in two modes: **home mode** (deep router integration for full control) and **travel mode** (passive scanning to secure your own devices on untrusted networks). Designed for a single user/household but architected from day one for open-source distribution and potential commercial use.

**Core Value:** See every device on your network and what it's doing, in real time — and be able to act on it.

### Constraints

- **Portability**: No machine-specific or network-specific assumptions anywhere — must work on any Docker-capable machine joined to any network
- **Self-hosted only**: All data stays local; no cloud services required for any core feature
- **Deployment via Docker Compose**: The full stack (backend, frontend, DB, optional integrations) must be launchable with `docker compose up`
- **Router-agnostic core**: Router integrations are adapters — the core platform must function (in limited mode) with no router integration at all
- **Data privacy**: Network traffic data is sensitive; no telemetry, no external calls unless user explicitly configures an integration

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## CRITICAL FINDING — Resolve Before Roadmap

## Recommended Stack

### Language & Runtime

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Python | **3.13.x** | Backend runtime | Required by `aiounifi`; latest stable; best free-threading / perf story for 2026 greenfield. **Overrides the 3.12 decision in PROJECT.md.** |
| Node.js | **22 LTS** (or 24) | Frontend build/runtime | Vite 6 + SvelteKit 2 target; 22 is current LTS |

### Core Backend Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| FastAPI | **0.136.x** | HTTP API, dependency injection, OpenAPI | Async-native, Pydantic v2 default, huge ecosystem. Latest as of Apr 2026 |
| Pydantic | **2.13.x** | Validation / settings / serialization | Rust-core (`pydantic-core`), 5–50× faster than v1; FastAPI requires >=2.9 |
| pydantic-settings | **2.x** | Typed env/config loading | Standard companion for 12-factor config in Docker |
| Uvicorn | **0.3x** (latest) | ASGI server | The standard FastAPI server. Run with `--workers` or behind Gunicorn for multi-proc |
| uvloop | latest | Event loop accelerator | Drop-in `asyncio` speedup on Linux containers; meaningful for high-concurrency SSE + scanning |

### Real-Time (SSE)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| sse-starlette | **latest (2.x+)** | `EventSourceResponse` for FastAPI | Production-grade W3C SSE: handles keep-alive pings, disconnect detection, multi-channel. Don't hand-roll SSE |

### Database & Time-Series

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| PostgreSQL | **17** | Primary datastore | TimescaleDB 2.27 fully supports PG 15–18; PG 17 is the safe, mature sweet spot (avoid PG 15 — last TimescaleDB support ends June 2026) |
| TimescaleDB | **2.27.x** | Hypertables for bandwidth/traffic metrics | SQL-native time-series in the same DB as config/registry; Grafana-compatible; no separate query language. Released 2026-05-12 |
| SQLAlchemy | **2.0.x** (async) | ORM / query layer | 2.0 async mode is the modern standard; massive latency wins reported in 2026 prototypes |
| asyncpg | **latest** | Async PG driver | Fastest async driver; SQLAlchemy async uses it under the hood; ideal for high-ingest time-series writes |
| Alembic | **latest** | Schema migrations | Standard with SQLAlchemy; you'll run a migration to create hypertables (see pattern below) |

### Network Inspection & Discovery

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Scapy | **2.7.x** | Packet crafting, ARP discovery, sniffing | The standard for ARP scanning + low-level packet work; can replace arping/arp-scan. Released Dec 2025 |
| python-zeroconf | **0.149.x** (latest 1.0 line emerging) | mDNS / Bonjour service discovery | Pure-Python, async API (`AsyncZeroconf`), actively maintained, used by Home Assistant. The de-facto mDNS lib |
| python-nmap (**home-assistant-libs fork**) | latest fork | Port/service scanning via system nmap | **Use the `home-assistant-libs/python-nmap` fork — the original xael/python-nmap on PyPI is unmaintained.** Wraps the `nmap` binary (must be installed in the container) |
| (system) nmap | latest in base image | Actual scanning engine | Install via `apt-get install nmap` in the backend Dockerfile; the Python lib is just a wrapper |
| mac-vendor-lookup | latest | MAC → vendor (OUI) resolution | Offline OUI lookup for device discovery; avoids per-lookup network calls |

### Router Integration (Adapter Pattern)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| aiounifi | **91** | UniFi Network Controller async client | Maintained by Kane610, used by Home Assistant's UniFi integration; the standard async UniFi lib. **Forces Python >= 3.13** |
| aiohttp | **>3.9** | HTTP transport (transitive via aiounifi) | aiounifi dependency; you'll likely have it anyway |

### Notifications

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| httpx | **latest** | Async HTTP client (ntfy.sh + Pushover + general) | ntfy.sh and Pushover are both simple REST/POST APIs — a thin internal client over `httpx` is cleaner and lighter than any SDK |
| (optional) Apprise | latest | Multi-backend notification abstraction | If you want one library spanning ntfy/Pushover/email/Telegram/etc., Apprise is the mature standard. Good fit for a "configurable alert channels" feature |

### Frontend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Svelte | **5.56.x** | UI framework | Runes-based reactivity, compiler-first, small bundles. Latest stable line |
| SvelteKit | **2.65.x** | App framework / routing / build | Current major; Svelte 5 + Vite 6 support; use the `sv` CLI to scaffold (not the deprecated `create-svelte`) |
| Vite | **6.x** | Build tool / dev server | SvelteKit 2's bundler |
| TypeScript | **5.x / 6.0** | Typing | PROJECT.md requirement; SvelteKit added TS 6.0 support in 2026 |
| native `EventSource` | browser API | SSE client | No library needed — browser-native `EventSource` auto-reconnects; pairs directly with sse-starlette |

### CLI (power-user interface)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Typer | latest | CLI framework | Built by the FastAPI author, Pydantic-friendly, type-hint driven; reuses backend models/services |
| Rich | latest | Terminal formatting | Tables/colors for device lists; pairs with Typer |

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Python version | 3.13 | 3.12 (per PROJECT.md) | aiounifi requires >=3.13; pinning old aiounifi means stale critical dependency |
| ASGI server | Uvicorn (+Gunicorn optional) | Granian | Granian is ~20–50% faster on CPU-bound but younger; gap is small for I/O-bound API + SSE; Uvicorn is the FastAPI standard with best operational familiarity |
| ASGI server | Uvicorn | Hypercorn | Hypercorn's edge is HTTP/3/QUIC/Trio — not needed for a LAN dashboard |
| Packet parsing (hot path) | Scapy for discovery; router counters/dpkt for bandwidth | Scapy for everything | Scapy is ~130× slower than dpkt for bulk parsing; don't parse every packet in Scapy |
| Deep protocol dissection | Scapy (+dpkt) | pyshark/tshark | pyshark is slowest and pulls in Wireshark; only if a security feature truly needs Wireshark dissectors |
| nmap wrapper | home-assistant-libs/python-nmap fork | original python-nmap (xael) | Original is unmaintained |
| mDNS | python-zeroconf | aiozeroconf | aiozeroconf is stale; python-zeroconf is now async and actively maintained |
| TimescaleDB access | SQLAlchemy 2.0 async + explicit `create_hypertable` SQL | sqlalchemy-timescaledb dialect | Dialect is a thin, lightly-maintained wrapper (v0.4.x); explicit SQL gives full control over hypertables, retention, continuous aggregates |
| DB driver | asyncpg | psycopg3 | Both excellent; asyncpg is fastest for async time-series ingest and is SQLAlchemy-async default |
| Notifications | httpx + thin client (or Apprise) | PyPI `ntfy` package | That package is an unrelated CLI, not an ntfy.sh client |
| Real-time transport | SSE (sse-starlette) | WebSockets | Per PROJECT.md: data flows server→client only; SSE auto-reconnects, proxy-friendly, simpler. Correct call |
| Frontend deploy | adapter-static (SPA) | SvelteKit Node SSR | SSR server is unnecessary overhead for a local-only dashboard |

## Installation

# Backend (Python 3.13) — use uv or pip

# python-nmap: install the maintained fork explicitly, e.g.

#   uv add "python-nmap @ git+https://github.com/home-assistant-libs/python-nmap"

# (verify the fork's current PyPI/publish status before pinning)

# Frontend (Node 22 LTS)

# select: SvelteKit, TypeScript, adapter-static for SPA

## Docker Compose Service Patterns

# backend — needs host network access for packet capture + ARP + mDNS

## Confidence Summary

| Layer | Recommendation | Confidence | Note |
|-------|---------------|------------|------|
| Python version bump to 3.13 | Adopt 3.13 | HIGH | Read from aiounifi pyproject.toml |
| FastAPI / Pydantic v2 | 0.136 / 2.13 | HIGH | Verified PyPI Apr 2026 |
| SSE via sse-starlette | Use it | HIGH | Standard, documented best practices |
| PostgreSQL 17 + TimescaleDB 2.27 | Use it | HIGH | Verified release 2026-05-12 |
| SQLAlchemy 2.0 async + asyncpg + explicit hypertable SQL | Use it | MEDIUM-HIGH | Pattern sound; dialect lib intentionally avoided |
| Scapy 2.7 for discovery | Use it | HIGH | Verified Dec 2025 release |
| Bandwidth hot-path parsing | Avoid Scapy per-packet | MEDIUM | Travel-mode accounting needs phase research |
| python-zeroconf | Use it | HIGH | Active, async, HA-backed |
| python-nmap fork | Use HA-libs fork | MEDIUM-HIGH | Confirm fork's PyPI publish status before pinning |
| aiounifi 91 | Use it (drives 3.13) | HIGH | Verified PyPI 2026-05-25 |
| Notifications via httpx/Apprise | Use it; avoid `ntfy` pkg | HIGH | Confirmed `ntfy` pkg is unrelated CLI |
| Svelte 5.56 / SvelteKit 2.65 / Vite 6 | Use them; `sv` CLI | HIGH | Verified npm June 2026 |
| Docker capture on macOS | Real constraint | HIGH (problem) / MEDIUM (fix) | Needs early architecture research |

## Sources

- [aiounifi · PyPI](https://pypi.org/project/aiounifi/) and [pyproject.toml](https://github.com/Kane610/aiounifi/blob/master/pyproject.toml) — v91, requires-python >=3.13
- [fastapi · PyPI](https://pypi.org/project/fastapi/) / [Release Notes](https://fastapi.tiangolo.com/release-notes/) — 0.136.x, Pydantic 2.13
- [TimescaleDB 2.27.0 release](https://github.com/timescale/timescaledb/releases/tag/2.27.0) — 2026-05-12, PG15–18
- [scapy · PyPI](https://pypi.org/project/scapy/) / [Releases](https://github.com/secdev/scapy/releases) — 2.7.x
- [python-zeroconf](https://github.com/python-zeroconf/python-zeroconf) — async, actively maintained
- [home-assistant-libs/python-nmap](https://github.com/home-assistant-libs/python-nmap) — maintained fork (original unmaintained)
- [sse-starlette](https://github.com/sysid/sse-starlette) / [FastAPI SSE docs](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [Granian vs Uvicorn vs Hypercorn](https://blog.hashhackers.com/blog/granian-uvicorn-asgi/) / [FastAPI deployment](https://fastapi.tiangolo.com/deployment/manually/)
- [Scapy vs dpkt vs pyshark benchmark](https://oneuptime.com/blog/post/2026-03-20-compare-scapy-dpkt-pyshark-ipv4/view)
- [svelte npm](https://www.npmjs.com/package/svelte) (5.56.x) / [@sveltejs/kit npm](https://www.npmjs.com/package/@sveltejs/kit) (2.65.x)
- [ntfy.sh publish API](https://docs.ntfy.sh/publish/) — header-based priority/tags via POST
- [SQLAlchemy vs asyncpg performance 2026](https://dasroot.net/posts/2026/02/python-postgresql-sqlalchemy-asyncpg-performance-comparison/)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

| Skill | Description | Path |
|-------|-------------|------|
| architect | > Activates the Architect role for gathering requirements, writing specs, and defining system boundaries before any code is written. Use when starting a new feature, planning a change, or drafting a specification. Trigger phrases: "architect", "write a spec", "gather requirements", "plan this feature", "act as architect". | `.claude/skills/architect/SKILL.md` |
| implementor | > Activates the Implementor role for writing production code that matches approved specifications. Use when a spec is approved and it's time to build. Trigger phrases: "implementor", "implement this", "write the code", "build the feature", "act as implementor", "start coding". | `.claude/skills/implementor/SKILL.md` |
| verifier | > Activates the Verifier role for writing tests, running the test suite, and ensuring full traceability between specs and tests. Use before or after implementation to validate correctness. Trigger phrases: "verifier", "write tests", "verify this", "run tests", "act as verifier", "TDAD". | `.claude/skills/verifier/SKILL.md` |
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- openspec-start -->

## Feature Development Process (OpenSpec + TDD)

Every feature is built spec-first using [OpenSpec](https://github.com/Fission-AI/OpenSpec) (Spec-Driven Development). GSD manages phases and roadmap; OpenSpec manages per-feature specs and TDD flow.

### Workflow per plan task

```
1. /opsx:propose   → write spec: requirements (MUST/SHALL), scenarios (Given/When/Then), design, tasks
2. Write tests     → extract scenarios from spec, write failing pytest tests (TDD red)
3. Implement       → write code to make tests pass (TDD green)
4. /opsx:sync      → align specs with implementation reality
5. /opsx:archive   → merge delta specs into openspec/specs/ living docs
6. GSD verify      → confirm phase success criteria via /gsd-verify-work
```

### Role skills for this project

Use the skills already installed in `.claude/skills/`:
- **architect** — use when proposing a feature (`/opsx:propose`), gathering requirements, writing specs
- **implementor** — use when implementing code against an approved spec
- **verifier** — use when writing tests from scenarios and verifying coverage

### Directory structure

```
openspec/
├── specs/          ← Living spec (grows as phases complete, one folder per domain)
│   ├── auth/
│   ├── discovery/
│   ├── traffic/
│   └── ...
└── changes/        ← In-flight feature work
    └── <feature>/
        ├── proposal.md
        ├── design.md
        ├── tasks.md
        └── specs/  ← Delta specs with Given/When/Then scenarios
```

### Spec quality rules

- Requirements use RFC 2119 keywords: **MUST**, **SHALL**, **SHOULD**, **MAY**
- Scenarios are concrete and testable: `Given [state] / When [action] / Then [outcome]`
- Delta specs describe what's changing — don't restate the whole system
- Good scenarios translate directly to pytest test functions

<!-- openspec-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
