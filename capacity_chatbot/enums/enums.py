"""Enums for capacity chatbot - matching Java API enums."""

from enum import Enum
from typing import List, Optional


# Maximum integer value used by API to represent "unlimited"
MAX_LIMIT = 2147483647


class CapacityType(str, Enum):
    """Capacity type enum."""
    APPOINTMENT_COUNT = "APPOINTMENT_COUNT"
    SERVICE_HOURS = "SERVICE_HOURS"


class ApplicabilityRuleField(str, Enum):
    """Applicability rule field enum."""
    DAY = "DAY"
    DATE = "DATE"
    DATE_AND_TIME = "DATE_AND_TIME"
    DAY_AND_TIME = "DAY_AND_TIME"


class RuleMatchingCriteria(str, Enum):
    """Rule matching criteria enum."""
    EXACTLY_MATCHES = "EXACTLY_MATCHES"
    INCLUSIVELY_MATCHES = "INCLUSIVELY_MATCHES"


class RuleField(str, Enum):
    """Rule field enum for entity/filter mapping."""
    TRANSPORT_OPTION_UUID = "TRANSPORT_OPTION_UUID"
    DEALER_ASSOCIATE_UUID = "DEALER_ASSOCIATE_UUID"
    TEAM_UUID = "TEAM_UUID"
    OPERATION_UUID = "OPERATION_UUID"
    SKILL_UUID = "SKILL_UUID"
    VEHICLE_MAKE = "VEHICLE_MAKE"
    VEHICLE_MODEL = "VEHICLE_MODEL"
    VEHICLE_YEAR = "VEHICLE_YEAR"
    SOURCE = "SOURCE"
    CUSTOMER_UUID = "CUSTOMER_UUID"


class LimitingFactor(str, Enum):
    """Limiting factor types returned by capacity API."""
    TRANSPORT_OPTION = "TRANSPORT_OPTION"
    CAPACITY_RULE = "CAPACITY_RULE"
    DEALER_SCHEDULE = "DEALER_SCHEDULE"
    INDIVIDUAL_SCHEDULE = "INDIVIDUAL_SCHEDULE"
    OPCODE_DAILY_LIMIT = "OPCODE_DAILY_LIMIT"
    TEAM = "TEAM"

    @property
    def display_name(self) -> str:
        """Human-readable name for the limiting factor."""
        names = LimitingFactor.__dict__.get("_DISPLAY_NAMES", {})
        return names.get(self.value, self.value.lower().replace("_", " "))


LimitingFactor._DISPLAY_NAMES = {
    "TRANSPORT_OPTION": "transport option limit",
    "CAPACITY_RULE": "capacity rule",
    "DEALER_SCHEDULE": "dealer schedule",
    "INDIVIDUAL_SCHEDULE": "advisor schedule",
    "OPCODE_DAILY_LIMIT": "opcode daily limit",
    "TEAM": "team limit",
}


class SourceType(str, Enum):
    """Booking source types."""
    WEB = "Web"
    DEALER_APP = "DealerApp"
    DMS = "DMS"

    @classmethod
    def from_input(cls, value: str) -> "SourceType":
        """Map user input to SourceType."""
        # Use class __dict__ to access the mapping (Enum treats class vars as members)
        mappings = SourceType.__dict__.get("_INPUT_MAPPINGS", {})
        return cls[mappings.get(value.lower(), "WEB")]


SourceType._INPUT_MAPPINGS = {
    "web": "WEB",
    "online": "WEB",
    "online scheduler": "WEB",
    "dealerapp": "DEALER_APP",
    "dealer app": "DEALER_APP",
    "dms": "DMS",
}


class EntityType(str, Enum):
    """Entity types for filtering and display."""
    TRANSPORT_OPTIONS = "transport_options"
    ADVISORS = "advisors"
    TEAMS = "teams"

    @classmethod
    def from_alias(cls, value: str) -> Optional["EntityType"]:
        """Resolve entity type from alias."""
        # Use class __dict__ to access the mapping (Enum treats class vars as members)
        aliases = EntityType.__dict__.get("_ALIAS_MAPPINGS", {})
        alias_key = value.lower().strip()
        enum_name = aliases.get(alias_key)
        return cls[enum_name] if enum_name else None


EntityType._ALIAS_MAPPINGS = {
    "transport_options": "TRANSPORT_OPTIONS",
    "transport": "TRANSPORT_OPTIONS",
    "transportation": "TRANSPORT_OPTIONS",
    "advisors": "ADVISORS",
    "advisor": "ADVISORS",
    "service_advisors": "ADVISORS",
    "teams": "TEAMS",
    "team": "TEAMS",
}


class FieldDisplayName(str, Enum):
    """Human-readable field names for API fields."""
    DEALER_ASSOCIATE_UUID = "Advisor"
    TEAM_UUID = "Team"
    TRANSPORT_OPTION_UUID = "Transport Option"
    OPERATION_UUID = "Opcode"
    OP_CODE = "Opcode"
    OPCODE = "Opcode"
    SKILL = "Service"
    VEHICLE_MAKE = "Vehicle Make"
    VEHICLE_MODEL = "Vehicle Model"
    VEHICLE_YEAR = "Vehicle Year"
    CUSTOMER_TYPE = "Customer Type"
    SOURCE = "Booking Source"

    @classmethod
    def get(cls, field: str, default: str = None) -> str:
        """Get display name for a field."""
        try:
            return cls[field].value
        except KeyError:
            return default or field.replace("_UUID", "").replace("_", " ").title()


class DayName(str, Enum):
    """Day names for scheduling (index 0 = Sunday)."""
    SUN = "Sun"
    MON = "Mon"
    TUE = "Tue"
    WED = "Wed"
    THU = "Thu"
    FRI = "Fri"
    SAT = "Sat"

    @property
    def full_name(self) -> str:
        """Get full day name."""
        # Use class __dict__ to access the mapping (Enum treats class vars as members)
        full_names = DayName.__dict__.get("_FULL_NAMES", {})
        return full_names[self.value]

    @classmethod
    def from_index(cls, index: int) -> "DayName":
        """Get day name by index (0=Sunday, 6=Saturday)."""
        return list(cls)[index % 7]

    @classmethod
    def all_short(cls) -> List[str]:
        """Get all short day names."""
        return [d.value for d in cls]

    @classmethod
    def all_full(cls) -> List[str]:
        """Get all full day names."""
        return [d.full_name for d in cls]


DayName._FULL_NAMES = {
    "Sun": "Sunday",
    "Mon": "Monday",
    "Tue": "Tuesday",
    "Wed": "Wednesday",
    "Thu": "Thursday",
    "Fri": "Friday",
    "Sat": "Saturday",
}


class FilterField(str, Enum):
    """Maps filter parameter names to API field names."""
    TEAM = "TEAM_UUID,TEAM"
    ADVISOR = "DEALER_ASSOCIATE_UUID,ADVISOR,SERVICE_ADVISOR"
    TRANSPORT = "TRANSPORT_OPTION_UUID,TRANSPORT_OPTION"
    OPCODE = "OPERATION_UUID,OP_CODE,OPCODE,SKILL"

    @property
    def fields(self) -> List[str]:
        """Get list of API field names for this filter."""
        return self.value.split(",")

    @classmethod
    def from_param_name(cls, param: str) -> Optional["FilterField"]:
        """Map parameter name to FilterField."""
        # Use class __dict__ to access the mapping (Enum treats class vars as members)
        mappings = FilterField.__dict__.get("_PARAM_NAME_MAPPINGS", {})
        enum_name = mappings.get(param)
        return cls[enum_name] if enum_name else None

    @classmethod
    def from_entity_type(cls, entity_type: str) -> Optional["FilterField"]:
        """Map entity type to FilterField."""
        # Use class __dict__ to access the mapping (Enum treats class vars as members)
        mappings = FilterField.__dict__.get("_ENTITY_TYPE_MAPPINGS", {})
        enum_name = mappings.get(entity_type.lower())
        return cls[enum_name] if enum_name else None


FilterField._PARAM_NAME_MAPPINGS = {
    "team_name": "TEAM",
    "advisor_name": "ADVISOR",
    "transport_option": "TRANSPORT",
    "opcode_name": "OPCODE",
}

FilterField._ENTITY_TYPE_MAPPINGS = {
    "team": "TEAM",
    "advisor": "ADVISOR",
    "transport": "TRANSPORT",
    "opcode": "OPCODE",
}
