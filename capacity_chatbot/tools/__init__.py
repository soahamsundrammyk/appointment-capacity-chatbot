"""Tool exports for capacity chatbot."""

from capacity_chatbot.enums import (
    ApplicabilityRuleField,
    CapacityType,
    RuleField,
    RuleMatchingCriteria,
)
from capacity_chatbot.tools.appointments import APPOINTMENT_TOOLS
from capacity_chatbot.tools.capacity import get_capacity_tool
from capacity_chatbot.tools.entities import ENTITY_TOOLS
from capacity_chatbot.tools.first_available_slot import get_first_available_slot_tool
from capacity_chatbot.tools.opcode import search_opcode_tool
from capacity_chatbot.tools.rules import get_rules_tool

CAPACITY_TOOLS = [
    *ENTITY_TOOLS,
    *APPOINTMENT_TOOLS,
    get_rules_tool,
    get_capacity_tool,
    get_first_available_slot_tool,
    search_opcode_tool,
]

__all__ = [
    "CapacityType",
    "ApplicabilityRuleField",
    "RuleMatchingCriteria",
    "RuleField",
    "ENTITY_TOOLS",
    "APPOINTMENT_TOOLS",
    "CAPACITY_TOOLS",
    "get_rules_tool",
    "get_capacity_tool",
    "get_first_available_slot_tool",
    "search_opcode_tool",
]
