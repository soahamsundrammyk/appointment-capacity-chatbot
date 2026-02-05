"""Date parsing utilities for natural language date expressions."""

import re
from datetime import date, timedelta
from typing import List, Optional

# Day name to weekday number (Monday=0, Sunday=6)
DAY_NAME_TO_NUM = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6,
}


def parse_date_query(query: str, reference_date: Optional[date] = None) -> List[str]:
    """Parse natural language date expressions to list of YYYY-MM-DD strings.

    Args:
        query: Natural language date expression or YYYY-MM-DD date
        reference_date: Reference date for relative expressions (defaults to today)

    Returns:
        List of dates in YYYY-MM-DD format

    Examples:
        parse_date_query("tomorrow") -> ["2026-01-14"]
        parse_date_query("Thursday") -> ["2026-01-16"]  # next Thursday
        parse_date_query("this week") -> ["2026-01-13", ..., "2026-01-19"]
        parse_date_query("next 7 days") -> ["2026-01-14", ..., "2026-01-20"]
        parse_date_query("2026-01-15") -> ["2026-01-15"]
    """
    if not query:
        return []

    if reference_date is None:
        reference_date = date.today()

    query_lower = query.lower().strip()

    # Try to parse as YYYY-MM-DD first
    if re.match(r'^\d{4}-\d{2}-\d{2}$', query):
        return [query]

    # Handle relative expressions
    if query_lower == "today":
        return [reference_date.strftime("%Y-%m-%d")]

    if query_lower == "tomorrow":
        return [(reference_date + timedelta(days=1)).strftime("%Y-%m-%d")]

    if query_lower == "yesterday":
        return [(reference_date - timedelta(days=1)).strftime("%Y-%m-%d")]

    # Handle "this week" (Monday to Sunday of current week)
    if query_lower == "this week":
        # Find Monday of this week
        days_since_monday = reference_date.weekday()  # Monday=0
        monday = reference_date - timedelta(days=days_since_monday)
        return [(monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    # Handle "next week"
    if query_lower == "next week":
        # Find Monday of next week
        days_until_next_monday = (7 - reference_date.weekday()) % 7
        if days_until_next_monday == 0:
            days_until_next_monday = 7
        next_monday = reference_date + timedelta(days=days_until_next_monday)
        return [(next_monday + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

    # Handle "next N days"
    next_n_match = re.match(r'next\s+(\d+)\s+days?', query_lower)
    if next_n_match:
        n_days = int(next_n_match.group(1))
        return [(reference_date + timedelta(days=i+1)).strftime("%Y-%m-%d") for i in range(n_days)]

    # Handle day names (e.g., "Thursday", "next Monday")
    # Check for "next [day]" pattern first
    next_day_match = re.match(r'next\s+(\w+)', query_lower)
    if next_day_match:
        day_name = next_day_match.group(1).lower()
        if day_name in DAY_NAME_TO_NUM:
            target_weekday = DAY_NAME_TO_NUM[day_name]
            return [_get_next_weekday(reference_date, target_weekday, skip_this_week=True)]

    # Check for just day name (e.g., "Thursday")
    for day_name, weekday_num in DAY_NAME_TO_NUM.items():
        if query_lower == day_name:
            return [_get_next_weekday(reference_date, weekday_num, skip_this_week=False)]

    # If nothing matched, return empty (caller should handle fallback)
    return []


def _get_next_weekday(from_date: date, target_weekday: int, skip_this_week: bool = False) -> str:
    """Get the next occurrence of a weekday.

    Args:
        from_date: Starting date
        target_weekday: Target weekday (Monday=0, Sunday=6)
        skip_this_week: If True, skip to next week's occurrence

    Returns:
        Date string in YYYY-MM-DD format
    """
    current_weekday = from_date.weekday()
    days_ahead = (target_weekday - current_weekday) % 7

    if skip_this_week:
        # "next Monday" means next week's Monday regardless of current day
        # If today is Tuesday and target is Monday, days_ahead = 6 (already next week)
        # If today is Monday and target is Monday, days_ahead = 0, need to add 7
        # If today is Wednesday and target is Friday, days_ahead = 2 (this week), need to add 7
        if days_ahead == 0 or days_ahead > 0:
            days_ahead += 7
    else:
        # Find next occurrence (could be this week)
        if days_ahead == 0:
            days_ahead = 7  # Same day means next occurrence

    result_date = from_date + timedelta(days=days_ahead)
    return result_date.strftime("%Y-%m-%d")


def is_date_expression(query: str) -> bool:
    """Check if the query looks like a date expression.

    Args:
        query: Input string to check

    Returns:
        True if it appears to be a date expression
    """
    if not query:
        return False

    query_lower = query.lower().strip()

    # Check YYYY-MM-DD format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', query):
        return True

    # Check common date expressions
    date_keywords = [
        "today", "tomorrow", "yesterday",
        "this week", "next week",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "mon", "tue", "wed", "thu", "fri", "sat", "sun",
    ]

    for keyword in date_keywords:
        if keyword in query_lower:
            return True

    # Check "next N days" pattern
    if re.match(r'next\s+\d+\s+days?', query_lower):
        return True

    return False


def parse_time_query(query: str) -> Optional[str]:
    """Parse natural language time expressions to HH:MM format (24-hour).

    Args:
        query: Natural language time expression or HH:MM/H:MM format

    Returns:
        Time string in HH:MM format (24-hour), or None if parsing fails

    Examples:
        parse_time_query("9 AM") -> "09:00"
        parse_time_query("9:30 AM") -> "09:30"
        parse_time_query("2 PM") -> "14:00"
        parse_time_query("14:00") -> "14:00"
        parse_time_query("morning") -> "08:00"
        parse_time_query("afternoon") -> "12:00"
    """
    if not query:
        return None

    query_lower = query.lower().strip()

    # Handle time period keywords (return start of period)
    time_periods = {
        "morning": "08:00",
        "afternoon": "12:00",
        "evening": "17:00",
    }
    if query_lower in time_periods:
        return time_periods[query_lower]

    # Try to match HH:MM (24-hour) format first
    match_24h = re.match(r'^(\d{1,2}):(\d{2})$', query)
    if match_24h:
        hour = int(match_24h.group(1))
        minute = int(match_24h.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    # Try to match 12-hour format: "9 AM", "9:30 AM", "9AM", "9:30AM"
    match_12h = re.match(r'^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$', query_lower)
    if match_12h:
        hour = int(match_12h.group(1))
        minute = int(match_12h.group(2)) if match_12h.group(2) else 0
        period = match_12h.group(3)

        if period == "pm" and hour != 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    return None
