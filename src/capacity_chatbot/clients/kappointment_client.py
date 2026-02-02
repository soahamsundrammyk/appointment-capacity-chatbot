"""HTTP client for kappointment-api endpoints."""

import json
import logging
from typing import Any, Dict, Optional

import httpx

from capacity_chatbot.config import KAppointmentAPIConfig

logger = logging.getLogger(__name__)


class KAppointmentAPIClient:
    """Client for calling kappointment-api endpoints."""

    def __init__(self, config: Optional[KAppointmentAPIConfig] = None):
        """Initialize the API client."""
        self.config = config or KAppointmentAPIConfig()
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
    
    def _get_cookies(self) -> Dict[str, str]:
        """Get cookies for API requests."""
        return self.config.get_cookies()

    async def get_capacity(self, department_uuid: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call getCapacity endpoint."""
        url = f"{self.config.base_url}/appointment/v2/webservice/department/{department_uuid}/capacity"
        
        try:
            cookies = self._get_cookies()
            logger.info(f"POST {url}")
            logger.info(f"Request: {json.dumps(request, indent=2, default=str)}")
            
            response = await self._client.post(url, json=request, cookies=cookies)
            logger.info(f"Response Status: {response.status_code}")
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling getCapacity: {e}")
            raise

    async def get_resource_availability(self, department_uuid: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call getResourceAvailability endpoint."""
        url = f"{self.config.base_url}/appointment/v2/department/{department_uuid}/availability"
        
        try:
            cookies = self._get_cookies()
            response = await self._client.post(url, json=request, cookies=cookies)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling getResourceAvailability: {e}")
            raise

    async def get_rules(self, department_uuid: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call getRules endpoint."""
        url = f"{self.config.base_url}/appointment/v2/department/{department_uuid}/rules"
        
        try:
            cookies = self._get_cookies()
            response = await self._client.post(url, json=request, cookies=cookies)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling getRules: {e}")
            raise

    async def get_rule_list(self, department_uuid: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call rule/list endpoint to get list of rules."""
        url = f"{self.config.base_url}/appointment/v2/webservice/department/{department_uuid}/rule/list"
        
        try:
            headers = {"accept": "application/json", "content-type": "application/json"}
            cookies = self._get_cookies()
            response = await self._client.post(url, json=request, headers=headers, cookies=cookies)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling get_rule_list: {e}")
            raise

    async def get_first_available_slot(self, department_uuid: str, request: Dict[str, Any]) -> Dict[str, Any]:
        """Call getFirstAvailableSlot endpoint (requires Basic Auth)."""
        url = f"{self.config.base_url}/appointment/v2/department/{department_uuid}/first-available-slot"
        
        try:
            headers = {"accept": "application/json", "content-type": "application/json"}
            auth = self.config.get_auth()
            cookies = self._get_cookies()
            
            response = await self._client.post(url, json=request, headers=headers, auth=auth, cookies=cookies)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling get_first_available_slot: {e}")
            raise

    async def fetch_operations_with_limits(self, department_uuid: str) -> Dict[str, Any]:
        """Call operations-with-limits endpoint to get opcodes with daily limits.
        
        Returns only opcodes that have daily limits configured (dayLimit != MAX_INT).
        Also includes opcodes mentioned in capacity rules.
        """
        url = f"{self.config.base_url}/appointment/v2/webservice/departments/{department_uuid}/operations-with-limits"
        
        try:
            cookies = self._get_cookies()
            logger.info(f"GET {url}")
            
            response = await self._client.get(url, cookies=cookies)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling fetch_operations_with_limits: {e}")
            raise

    async def search_operations(self, department_uuid: str, search_token: str, result_size: int = 20) -> Dict[str, Any]:
        """Search for opcodes using the operations endpoint.
        
        Endpoint: POST /v2/consumer/webservice/department/{dealerDepartmentUuid}/operations
        Uses searchToken field to search for opcodes by name/description.
        
        Args:
            department_uuid: Department UUID
            search_token: Search term for finding opcodes
            result_size: Max number of results to return (default 20)
            
        Returns:
            Response with operationList array containing matching operations
        """
        url = f"{self.config.base_url}/appointment/v2/consumer/webservice/department/{department_uuid}/operations"
        
        request_body = {
            "searchToken": search_token,
            "typeList": ["OPCODE"],
            "resultSize": result_size,
            "startPosition": 0,
        }
        
        try:
            cookies = self._get_cookies()
            logger.info(f"POST {url}")
            logger.info(f"Request: {json.dumps(request_body, indent=2)}")
            
            response = await self._client.post(url, json=request_body, cookies=cookies)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling search_operations: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
