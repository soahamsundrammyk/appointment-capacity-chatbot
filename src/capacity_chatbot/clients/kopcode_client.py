"""HTTP client for kopcode-api endpoints (opcode search)."""

import logging
from typing import Any, Dict, Optional

import httpx

from capacity_chatbot.config import KAppointmentAPIConfig

logger = logging.getLogger(__name__)


class KopcodeAPIClient:
    """Client for calling kopcode-api endpoints (opcode search via RAG)."""

    def __init__(self, config: Optional[KAppointmentAPIConfig] = None):
        """Initialize the API client."""
        self.config = config or KAppointmentAPIConfig()
        self._client = httpx.AsyncClient(timeout=self.config.timeout)
    
    def _get_cookies(self) -> Dict[str, str]:
        """Get cookies for API requests."""
        return self.config.get_cookies()

    async def search_opcode(self, dealer_uuid: str, concern_text: str) -> Dict[str, Any]:
        """Search for opcodes using RAG endpoint.
        
        Endpoint: POST /opcodes/v1/dealers/{dealer_uuid}/operations/match
        
        Args:
            dealer_uuid: Dealer UUID
            concern_text: User's concern or query text
            
        Returns:
            Response with matchedOpcodes array
        """
        url = f"{self.config.base_url}/opcodes/v1/dealers/{dealer_uuid}/operations/match"
        
        try:
            headers = {"accept": "application/json", "content-type": "application/json"}
            cookies = self._get_cookies()
            request_body = {"concernText": concern_text}
            
            logger.info(f"POST {url}")
            
            response = await self._client.post(url, json=request_body, headers=headers, cookies=cookies)
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error calling search_opcode: {e}")
            raise

    async def close(self):
        """Close the HTTP client."""
        await self._client.aclose()
