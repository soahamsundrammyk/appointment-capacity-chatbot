"""Entity validation utilities for matching names to UUIDs."""

import logging
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def find_closest_match(query: str, candidates: List[str], threshold: float = 0.6) -> Optional[Tuple[str, float]]:
    """Find the closest matching string from a list of candidates.

    Args:
        query: The string to match
        candidates: List of possible matches
        threshold: Minimum similarity ratio (0.0-1.0) to consider a match

    Returns:
        Tuple of (best_match, similarity_score) or None if no match above threshold
    """
    if not query or not candidates:
        return None

    query_lower = query.lower().strip()
    best_match = None
    best_score = 0.0

    for candidate in candidates:
        candidate_lower = candidate.lower().strip()

        # Exact match (case-insensitive)
        if query_lower == candidate_lower:
            return (candidate, 1.0)

        # Fuzzy match using SequenceMatcher
        score = SequenceMatcher(None, query_lower, candidate_lower).ratio()

        # Also check if query is contained in candidate or vice versa
        if query_lower in candidate_lower or candidate_lower in query_lower:
            score = max(score, 0.8)  # Boost score for substring matches

        if score > best_score:
            best_score = score
            best_match = candidate

    if best_match and best_score >= threshold:
        return (best_match, best_score)

    return None


def validate_advisor_names(
    advisor_names: List[str],
    cached_data: Dict[str, Any],
    fuzzy_match: bool = True
) -> Dict[str, Any]:
    """Validate advisor names against cached data.

    Args:
        advisor_names: List of advisor names to validate
        cached_data: Cached data containing advisors list
        fuzzy_match: If True, suggest similar names for non-exact matches

    Returns:
        Dict with:
        - valid: List of valid (advisor_name, uuid) tuples
        - invalid: List of names that couldn't be matched
        - suggestions: Dict of invalid_name -> [suggested_names]
        - message: Human-readable summary
    """
    advisors = cached_data.get("advisors", [])
    if not advisors:
        return {
            "valid": [],
            "invalid": advisor_names,
            "suggestions": {},
            "message": "No advisor data available in cache."
        }

    # Build name -> uuid mapping
    # Note: Match how UUIDMapper extracts names: firstName + lastName
    name_to_uuid = {}
    all_names = []
    for advisor in advisors:
        # Get UUID - check both possible field names
        uuid = advisor.get("uuid", "") or advisor.get("dealerAssociateUUID", "")
        if not uuid:
            continue

        # Get name - use firstName + lastName
        first_name = advisor.get("firstName", "") or ""
        last_name = advisor.get("lastName", "") or ""
        name = f"{first_name} {last_name}".strip()

        # Fallback to associateName or name fields if firstName/lastName not available
        if not name:
            name = advisor.get("associateName", "") or advisor.get("name", "")

        if name and uuid:
            name_to_uuid[name.lower().strip()] = (name, uuid)
            all_names.append(name)

    valid = []
    invalid = []
    suggestions = {}

    for name in advisor_names:
        name_lower = name.lower().strip()

        # Exact match
        if name_lower in name_to_uuid:
            original_name, uuid = name_to_uuid[name_lower]
            valid.append((original_name, uuid))
            logger.info(f"Validated advisor: '{name}' -> UUID: {uuid[:20]}...")
        elif fuzzy_match:
            # Try fuzzy match
            match_result = find_closest_match(name, all_names)
            if match_result:
                matched_name, score = match_result
                matched_lower = matched_name.lower().strip()
                original_name, uuid = name_to_uuid[matched_lower]
                valid.append((original_name, uuid))
                logger.info(f"Fuzzy matched advisor: '{name}' -> '{original_name}' (score: {score:.2f})")
            else:
                invalid.append(name)
                # Find partial matches for suggestions
                partial_matches = [n for n in all_names if name_lower in n.lower() or n.lower() in name_lower]
                if partial_matches:
                    suggestions[name] = partial_matches[:3]
                logger.warning(f"Invalid advisor name: '{name}'. No match found.")
        else:
            invalid.append(name)
            logger.warning(f"Invalid advisor name: '{name}'")

    # Build message
    if not invalid:
        message = f"All {len(valid)} advisor(s) validated successfully."
    else:
        message = f"Validated {len(valid)} advisor(s). Could not find: {', '.join(invalid)}."
        if suggestions:
            message += " Did you mean: " + "; ".join([
                f"'{k}' -> {v}" for k, v in suggestions.items()
            ])

    return {
        "valid": valid,
        "invalid": invalid,
        "suggestions": suggestions,
        "message": message
    }


def validate_transport_option_names(
    transport_names: List[str],
    cached_data: Dict[str, Any],
    fuzzy_match: bool = True
) -> Dict[str, Any]:
    """Validate transport option names against cached data.

    Args:
        transport_names: List of transport option names to validate
        cached_data: Cached data containing transport_options list
        fuzzy_match: If True, suggest similar names for non-exact matches

    Returns:
        Dict with valid, invalid, suggestions, and message
    """
    transport_options = cached_data.get("transport_options", [])
    if not transport_options:
        return {
            "valid": [],
            "invalid": transport_names,
            "suggestions": {},
            "message": "No transport option data available in cache."
        }

    # Build name -> uuid mapping
    # Note: Transport options use customName/optionName, not 'name'
    name_to_uuid = {}
    all_names = []
    for option in transport_options:
        # Match how UUIDMapper extracts names: customName first, then optionName
        name = option.get("customName", "") or option.get("optionName", "") or option.get("name", "") or option.get("transportOptionName", "")
        uuid = option.get("transportOptionUuid", "") or option.get("uuid", "") or option.get("transportOptionUUID", "")
        if name and uuid:
            name_to_uuid[name.lower().strip()] = (name, uuid)
            all_names.append(name)

    valid = []
    invalid = []
    suggestions = {}

    for name in transport_names:
        name_lower = name.lower().strip()

        if name_lower in name_to_uuid:
            original_name, uuid = name_to_uuid[name_lower]
            valid.append((original_name, uuid))
            logger.info(f"Validated transport option: '{name}' -> UUID: {uuid[:20]}...")
        elif fuzzy_match:
            match_result = find_closest_match(name, all_names)
            if match_result:
                matched_name, score = match_result
                matched_lower = matched_name.lower().strip()
                original_name, uuid = name_to_uuid[matched_lower]
                valid.append((original_name, uuid))
                logger.info(f"Fuzzy matched transport: '{name}' -> '{original_name}' (score: {score:.2f})")
            else:
                invalid.append(name)
                partial_matches = [n for n in all_names if name_lower in n.lower() or n.lower() in name_lower]
                if partial_matches:
                    suggestions[name] = partial_matches[:3]
                logger.warning(f"Invalid transport option: '{name}'")
        else:
            invalid.append(name)

    if not invalid:
        message = f"All {len(valid)} transport option(s) validated successfully."
    else:
        message = f"Validated {len(valid)} transport option(s). Could not find: {', '.join(invalid)}."
        if suggestions:
            message += " Did you mean: " + "; ".join([
                f"'{k}' -> {v}" for k, v in suggestions.items()
            ])

    return {
        "valid": valid,
        "invalid": invalid,
        "suggestions": suggestions,
        "message": message
    }


def validate_team_names(
    team_names: List[str],
    cached_data: Dict[str, Any],
    fuzzy_match: bool = True
) -> Dict[str, Any]:
    """Validate team names against cached data.

    Args:
        team_names: List of team names to validate
        cached_data: Cached data containing teams list
        fuzzy_match: If True, suggest similar names for non-exact matches

    Returns:
        Dict with valid, invalid, suggestions, and message
    """
    teams = cached_data.get("teams", [])
    if not teams:
        return {
            "valid": [],
            "invalid": team_names,
            "suggestions": {},
            "message": "No team data available in cache."
        }

    # Build name -> uuid mapping
    name_to_uuid = {}
    all_names = []
    for team in teams:
        name = team.get("name", "") or team.get("teamName", "")
        uuid = team.get("uuid", "") or team.get("teamUUID", "")
        if name and uuid:
            name_to_uuid[name.lower().strip()] = (name, uuid)
            all_names.append(name)

    valid = []
    invalid = []
    suggestions = {}

    for name in team_names:
        name_lower = name.lower().strip()

        if name_lower in name_to_uuid:
            original_name, uuid = name_to_uuid[name_lower]
            valid.append((original_name, uuid))
            logger.info(f"Validated team: '{name}' -> UUID: {uuid[:20]}...")
        elif fuzzy_match:
            match_result = find_closest_match(name, all_names)
            if match_result:
                matched_name, score = match_result
                matched_lower = matched_name.lower().strip()
                original_name, uuid = name_to_uuid[matched_lower]
                valid.append((original_name, uuid))
                logger.info(f"Fuzzy matched team: '{name}' -> '{original_name}' (score: {score:.2f})")
            else:
                invalid.append(name)
                partial_matches = [n for n in all_names if name_lower in n.lower() or n.lower() in name_lower]
                if partial_matches:
                    suggestions[name] = partial_matches[:3]
                logger.warning(f"Invalid team name: '{name}'")
        else:
            invalid.append(name)

    if not invalid:
        message = f"All {len(valid)} team(s) validated successfully."
    else:
        message = f"Validated {len(valid)} team(s). Could not find: {', '.join(invalid)}."
        if suggestions:
            message += " Did you mean: " + "; ".join([
                f"'{k}' -> {v}" for k, v in suggestions.items()
            ])

    return {
        "valid": valid,
        "invalid": invalid,
        "suggestions": suggestions,
        "message": message
    }


def validate_entities(
    entity_type: str,
    entity_names: List[str],
    cached_data: Dict[str, Any],
    fuzzy_match: bool = True
) -> Dict[str, Any]:
    """Generic entity validation dispatcher.

    Args:
        entity_type: Type of entity ('advisor', 'transport', 'team')
        entity_names: List of names to validate
        cached_data: Cached data from state
        fuzzy_match: Whether to use fuzzy matching

    Returns:
        Validation result dict
    """
    entity_type_lower = entity_type.lower().strip()

    if entity_type_lower in ("advisor", "advisors", "service_advisor"):
        return validate_advisor_names(entity_names, cached_data, fuzzy_match)
    elif entity_type_lower in ("transport", "transport_option", "transport_options"):
        return validate_transport_option_names(entity_names, cached_data, fuzzy_match)
    elif entity_type_lower in ("team", "teams"):
        return validate_team_names(entity_names, cached_data, fuzzy_match)
    else:
        return {
            "valid": [],
            "invalid": entity_names,
            "suggestions": {},
            "message": f"Unknown entity type: {entity_type}. Valid types: advisor, transport, team"
        }
