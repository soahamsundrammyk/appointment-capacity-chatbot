"""HTTP client for kmanage API endpoints."""

import logging
from typing import Any

import httpx

from capacity_chatbot.config.api_config import KManageAPIConfig

logger = logging.getLogger(__name__)


class KManageAPIClient:
    """Client for calling kmanage API endpoints.

    Usage:
        async with KManageAPIClient() as client:
            result = await client.get_session_info(...)
    """

    def __init__(self, config: KManageAPIConfig | None = None):
        """Initialize the API client."""
        self.config = config or KManageAPIConfig()
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=float(self.config.timeout))

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def get_session_info(self, mkid: str) -> dict[str, Any] | None:
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
                auth=self.config.get_auth(),
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
                logger.warning("Invalid/expired mkid (status: %s)", response.status_code)
                return None
            else:
                logger.error(f"Kmanage API error: {response.status_code}")
                return None

        except httpx.TimeoutException:
            logger.error("Timeout calling kmanage API")
            return None
        except Exception as e:
            logger.exception(f"Error validating mkid: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
