"""API middleware module."""

from capacity_chatbot.api.middleware.auth import get_authenticated_session

__all__ = ["get_authenticated_session"]
