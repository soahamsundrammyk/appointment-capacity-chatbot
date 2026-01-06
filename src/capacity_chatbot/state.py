"""Define the state structures for the capacity chatbot agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from langchain_core.messages import AnyMessage
from langgraph.graph import add_messages
from typing_extensions import Annotated


def add_items(left: List[Any] | None, right: List[Any] | None) -> List[Any]:
    """Reducer to append items to a list."""
    if left is None:
        left = []
    if right is None:
        return left
    return left + right


@dataclass
class InputState:
    """Defines the input state for the capacity chatbot.
    
    This represents the interface to the outside world (frontend/API).
    """

    messages: Annotated[Sequence[AnyMessage], add_messages] = field(
        default_factory=list
    )
    """
    Messages tracking the conversation history.
    
    Uses `add_messages` annotation to ensure messages are merged by ID,
    maintaining an append-only state.
    """
    
    department_uuid: str = ""
    """Department UUID for API calls."""
    
    dealer_uuid: str = ""
    """Dealer UUID for API calls (optional, can be derived from department)."""
    
    mkid: str = ""
    """MyKaarma cookie ID (mkid) for API authentication."""
    
    cached_data: Optional[Dict[str, Any]] = None
    """
    Cached data from frontend (transport options, advisors, hours of operation).
    This avoids redundant API calls.
    """


@dataclass
class CapacityChatbotState(InputState):
    """Complete state of the capacity chatbot agent."""

    # Parsed and extracted data
    parsed_intent: Optional[str] = None
    """Intent classification: 'simple_capacity', 'diagnostic_query'"""
    
    extracted_entities: Dict[str, Any] = field(default_factory=dict)
    """Extracted entities: dates, advisor names, transport options, times, etc."""
    
    # API Responses
    capacity_data: Optional[Dict[str, Any]] = None
    """Response from getCapacity endpoint"""
    
    schedule_data: Optional[Dict[str, Any]] = None
    """Response from schedule endpoints"""
    
    rules_data: Optional[Dict[str, Any]] = None
    """Response from getRules endpoint"""
    
    first_available_slot_data: Optional[Dict[str, Any]] = None
    """Response from getFirstAvailableSlot endpoint"""
    
    # Final Output
    response_message: str = ""
    """Final response message to send to user"""
    
    # Metadata
    errors: Annotated[List[str], add_items] = field(default_factory=list)
    """List of errors encountered during processing"""
    
    reasoning: Annotated[List[str], add_items] = field(default_factory=list)
    """Reasoning steps for debugging and transparency"""

