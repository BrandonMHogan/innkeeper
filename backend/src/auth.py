import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


def hash_password(password: str) -> str:
    """Hash a password using hashlib.scrypt (stdlib, no extra dependency).

    Stored as `salt$hash`, both hex-encoded, in a single string.
    """
    salt = secrets.token_hex(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return f"{salt}${derived.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Recompute scrypt with the stored salt and compare in constant time."""
    try:
        salt, stored_hex = password_hash.split("$", 1)
    except ValueError:
        return False

    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    )
    return hmac.compare_digest(derived.hex(), stored_hex)


async def require_auth(request: Request) -> None:
    """FastAPI dependency — raises 401 if the session is not authenticated."""
    if not request.session.get("authenticated"):
        raise HTTPException(status_code=401, detail="Not authenticated")
