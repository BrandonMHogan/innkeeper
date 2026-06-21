"""Host-level module settings routes (MOD-02/MOD-04) — backs the dashboard's
/settings/modules page: list feature modules with their live enabled state,
and toggle that state immediately (no restart, matching
src/host/dependencies.py's require_module_enabled's read-the-DB-every-
request design).

This is NOT itself a module — it is host-level settings infrastructure,
mirroring auth/capture's hardcoded-router status in main.py (see
05-05-SUMMARY.md's "only auth/capture stay hardcoded" note). It reads the
in-memory manifest list assembled once at startup (main.py's
_load_native_modules() return value) to answer "what feature modules exist,
what do they depend on" — never queries a module's own schema directly.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import require_auth
from src.database import get_db
from src.host.manifest import ModuleManifest
from src.models.module_config import ModuleConfig

router = APIRouter()

# Populated once by main.py after _load_native_modules() runs, mirroring
# main.py's own _module_load_result module-level global pattern — this
# router needs read-only access to the manifest list (id/display_name/kind/
# provides/requires) assembled at startup, not the live ModuleLoader
# instances themselves.
_manifests: list[ModuleManifest] = []


def set_manifests(manifests: list[ModuleManifest]) -> None:
    """Called once from main.py after the ModuleLoader call, so this
    settings router can answer GET /api/modules/ without re-scanning
    backend/src/modules/*/manifest.py itself."""
    global _manifests
    _manifests = manifests


class ToggleRequest(BaseModel):
    confirm: bool = False


async def _enabled_state(db: AsyncSession, module_id: str) -> bool:
    result = await db.execute(select(ModuleConfig).where(ModuleConfig.module_id == module_id))
    config = result.scalar_one_or_none()
    if config is None:
        return True
    return config.enabled


def _feature_manifests() -> list[ModuleManifest]:
    # device_identity (kind="support") is excluded from the settings list —
    # support modules have no UI/settings row per D-01.
    return [m for m in _manifests if m.kind == "feature"]


def _dependents_of(module_id: str) -> list[str]:
    """Every OTHER manifest (feature or support) whose `requires` contains
    any Protocol type the given module_id's manifest `provides` — i.e. who
    would break if module_id were disabled."""
    target = next((m for m in _manifests if m.id == module_id), None)
    if target is None or not target.provides:
        return []

    provided_types = set(target.provides)
    dependents = []
    for m in _manifests:
        if m.id == module_id:
            continue
        if provided_types & set(m.requires):
            dependents.append(m.id)
    return dependents


@router.get("/")
async def list_modules(db: AsyncSession = Depends(get_db), _: None = Depends(require_auth)) -> list[dict]:
    modules = []
    for manifest in _feature_manifests():
        modules.append(
            {
                "id": manifest.id,
                "display_name": manifest.display_name,
                "enabled": await _enabled_state(db, manifest.id),
                "ui_route": None,
            }
        )
    return modules


@router.post("/{module_id}/toggle")
async def toggle_module(
    module_id: str,
    payload: ToggleRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(require_auth),
) -> dict:
    current_enabled = await _enabled_state(db, module_id)
    new_enabled = not current_enabled

    if not new_enabled:
        dependents = [
            dep
            for dep in _dependents_of(module_id)
            if await _enabled_state(db, dep)
        ]
        if dependents and not payload.confirm:
            return {"requires_confirmation": True, "dependents": dependents}

    result = await db.execute(select(ModuleConfig).where(ModuleConfig.module_id == module_id))
    config = result.scalar_one_or_none()
    if config is None:
        config = ModuleConfig(module_id=module_id, enabled=new_enabled)
        db.add(config)
    else:
        config.enabled = new_enabled
    await db.commit()

    return {"id": module_id, "enabled": new_enabled}
