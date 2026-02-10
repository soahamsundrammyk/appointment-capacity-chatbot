"""Enums for capacity chatbot tools - matching Java API enums."""

from enum import Enum
from typing import List


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
        names = {
            "TRANSPORT_OPTION": "transport option limit",
            "CAPACITY_RULE": "capacity rule",
            "DEALER_SCHEDULE": "dealer schedule",
            "INDIVIDUAL_SCHEDULE": "advisor schedule",
            "OPCODE_DAILY_LIMIT": "opcode daily limit",
            "TEAM": "team limit",
        }
        return names.get(self.value, self.value.lower().replace("_", " "))


class SourceType(str, Enum):
    """Booking source types."""
    WEB = "Web"
    DEALER_APP = "DealerApp"
    DMS = "DMS"

    @classmethod
    def from_input(cls, value: str) -> "SourceType":
        """Map user input to SourceType."""
        mappings = {
            "web": cls.WEB,
            "online": cls.WEB,
            "online scheduler": cls.WEB,
            "dealerapp": cls.DEALER_APP,
            "dealer app": cls.DEALER_APP,
            "dms": cls.DMS,
        }
        return mappings.get(value.lower(), cls.WEB)


class EntityType(str, Enum):
    """Entity types for filtering and display."""
    TRANSPORT_OPTIONS = "transport_options"
    ADVISORS = "advisors"
    TEAMS = "teams"

    @classmethod
    def from_alias(cls, value: str) -> "EntityType":
        """Resolve entity type from alias."""
        aliases = {
            "transport_options": cls.TRANSPORT_OPTIONS,
            "transport": cls.TRANSPORT_OPTIONS,
            "transportation": cls.TRANSPORT_OPTIONS,
            "advisors": cls.ADVISORS,
            "advisor": cls.ADVISORS,
            "service_advisors": cls.ADVISORS,
            "teams": cls.TEAMS,
            "team": cls.TEAMS,
        }
        return aliases.get(value.lower().strip())


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
        return {
            "Sun": "Sunday",
            "Mon": "Monday",
            "Tue": "Tuesday",
            "Wed": "Wednesday",
            "Thu": "Thursday",
            "Fri": "Friday",
            "Sat": "Saturday",
        }[self.value]

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
    def from_param_name(cls, param: str) -> "FilterField":
        """Map parameter name to FilterField."""
        mappings = {
            "team_name": cls.TEAM,
            "advisor_name": cls.ADVISOR,
            "transport_option": cls.TRANSPORT,
            "opcode_name": cls.OPCODE,
        }
        return mappings.get(param)

    @classmethod
    def from_entity_type(cls, entity_type: str) -> "FilterField":
        """Map entity type to FilterField."""
        mappings = {
            "team": cls.TEAM,
            "advisor": cls.ADVISOR,
            "transport": cls.TRANSPORT,
            "opcode": cls.OPCODE,
        }
        return mappings.get(entity_type.lower())

