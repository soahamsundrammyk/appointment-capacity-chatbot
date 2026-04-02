"""HTTP client for kappointment-api endpoints."""

import json
import logging
from typing import Any

import httpx

from capacity_chatbot.config.api_config import KAppointmentAPIConfig

logger = logging.getLogger(__name__)


class KAppointmentAPIClient:
    """Client for calling kappointment-api endpoints.

    Authentication:
    - Most endpoints use basic auth (username/password)
    - fetch_operations_with_limits uses cookie auth (mkid) - webservice endpoint

    Usage:
        async with KAppointmentAPIClient() as client:
            result = await client.get_capacity(...)
    """

    def __init__(self, config: KAppointmentAPIConfig | None = None):
        """Initialize the API client."""
        self.config = config or KAppointmentAPIConfig()
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=float(self.config.timeout))

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    def _get_auth(self) -> tuple[str, str]:
        """Get basic auth credentials."""
        return self.config.get_auth()

    def _get_headers(self, include_content_type: bool = True) -> dict[str, str]:
        """Get standard request headers."""
        headers = {"accept": "application/json"}
        if include_content_type:
            headers["content-type"] = "application/json"
        return headers

    def _build_url(self, path: str) -> str:
        """Build full URL from base URL and path."""
        return f"{self.config.base_url}/{path.lstrip('/')}"

    async def _make_post_request(
        self, url: str, json_data: dict[str, Any], endpoint_name: str
    ) -> dict[str, Any]:
        """Make a POST request with basic auth, logging, and error handling."""
        try:
            auth = self._get_auth()
            headers = self._get_headers()
            logger.debug("Request: %s", json.dumps(json_data, indent=2, default=str))

            response = await self._client.post(url, json=json_data, headers=headers, auth=auth)
            response.raise_for_status()
            response_data = response.json()
            logger.debug("Response: %s", json.dumps(response_data, indent=2, default=str))

            return response_data
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling %s: %s", endpoint_name, e)
            raise

    async def _make_get_request(
        self, url: str, endpoint_name: str, cookies: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """Make a GET request with optional cookies, logging, and error handling."""
        try:
            headers = self._get_headers(include_content_type=False)
            logger.debug("GET request to: %s", url)

            response = await self._client.get(url, headers=headers, cookies=cookies)
            response.raise_for_status()
            response_data = response.json()
            logger.debug("Response: %s", json.dumps(response_data, indent=2, default=str))

            return response_data
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error calling %s: %s", endpoint_name, e)
            raise

    async def get_capacity(self, department_uuid: str, request: dict[str, Any]) -> dict[str, Any]:
        """Call getCapacity endpoint."""
        url = self._build_url(f"department/{department_uuid}/capacity")
        return await self._make_post_request(url, request, "getCapacity")

    async def get_rule_list(self, department_uuid: str, request: dict[str, Any]) -> dict[str, Any]:
        """Call rule/list endpoint to get list of rules."""
        url = self._build_url(f"department/{department_uuid}/rule/list")
        return await self._make_post_request(url, request, "get_rule_list")

    async def get_first_available_slot(
        self, department_uuid: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Call getFirstAvailableSlot endpoint."""
        url = self._build_url(f"department/{department_uuid}/first-available-slot")
        return await self._make_post_request(url, request, "get_first_available_slot")

    async def fetch_operations_with_limits(
        self, department_uuid: str, mkid: str | None = None
    ) -> dict[str, Any]:
        """Call operations-with-limits endpoint to get opcodes with daily limits.

        This endpoint requires mkid cookie authentication (webservice endpoint).
        Does NOT accept basic auth - only mkid cookie.

        Args:
            department_uuid: Department UUID
            mkid: Optional mkid cookie. If not provided, falls back to config.mkid

        Returns only opcodes that have daily limits configured (dayLimit != MAX_INT).
        Also includes opcodes mentioned in capacity rules.
        """
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

        url = self._build_url(f"webservice/departments/{department_uuid}/operations-with-limits")
        cookies = {"mkid": mkid}
        # Webservice endpoint only accepts mkid cookie, NOT basic auth
        return await self._make_get_request(url, "fetch_operations_with_limits", cookies=cookies)

    async def search_operations(
        self, department_uuid: str, search_token: str, result_size: int = 20
    ) -> dict[str, Any]:
        """Search for opcodes using the operations endpoint.

        Args:
            department_uuid: Department UUID
            search_token: Search term for finding opcodes
            result_size: Max number of results to return (default 20)

        Returns:
            Response with operationList array containing matching operations
        """
        url = self._build_url(f"department/{department_uuid}/operations")

        request_body = {
            "searchToken": search_token,
            "typeList": ["OPCODE"],
            "resultSize": result_size,
            "startPosition": 0,
        }

        return await self._make_post_request(url, request_body, "search_operations")

    async def list_appointments(
        self, department_uuid: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        """Call POST /department/{uuid}/list to filter and list appointments.

        Args:
            department_uuid: Department UUID
            request: FilterServiceAppointmentRequest with:
                - pageNumber (int, required): 1-based page number
                - pageSize (int, required): results per page
                - startDate/endDate: scheduled date range (yyyy-MM-dd)
                - startCreatedDate/endCreatedDate: creation date range (yyyy-MM-dd)
                - createdBy: platform source (Web, DealerApp, DMS, etc.)
                - teamUuids: list of team UUIDs
                - orderBy: sort field (e.g. "createdTimeStamp")
                - isSortAscending: sort direction

        Returns:
            FilterServiceAppointmentResponse with:
                - appointmentInfo: list of AppointmentInfoLite
                - totalCount: total matching records
        """
        url = self._build_url(f"department/{department_uuid}/list")
        return await self._make_post_request(url, request, "list_appointments")

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
