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


def _validate_entity_names_generic(
    name_uuid_pairs: List[Tuple[str, str]],
    entity_type_name: str,
    names_to_validate: List[str],
) -> Dict[str, Any]:
    """Generic entity validation function.

    Args:
        name_uuid_pairs: List of (name, uuid) tuples from cached_data
        entity_type_name: Human-readable entity type name (e.g., "advisor", "transport option")
        names_to_validate: List of names to validate

    Returns:
        Dict with valid, invalid, suggestions, and message
    """
    if not name_uuid_pairs:
        return {
            "valid": [],
            "message": f"No {entity_type_name} data available in cache.",
        }

    # Build name -> uuid mapping
    name_to_uuid = {}
    all_names = []
    for name, uuid in name_uuid_pairs:
        if name and uuid:
            name_to_uuid[name.lower().strip()] = (name, uuid)
            all_names.append(name)

    valid = []
    invalid = []
    suggestions = {}

    for name in names_to_validate:
        name_lower = name.lower().strip()

        # Exact match
        if name_lower in name_to_uuid:
            original_name, uuid = name_to_uuid[name_lower]
            valid.append((original_name, uuid))
            logger.info("Validated %s: '%s' -> UUID: %s", entity_type_name, name, uuid)
        else:
            # Try fuzzy match
            match_result = find_closest_match(name, all_names)
            if match_result:
                matched_name, score = match_result
                matched_lower = matched_name.lower().strip()
                original_name, uuid = name_to_uuid[matched_lower]
                valid.append((original_name, uuid))
                logger.info("Fuzzy matched %s: '%s' -> '%s' (score: %.2f)", entity_type_name, name, original_name, score)
            else:
                invalid.append(name)
                # Find partial matches for suggestions
                partial_matches = [n for n in all_names if name_lower in n.lower() or n.lower() in name_lower]
                if partial_matches:
                    suggestions[name] = partial_matches[:3]
                logger.warning("Invalid %s name: '%s'. No match found.", entity_type_name, name)

    # Build message
    if not invalid:
        message = "All %d %s(s) validated successfully." % (len(valid), entity_type_name)
    else:
        message = "Validated %d %s(s). Could not find: %s." % (len(valid), entity_type_name, ", ".join(invalid))
        if suggestions:
            message += " Did you mean: " + "; ".join([
                "'%s' -> %s" % (k, v) for k, v in suggestions.items()
            ])

    return {
        "valid": valid,
        "message": message,
    }


def _extract_advisor_name(advisor: Dict[str, Any]) -> Optional[str]:
    """Extract advisor name from advisor dict."""
    first_name = advisor.get("firstName", "") or ""
    last_name = advisor.get("lastName", "") or ""
    name = "%s %s" % (first_name, last_name) if first_name or last_name else ""
    name = name.strip()
    return name if name else None


def _extract_advisor_uuid(advisor: Dict[str, Any]) -> Optional[str]:
    """Extract advisor UUID from advisor dict."""
    return advisor.get("uuid", "")


def validate_advisor_names(
    advisor_names: List[str],
    cached_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate advisor names against cached data.

    Args:
        advisor_names: List of advisor names to validate
        cached_data: Cached data containing advisors list

    Returns:
        Dict with:
        - valid: List of valid (advisor_name, uuid) tuples
        - invalid: List of names that couldn't be matched
        - suggestions: Dict of invalid_name -> [suggested_names]
        - message: Human-readable summary
    """
    advisors = cached_data.get("advisors", [])
    name_uuid_pairs = []
    for advisor in advisors:
        name = _extract_advisor_name(advisor)
        uuid = _extract_advisor_uuid(advisor)
        if name and uuid:
            name_uuid_pairs.append((name, uuid))
    
    return _validate_entity_names_generic(
        name_uuid_pairs=name_uuid_pairs,
        entity_type_name="advisor",
        names_to_validate=advisor_names,
    )


def _extract_transport_name(option: Dict[str, Any]) -> Optional[str]:
    """Extract transport option name from option dict."""
    return (
        option.get("customName", "") or
        option.get("optionName", "") or
        None
    )


def _extract_transport_uuid(option: Dict[str, Any]) -> Optional[str]:
    """Extract transport option UUID from option dict."""
    return (
        option.get("transportOptionUuid", "") or
        None
    )


def validate_transport_option_names(
    transport_names: List[str],
    cached_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate transport option names against cached data.

    Args:
        transport_names: List of transport option names to validate
        cached_data: Cached data containing transport_options list

    Returns:
        Dict with valid, invalid, suggestions, and message
    """
    transport_options = cached_data.get("transport_options", [])
    name_uuid_pairs = []
    for option in transport_options:
        name = _extract_transport_name(option)
        uuid = _extract_transport_uuid(option)
        if name and uuid:
            name_uuid_pairs.append((name, uuid))
    
    return _validate_entity_names_generic(
        name_uuid_pairs=name_uuid_pairs,
        entity_type_name="transport option",
        names_to_validate=transport_names,
    )


def _extract_team_name(team: Dict[str, Any]) -> Optional[str]:
    """Extract team name from team dict."""
    return team.get("name", "") or team.get("teamName", "") or None


def _extract_team_uuid(team: Dict[str, Any]) -> Optional[str]:
    """Extract team UUID from team dict."""
    return team.get("uuid", "") or team.get("teamUUID", "") or None


def validate_team_names(
    team_names: List[str],
    cached_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Validate team names against cached data.

    Args:
        team_names: List of team names to validate
        cached_data: Cached data containing teams list

    Returns:
        Dict with valid, invalid, suggestions, and message
    """
    teams = cached_data.get("teams", [])
    name_uuid_pairs = []
    for team in teams:
        name = _extract_team_name(team)
        uuid = _extract_team_uuid(team)
        if name and uuid:
            name_uuid_pairs.append((name, uuid))
    
    return _validate_entity_names_generic(
        name_uuid_pairs=name_uuid_pairs,
        entity_type_name="team",
        names_to_validate=team_names,
    )


def validate_entities(
    entity_type: str,
    entity_names: List[str],
    cached_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Generic entity validation dispatcher.

    Args:
        entity_type: Type of entity ('advisor', 'transport', 'team')
        entity_names: List of names to validate
        cached_data: Cached data from state

    Returns:
        Validation result dict
    """
    entity_type_lower = entity_type.lower().strip()

    if entity_type_lower in ("advisor", "advisors", "service_advisor"):
        return validate_advisor_names(entity_names, cached_data)
    elif entity_type_lower in ("transport", "transport_option", "transport_options"):
        return validate_transport_option_names(entity_names, cached_data)
    elif entity_type_lower in ("team", "teams"):
        return validate_team_names(entity_names, cached_data)
    else:
        return {
            "valid": [],
            "message": "Unknown entity type: %s. Valid types: advisor, transport, team" % entity_type,
        }
