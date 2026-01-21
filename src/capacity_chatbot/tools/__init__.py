"""Tool exports for capacity chatbot.

This package provides all tools for the ReAct agent.
"""

from capacity_chatbot.utils.enums import (
    CapacityType,
    ApplicabilityRuleField,
    RuleMatchingCriteria,
    RuleField,
)

# Import tools from individual modules
from capacity_chatbot.tools.knowledge import KNOWLEDGE_TOOLS
from capacity_chatbot.tools.entities import ENTITY_TOOLS
from capacity_chatbot.tools.rules import get_rules_tool
from capacity_chatbot.tools.capacity import get_capacity_tool
from capacity_chatbot.tools.first_available_slot import get_first_available_slot_tool
from capacity_chatbot.tools.opcode import search_opcode_tool

# Combined list of all tools for ReAct agent
CAPACITY_TOOLS = [
    *KNOWLEDGE_TOOLS,    # get_knowledge_answer
    *ENTITY_TOOLS,       # get_available_entities, confirm_entity
    get_rules_tool,
    get_capacity_tool,
    get_first_available_slot_tool,
    search_opcode_tool,
]

__all__ = [
    # Enums
    "CapacityType",
    "ApplicabilityRuleField", 
    "RuleMatchingCriteria",
    "RuleField",
    # Tool collections
    "KNOWLEDGE_TOOLS",
    "ENTITY_TOOLS",
    "CAPACITY_TOOLS",
    # Individual tools
    "get_rules_tool",
    "get_capacity_tool",
    "get_first_available_slot_tool",
    "search_opcode_tool",
]
