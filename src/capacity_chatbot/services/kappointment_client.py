"""HTTP client for kappointment-api endpoints."""

import logging
from typing import Any, Dict, Optional

import httpx

from capacity_chatbot.config.api_config import KAppointmentAPIConfig

logger = logging.getLogger(__name__)


class KAppointmentAPIClient:
    """Client for calling kappointment-api endpoints."""

    def __init__(
        self,
        config: Optional[KAppointmentAPIConfig] = None,
    ):
        """Initialize the API client.
        
        Args:
            config: API configuration. If None, creates default config from environment variables.
        """
        self.config = config or KAppointmentAPIConfig()
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
    
    def _get_cookies(self) -> Dict[str, str]:
        """Get cookies for API requests.
        
        Returns:
            Dictionary with cookie values (mkid)
        """
        return self.config.get_cookies()

    async def get_capacity(
        self,
        department_uuid: str,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call getCapacity endpoint.
        
        Args:
            department_uuid: Department UUID
            request: CapacityRequest payload
            
        Returns:
            CapacityResponse as dictionary
        """
        url = f"{self.config.base_url}/appointment/v2/webservice/department/{department_uuid}/capacity"
        
        try:
            cookies = self._get_cookies()
            
            # Log the exact HTTP request being made
            import json
            logger.info("=" * 80)
            logger.info("HTTP Request to kappointment-api:")
            logger.info(f"  Method: POST")
            logger.info(f"  URL: {url}")
            logger.info(f"  Cookies: mkid={cookies.get('mkid', 'NOT_SET')[:20]}...")
            logger.info("  Request Body:")
            logger.info(json.dumps(request, indent=2, default=str))
            logger.info("=" * 80)
            
            response = await self._client.post(url, json=request, cookies=cookies)
            
            # Log response status
            logger.info(f"Response Status: {response.status_code}")
            response.raise_for_status()
            
            # Parse response
            response_data = response.json()
            
            # Log full response (for debugging)
            import json
            logger.info("=" * 80)
            logger.info("HTTP Response from kappointment-api:")
            logger.info(f"  Status: {response.status_code}")
            logger.info("  Response Body (JSON):")
            # Truncate if too large (diagnostics can be huge)
            response_str = json.dumps(response_data, indent=2, default=str)
            if len(response_str) > 5000:
                logger.info(response_str[:5000] + "\n... (truncated, see full response in LangSmith)")
            else:
                logger.info(response_str)
            logger.info("=" * 80)
            
            return response_data
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling getCapacity: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling getCapacity: {e}")
            raise

    async def get_resource_availability(
        self,
        department_uuid: str,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call getResourceAvailability endpoint.
        
        Args:
            department_uuid: Department UUID
            request: GetResourceAvailabilitiesRequest payload
            
        Returns:
            AvailabilityResponse as dictionary
        """
        url = f"{self.config.base_url}/appointment/v2/department/{department_uuid}/availability"
        
        try:
            cookies = self._get_cookies()
            response = await self._client.post(url, json=request, cookies=cookies)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling getResourceAvailability: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling getResourceAvailability: {e}")
            raise

    async def get_rules(
        self,
        department_uuid: str,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call getRules endpoint.
        
        Args:
            department_uuid: Department UUID
            request: RulesRequest payload
            
        Returns:
            RulesResponse as dictionary
        """
        url = f"{self.config.base_url}/appointment/v2/department/{department_uuid}/rules"
        
        try:
            cookies = self._get_cookies()
            response = await self._client.post(url, json=request, cookies=cookies)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling getRules: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling getRules: {e}")
            raise

    async def get_rule_list(
        self,
        department_uuid: str,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call rule/list endpoint to get list of rules.
        
        Endpoint: POST /appointment/v2/webservice/department/{department_uuid}/rule/list
        
        Args:
            department_uuid: Department UUID
            request: Request payload with filters:
                - dealerUUIDList: List of dealer UUIDs (empty = all)
                - resultSize: Max results to return
                - startPosition: Pagination offset
                - ruleStatusList: Filter by status (e.g., ["ACTIVE"])
                - ruleTypeList: Filter by type (e.g., ["CAPACITY"])
            
        Returns:
            Response with ruleList, totalCount, etc.
        """
        url = f"{self.config.base_url}/appointment/v2/webservice/department/{department_uuid}/rule/list"
        
        try:
            headers = {
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json"
            }
            cookies = self._get_cookies()
            
            response = await self._client.post(
                url,
                json=request,
                headers=headers,
                cookies=cookies
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling get_rule_list: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling get_rule_list: {e}")
            raise

    async def get_first_available_slot(
        self,
        department_uuid: str,
        request: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Call getFirstAvailableSlot endpoint.
        
        NOTE: This endpoint requires Basic Auth (not just cookies).
        
        Args:
            department_uuid: Department UUID
            request: FirstAvailableSlotRequest payload with:
                - selectedAvailabilityAttributes (required): Contains advisor/team/transport UUIDs
                - dates (optional): List of dates in yyyy-MM-dd format
                - startTime (optional): Time in HH:mm:ss format
                - endTime (optional): Time in HH:mm:ss format
                - customerInformation (optional): Customer details
                - vehicleInformation (optional): Vehicle details
                - selectedOperationUuidSet (optional): Opcodes
                - Other optional fields
                
        Returns:
            Response with dateTime (yyyy-MM-dd HH:mm:ss), statusCode, error, warnings
        """
        url = f"{self.config.base_url}/appointment/v2/department/{department_uuid}/first-available-slot"
        
        try:
            # Prepare headers
            headers = {
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json"
            }
            
            # Prepare basic auth
            auth = self.config.get_auth()
            
            # Also include cookies (some endpoints need both)
            cookies = self._get_cookies()
            
            response = await self._client.post(
                url,
                json=request,
                headers=headers,
                auth=auth,  # Basic auth
                cookies=cookies  # Also include cookies
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling get_first_available_slot: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling get_first_available_slot: {e}")
            raise

    async def search_opcode(
        self,
        dealer_uuid: str,
        concern_text: str,
    ) -> Dict[str, Any]:
        """Search for opcodes using RAG endpoint.
        
        Endpoint: POST /opcodes/v1/dealers/{dealer_uuid}/operations/match
        
        This endpoint uses RAG (Retrieval Augmented Generation) to find opcodes
        that match a user's concern text (e.g., "oil change", "tire rotation").
        
        Args:
            dealer_uuid: Dealer UUID
            concern_text: User's concern or query text (e.g., "Why can't I book for oil change?")
            
        Returns:
            Response with matchedOpcodes array containing:
                - operationDTO: Full opcode details including uuid, opCodeName, description
                - score: Match confidence score (0-1)
                - evidence: Evidence text (if available)
        """
        url = f"{self.config.base_url}/opcodes/v1/dealers/{dealer_uuid}/operations/match"
        
        try:
            headers = {
                "accept": "application/json, text/plain, */*",
                "content-type": "application/json"
            }
            cookies = self._get_cookies()
            
            request_body = {
                "concernText": concern_text
            }
            
            response = await self._client.post(
                url,
                json=request_body,
                headers=headers,
                cookies=cookies
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling search_opcode: {e}")
            raise
        except Exception as e:
            logger.error(f"Error calling search_opcode: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()

