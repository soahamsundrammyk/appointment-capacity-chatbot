"""Request models for API endpoints."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RunInput(BaseModel):
    """Input for a run - matches LangGraph API format."""
    messages: List[Dict[str, Any]]
    department_uuid: Optional[str] = ""
    dealer_uuid: Optional[str] = ""
    cached_data: Optional[Dict[str, Any]] = None


class RunRequest(BaseModel):
    """Request to create a run - matches LangGraph API format."""
    input: RunInput
    config: Optional[Dict[str, Any]] = None
    stream_mode: Optional[List[str]] = None


class EntityFilterRequest(BaseModel):
    """Shared request model for capacity and first available slot queries.
    
    Contains common entity filtering parameters used by both tools.
    """
    dates: Optional[List[str]] = None
    transport_option_names: Optional[List[str]] = None
    advisor_names: Optional[List[str]] = None
    team_names: Optional[List[str]] = None
    opcodes: Optional[List[str]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None  # Only used by first_available_slot
    source: Optional[str] = None  # Only used by capacity (booking channel filter)


@dataclass
class GetCapacityRequest:
    """Prepared request for getCapacity API call.
    
    Contains all validated and parsed data ready for API consumption.
    """
    dates: List[str]
    entity_map: Dict[str, List[str]]
    field_combinations: List[List[str]]
    has_entity_filters: bool
    start_time: Optional[str] = None
