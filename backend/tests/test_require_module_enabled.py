from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker

from src.database import get_db
from src.host.dependencies import require_module_enabled
from src.models.module_config import ModuleConfig


def _build_test_app():
    app = FastAPI()

    @app.get("/gated", dependencies=[Depends(require_module_enabled("x"))])
    async def gated():
        return {"ok": True}

    return app


async def _client_for(test_db):
    app = _build_test_app()
    session_maker = async_sessionmaker(test_db, expire_on_commit=False)

    async def override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), session_maker


async def test_disabled_module_returns_404(test_db):
    client, session_maker = await _client_for(test_db)
    async with session_maker() as db:
        db.add(ModuleConfig(module_id="x", enabled=False))
        await db.commit()

    async with client as c:
        response = await c.get("/gated")

    assert response.status_code == 404
    assert response.json()["detail"] == "Module disabled"


async def test_enabled_module_returns_200(test_db):
    client, session_maker = await _client_for(test_db)
    async with session_maker() as db:
        db.add(ModuleConfig(module_id="x", enabled=True))
        await db.commit()

    async with client as c:
        response = await c.get("/gated")

    assert response.status_code == 200


async def test_no_row_defaults_to_enabled(test_db):
    client, _ = await _client_for(test_db)

    async with client as c:
        response = await c.get("/gated")

    assert response.status_code == 200
