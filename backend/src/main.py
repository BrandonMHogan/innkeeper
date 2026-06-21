import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.host.event_bus import EventBus
from src.host.loader import ModuleLoader
from src.host.registry import ModuleRegistry
from src.modules.device_identity import manifest as device_identity_manifest
from src.modules.device_identity import module as device_identity_module
from src.modules.devices import manifest as devices_manifest
from src.modules.devices import module as devices_module
from src.modules.linked_apps import manifest as linked_apps_manifest
from src.modules.linked_apps import module as linked_apps_module
from src.modules.security import manifest as security_manifest
from src.modules.security import module as security_module
from src.modules.traffic import manifest as traffic_manifest
from src.modules.traffic import module as traffic_module
from src.routes import auth, capture, modules
from src.settings import get_settings


_module_load_result = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.database import engine

    # _load_native_modules() already ran at create_app() time (synchronous,
    # no event loop yet) so routers are mounted before the test client's
    # ASGITransport ever dispatches a request (httpx's ASGITransport never
    # runs lifespan events, so module routes must be mounted eagerly — see
    # Plan 03's precedent). The loader's per-capability try/except (D-03)
    # already swallows HasCollector's asyncio.create_task() RuntimeError
    # ("no running event loop") at that time and skips collector_tasks —
    # now that lifespan() is executing inside uvicorn's real loop, retry
    # wiring just the HasCollector capability for every loaded instance so
    # Traffic's broadcaster loop actually starts in production.
    collector_tasks = _start_collectors(_module_load_result)

    yield

    for stop_event, task in collector_tasks:
        stop_event.set()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    await engine.dispose()


def _start_collectors(load_result) -> list[tuple[asyncio.Event, "asyncio.Task"]]:
    """Starts a HasCollector task (D-08/MOD-05) for every loaded module
    instance that satisfies the protocol — called from lifespan()'s startup
    phase where a real event loop is guaranteed to be running, unlike
    create_app()'s synchronous, no-loop context."""
    from src.host.protocols import HasCollector

    if load_result is None:
        return []

    tasks: list[tuple[asyncio.Event, "asyncio.Task"]] = []
    for instance in load_result.instances.values():
        if isinstance(instance, HasCollector):
            stop_event = asyncio.Event()
            task = asyncio.create_task(instance.run_collector(stop_event))
            tasks.append((stop_event, task))
    return tasks


def _load_native_modules(app: FastAPI):
    """Boots device_identity/devices/traffic/security/linked_apps through
    Plan 01's ModuleLoader (D-08/D-09) instead of hardcoded per-module
    router-mounting calls / a hardcoded lifespan broadcaster task.
    auth/capture stay hardcoded — they are host-level concerns (session
    bootstrap, privileged capture-container ingest), not modules, per
    CONTEXT.md scope; every other module this codebase has goes through
    this single ModuleLoader call as of Plan 05.

    Called synchronously from create_app() (module-import time, no running
    event loop) so routers are mounted before any request — matching Plan
    03's devices/device_identity precedent, required because httpx's
    ASGITransport (used by every test fixture) never runs FastAPI's
    lifespan events. Traffic's HasCollector-wired broadcaster loop is
    actually started later, in lifespan()'s startup phase via
    _start_collectors(), once a real event loop exists.
    """
    loader = ModuleLoader(registry=ModuleRegistry(), event_bus=EventBus())
    manifests = [
        device_identity_manifest.MANIFEST,
        devices_manifest.MANIFEST,
        traffic_manifest.MANIFEST,
        security_manifest.MANIFEST,
        linked_apps_manifest.MANIFEST,
    ]
    factory_by_id = {
        device_identity_manifest.MANIFEST.id: device_identity_module.create,
        devices_manifest.MANIFEST.id: devices_module.create,
        traffic_manifest.MANIFEST.id: traffic_module.create,
        security_manifest.MANIFEST.id: security_module.create,
        linked_apps_manifest.MANIFEST.id: linked_apps_module.create,
    }
    result = loader.load(manifests, factory_by_id)

    # Host-level settings router (backend/src/routes/modules.py) needs the
    # manifest list to compute dependents for the destructive-confirmation
    # check on toggle — set this before mounting per-module routers so the
    # settings router's specific literal "/api/modules/" path is registered
    # first (FastAPI route-resolution precedent: specific literal paths
    # before parameterized per-module prefixes, per STATE.md's Phase 03
    # P03 lesson cited in 05-06-PLAN.md).
    modules.set_manifests(manifests)
    app.include_router(modules.router, prefix="/api/modules")

    for module_id, router in result.routers:
        app.include_router(router, prefix=f"/api/modules/{module_id.replace('_', '-')}")

    return result


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Innkeeper API", lifespan=lifespan)

    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret,
        session_cookie="innkeeper_session",
        same_site="lax",
        https_only=False,
        max_age=None,  # D-10 — sessions never expire automatically
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/auth")
    app.include_router(capture.router, prefix="/api/capture")

    global _module_load_result
    _module_load_result = _load_native_modules(app)

    return app


app = create_app()
