import logging
import os
import secrets

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


def _expected_api_key() -> str:
    return os.getenv("API_KEY", "").strip()


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    expected = _expected_api_key()
    if not expected:
        return None
    if x_api_key and secrets.compare_digest(x_api_key, expected):
        return None
    logger.warning(
        "rejected request with missing or invalid API key",
        extra={"event": "api_key_rejected"},
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
    )
