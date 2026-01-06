"""Tool modules for capacity chatbot.

This package re-exports tool implementations from the parent tools.py module
to maintain backward compatibility while organizing tools in a package structure.
"""

# Import tool implementations from the parent tools.py module
# Since tools.py is a sibling file (not in this package), we need to import it directly
import importlib.util
import sys
import os

# Get the path to the parent tools.py module
_parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_tools_py_path = os.path.join(_parent_dir, "tools.py")

# Load the tools.py module
_spec = importlib.util.spec_from_file_location("capacity_chatbot.tools_module", _tools_py_path)
_tools_module = importlib.util.module_from_spec(_spec)
sys.modules["capacity_chatbot.tools_module"] = _tools_module
_spec.loader.exec_module(_tools_module)

# Re-export all the tool implementations and types
__all__ = [
    "get_rules_tool_impl",
    "get_capacity_tool_impl",
    "get_first_available_slot_tool_impl",
    "search_opcode_tool_impl",
    "CapacityType",
    "ApplicabilityRuleField",
    "RuleMatchingCriteria",
]

# Re-export functions and classes
get_rules_tool_impl = _tools_module.get_rules_tool_impl
get_capacity_tool_impl = _tools_module.get_capacity_tool_impl
get_first_available_slot_tool_impl = _tools_module.get_first_available_slot_tool_impl
search_opcode_tool_impl = _tools_module.search_opcode_tool_impl
CapacityType = _tools_module.CapacityType
ApplicabilityRuleField = _tools_module.ApplicabilityRuleField
RuleMatchingCriteria = _tools_module.RuleMatchingCriteria
