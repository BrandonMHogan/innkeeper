# Spec: 01-Docker-Stack

* **Status:** Approved
* **Version:** 1.0.0
* **Last Updated:** 2026-05-26

---

## 1. Goal & Context
The goal of this module is to containerize the entire *Innkeeper* application using Docker and Docker Compose. This ensures the dashboard is fully OS-agnostic and hardware-agnostic, capable of running seamlessly on macOS, Windows (via WSL2), or Linux-based home servers/mini-PCs.

---

## 2. Dependencies
This is the foundational specification for the project repository. It has no external software dependencies but serves as the orchestration host for all future modules.

---

## 3. System Outcomes (What We Want)
* **Outcome 1**: A single command (`docker compose up --build`) spins up the entire local network monitoring environment.
* **Outcome 2**: The database container is fully healthy before the backend service attempts to run migrations or connect.
* **Outcome 3**: Network monitoring tools (`scapy`, `icmplib`) have the necessary raw socket and administrative packet privileges within their container.
* **Outcome 4**: High performance, hot-reloading development environment for Svelte 5 frontend and FastAPI backend.

---

## 4. Non-Goals (What We Do NOT Want)
* **Non-Goal 1**: Production SSL/TLS certificate generation (e.g. Let's Encrypt integration) inside the local development stack.
* **Non-Goal 2**: Setup of cloud orchestration tools (Kubernetes/ECS) or advanced CI/CD CD pipeline stages.

---

## 5. Tech Stack & Integration Points
* **Database**: PostgreSQL 16 (official Docker image) with persistent volumes.
* **Backend**: FastAPI running inside a Python 3.12 container.
* **Frontend**: Svelte 5 Single Page Application running in a Node 20+ container with Vite.
* **Networking**: Elevated Docker capabilities (`NET_ADMIN` and `NET_RAW`) assigned to the backend to allow deep scanning and ARP discovery.

---

## 6. Execution Tasks
- [ ] **Task 1 (Verifier)**: Create a bash-based integration test script (`tests/docker_stack/verify_stack.sh`) that asserts the existence of the Compose configuration, health check settings, and capability requirements.
- [ ] **Task 2 (Implementor)**: Create `.env.example` file.
- [ ] **Task 3 (Implementor)**: Create backend multi-stage `Dockerfile`.
- [ ] **Task 4 (Implementor)**: Create frontend `Dockerfile`.
- [ ] **Task 5 (Implementor)**: Create the root `docker-compose.yml`.
- [ ] **Task 6 (Verifier)**: Run the verification test script and confirm all containers boot, become healthy, and communicate correctly.

---

## 7. Acceptance Criteria (Strict Requirements)

### Multi-Container Orchestration
#### `REQ-01-01`: Service Definition
* **Behavior**: The `docker-compose.yml` file must define exactly three core services: `db`, `backend`, and `frontend`.
* **Verification**: Test script parses `docker-compose.yml` and asserts that `db`, `backend`, and `frontend` exist under the `services` key.

#### `REQ-01-02`: PostgreSQL Persistence & Version
* **Behavior**: The `db` service must run PostgreSQL 16+ and persist database files using a named volume called `postgres_data` mapped to `/var/lib/postgresql/data`.
* **Verification**: Test script verifies that `db` uses `image: postgres:16-alpine` (or similar 16.x) and has a volume named `postgres_data` declared at the root level and mapped under `volumes`.

#### `REQ-01-03`: FastAPI Multi-stage Build & Net Capabilities
* **Behavior**: The `backend` service must run a multi-stage Docker build with Python 3.12. It must possess elevated network capabilities `NET_ADMIN` and `NET_RAW` to allow execution of raw-packet tools like `scapy` and `icmplib`.
* **Verification**: Test script checks the backend Dockerfile for a multi-stage build structure and verifies that the `backend` service in `docker-compose.yml` contains `cap_add: [NET_ADMIN, NET_RAW]`.

#### `REQ-01-04`: Svelte 5 Node Environment
* **Behavior**: The `frontend` service must run in a Svelte 5 ready Node 20+ environment with hot-reloading supported.
* **Verification**: Test script inspects the frontend Dockerfile for base image `node:20` or higher.

### Connectivity & Resilience
#### `REQ-01-05`: Strict Health Checks & Startup Order
* **Behavior**: The `db` container must implement a health check using `pg_isready`. The `backend` container must wait to start until the `db` is fully healthy using a `depends_on` block with `condition: service_healthy`.
* **Verification**: Test script verifies the presence of `healthcheck` on `db` (with `pg_isready`) and the matching `depends_on` block on `backend`.

#### `REQ-01-06`: Environment Orchestration
* **Behavior**: All sensitive database credentials, API urls, and ports must be configurable via a root `.env` file, with safe defaults provided in a `.env.example` file.
* **Verification**: Verify that the project contains `.env.example` and that `docker-compose.yml` references these variables.
