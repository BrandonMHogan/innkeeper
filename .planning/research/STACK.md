# Technology Stack

**Project:** Innkeeper (self-hosted home network monitoring & management platform)
**Researched:** 2026-06-16
**Overall confidence:** HIGH (versions verified against PyPI / npm / official repos June 2026)

The architectural backbone (FastAPI, Svelte 5, PostgreSQL+TimescaleDB, SSE, Docker Compose) is already decided in PROJECT.md. This document confirms current versions, prescribes the supporting libraries for each layer, and flags one decision conflict that must be resolved before roadmap planning.

---

## CRITICAL FINDING — Resolve Before Roadmap

> **`aiounifi` requires Python >= 3.13.0, but PROJECT.md commits to Python 3.12.**
>
> `aiounifi` v91 (released 2026-05-25) sets `requires-python = ">=3.13.0"` in its `pyproject.toml`. The UniFi adapter is the first router integration target. You cannot install current `aiounifi` on Python 3.12.
>
> **Recommendation: adopt Python 3.13 as the project baseline.** Every other library below supports 3.13, and 3.13 is the right long-term choice for a greenfield 2026 project anyway. The alternative — pinning to an older `aiounifi` that still supported 3.12 — means shipping a stale, unmaintained dependency for the single most important integration. Not worth it.
>
> Confidence: **HIGH** (read directly from the library's `pyproject.toml`).

---

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

> **TimescaleDB + Python pattern:** Use SQLAlchemy 2.0 async + asyncpg for ORM modeling of regular tables (device registry, alerts, config). Create hypertables via an Alembic migration that runs `SELECT create_hypertable('bandwidth_samples', 'time')` as raw SQL after the table is created. Do **not** rely on `sqlalchemy-timescaledb` dialect as a hard dependency — it is a thin, lightly-maintained wrapper (v0.4.x); use plain SQLAlchemy + explicit `create_hypertable`/`add_retention_policy` SQL for full control and fewer surprises. Use TimescaleDB **continuous aggregates** for per-device rollups (hourly/daily bandwidth) instead of querying raw samples on every dashboard load. Confidence: **MEDIUM-HIGH**.

### Network Inspection & Discovery
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Scapy | **2.7.x** | Packet crafting, ARP discovery, sniffing | The standard for ARP scanning + low-level packet work; can replace arping/arp-scan. Released Dec 2025 |
| python-zeroconf | **0.149.x** (latest 1.0 line emerging) | mDNS / Bonjour service discovery | Pure-Python, async API (`AsyncZeroconf`), actively maintained, used by Home Assistant. The de-facto mDNS lib |
| python-nmap (**home-assistant-libs fork**) | latest fork | Port/service scanning via system nmap | **Use the `home-assistant-libs/python-nmap` fork — the original xael/python-nmap on PyPI is unmaintained.** Wraps the `nmap` binary (must be installed in the container) |
| (system) nmap | latest in base image | Actual scanning engine | Install via `apt-get install nmap` in the backend Dockerfile; the Python lib is just a wrapper |
| mac-vendor-lookup | latest | MAC → vendor (OUI) resolution | Offline OUI lookup for device discovery; avoids per-lookup network calls |

> **Packet-capture library decision (Scapy vs alternatives):** Scapy is correct for Innkeeper's needs (ARP discovery, targeted sniffing, packet crafting for active probes). Benchmarks show Scapy is **slow and memory-heavy for bulk PCAP parsing** (100k packets: dpkt 0.23s vs Scapy ~30s vs pyshark ~60s). Implications:
> - **For ARP discovery and control-plane probing:** Scapy. ✅
> - **For high-throughput continuous traffic accounting** (per-device bandwidth, top-talkers): do **not** parse every packet in Scapy. Prefer router-provided counters (UniFi API) in home mode, and in travel mode use lightweight flow accounting. If you must parse a live capture stream, consider **dpkt** for the hot path and reserve Scapy for crafting. Flag this for phase-specific research.
> - **pyshark** (tshark wrapper) is rich but the slowest and adds a Wireshark dependency — avoid for the hot path; only worth it if you need deep protocol dissection for a security feature.
> Confidence: **HIGH** on the recommendation, **MEDIUM** on the exact travel-mode accounting approach (needs phase research).

### Router Integration (Adapter Pattern)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| aiounifi | **91** | UniFi Network Controller async client | Maintained by Kane610, used by Home Assistant's UniFi integration; the standard async UniFi lib. **Forces Python >= 3.13** |
| aiohttp | **>3.9** | HTTP transport (transitive via aiounifi) | aiounifi dependency; you'll likely have it anyway |

> **Adapter pattern note:** Define a `RouterAdapter` Protocol/ABC (`list_clients()`, `block_client()`, `unblock_client()`, `get_traffic()`, etc.). `UniFiAdapter` wraps `aiounifi`. A `NullAdapter`/`PassiveAdapter` (no router) backs travel mode using Scapy/zeroconf/nmap only. This keeps `aiounifi`'s Python 3.13 constraint and any future router SDKs isolated behind the interface — exactly what the open-source/extensibility goal in PROJECT.md wants. Confidence: **HIGH**.

### Notifications
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| httpx | **latest** | Async HTTP client (ntfy.sh + Pushover + general) | ntfy.sh and Pushover are both simple REST/POST APIs — a thin internal client over `httpx` is cleaner and lighter than any SDK |
| (optional) Apprise | latest | Multi-backend notification abstraction | If you want one library spanning ntfy/Pushover/email/Telegram/etc., Apprise is the mature standard. Good fit for a "configurable alert channels" feature |

> **Notifications decision:** **Do NOT add the PyPI package named `ntfy` (dschep/ntfy).** It is an unrelated CLI tool, not a client for the ntfy.sh service, and is a common point of confusion. For ntfy.sh, POST to `https://ntfy.sh/<topic>` (or self-hosted URL) with `X-Title`, `X-Priority`, `X-Tags` headers via `httpx` — no dependency needed. For Pushover, POST to its `/1/messages.json` endpoint. If channel count grows, switch to **Apprise** for a unified abstraction. Confidence: **HIGH**.

### Frontend
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Svelte | **5.56.x** | UI framework | Runes-based reactivity, compiler-first, small bundles. Latest stable line |
| SvelteKit | **2.65.x** | App framework / routing / build | Current major; Svelte 5 + Vite 6 support; use the `sv` CLI to scaffold (not the deprecated `create-svelte`) |
| Vite | **6.x** | Build tool / dev server | SvelteKit 2's bundler |
| TypeScript | **5.x / 6.0** | Typing | PROJECT.md requirement; SvelteKit added TS 6.0 support in 2026 |
| native `EventSource` | browser API | SSE client | No library needed — browser-native `EventSource` auto-reconnects; pairs directly with sse-starlette |

> **Frontend deployment note:** For a self-hosted dashboard served behind FastAPI, use SvelteKit's `adapter-static` (SPA mode) and serve the built assets via the backend or a small nginx/Caddy container. You do **not** need SvelteKit's Node SSR server for a local dashboard — static build keeps the Docker Compose footprint minimal. Confidence: **MEDIUM-HIGH**.

### CLI (power-user interface)
| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Typer | latest | CLI framework | Built by the FastAPI author, Pydantic-friendly, type-hint driven; reuses backend models/services |
| Rich | latest | Terminal formatting | Tables/colors for device lists; pairs with Typer |

---

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

---

## Installation

```bash
# Backend (Python 3.13) — use uv or pip
uv add fastapi uvicorn[standard] uvloop pydantic pydantic-settings \
       sse-starlette \
       sqlalchemy[asyncio] asyncpg alembic \
       scapy "zeroconf>=0.149" mac-vendor-lookup \
       aiounifi httpx typer rich
# python-nmap: install the maintained fork explicitly, e.g.
#   uv add "python-nmap @ git+https://github.com/home-assistant-libs/python-nmap"
# (verify the fork's current PyPI/publish status before pinning)

# Frontend (Node 22 LTS)
npx sv create frontend        # the new SvelteKit scaffolder (replaces create-svelte)
# select: SvelteKit, TypeScript, adapter-static for SPA
```

System packages required inside the backend container: `nmap`, and `libpcap` (for Scapy live capture). Scapy live sniffing and ARP also require the container to run with appropriate network privileges (see Docker Compose patterns).

---

## Docker Compose Service Patterns

Patterns, not a full file — the roadmap/build phases will flesh these out.

```yaml
# backend — needs host network access for packet capture + ARP + mDNS
services:
  backend:
    build: ./backend            # base: python:3.13-slim + apt: nmap libpcap0.8
    # Packet capture / ARP / mDNS require L2 visibility. Options, in order of preference:
    #   network_mode: "host"    # simplest for discovery; Linux only (NOT on Docker Desktop/macOS)
    # OR grant capabilities if not using host networking:
    cap_add: ["NET_RAW", "NET_ADMIN"]   # required for Scapy raw sockets / ARP
    environment:
      - DATABASE_URL=postgresql+asyncpg://innkeeper:...@db:5432/innkeeper
      - UNIFI_HOST=...          # adapter config via env / pydantic-settings
    depends_on: [db]

  db:
    image: timescale/timescaledb:2.27.0-pg17   # official TimescaleDB image, PG17
    environment:
      - POSTGRES_DB=innkeeper
    volumes:
      - tsdb_data:/var/lib/postgresql/data     # named volume; retention is user-controlled, no auto-delete

  frontend:
    build: ./frontend           # static SvelteKit build served by nginx/caddy, OR mounted into backend
    depends_on: [backend]

volumes:
  tsdb_data:
```

> **Deployment caveat (HIGH importance):** The hardware target in PROJECT.md is a **Mac Mini**. Docker Desktop on macOS runs containers inside a Linux VM, so `network_mode: host` does NOT give true host-network/L2 access, and raw ARP/mDNS/packet capture from inside a container is unreliable on macOS. This directly affects **travel mode + passive discovery**. Mitigations to evaluate during roadmap: (a) run the discovery/capture component natively on the host (outside Docker) and have it talk to the containerized backend, or (b) target a Linux host for full passive-scanning fidelity and treat macOS as "home-mode / router-API primary." **Flag this for early architecture research** — it shapes how much of the stack can actually live in Docker. Confidence: **HIGH** that this is a real constraint; **MEDIUM** on the best mitigation.

---

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
