"""Date parsing and formatting utilities for natural language date expressions and API responses."""

import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

# Constants
MIN_YEAR = 2024  # Minimum year for date validation
TIME_STRING_WITH_SECONDS_LENGTH = 8  # Length of "HH:MM:SS" format
MAX_DATES_DISPLAY = 2
MAX_TIME_SLOTS_DISPLAY = 2
MAX_DAYS_DISPLAY = 3

# Regex patterns
DATE_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}$')

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
    if DATE_PATTERN.match(query):
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
        # Since days_ahead is always >= 0 (result of modulo 7), we always add 7
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
    if DATE_PATTERN.match(query):
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


def format_date(date_str: str) -> str:
    """Format date string from API format (YYYY-MM-DD) to human-readable format.
    
    Args:
        date_str: Date string in YYYY-MM-DD format
        
    Returns:
        Formatted date string like "January 15, 2024", or original string if parsing fails
        
    Examples:
        format_date("2024-01-15") -> "January 15, 2024"
        format_date("invalid") -> "invalid"
    """
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        return date_str


def format_time(time_str: str) -> str:
    """Format time string from API format (HH:MM or HH:MM:SS) to human-readable 12-hour format.
    
    Args:
        time_str: Time string in HH:MM or HH:MM:SS format (24-hour)
        
    Returns:
        Formatted time string like "9:00 AM", or original string if parsing fails
        
    Examples:
        format_time("09:00:00") -> "9:00 AM"
        format_time("14:30") -> "2:30 PM"
        format_time("invalid") -> "invalid"
    """
    try:
        fmt = "%H:%M:%S" if len(time_str) == TIME_STRING_WITH_SECONDS_LENGTH else "%H:%M"
        return datetime.strptime(time_str, fmt).strftime("%I:%M %p").lstrip("0")
    except Exception:
        return time_str


def format_timing(applicability: Dict[str, Any]) -> str:
    """Format timing info from applicability clause to human-readable string.
    
    Handles different applicability field types:
    - DATE: Specific dates
    - DAY: Days of week
    - DAY_AND_TIME: Days with time slots
    - DATE_AND_TIME: Specific dates with time slots
    
    Args:
        applicability: Applicability clause dictionary with:
            - field: Field type (DATE, DAY, DAY_AND_TIME, DATE_AND_TIME)
            - dateList: List of date strings (YYYY-MM-DD)
            - dayTimeList: List of day/time entries
            
    Returns:
        Human-readable timing string, or empty string if no timing info
        
    Examples:
        format_timing({"field": "DATE", "dateList": ["2024-01-15"]})
        # Returns: "on January 15, 2024"
        
        format_timing({"field": "DAY", "dayTimeList": [{"day": "monday"}, {"day": "wednesday"}]})
        # Returns: "on Monday, Wednesday"
        
        format_timing({"field": "DATE_AND_TIME", "dateList": ["2024-01-15"], 
                       "dayTimeList": [{"timeSlots": ["09:00:00", "14:00:00"]}]})
        # Returns: "on January 15, 2024 at 9:00 AM, 2:00 PM"
    """
    if not applicability:
        return ""


def parse_dates(dates: Optional[List[str]], reference_date: Optional[date] = None) -> List[str]:
    """Parse dates from natural language or YYYY-MM-DD format.
    
    Parses a list of date strings (which can be natural language like "tomorrow" or 
    YYYY-MM-DD format) and returns a sorted, deduplicated list of valid dates.
    If no valid dates are found, returns tomorrow's date as default.
    
    Args:
        dates: List of date strings to parse (can be None or empty)
        reference_date: Reference date for relative expressions (defaults to today)
        
    Returns:
        Sorted list of unique date strings in YYYY-MM-DD format
        
    Examples:
        parse_dates(["tomorrow", "2024-01-15"]) -> ["2024-01-14", "2024-01-15"]
        parse_dates(None) -> ["2024-01-14"]  # tomorrow
        parse_dates(["invalid"]) -> ["2024-01-14"]  # falls back to tomorrow
    """
    if reference_date is None:
        reference_date = date.today()
    
    default_date = (reference_date + timedelta(days=1)).strftime("%Y-%m-%d")
    
    if not dates:
        return [default_date]
    
    parsed = []
    for d in dates:
        result = parse_date_query(d, reference_date=reference_date)
        if result:
            parsed.extend(result)
        else:
            # Try to parse as YYYY-MM-DD directly
            try:
                dt = datetime.strptime(d, "%Y-%m-%d").date()
                # Validate year and date range (within last year to future)
                if dt.year >= MIN_YEAR and dt >= (reference_date - timedelta(days=365)):
                    parsed.append(d)
            except ValueError:
                continue
    
    if not parsed:
        return [default_date]
    
    return sorted(list(set(parsed)))

    field = applicability.get("field", "")
    date_list = applicability.get("dateList", [])
    day_time_list = applicability.get("dayTimeList", [])

    if field == "DATE" and date_list:
        dates = [format_date(d) for d in date_list[:MAX_DATES_DISPLAY]]
        return "on %s" % ", ".join(dates)

    elif field in ["DAY", "DAY_AND_TIME"]:
        days = [e.get("day", "").capitalize() for e in (day_time_list or []) if e.get("day")]
        if days:
            all_days = {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}
            missing = all_days - set(days)
            if len(missing) == 1:
                return "(except %ss)" % list(missing)[0]
            elif len(missing) > 0 and len(missing) < 3:
                return "(except %s)" % ", ".join(missing)
            return "on %s" % ", ".join(days[:MAX_DAYS_DISPLAY])

    elif field == "DATE_AND_TIME" and date_list:
        date_str = format_date(date_list[0])
        times = []
        for entry in (day_time_list or []):
            for slot in entry.get("timeSlots", [])[:MAX_TIME_SLOTS_DISPLAY]:
                times.append(format_time(slot))
        if times:
            return "on %s at %s" % (date_str, ", ".join(times[:MAX_TIME_SLOTS_DISPLAY]))
        return "on %s" % date_str

    return ""
