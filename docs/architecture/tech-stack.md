# Global Technical Stack & Architectural Standards

This document serves as the **Single Source of Truth (SSOT)** for the technology stack, development environments, and quality gate commands for the Innkeeper project. All modules, specifications, and agents working in this repository must align with the standards defined here.

**Before running any quality gate command:** confirm the development environment is healthy. See `docs/environment.md`.

---

## 1. Core Technology Stack

### 1.1 Backend
*   **Runtime:** Python 3.12+
*   **Web Framework:** FastAPI (async-first, using modern Pydantic v2 schemas and dependency injection).
*   **Database:** PostgreSQL.
    *   **ORM / Client:** SQLAlchemy (with `asyncpg` for asynchronous session pooling).
    *   **Migrations:** Alembic for automatic schema migrations.
*   **Background Scheduler:** APScheduler.
    *   **Job Store:** PostgreSQL-backed storage for persistence.
    *   **Design Pattern:** Strict transaction boundaries per job execution, safe exception handling, and error logging.
*   **System & Network Integration:**
    *   **ARP Discovery:** `scapy` for scanning local network segments.
    *   **ICMP Pinging:** `icmplib` for asynchronous, parallel latency checks.
    *   **Port Scanning:** `python-nmap` execution.
    *   **Docker Container Capabilities:** The backend Docker service requires elevated capabilities (`cap_add: [NET_ADMIN, NET_RAW]`) or `network_mode: host` to access raw network sockets for Scapy/ICMP.

### 1.2 Frontend
*   **Build Tool & Runner:** Vite.
*   **Framework:** Svelte 5 (compiled as a Single-Page Application (SPA)).
    *   **State Management:** Svelte 5 Runes (`$state`, `$derived`, `$effect`), bindable props, module-extracted store modules.
    *   **Styling:** Pure Vanilla CSS. Clean, responsive grids and flexbox layouts. Avoid TailwindCSS unless explicitly requested. Custom HSL theme colors, modern typography (Inter/Outfit), micro-animations, and glassmorphism styling are preferred.
*   **API Communication:**
    *   **State Transfer:** Async HTTP REST fetch operations using native `fetch`.
    *   **Real-time Streaming:** Server-Sent Events (SSE) strictly. **No WebSockets.**

### 1.3 Containerization & Environment
*   **Container Engine:** Docker & Docker Compose.
*   **Services:**
    *   `db`: PostgreSQL database with persistent volume mounting.
    *   `backend`: FastAPI application container with Python 3.12, using host network or raw packet capabilities.
    *   `frontend`: Svelte SPA served via standard Vite dev-server (development) or compiled static files served via Nginx (production).

---

## 2. CLI Quality Gates & Commands

All implementing and verifying agents **MUST** execute these commands to validate changes. No requirement is considered "Complete" until these quality checks pass.

### 2.1 Backend Commands (Python)
*   **Format & Lint Check:**
    ```bash
    ruff format --check . && ruff check .
    ```
*   **Apply Formatting & Lint Fixes:**
    ```bash
    ruff format . && ruff check --fix .
    ```
*   **Run Unit & Integration Tests:**
    ```bash
    pytest
    ```
*   **Run a Specific Test File:**
    ```bash
    pytest tests/path_to_test.py
    ```
*   **Verify Test Coverage (minimum 70% required — build fails below this threshold):**
    ```bash
    pytest --cov=app --cov-fail-under=70 tests/
    ```

### 2.2 Frontend Commands (TypeScript/JS/Svelte)
*   **Format & Lint Check:**
    ```bash
    npm run lint
    ```
*   **Run Unit & Component Tests:**
    ```bash
    npm run test
    ```
*   **Run a Specific Frontend Test File:**
    ```bash
    npx vitest run src/tests/path_to_test.test.ts
    ```
*   **Run End-to-End (E2E) Playwright Tests:**
    ```bash
    npx playwright test
    ```
*   **Full Production Build Compilation Check:**
    ```bash
    npm run build
    ```

---

## 3. SDD / TDAD Design Patterns & Verification Rules

### 3.1 Interface-First Implementation (SDD)
Before implementing any backend endpoint or frontend page, the agent must define:
1.  **Zod Schemas** or **TypeScript Interfaces** for all frontend data representations.
2.  **Pydantic Models** for all backend API endpoints.
3.  **SQL DDL Schemas** (Alembic models) representing table constraints.

These contracts must be documented directly in the corresponding module specification file under `/docs/specs/`.

### 3.2 Test-Driven Red-Green-Refactor Flow (TDAD)
1.  **Red Phase (Fail):** Tests asserting the new feature's behavior must be written *first*. The verifier agent must execute the tests and confirm they fail with the expected assertion errors.
2.  **Green Phase (Pass):** The minimum application logic necessary to satisfy the assertions is written. The implementor agent must run the tests and confirm they pass successfully.
3.  **Refactor Phase (Clean):** The code is refactored for clarity, performance, and structure. The verifier runs the tests again to guarantee zero regressions.
4.  **Static Analysis:** Linting and formatting checkers are run. Any failure in static analysis fails the build.
