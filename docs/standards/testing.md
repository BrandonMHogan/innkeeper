# Testing Standards — Innkeeper

HOW to write tests in this project. For test placement, naming, and traceability link format, see `docs/ai-skills/references/test-conventions.md`. For run commands, see `docs/architecture/tech-stack.md §2`.

---

## pytest (Backend)

### Fixtures

- Define fixtures in `conftest.py` at the appropriate scope level: test directory for local fixtures, root `tests/` for globally shared ones.
- Use `scope="session"` for expensive one-time setup (database engine, Docker containers).
- Use `scope="function"` (default) for anything involving mutable state — every test gets a clean copy.
- Never share mutable state between test functions via a module-level variable.

### Async Tests

- Configure `pytest-asyncio` with `asyncio_mode = "auto"` in `pyproject.toml`. All async test functions work without `@pytest.mark.asyncio`.
- Use `httpx.AsyncClient` with the FastAPI `app` for testing routes. Never use the synchronous `TestClient` for an async app.
- All async fixtures use `async def`.

**FastAPI async client fixture:**
```python
# tests/conftest.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
```

**Route test pattern:**
```python
async def test_create_device_returns_201(client: AsyncClient):
    # REQ: docs/specs/SPEC-02_devices.md#REQ-02-01
    response = await client.post("/devices", json={"name": "Router", "ip": "192.168.1.1"})
    assert response.status_code == 201
    assert response.json()["name"] == "Router"
```

### Database Tests

- Use a separate test database. Configure via `TEST_DATABASE_URL` environment variable.
- Wrap each test in a transaction that rolls back after the test. Never commit to the test database from tests — let the rollback fixture clean up.

**Transaction rollback fixture:**
```python
# tests/conftest.py
@pytest.fixture
async def db_session(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        async with AsyncSession(bind=conn) as session:
            yield session
            await session.rollback()
```

### Failure Mode Tests (`FC-XX-*`)

- Simulate database failures using `monkeypatch` on the session factory or connection pool.
- Simulate external service failures using `respx` for HTTP mocking.
- Assert on **both** the HTTP response AND the log output using `pytest`'s `caplog` fixture.
- The error response must match the exact status code and safe detail string defined in the spec.

**Failure mode test pattern:**
```python
async def test_db_unavailable_returns_503(client: AsyncClient, monkeypatch):
    # REQ: docs/specs/SPEC-02_devices.md#FC-02-01
    async def fail_get_session():
        raise ConnectionRefusedError("simulated db failure")

    monkeypatch.setattr("app.dependencies.get_session", fail_get_session)
    response = await client.get("/devices")

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"].lower()
```

### Log Assertions

When a spec requirement states a log entry must be emitted, assert on it:

```python
import logging

async def test_logs_error_on_db_failure(client: AsyncClient, monkeypatch, caplog):
    # REQ: docs/specs/SPEC-02_devices.md#FC-02-01
    with caplog.at_level(logging.ERROR):
        # ... trigger failure ...
        pass
    assert any("data store connection failed" in r.message for r in caplog.records)
```

---

## vitest (Frontend Unit)

### Component Tests

- Use `@testing-library/svelte` for mounting and interacting with components.
- Query priority: `getByRole` → `getByLabelText` → `getByText` → `getByTestId`. Never query by CSS class or element tag.
- Test observable behavior (what the user sees), not implementation details (which functions were called).

**Component test pattern:**
```typescript
import { render } from '@testing-library/svelte';
import DeviceCard from './DeviceCard.svelte';

test('shows offline badge when device is unreachable', () => {
    // REQ: docs/specs/SPEC-02_devices.md#REQ-02-06
    const { getByRole } = render(DeviceCard, { props: { status: 'offline' } });
    expect(getByRole('status')).toHaveTextContent('Offline');
});
```

### Async Component Tests

- Use `waitFor` from `@testing-library/svelte` for state that updates asynchronously.
- Never use `setTimeout` or `vi.advanceTimersByTime` for async UI updates — use `waitFor`.

```typescript
test('displays fetched devices after load', async () => {
    // REQ: docs/specs/SPEC-02_devices.md#REQ-02-04
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [{ id: '1', name: 'Router' }],
    }));

    const { getByText } = render(DeviceList);
    await waitFor(() => expect(getByText('Router')).toBeInTheDocument());

    vi.unstubAllGlobals();
});
```

### Mocking

- Mock `fetch` with `vi.stubGlobal('fetch', ...)`. Always restore with `vi.unstubAllGlobals()` in `afterEach`.
- Mock `EventSource` with a custom class when testing SSE-consuming components.
- Never mock internal module functions to avoid testing implementation details.

---

## playwright (E2E)

### Test Setup

- Each test must set up its own data via the API before asserting on the UI. Never rely on prior tests having created data.
- Use a dedicated test base URL configured via environment variable.
- Each test gets a fresh browser context — no shared cookies, local storage, or session state.

### Selectors

- Selector priority: `getByRole` → `getByLabel` → `getByText` → `getByTestId`.
- Add `data-testid` attributes only when no semantic selector exists. Define the attribute value in the spec §7.

**E2E test pattern:**
```typescript
test('user can add a device and see it in the list', async ({ page }) => {
    // REQ: docs/specs/SPEC-02_devices.md#REQ-02-01
    await page.goto('/devices');
    await page.getByRole('button', { name: 'Add Device' }).click();
    await page.getByLabel('IP Address').fill('192.168.1.100');
    await page.getByRole('button', { name: 'Save' }).click();
    await expect(page.getByText('192.168.1.100')).toBeVisible();
});
```

### Assertions

- Always `await` assertions: `await expect(locator).toBeVisible()`.
- Use `toBeVisible()` for elements that should appear. Use `toBeHidden()` or `not.toBeVisible()` for elements that should not.
- Never use `toBeTruthy()` on a locator — it always passes even if the element doesn't exist.

### Error Scenario Tests

- Use `page.route()` to intercept and mock API responses for error state testing:

```typescript
test('shows error banner when API returns 503', async ({ page }) => {
    // REQ: docs/specs/SPEC-02_devices.md#FC-02-01
    await page.route('/api/devices', route => route.fulfill({ status: 503 }));
    await page.goto('/devices');
    await expect(page.getByRole('alert')).toContainText('unavailable');
});
```

---

## Anti-Patterns

| ❌ Anti-Pattern | ✅ Correct Approach |
| :--- | :--- |
| `time.sleep()` / `asyncio.sleep()` in tests | `pytest-asyncio` `waitFor`, or proper async fixtures |
| Asserting on internal function calls instead of behavior | Assert on HTTP response, DOM state, or log output |
| Skipping tests without a spec reference | `pytest.skip("FC-02-01: known infra gap — fix by YYYY-MM-DD")` |
| `assert response.json() == { ...entire object... }` | Assert on specific fields relevant to the requirement |
| Committing to the test database | Use rollback fixtures — never commit from tests |
| Sharing test state via module-level variables | Use fixtures with appropriate scope |
| Querying by CSS class in frontend tests | Use `getByRole`, `getByLabel`, `getByText` |
| `toBeTruthy()` on a Playwright locator | `toBeVisible()` |
