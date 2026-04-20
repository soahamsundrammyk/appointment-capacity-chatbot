"""Request models for API endpoints."""

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, field_validator


class RunInput(BaseModel):
    """Input for a run - matches LangGraph API format."""

    messages: list[dict[str, Any]]
    department_uuid: str | None = ""
    dealer_uuid: str | None = ""
    cached_data: dict[str, Any] | None = None
    user_tier: Literal["base", "manager", "internal"] = "base"


class RunRequest(BaseModel):
    """Request to create a run - matches LangGraph API format."""

    input: RunInput
    config: dict[str, Any] | None = None
    stream_mode: list[str] | None = None


class EntityFilterRequest(BaseModel):
    """Shared request model for capacity and first available slot queries.

    Contains common entity filtering parameters used by both tools.
    """

    dates: list[str] | None = None
    transport_option_names: list[str] | None = None
    advisor_names: list[str] | None = None
    team_names: list[str] | None = None
    opcodes: list[str] | None = None
    start_time: str | None = None

    @field_validator("dates", "transport_option_names", "advisor_names", "team_names", "opcodes", mode="before")
    @classmethod
    def coerce_str_to_list(cls, v: Any) -> list[str] | None:
        """Coerce a bare string into a single-element list.

        LLMs sometimes pass a string instead of a list for these fields.
        """
        if isinstance(v, str):
            return [v]
        return v
    end_time: str | None = None  # Only used by first_available_slot
    source: str | None = None  # Only used by capacity (booking channel filter)


@dataclass
class GetCapacityRequest:
    """Prepared request for getCapacity API call.

    Contains all validated and parsed data ready for API consumption.
    """

    dates: list[str]
    entity_map: dict[str, list[str]]
    field_combinations: list[list[str]]
    has_entity_filters: bool
    start_time: str | None = None
