"""Plan 03 Task 2 Test 2 — proves MOD-04's "core app boots with zero modules
enabled" criterion concretely for the devices module, not just the generic
ModuleLoader unit test in test_module_loader.py.

With zero ModuleConfig rows present (the default, untouched-by-any-test
state), require_module_enabled("devices") defaults to enabled — confirmed
here at the live FastAPI app level, not just is_module_enabled's own unit
test, by hitting the real GET /api/modules/devices/ route.
"""

import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.models.module_config import ModuleConfig


async def _login(client):
    await client.post("/api/auth/setup", json={"password": "correct-password"})
    login_response = await client.post("/api/auth/login", json={"password": "correct-password"})
    assert login_response.status_code == 200


async def test_app_boots_and_devices_route_reachable_with_zero_module_configs(client, test_db):
    """With zero rows in module_configs (the default state — no test in this
    suite seeds one for "devices"), the app has already booted successfully
    (the `client` fixture itself constructing src.main.app proves this), and
    GET /api/modules/devices/ returns 200, not 404 — devices defaults
    enabled."""
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        rows = (await db.execute(select(ModuleConfig))).scalars().all()
        assert rows == []

    await _login(client)
    response = await client.get("/api/modules/devices/")
    assert response.status_code == 200


async def test_devices_route_404s_when_explicitly_disabled(client, test_db):
    """Disabling the devices module via a ModuleConfig row causes
    GET /api/modules/devices/ to 404 (T-05-09) — the route is mounted
    regardless (FastAPI routers are append-only), but require_module_enabled
    gates every handler."""
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)
    async with session_maker() as db:
        db.add(ModuleConfig(module_id="devices", enabled=False))
        await db.commit()

    await _login(client)
    response = await client.get("/api/modules/devices/")
    assert response.status_code == 404


def test_devices_routes_contains_no_direct_canonical_data_query():
    """Plan 03 Task 2 Test 3 — grep-verified (not just visually inspected):
    devices/routes.py contains no direct select(Device)/select(DiscoveredIdentity)
    call. T-05-07's mitigation depends on this acceptance criterion actually
    being enforced, not just documented."""
    routes_path = Path(__file__).parent.parent / "src" / "modules" / "devices" / "routes.py"
    source = routes_path.read_text()
    matches = re.findall(r"select\(Device\)|select\(DiscoveredIdentity\)", source)
    assert matches == []
