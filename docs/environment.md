# Development Environment

**All agents: confirm the environment is healthy before running any test or quality gate command.**
See `docs/architecture/tech-stack.md §2` for the full list of quality gate commands.

---

## Stack Overview

The entire application runs inside Docker Compose. Do not install services directly on the host.

| Service | Description | Default Port |
| :--- | :--- | :--- |
| `db` | PostgreSQL — data persisted in Docker volume | 5432 |
| `backend` | FastAPI (Python 3.12) | 8000 |
| `frontend` | Svelte 5 via Vite dev server | 5173 |

---

## Starting the Stack

```bash
docker compose up --build
```

Confirm all services are running before proceeding:

```bash
docker compose ps
```

All services must show status `running` or `healthy`. If `db` is not healthy, wait for its healthcheck to pass before running any backend tests or migrations.

---

## Environment Variables

All environment variables are defined in `.env` at the project root. Do not hardcode values anywhere in application or test code.

| Variable | Purpose |
| :--- | :--- |
| `DATABASE_URL` | Backend → PostgreSQL (used at runtime inside the container) |
| `TEST_DATABASE_URL` | Test suite → PostgreSQL (separate test database on the same `db` service) |

---

## Test Database

Tests run against a separate database defined by `TEST_DATABASE_URL`. Before the first test run (and after any new migration), apply migrations:

```bash
docker compose exec backend alembic upgrade head
```

The test suite uses transaction-rollback fixtures — tests never commit to the database and require no reset between runs. See `docs/standards/testing.md` for the fixture pattern.

---

## Recovering from a Down Environment

If `pytest` fails with a connection error, the database service is not healthy. Start it first, then test:

```bash
docker compose up db -d
# wait for healthcheck to pass, then:
pytest
```

Do not proceed with implementation or verification steps if the environment is not healthy.
