"""Authentication middleware for mkid validation via kmanage API."""

import logging
import os
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from capacity_chatbot.clients.kmanage_client import KManageAPIClient
from capacity_chatbot.config.api_config import KManageAPIConfig

logger = logging.getLogger(__name__)

# Bearer token security scheme
security = HTTPBearer(auto_error=False)


async def get_authenticated_session(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Dict[str, Any]:
    """
    To extract and validate mkid from Authorization header.

    Returns:
        Session info dict with userUuid, dealerUuid, departmentUuid, mkid

    Raises:
        HTTPException(401): If mkid is missing or invalid
    """
    config = KManageAPIConfig()
    
    # Feature flag to disable auth (for local development)
    auth_enabled = os.getenv("ENABLE_MKID_AUTH", "true").lower() == "true"

    # Skip auth if disabled (local development)
    if not auth_enabled:
        logger.debug("Auth disabled, skipping mkid validation")
        return {"userUuid": "", "dealerUuid": "", "departmentUuid": "", "mkid": ""}

    # Extract mkid from Bearer token (HTTPBearer handles Authorization: Bearer <token>)
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing mkid. Provide Authorization: Bearer <mkid>",
        )
    
    mkid = credentials.credentials

    # Validate mkid with kmanage
    async with KManageAPIClient(config=config) as client:
        session_info = await client.get_session_info(mkid)

    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired mkid. Please refresh your session.",
        )

    user_uuid = session_info.get('userUuid')
    logger.info("Authenticated user: %s", user_uuid)
    return session_info
