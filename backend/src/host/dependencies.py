"""require_module_enabled/is_module_enabled — FastAPI dependency factory
gating retrofitted module routes (RESEARCH.md Pattern 9, mirrors
src/auth.py's require_auth convention).

FastAPI/Starlette cannot cleanly un-register a router at runtime
(`app.include_router()` is append-only) — every discovered module's router
is mounted once at startup regardless of its initial enabled state, and
each route stacks `Depends(require_module_enabled(module_id))` alongside
`Depends(require_auth)` to 404 when disabled, satisfying MOD-04's "no core
rebuild on toggle" requirement.
"""

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.models.module_config import ModuleConfig


async def is_module_enabled(db: AsyncSession, module_id: str) -> bool:
    """Returns True if no ModuleConfig row exists yet for module_id
    (default-enabled, matching ModuleConfig.enabled's column default),
    else returns the row's enabled value."""
    result = await db.execute(select(ModuleConfig).where(ModuleConfig.module_id == module_id))
    config = result.scalar_one_or_none()
    if config is None:
        return True
    return config.enabled


def require_module_enabled(module_id: str):
    async def _check(db: AsyncSession = Depends(get_db)) -> None:
        if not await is_module_enabled(db, module_id):
            raise HTTPException(status_code=404, detail="Module disabled")

    return _check
