"""Authentication middleware for mkid validation via kmanage API."""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from capacity_chatbot.clients.kmanage_client import KManageAPIClient, KManageAPIConfig

logger = logging.getLogger(__name__)

# Bearer token security scheme
security = HTTPBearer(auto_error=False)


# Global config instance
_auth_config: Optional[KManageAPIConfig] = None


def get_auth_config() -> KManageAPIConfig:
    """Get the auth configuration."""
    global _auth_config
    if _auth_config is None:
        _auth_config = KManageAPIConfig()
    return _auth_config


async def get_authenticated_session(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    FastAPI dependency to extract and validate mkid from Authorization header.

    Usage:
        @app.post("/endpoint")
        async def endpoint(session: Dict = Depends(get_authenticated_session)):
            user_uuid = session["userUuid"]

    Returns:
        Session info dict with userUuid, dealerUuid, departmentUuid, mkid

    Raises:
        HTTPException(401): If mkid is missing or invalid
    """
    config = get_auth_config()
    
    # Feature flag to disable auth (for local development)
    auth_enabled = os.getenv("ENABLE_MKID_AUTH", "true").lower() == "true"

    # Skip auth if disabled (local development)
    if not auth_enabled:
        logger.debug("Auth disabled, skipping mkid validation")
        return {"userUuid": "", "dealerUuid": "", "departmentUuid": "", "mkid": ""}

    # Extract mkid from Authorization header
    mkid = None

    # Try Bearer token first
    if credentials:
        mkid = credentials.credentials

    # Fallback: Check Authorization header directly
    if not mkid:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            mkid = auth_header[7:].strip()
        elif auth_header and not auth_header.startswith("Basic "):
            mkid = auth_header.strip()

    # Fallback: Check cookies
    if not mkid:
        mkid = request.cookies.get("mkid")

    if not mkid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing mkid. Provide Authorization: Bearer <mkid>",
        )

    # Validate mkid with kmanage
    client = KManageAPIClient(config=config)
    try:
        session_info = await client.get_session_info(mkid)
    finally:
        await client.close()

    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired mkid. Please refresh your session.",
        )

    logger.info(f"Authenticated user: {session_info.get('userUuid', 'unknown')[:8]}...")
    return session_info
