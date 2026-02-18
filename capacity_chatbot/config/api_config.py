"""Configuration for API clients."""

import os
from dataclasses import dataclass


@dataclass
class BaseAPIConfig:
    """Base configuration with common fields for API clients."""

    basic_auth_username: str | None = None
    basic_auth_password: str | None = None
    timeout: int | None = None

    def _init_basic_auth(self) -> None:
        """Initialize basic auth credentials from environment variables."""
        if self.basic_auth_username is None:
            self.basic_auth_username = os.environ.get("APPOINTMENT_CAPACITY_CHATBOT_USERNAME", "1")

        if self.basic_auth_password is None:
            self.basic_auth_password = os.environ.get("APPOINTMENT_CAPACITY_CHATBOT_PASSWORD", "1")

    def _init_timeout(self, env_var: str, default: int = 30) -> None:
        """Initialize timeout from environment variable."""
        if self.timeout is None:
            self.timeout = int(os.environ.get(env_var, str(default)))

    def get_auth(self) -> tuple:
        """Get Basic Auth tuple (username, password)."""
        return (self.basic_auth_username, self.basic_auth_password)


@dataclass
class KAppointmentAPIConfig(BaseAPIConfig):
    """Configuration for KAppointment API client."""

    base_url: str | None = None
    mkid: str | None = None

    def __post_init__(self):
        if self.base_url is None:
            self.base_url = os.environ.get(
                "KAPPOINTMENT_API_BASE_URL", "https://srishti244.mykaarma.dev/appointment/v2"
            ).rstrip("/")

        if self.mkid is None:
            self.mkid = os.environ.get("MYKAARMA_MKID")

        self._init_basic_auth()
        self._init_timeout("KAPPOINTMENT_API_TIMEOUT", 30)

    def get_cookies(self) -> dict:
        """Get cookies dict with mkid if available."""
        if self.mkid:
            return {"mkid": self.mkid}
        return {}


@dataclass
class KManageAPIConfig(BaseAPIConfig):
    """Configuration for KManage API client."""

    kmanage_api_url: str | None = None

    def __post_init__(self):
        if self.kmanage_api_url is None:
            self.kmanage_api_url = os.environ.get(
                "KMANAGE_API_URL", "https://srishti244.mykaarma.dev/manage/v2"
            ).rstrip("/")

        self._init_basic_auth()
        self._init_timeout("KMANAGE_API_TIMEOUT", 30)

    def is_configured(self) -> bool:
        """Check if auth is properly configured."""
        return bool(self.basic_auth_username and self.basic_auth_password)
