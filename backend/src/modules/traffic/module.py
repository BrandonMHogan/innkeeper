"""TrafficModule — constructor-injection factory satisfying HasAPIRoutes and
HasCollector, requires=[DeviceLookupInterface] (D-08).

On construction, wires the resolved DeviceLookupInterface instance into
routes.py's module-level accessor (set_device_lookup) so every route handler
in that file calls through the exact instance the ModuleLoader resolved from
the registry — not a second, independently constructed one (mirrors
DevicesModule's set_device_identity()/get_device_identity() pattern from
Plan 03).

run_collector(stop_event) satisfies HasCollector — the loader calls this
with a single asyncio.Event argument; update_snapshot_loop's internal
mechanics (stop_event.is_set()/asyncio.wait_for) are unchanged.
"""

import asyncio

from fastapi import APIRouter

from src.modules.device_identity.interfaces import DeviceLookupInterface
from src.modules.traffic import routes
from src.modules.traffic.broadcaster import update_snapshot_loop


def _live_session_factory():
    """Re-imports src.database and constructs a fresh async_sessionmaker
    bound to whatever `src.database.engine` currently is, on every call —
    not resolved once and cached (Rule 1 fix, Plan 04, mirrors
    device_identity/module.py's _live_session_factory). _load_native_modules()
    runs once at module-import time (create_app()), before any per-test
    monkeypatch of src.database.engine can take effect; binding a session
    factory to a literal `engine` reference at that moment would
    permanently miss the test fixture's migrated/schema-translated engine.
    update_snapshot_loop calls `session_factory()` once per tick (every 7s),
    so resolving fresh on every call lets tests' monkeypatch take effect."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    import src.database as database_module

    return async_sessionmaker(database_module.engine, expire_on_commit=False)()


class TrafficModule:
    def __init__(self, device_lookup: DeviceLookupInterface, session_factory) -> None:
        self.device_lookup = device_lookup
        self._session_factory = session_factory
        routes.set_device_lookup(device_lookup)

    def get_router(self) -> APIRouter:
        return routes.router

    async def run_collector(self, stop_event: asyncio.Event) -> None:
        await update_snapshot_loop(stop_event, self._session_factory)


def create(deps: dict[type, object]) -> TrafficModule:
    """Constructor-injection factory (D-08) — requires=[DeviceLookupInterface]
    resolved by the ModuleLoader before this factory is called. Passes a
    callable that re-resolves the live engine on every invocation rather
    than a session factory bound to a literal engine captured once at
    create()-time (mirrors device_identity/module.py's create())."""
    return TrafficModule(deps[DeviceLookupInterface], _live_session_factory)
