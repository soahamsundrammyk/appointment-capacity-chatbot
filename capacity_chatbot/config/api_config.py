"""Configuration for KAppointment API client."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class KAppointmentAPIConfig:
    """Configuration for KAppointment API client."""
    
    base_url: Optional[str] = None
    timeout: Optional[int] = None
    mkid: Optional[str] = None
    basic_auth_username: Optional[str] = None
    basic_auth_password: Optional[str] = None
    
    def __post_init__(self):
        if self.base_url is None:
            self.base_url = os.environ.get("KAPPOINTMENT_API_BASE_URL", "https://srishti244.mykaarma.dev/appointment/v2").rstrip('/')
        
        if self.timeout is None:
            self.timeout = int(os.environ.get("KAPPOINTMENT_API_TIMEOUT", "30"))
        
        if self.mkid is None:
            self.mkid = os.environ.get("MYKAARMA_MKID")
        
        if self.basic_auth_username is None:
            self.basic_auth_username = os.environ.get("APPOINTMENT_CAPACITY_CHATBOT_USERNAME", "1")
        
        if self.basic_auth_password is None:
            self.basic_auth_password = os.environ.get("APPOINTMENT_CAPACITY_CHATBOT_PASSWORD", "1")
    
    def get_cookies(self) -> dict:
        """Get cookies dict with mkid if available."""
        if self.mkid:
            return {"mkid": self.mkid}
        return {}
    
    def get_auth(self) -> tuple:
        return (self.basic_auth_username, self.basic_auth_password)
