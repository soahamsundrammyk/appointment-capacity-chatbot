"""State structures for the capacity chatbot agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated


@dataclass
class InputState:
    """Input state from the frontend/API."""

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)
    department_uuid: str = ""
    dealer_uuid: str = ""
    cached_data: Optional[Dict[str, Any]] = None


@dataclass
class OutputState:
    """Output state returned to the client."""

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)


@dataclass
class CapacityChatbotState(InputState):
    """Complete state of the capacity chatbot agent."""
    mkid: str = ""  # Authentication cookie for endpoints requiring mkid
