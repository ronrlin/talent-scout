"""API key authentication.

Auto-generates a key on first server start, stored in data/.api-key.
Clients pass the key via X-API-Key header.
"""

import secrets
from pathlib import Path

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY_FILE = Path(__file__).parent.parent / "data" / ".api-key"

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_or_create_api_key() -> str:
    """Get existing API key or generate a new one."""
    if API_KEY_FILE.exists():
        return API_KEY_FILE.read_text().strip()

    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    key = secrets.token_urlsafe(32)
    API_KEY_FILE.write_text(key)
    return key


async def verify_api_key(api_key: str | None = Security(api_key_header)) -> str:
    """FastAPI dependency that verifies the X-API-Key header."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    expected = get_or_create_api_key()
    if api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return api_key
