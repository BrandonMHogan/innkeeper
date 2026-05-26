# Python Coding Standards — Innkeeper

HOW to write Python code in this project. For library versions and quality gate commands, see `docs/architecture/tech-stack.md`.

---

## Module & File Structure

- One module per domain concern. A `devices/` package contains `router.py`, `service.py`, `models.py`, `schemas.py`.
- Route handlers live in `router.py`. Business logic lives in `service.py`. Never put business logic in route handlers.
- Keep modules small. If a file exceeds ~200 lines, split it.

## FastAPI

### Route Handlers
- All route handlers are `async def`. No synchronous route handlers.
- Route handlers are thin: validate input, call a service function, return a response model. No business logic inline.
- Register routers in `main.py` with a prefix and tags. One router per domain module.

```python
# router.py — thin handler, delegates to service
@router.post("/devices", response_model=DeviceResponse, status_code=201)
async def create_device(
    payload: CreateDeviceRequest,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(require_auth),
) -> DeviceResponse:
    # REQ: docs/specs/SPEC-XX.md#REQ-XX-01
    return await device_service.create(session, payload, owner_id=current_user.id)
```

### Request / Response Models
- Define separate Pydantic models for create, update, and read operations. Never reuse one model for all three.
- Name with the action prefix: `CreateDeviceRequest`, `UpdateDeviceRequest`, `DeviceResponse`.
- Response models are what the API promises to external callers — treat them as a contract.

### Dependency Injection
- Use `Depends` for: database sessions, auth checks, service configuration.
- Never instantiate `AsyncSession` inside a route handler directly — always via `Depends(get_session)`.
- Auth enforcement is a dependency, not an inline check.

### Error Handling
- Raise `HTTPException(status_code=..., detail="safe message")` for all client-facing errors.
- `detail` must be a safe, human-readable string — never an internal error message, stack trace, or raw exception.
- Define a global exception handler for domain exceptions (`ResourceNotFoundError → 404`, `ConflictError → 409`).
- Use explicit exception types in `try/except`. Never catch bare `except:` or `except Exception:` without logging.

```python
# correct: specific exception, safe detail
try:
    device = await device_service.get(session, device_id)
except ResourceNotFoundError:
    raise HTTPException(status_code=404, detail="Device not found")
```

---

## SQLAlchemy (Async)

### Session Management
- Use `AsyncSession` obtained via `Depends(get_session)` — never create sessions manually in service functions.
- Wrap writes in explicit transactions. Call `await session.commit()` after all writes in a transaction succeed.
- Use `async with session.begin()` for multi-step transactions that must be atomic.

```python
# correct: explicit transaction boundary
async def create_device(session: AsyncSession, payload: CreateDeviceRequest) -> Device:
    device = Device(**payload.model_dump())
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device
```

### Queries
- Use the SQLAlchemy 2.x `select()` API. Never use the legacy `session.query()` style.
- Avoid N+1 queries. Use `selectinload()` or `joinedload()` to eager-load relationships when you know you'll access them.
- Never execute raw SQL strings. Use the ORM or `text()` with bound parameters for complex queries.

```python
# correct: 2.x style with eager loading
stmt = select(Device).options(selectinload(Device.ports)).where(Device.id == device_id)
result = await session.execute(stmt)
device = result.scalar_one_or_none()
```

### Alembic Migrations
- Never edit a migration file that has already been applied. Always create a new migration.
- Every migration must implement both `upgrade()` and `downgrade()`.
- Migration files must be deterministic — no random values, no timestamp-dependent logic.

---

## APScheduler

### Job Design
- Every job function must catch all exceptions internally and log them at `ERROR` level. A job must never raise an unhandled exception to the scheduler.
- Jobs must be idempotent — safe to run twice without corrupting state or duplicating work.
- Jobs must complete quickly. If a task is long-running, offload it to a background thread/process pool.

```python
# correct: job with full exception guard
async def ping_all_devices():
    try:
        devices = await get_all_devices()
        await asyncio.gather(*(ping_device(d) for d in devices))
    except Exception as exc:
        logger.error("ping_all_devices failed: %s", exc)
```

### Job Registration
- Register all jobs in a dedicated `scheduler.py` module. Never register jobs inline in route handlers.
- Use the PostgreSQL job store for all persistent jobs. In-memory jobs do not survive container restarts.

---

## Pydantic

- Use `model_config = ConfigDict(from_attributes=True)` on response models that map from ORM objects.
- Use `Field(..., description="...")` on all fields in API-facing models.
- Use `model_validator(mode="after")` for cross-field validation.
- Do not use `orm_mode = True` (legacy v1 syntax). Use `ConfigDict`.

---

## Naming Conventions

| Thing | Convention | Example |
| :--- | :--- | :--- |
| Modules / files | `snake_case` | `device_service.py` |
| Classes | `PascalCase` | `DeviceService`, `CreateDeviceRequest` |
| Functions / methods | `snake_case` | `get_device_by_id` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_ATTEMPTS = 3` |
| Private functions | `_snake_case` prefix | `_build_filter_query` |
| Type aliases | `PascalCase` | `DeviceId = UUID` |
| Route handler functions | verb + noun | `create_device`, `list_devices`, `delete_device` |

---

## Import Order

1. Standard library (`os`, `asyncio`, `uuid`)
2. Third-party packages (`fastapi`, `sqlalchemy`, `pydantic`)
3. Local modules (`from app.devices import service`)

Let `ruff` enforce this automatically. Do not manually sort imports.

---

## Anti-Patterns

| ❌ Anti-Pattern | ✅ Correct Approach |
| :--- | :--- |
| Business logic in route handlers | Delegate to `service.py` |
| `session.query()` style queries | Use `select()` from SQLAlchemy 2.x |
| `except Exception: pass` | Catch specific types; always log |
| `time.sleep()` in async code | Use `asyncio.sleep()` |
| `requests.get()` in async code | Use `httpx.AsyncClient` |
| Returning ORM objects directly from routes | Always serialize through a Pydantic response model |
| Global mutable state | Use session-scoped or dependency-injected state |
| Calling `session.commit()` inside route handlers | Keep commit in the service layer |
