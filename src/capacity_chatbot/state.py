"""Define the state structures for the capacity chatbot agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Sequence

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated


@dataclass
class InputState:
    """Defines the input state for the capacity chatbot.
    
    This represents the interface to the outside world (frontend/API).
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """Messages tracking the conversation history."""
    
    department_uuid: str = ""
    """Department UUID for API calls."""
    
    dealer_uuid: str = ""
    """Dealer UUID for API calls."""
    
    mkid: str = ""
    """MyKaarma cookie ID (mkid) for API authentication."""
    
    cached_data: Optional[Dict[str, Any]] = None
    """Cached data from frontend (transport options, advisors, hours of operation)."""


@dataclass
class OutputState:
    """Defines the output state returned to the client.
    
    This filters out redundant data the client already has.
    Only returns what the client needs.
    """
    
    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """Messages tracking the conversation history."""


@dataclass
class CapacityChatbotState(InputState):
    """Complete state of the capacity chatbot agent.
    
    Extends InputState with any internal fields needed by graph nodes.
    Currently, the ReAct agent stores all tool results in messages,
    so no additional fields are needed.
    """
    pass  # No additional fields needed for ReAct architecture
