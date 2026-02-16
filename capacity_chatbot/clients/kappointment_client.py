"""HTTP client for kappointment-api endpoints."""

import json
import logging
from typing import Any, Dict, Optional, Tuple

import httpx

from capacity_chatbot.config.api_config import KAppointmentAPIConfig

logger = logging.getLogger(__name__)


class KAppointmentAPIClient:
    """Client for calling kappointment-api endpoints.
    
    All endpoints use basic auth authentication.
    
    Usage:
        # Manual close
        client = KAppointmentAPIClient()
        try:
            result = await client.get_capacity(...)
        finally:
            await client.close()
        
        # Context manager (recommended)
        async with KAppointmentAPIClient() as client:
            result = await client.get_capacity(...)
    """

    def __init__(self, config: Optional[KAppointmentAPIConfig] = None):
        """Initialize the API client."""
        self.config = config or KAppointmentAPIConfig()
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=float(self.config.timeout))

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _get_auth(self) -> Tuple[str, str]:
        """Get basic auth credentials."""
        return self.config.get_auth()

    def _get_headers(self, include_content_type: bool = True) -> Dict[str, str]:
        """Get standard request headers."""
        headers = {"accept": "application/json"}
        if include_content_type:
            headers["content-type"] = "application/json"
        return headers

    async def get_capacity(self, department_uuid: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call getCapacity endpoint."""
        url = f"{self.config.base_url}/department/{department_uuid}/capacity"

        try:
            auth = self._get_auth()
            headers = self._get_headers()
            logger.debug("Request: %s", json.dumps(request, indent=2, default=str))

            response = await self._client.post(url, json=request, headers=headers, auth=auth)
            response.raise_for_status()
            response_data = response.json()
            logger.debug("Response: %s", json.dumps(response_data, indent=2, default=str))

            return response_data
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling getCapacity: %s", e)
            raise

    async def get_rule_list(self, department_uuid: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call rule/list endpoint to get list of rules."""
        url = f"{self.config.base_url}/department/{department_uuid}/rule/list"

        try:
            auth = self._get_auth()
            headers = self._get_headers()
            logger.debug("Request: %s", json.dumps(request, indent=2, default=str))

            response = await self._client.post(url, json=request, headers=headers, auth=auth)
            response.raise_for_status()
            response_data = response.json()
            logger.debug("Response: %s", json.dumps(response_data, indent=2, default=str))

            return response_data
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling get_rule_list: %s", e)
            raise

    async def get_first_available_slot(self, department_uuid: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call getFirstAvailableSlot endpoint."""
        url = f"{self.config.base_url}/department/{department_uuid}/first-available-slot"

        try:
            auth = self._get_auth()
            headers = self._get_headers()
            logger.debug("Request: %s", json.dumps(request, indent=2, default=str))

            response = await self._client.post(url, json=request, headers=headers, auth=auth)
            response.raise_for_status()
            response_data = response.json()
            logger.debug("Response: %s", json.dumps(response_data, indent=2, default=str))

            return response_data
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling get_first_available_slot: %s", e)
            raise

    async def fetch_operations_with_limits(self, department_uuid: str, mkid: Optional[str] = None) -> Dict[str, Any]:
        """Call operations-with-limits endpoint to get opcodes with daily limits.

        This endpoint requires mkid cookie authentication (webservice endpoint).
        Does NOT accept basic auth - only mkid cookie.

        Args:
            department_uuid: Department UUID
            mkid: Optional mkid cookie. If not provided, falls back to config.mkid

        Returns only opcodes that have daily limits configured (dayLimit != MAX_INT).
        Also includes opcodes mentioned in capacity rules.
        """
        url = f"{self.config.base_url}/webservice/departments/{department_uuid}/operations-with-limits"

        # Fallback to config's mkid if not provided
        if not mkid:
            cookies = self.config.get_cookies()
            mkid = cookies.get("mkid") if cookies else None

        if not mkid or not mkid.strip():
            raise ValueError(
                "mkid is required for operations-with-limits endpoint "
                "(webservice endpoint only accepts cookie auth). "
                "Please ensure you're logged in with a valid session or set MYKAARMA_MKID in config."
            )

        try:
            headers = self._get_headers(include_content_type=False)
            cookies = {"mkid": mkid}

            # Webservice endpoint only accepts mkid cookie, NOT basic auth
            response = await self._client.get(url, headers=headers, cookies=cookies)
            response.raise_for_status()
            response_data = response.json()
            logger.debug("Response: %s", json.dumps(response_data, indent=2, default=str))

            return response_data
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling fetch_operations_with_limits: %s", e)
            raise

    async def search_operations(self, department_uuid: str, search_token: str, result_size: int = 20) -> Dict[str, Any]:
        """Search for opcodes using the operations endpoint.

        Args:
            department_uuid: Department UUID
            search_token: Search term for finding opcodes
            result_size: Max number of results to return (default 20)

        Returns:
            Response with operationList array containing matching operations
        """
        url = f"{self.config.base_url}/department/{department_uuid}/operations"

        request_body = {
            "searchToken": search_token,
            "typeList": ["OPCODE"],
            "resultSize": result_size,
            "startPosition": 0,
        }

        try:
            auth = self._get_auth()
            headers = self._get_headers()
            logger.debug("Request: %s", json.dumps(request_body, indent=2))

            response = await self._client.post(url, json=request_body, headers=headers, auth=auth)
            response.raise_for_status()
            response_data = response.json()
            logger.debug("Response: %s", json.dumps(response_data, indent=2, default=str))

            return response_data
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling search_operations: %s", e)
            raise

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
