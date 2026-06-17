from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import hash_password, require_auth, verify_password
from src.database import get_db
from src.models.app_settings import AppSettings

router = APIRouter()


class PasswordPayload(BaseModel):
    password: str = Field(min_length=1)


async def _get_or_create_settings(db: AsyncSession) -> AppSettings:
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    row = result.scalar_one_or_none()
    if row is None:
        row = AppSettings(id=1, setup_complete=False)
        db.add(row)
        await db.flush()
    return row


@router.post("/setup")
async def setup(payload: PasswordPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """First-run: set the dashboard password. 409 if already set (D-08)."""
    settings_row = await _get_or_create_settings(db)

    if settings_row.setup_complete:
        raise HTTPException(status_code=409, detail="Setup already complete")

    settings_row.password_hash = hash_password(payload.password)
    settings_row.setup_complete = True
    await db.commit()
    return {"ok": True}


@router.post("/login")
async def login(payload: PasswordPayload, request: Request, db: AsyncSession = Depends(get_db)):
    """Authenticate. Sets the session cookie on success."""
    result = await db.execute(select(AppSettings).where(AppSettings.id == 1))
    settings_row = result.scalar_one_or_none()

    if settings_row is None or not settings_row.setup_complete:
        raise HTTPException(status_code=409, detail="Setup not complete")

    if not settings_row.password_hash or not verify_password(payload.password, settings_row.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect password")

    # Session-fixation mitigation (T-01-04 / ASVS V3): clear before granting auth.
    request.session.clear()
    request.session["authenticated"] = True
    return {"ok": True}


@router.get("/me")
async def me(request: Request, _: None = Depends(require_auth)):
    return {"authenticated": True}


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return {"ok": True}
