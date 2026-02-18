"""State structures for the capacity chatbot agent."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


@dataclass
class InputState:
    """Input state from the frontend/API."""

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)
    department_uuid: str = ""
    dealer_uuid: str = ""
    cached_data: dict[str, Any] | None = None


@dataclass
class OutputState:
    """Output state returned to the client."""

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)


@dataclass
class CapacityChatbotState(InputState):
    """Complete state of the capacity chatbot agent."""

    pass
