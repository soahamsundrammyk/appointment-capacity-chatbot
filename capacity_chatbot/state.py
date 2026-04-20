"""State structures for the capacity chatbot agent."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Annotated, Any, Literal

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages


@dataclass
class InputState:
    """Input state from the frontend/API."""

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)
    department_uuid: str = ""
    dealer_uuid: str = ""
    user_tier: Literal["base", "manager", "internal"] = "base"
    advisors: list[dict[str, Any]] = field(default_factory=list)
    transport_options: list[dict[str, Any]] = field(default_factory=list)
    teams: list[dict[str, Any]] = field(default_factory=list)

    @property
    def cached_data(self) -> dict[str, Any]:
        """Build legacy cached_data dict for UUIDMapper/validation. Read-only."""
        return {
            "advisors": self.advisors,
            "transport_options": self.transport_options,
            "teams": self.teams,
        }


@dataclass
class OutputState:
    """Output state returned to the client."""

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(default_factory=list)


@dataclass
class CapacityChatbotState(InputState):
    """Complete state of the capacity chatbot agent."""

    pass
