"""Authentication module for mkid validation via kmanage API."""

import httpx
import logging
import os
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

# Bearer token security scheme
security = HTTPBearer(auto_error=False)


class AuthConfig:
    """Authentication configuration from environment.
    
    Uses same pattern as KAppointmentAPIConfig for consistency.
    """

    def __init__(self):
        # Kmanage API URL (same pattern as kappointment-api)
        self.kmanage_api_url = os.getenv(
            "KMANAGE_API_URL", "https://api.mykaarma.com/manage/v2"
        ).rstrip("/")
        
        # Service subscriber credentials for kmanage API auth
        self.service_username = os.getenv(
            "APPOINTMENT_CAPACITY_CHATBOT_USERNAME"
        )
        self.service_password = os.getenv(
            "APPOINTMENT_CAPACITY_CHATBOT_PASSWORD"
        )
        
        # Feature flag to disable auth (for local development)
        self.auth_enabled = os.getenv("ENABLE_MKID_AUTH", "true").lower() == "true"
        
        # Timeout for kmanage API calls
        self.timeout = int(os.getenv("KMANAGE_API_TIMEOUT", "30"))

    def is_configured(self) -> bool:
        """Check if auth is properly configured."""
        return bool(self.service_username and self.service_password)


# Global config instance
_auth_config: Optional[AuthConfig] = None


def get_auth_config() -> AuthConfig:
    """Get the auth configuration."""
    global _auth_config
    if _auth_config is None:
        _auth_config = AuthConfig()
    return _auth_config


async def validate_mkid(mkid: str, config: AuthConfig) -> Optional[Dict[str, Any]]:
    """
    Validate mkid by calling kmanage getSessionInfo endpoint.

    Args:
        mkid: Session token to validate
        config: Auth configuration

    Returns:
        Session info dict if valid, None if invalid
    """
    if not mkid or not config.is_configured():
        return None

    url = f"{config.kmanage_api_url}/user/sessioninfo/{mkid}"

    try:
        async with httpx.AsyncClient(timeout=float(config.timeout)) as client:
            response = await client.get(
                url,
                auth=(config.service_username, config.service_password),
                headers={"Accept": "application/json"},
            )

            if response.status_code == 200:
                data = response.json()
                # Handle different response structures from kmanage
                session_info = data.get("sessionInfoDTO") or data.get("sessionInfo") or data
                return {
                    "userUuid": session_info.get("userUuid"),
                    "dealerUuid": session_info.get("dealerUuid"),
                    "departmentUuid": session_info.get("departmentUuid"),
                    "mkid": mkid,
                }
            elif response.status_code in (401, 404):
                logger.warning(f"Invalid/expired mkid: {mkid[:10]}... ({response.status_code})")
                return None
            else:
                logger.error(f"Kmanage API error: {response.status_code}")
                return None

    except httpx.TimeoutException:
        logger.error(f"Timeout calling kmanage API")
        return None
    except Exception as e:
        logger.exception(f"Error validating mkid: {e}")
        return None


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

    # Skip auth if disabled (local development)
    if not config.auth_enabled:
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
    session_info = await validate_mkid(mkid, config)

    if not session_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired mkid. Please refresh your session.",
        )

    logger.info(f"Authenticated user: {session_info.get('userUuid', 'unknown')[:8]}...")
    return session_info
