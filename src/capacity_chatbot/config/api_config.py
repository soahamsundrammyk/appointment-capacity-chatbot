"""Configuration for KAppointment API client."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KAppointmentAPIConfig:
    """Configuration for KAppointment API client."""
    
    base_url: Optional[str] = None
    """Base URL for KAppointment API endpoints."""
    
    timeout: int = 30
    """Request timeout in seconds."""
    
    mkid: Optional[str] = None
    """Cookie value for mkid authentication."""
    
    basic_auth_username: Optional[str] = None
    """Username for basic authentication."""
    
    basic_auth_password: Optional[str] = None
    """Password for basic authentication."""
    
    def __post_init__(self):
        """Set defaults from environment variables if not provided."""
        if self.base_url is None:
            self.base_url = os.environ.get(
                "KAPPOINTMENT_API_BASE_URL", "http://localhost:8080"
            ).rstrip('/')
        
        if self.timeout is None:
            self.timeout = int(os.environ.get("KAPPOINTMENT_API_TIMEOUT", "30"))
        
        if self.mkid is None:
            self.mkid = os.environ.get(
                "MYKAARMA_MKID", "af5e8676-3cf5-4786-9546-827ada744b23"
            )
        
        if self.basic_auth_username is None:
            self.basic_auth_username = os.environ.get("KAPPOINTMENT_API_USERNAME", "1")
        
        if self.basic_auth_password is None:
            self.basic_auth_password = os.environ.get("KAPPOINTMENT_API_PASSWORD", "1")
    
    def get_cookies(self) -> dict:
        """Get cookies for API requests.
        
        Returns:
            Dictionary with cookie values (mkid)
        """
        return {"mkid": self.mkid}
    
    def get_auth(self) -> tuple:
        """Get basic auth credentials.
        
        Returns:
            Tuple of (username, password) for basic auth
        """
        return (self.basic_auth_username, self.basic_auth_password)

