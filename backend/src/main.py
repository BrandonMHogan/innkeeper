import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.middleware.sessions import SessionMiddleware

from src.modules.linked_apps import routes as linked_apps_routes
from src.routes import auth, capture, devices, security, traffic
from src.services.traffic_broadcaster import update_snapshot_loop
from src.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    from src.database import engine

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    broadcaster_stop_event = asyncio.Event()
    broadcaster_task = asyncio.create_task(update_snapshot_loop(broadcaster_stop_event, session_factory))

    yield

    broadcaster_stop_event.set()
    broadcaster_task.cancel()
    try:
        await broadcaster_task
    except asyncio.CancelledError:
        pass

    await engine.dispose()


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
    app.include_router(devices.router, prefix="/api/devices")
    app.include_router(security.router, prefix="/api/security")
    app.include_router(traffic.router, prefix="/api/traffic")
    app.include_router(linked_apps_routes.router, prefix="/api/modules/linked-apps")

    return app


app = create_app()
