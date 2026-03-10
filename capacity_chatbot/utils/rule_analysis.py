"""Rule conflict and complementary analysis utilities.

Performs data-level analysis of capacity and assignment rules using exact time slots,
entity UUIDs, and operators rather than relying on text descriptions.
"""

from collections import defaultdict
from typing import Any

from capacity_chatbot.enums import FieldDisplayName

# Constants
MAX_SUMMARY_VALUES = 2


def detect_conflicts(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect conflicts in both CAPACITY and ASSIGNMENT rules.

    Performs data-level analysis using exact time slots, entity UUIDs, and operators
    rather than relying on text descriptions.
    """
    conflicts = []
    capacity_rules = [r for r in rules if r.get("ruleType") == "CAPACITY"]
    assignment_rules = [r for r in rules if r.get("ruleType") == "ASSIGNMENT"]

    conflicts.extend(_detect_capacity_conflicts(capacity_rules))
    conflicts.extend(_detect_assignment_conflicts(assignment_rules))

    return conflicts


def detect_complementary_rules(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect complementary CAPACITY rule pairs (same entity, non-overlapping time slots).

    These are rule pairs that look similar but intentionally cover different time slots,
    e.g., "allow 1 at 8 AM, 1 PM" + "block all other slots".
    """
    capacity_rules = [r for r in rules if r.get("ruleType") == "CAPACITY"]

    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for rule in capacity_rules:
        key = _get_entity_key(rule)
        groups[key].append(rule)

    complementary = []
    for group_rules in groups.values():
        if len(group_rules) < 2:
            continue
        for i, rule1 in enumerate(group_rules):
            for rule2 in group_rules[i + 1 :]:
                if _are_complementary(rule1, rule2):
                    complementary.append(
                        {
                            "rule1_name": rule1.get("ruleName", "Unnamed"),
                            "rule2_name": rule2.get("ruleName", "Unnamed"),
                        }
                    )

    return complementary


# =============================================================================
# Entity & Time Slot Helpers
# =============================================================================


def _get_entity_key(rule: dict[str, Any]) -> tuple:
    """Extract entity identity from ifClauses for grouping.

    Rules with the same entity key affect the same entity (advisor, team, etc.).
    """
    if_clauses = rule.get("ifClauses") or []
    parts = []
    for clause in if_clauses:
        field = clause.get("field", "")
        values = tuple(sorted(clause.get("values", [])))
        parts.append((field, values))
    return tuple(sorted(parts))


def _get_day_slots_map(rule: dict[str, Any]) -> dict[str, set[str] | None]:
    """Extract a scope map from a rule's applicabilityClause.

    Keys are day names (for DAY/DAY_AND_TIME) or date strings (for DATE/DATE_AND_TIME).
    Values are set(timeSlots) for time-specific rules, or None for "all day/date".

    Returns:
        Dict mapping scope key to set of time slots or None.
        Days with empty timeSlots in DAY_AND_TIME rules are excluded (rule doesn't apply).
    """
    applicability = rule.get("applicabilityClause") or {}
    day_time_list = applicability.get("dayTimeList") or []
    date_list = applicability.get("dateList") or []
    field = applicability.get("field", "")

    result: dict[str, set[str] | None] = {}

    if field == "DAY_AND_TIME":
        for entry in day_time_list:
            day = entry.get("day", "").upper()
            if not day:
                continue
            slots = entry.get("timeSlots", [])
            if not slots:
                continue  # Empty timeSlots = rule doesn't apply on this day
            result[day] = set(slots)

    elif field == "DAY":
        for entry in day_time_list:
            day = entry.get("day", "").upper()
            if day:
                result[day] = None  # None = applies all day

    elif field == "DATE":
        for date_str in date_list:
            if date_str:
                result[date_str] = None  # Applies all day on this date

    elif field == "DATE_AND_TIME":
        # Collect all time slots from dayTimeList
        all_slots: set[str] = set()
        for entry in day_time_list:
            for slot in entry.get("timeSlots", []):
                all_slots.add(slot)
        # Apply to each date
        for date_str in date_list:
            if date_str:
                result[date_str] = all_slots if all_slots else None

    return result


def _normalize_then_clauses(rule: dict[str, Any]) -> str:
    """Normalize THEN clauses into a comparable string."""
    parts = []
    for clause in rule.get("thenClauses") or []:
        parts.append(
            "%s:%s:%s"
            % (
                clause.get("field", ""),
                sorted(clause.get("values", [])),
                clause.get("frequency", ""),
            )
        )
    return "|".join(sorted(parts))


# =============================================================================
# Capacity Conflict Detection
# =============================================================================


def _detect_capacity_conflicts(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect conflicts among CAPACITY rules.

    Two capacity rules conflict only when ALL of:
    1. Same entity (same ifClauses field+values)
    2. Overlapping days
    3. Overlapping time slots on those days
    4. Different THEN values (different limits)
    """
    groups: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for rule in rules:
        key = _get_entity_key(rule)
        groups[key].append(rule)

    conflicts = []
    for group_rules in groups.values():
        if len(group_rules) < 2:
            continue
        for i, rule1 in enumerate(group_rules):
            for rule2 in group_rules[i + 1 :]:
                result = _check_capacity_pair(rule1, rule2)
                if result:
                    conflicts.append(result)

    return conflicts


def _check_capacity_pair(
    rule1: dict[str, Any], rule2: dict[str, Any]
) -> dict[str, Any] | None:
    """Check if two capacity rules for the same entity have conflicting time slots."""
    # Same THEN action = not a conflict (possibly redundant but not harmful)
    if _normalize_then_clauses(rule1) == _normalize_then_clauses(rule2):
        return None

    slots1 = _get_day_slots_map(rule1)
    slots2 = _get_day_slots_map(rule2)

    common_days = set(slots1.keys()) & set(slots2.keys())
    if not common_days:
        return None

    overlapping_days = []
    for day in common_days:
        s1 = slots1[day]
        s2 = slots2[day]
        if s1 is None or s2 is None:
            # At least one is "all day" → overlap
            overlapping_days.append(day)
        elif s1 & s2:
            overlapping_days.append(day)

    if not overlapping_days:
        return None  # Same days but non-overlapping time slots → complementary

    return {
        "type": "CAPACITY",
        "rule1_name": rule1.get("ruleName", "Unnamed"),
        "rule2_name": rule2.get("ruleName", "Unnamed"),
        "overlap_days": sorted(overlapping_days),
        "rule1_action": summarize_then(rule1),
        "rule2_action": summarize_then(rule2),
    }


def _are_complementary(rule1: dict[str, Any], rule2: dict[str, Any]) -> bool:
    """Check if two capacity rules are complementary (same entity, non-overlapping slots).

    Returns True when rules share days but cover different time slots with different limits.
    """
    if _normalize_then_clauses(rule1) == _normalize_then_clauses(rule2):
        return False  # Same action = redundant, not complementary

    slots1 = _get_day_slots_map(rule1)
    slots2 = _get_day_slots_map(rule2)

    common_days = set(slots1.keys()) & set(slots2.keys())
    if not common_days:
        return False  # Different days entirely

    for day in common_days:
        s1 = slots1[day]
        s2 = slots2[day]
        if s1 is None or s2 is None:
            return False  # One is "all day" → can't be complementary
        if s1 & s2:
            return False  # Overlapping slots

    return True


# =============================================================================
# Assignment Conflict Detection
# =============================================================================


def _detect_assignment_conflicts(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect conflicts among ASSIGNMENT rules, respecting IN/NOT_IN operators."""
    conflicts = []

    for i, rule1 in enumerate(rules):
        for rule2 in rules[i + 1 :]:
            if _assignment_conditions_overlap(rule1, rule2) and _has_different_actions(
                rule1, rule2
            ):
                conflicts.append(
                    {
                        "type": "ASSIGNMENT",
                        "rule1_name": rule1.get("ruleName", "Unnamed"),
                        "rule2_name": rule2.get("ruleName", "Unnamed"),
                        "rule1_action": summarize_then(rule1),
                        "rule2_action": summarize_then(rule2),
                    }
                )

    return conflicts


def _assignment_conditions_overlap(
    rule1: dict[str, Any], rule2: dict[str, Any]
) -> bool:
    """Check if two assignment rules' conditions can match the same input.

    Respects IN vs NOT_IN operators:
    - IN + IN with overlapping values → overlap
    - IN + NOT_IN where all IN values are excluded → mutually exclusive (no overlap)
    - NOT_IN + NOT_IN → overlap possible (both match inputs outside their lists)
    """
    clauses1 = {c.get("field", ""): c for c in (rule1.get("ifClauses") or [])}
    clauses2 = {c.get("field", ""): c for c in (rule2.get("ifClauses") or [])}

    # If either has no conditions, it matches everything → overlap
    if not clauses1 or not clauses2:
        return True

    common_fields = set(clauses1.keys()) & set(clauses2.keys())
    if not common_fields:
        return True  # Different fields → could match same input

    for field in common_fields:
        c1 = clauses1[field]
        c2 = clauses2[field]

        op1 = c1.get("operator", "IN").upper()
        op2 = c2.get("operator", "IN").upper()
        vals1 = set(c1.get("values", []))
        vals2 = set(c2.get("values", []))

        if op1 == "IN" and op2 == "IN":
            if not (vals1 & vals2):
                return False  # No value overlap → mutually exclusive
        elif (op1 == "IN" and op2 == "NOT_IN") or (op1 == "NOT_IN" and op2 == "IN"):
            in_vals = vals1 if op1 == "IN" else vals2
            not_in_vals = vals2 if op1 == "IN" else vals1
            if in_vals <= not_in_vals:
                return False  # All IN values are excluded by NOT_IN → mutually exclusive
        # NOT_IN + NOT_IN: assume overlap (can't determine without full value space)

    return True


def _has_different_actions(rule1: dict[str, Any], rule2: dict[str, Any]) -> bool:
    """Check if two rules have different THEN actions."""
    return _normalize_then_clauses(rule1) != _normalize_then_clauses(rule2)


def summarize_then(rule: dict[str, Any]) -> str:
    """Summarize a rule's THEN action."""
    parts = []
    for clause in rule.get("thenClauses") or []:
        field = clause.get("field", "")
        values = clause.get("verboseValues", []) or clause.get("values", [])
        name = FieldDisplayName.get(field)
        parts.append("%s: %s" % (name, ", ".join(str(v) for v in values[:MAX_SUMMARY_VALUES])))
    return "; ".join(parts) if parts else "No action"
