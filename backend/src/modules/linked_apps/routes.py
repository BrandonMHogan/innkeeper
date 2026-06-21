from fastapi import APIRouter, Depends

from src.auth import require_auth

router = APIRouter()


@router.get("/")
async def list_linked_apps(_: None = Depends(require_auth)):
    """Return the configured linked-app list.

    v1 ships zero real linked apps (D-23) — this endpoint exists so the
    frontend has a real contract to call, not a hardcoded frontend empty
    array.
    """
    return []
