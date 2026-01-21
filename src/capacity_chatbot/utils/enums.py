"""Enums for capacity chatbot tools - matching Java API enums."""

from enum import Enum


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
