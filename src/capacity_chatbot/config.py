"""Configuration for KAppointment API client."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class KAppointmentAPIConfig:
    """Configuration for KAppointment API client.
    
    Uses basic auth for all API calls.
    """

    base_url: Optional[str] = None
    timeout: Optional[int] = None
    basic_auth_username: Optional[str] = None
    basic_auth_password: Optional[str] = None

    def __post_init__(self):
        if self.base_url is None:
            self.base_url = os.environ.get("KAPPOINTMENT_API_BASE_URL", "http://localhost:8080").rstrip('/')

        if self.timeout is None:
            self.timeout = int(os.environ.get("KAPPOINTMENT_API_TIMEOUT", "30"))

        if self.basic_auth_username is None:
            self.basic_auth_username = os.environ.get("APPOINTMENT_CAPACITY_CHATBOT_USERNAME", "1")

        if self.basic_auth_password is None:
            self.basic_auth_password = os.environ.get("APPOINTMENT_CAPACITY_CHATBOT_PASSWORD", "1")

    def get_auth(self) -> tuple:
        """Get basic auth credentials."""
        return (self.basic_auth_username, self.basic_auth_password)

