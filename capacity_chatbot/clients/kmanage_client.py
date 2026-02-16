"""HTTP client for kmanage API endpoints."""

import httpx
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class KManageAPIConfig:
    """Configuration for KManage API client."""
    
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
        
        # Timeout for kmanage API calls
        self.timeout = int(os.getenv("KMANAGE_API_TIMEOUT", "30"))

    def is_configured(self) -> bool:
        """Check if auth is properly configured."""
        return bool(self.service_username and self.service_password)


class KManageAPIClient:
    """Client for calling kmanage API endpoints."""
    
    def __init__(self, config: Optional[KManageAPIConfig] = None):
        """Initialize the API client."""
        self.config = config or KManageAPIConfig()
        self._client = httpx.AsyncClient(timeout=float(self.config.timeout))
    
    async def get_session_info(self, mkid: str) -> Optional[Dict[str, Any]]:
        """
        Validate mkid by calling kmanage getSessionInfo endpoint.

        Args:
            mkid: Session token to validate

        Returns:
            Session info dict if valid, None if invalid
        """
        if not mkid or not self.config.is_configured():
            return None

        url = f"{self.config.kmanage_api_url}/user/sessioninfo/{mkid}"

        try:
            response = await self._client.get(
                url,
                auth=(self.config.service_username, self.config.service_password),
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
    
    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
