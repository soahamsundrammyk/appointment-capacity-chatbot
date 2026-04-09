"""Tests for date parsing utilities."""

from datetime import date

import pytest

from capacity_chatbot.utils.date_parser import (
    _get_next_weekday,
    parse_date_query,
    parse_date_range,
    parse_dates,
)


# =============================================================================
# parse_date_range tests (existing)
# =============================================================================


def test_parse_this_month():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("this month", reference_date=ref)
    assert start == "2026-03-01"
    assert end == "2026-03-31"


def test_parse_last_month():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last month", reference_date=ref)
    assert start == "2026-02-01"
    assert end == "2026-02-28"


def test_parse_last_month_leap_year():
    ref = date(2028, 3, 15)
    start, end = parse_date_range("last month", reference_date=ref)
    assert start == "2028-02-01"
    assert end == "2028-02-29"


def test_parse_this_week():
    ref = date(2026, 3, 18)  # Wednesday
    start, end = parse_date_range("this week", reference_date=ref)
    assert start == "2026-03-16"  # Monday
    assert end == "2026-03-22"  # Sunday


def test_parse_last_week():
    ref = date(2026, 3, 18)  # Wednesday
    start, end = parse_date_range("last week", reference_date=ref)
    assert start == "2026-03-09"  # Previous Monday
    assert end == "2026-03-15"  # Previous Sunday


def test_parse_today():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("today", reference_date=ref)
    assert start == "2026-03-15"
    assert end == "2026-03-15"


def test_parse_yesterday():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("yesterday", reference_date=ref)
    assert start == "2026-03-14"
    assert end == "2026-03-14"


def test_parse_explicit_date():
    start, end = parse_date_range("2026-03-15")
    assert start == "2026-03-15"
    assert end == "2026-03-15"


def test_parse_last_n_days():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last 7 days", reference_date=ref)
    assert start == "2026-03-09"  # 7 days: Mar 9-15 inclusive
    assert end == "2026-03-15"


def test_parse_last_30_days():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("last 30 days", reference_date=ref)
    assert start == "2026-02-14"  # 30 days: Feb 14-Mar 15 inclusive
    assert end == "2026-03-15"


def test_parse_tomorrow():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("tomorrow", reference_date=ref)
    assert start == "2026-03-16"
    assert end == "2026-03-16"


def test_parse_next_n_days():
    ref = date(2026, 3, 15)
    start, end = parse_date_range("next 7 days", reference_date=ref)
    assert start == "2026-03-15"
    assert end == "2026-03-21"  # 7 days: Mar 15-21 inclusive


def test_parse_none_returns_none():
    result = parse_date_range(None)
    assert result is None


def test_parse_empty_returns_none():
    result = parse_date_range("")
    assert result is None


def test_parse_unrecognized_returns_none():
    result = parse_date_range("gobbledygook")
    assert result is None


# =============================================================================
# _get_next_weekday — the core "next [day]" logic
# =============================================================================


class TestGetNextWeekday:
    """Tests for _get_next_weekday covering skip_this_week logic."""

    # --- skip_this_week=False (bare day name like "Monday") ---

    def test_bare_day_name_target_ahead_this_week(self):
        """'Friday' from Wednesday → this Friday (2 days)."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 4, skip_this_week=False) == "2026-04-10"

    def test_bare_day_name_target_behind_this_week(self):
        """'Monday' from Wednesday → next Monday (5 days)."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 0, skip_this_week=False) == "2026-04-13"

    def test_bare_day_name_same_day(self):
        """'Wednesday' from Wednesday → next Wednesday (7 days, not today)."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 2, skip_this_week=False) == "2026-04-15"

    def test_bare_day_name_tomorrow(self):
        """'Thursday' from Wednesday → tomorrow."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 3, skip_this_week=False) == "2026-04-09"

    def test_bare_day_name_yesterday(self):
        """'Tuesday' from Wednesday → next Tuesday (6 days)."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 1, skip_this_week=False) == "2026-04-14"

    # --- skip_this_week=True ("next Monday" pattern) ---

    def test_next_day_already_passed_this_week(self):
        """'next Monday' from Thursday → coming Monday (4 days), NOT 11 days."""
        # This is the exact bug scenario: April 9 (Thu) → April 13 (Mon)
        ref = date(2026, 4, 9)  # Thursday
        assert _get_next_weekday(ref, 0, skip_this_week=True) == "2026-04-13"

    def test_next_day_already_passed_this_week_tuesday_from_friday(self):
        """'next Tuesday' from Friday → coming Tuesday (4 days)."""
        ref = date(2026, 4, 10)  # Friday
        assert _get_next_weekday(ref, 1, skip_this_week=True) == "2026-04-14"

    def test_next_day_already_passed_monday_from_wednesday(self):
        """'next Monday' from Wednesday → coming Monday (5 days)."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 0, skip_this_week=True) == "2026-04-13"

    def test_next_day_same_day(self):
        """'next Wednesday' from Wednesday → next week's Wednesday (7 days)."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 2, skip_this_week=True) == "2026-04-15"

    def test_next_day_still_ahead_this_week(self):
        """'next Friday' from Wednesday → next week's Friday (9 days), skip this week's."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 4, skip_this_week=True) == "2026-04-17"

    def test_next_day_tomorrow(self):
        """'next Thursday' from Wednesday → next week's Thursday (8 days)."""
        ref = date(2026, 4, 8)  # Wednesday
        assert _get_next_weekday(ref, 3, skip_this_week=True) == "2026-04-16"

    def test_next_day_sunday_from_monday(self):
        """'next Sunday' from Monday → next week's Sunday (13 days)."""
        ref = date(2026, 4, 6)  # Monday
        assert _get_next_weekday(ref, 6, skip_this_week=True) == "2026-04-19"

    def test_next_day_monday_from_monday(self):
        """'next Monday' from Monday → next Monday (7 days)."""
        ref = date(2026, 4, 6)  # Monday
        assert _get_next_weekday(ref, 0, skip_this_week=True) == "2026-04-13"

    def test_next_day_saturday_from_sunday(self):
        """'next Saturday' from Sunday → next week's Saturday (6 days)."""
        ref = date(2026, 4, 12)  # Sunday
        assert _get_next_weekday(ref, 5, skip_this_week=True) == "2026-04-18"

    def test_next_day_monday_from_sunday(self):
        """'next Monday' from Sunday → tomorrow's Monday, then skip → Monday after (8 days)."""
        ref = date(2026, 4, 12)  # Sunday
        # Monday is weekday 0, Sunday is 6. (0-6)%7 = 1 day ahead = Apr 13
        # target(0) < current(6), so don't add 7 → Apr 13
        assert _get_next_weekday(ref, 0, skip_this_week=True) == "2026-04-13"

    def test_next_day_friday_from_saturday(self):
        """'next Friday' from Saturday → next week's Friday (6 days)."""
        ref = date(2026, 4, 11)  # Saturday
        assert _get_next_weekday(ref, 4, skip_this_week=True) == "2026-04-17"


# =============================================================================
# parse_date_query — natural language date expressions
# =============================================================================


class TestParseDateQuery:
    """Tests for parse_date_query with various natural language inputs."""

    REF = date(2026, 4, 9)  # Thursday

    def test_today(self):
        assert parse_date_query("today", self.REF) == ["2026-04-09"]

    def test_tomorrow(self):
        assert parse_date_query("tomorrow", self.REF) == ["2026-04-10"]

    def test_yesterday(self):
        assert parse_date_query("yesterday", self.REF) == ["2026-04-08"]

    def test_explicit_date(self):
        assert parse_date_query("2026-04-20", self.REF) == ["2026-04-20"]

    def test_this_week(self):
        dates = parse_date_query("this week", self.REF)
        assert dates[0] == "2026-04-06"  # Monday
        assert dates[-1] == "2026-04-12"  # Sunday
        assert len(dates) == 7

    def test_next_week(self):
        dates = parse_date_query("next week", self.REF)
        assert dates[0] == "2026-04-13"  # Next Monday
        assert dates[-1] == "2026-04-19"  # Next Sunday
        assert len(dates) == 7

    def test_next_7_days(self):
        dates = parse_date_query("next 7 days", self.REF)
        assert dates[0] == "2026-04-10"  # tomorrow
        assert dates[-1] == "2026-04-16"
        assert len(dates) == 7

    def test_next_3_days(self):
        dates = parse_date_query("next 3 days", self.REF)
        assert dates == ["2026-04-10", "2026-04-11", "2026-04-12"]

    def test_next_1_day(self):
        dates = parse_date_query("next 1 day", self.REF)
        assert dates == ["2026-04-10"]

    # --- Bare day names (find next occurrence) ---

    def test_bare_monday_from_thursday(self):
        """'Monday' from Thursday → next Monday (April 13)."""
        assert parse_date_query("monday", self.REF) == ["2026-04-13"]

    def test_bare_friday_from_thursday(self):
        """'Friday' from Thursday → this Friday (April 10)."""
        assert parse_date_query("friday", self.REF) == ["2026-04-10"]

    def test_bare_thursday_from_thursday(self):
        """'Thursday' from Thursday → next Thursday (April 16)."""
        assert parse_date_query("thursday", self.REF) == ["2026-04-16"]

    def test_bare_saturday_from_thursday(self):
        """'Saturday' from Thursday → this Saturday (April 11)."""
        assert parse_date_query("saturday", self.REF) == ["2026-04-11"]

    def test_bare_wednesday_from_thursday(self):
        """'Wednesday' from Thursday → next Wednesday (April 15)."""
        assert parse_date_query("wednesday", self.REF) == ["2026-04-15"]

    # --- Abbreviated day names ---

    def test_bare_mon(self):
        assert parse_date_query("mon", self.REF) == ["2026-04-13"]

    def test_bare_fri(self):
        assert parse_date_query("fri", self.REF) == ["2026-04-10"]

    def test_bare_sat(self):
        assert parse_date_query("sat", self.REF) == ["2026-04-11"]

    def test_bare_sun(self):
        assert parse_date_query("sun", self.REF) == ["2026-04-12"]

    # --- "next [day]" pattern ---

    def test_next_monday_from_thursday(self):
        """'next monday' from Thursday April 9 → April 13 (not April 20)."""
        assert parse_date_query("next monday", self.REF) == ["2026-04-13"]

    def test_next_friday_from_thursday(self):
        """'next friday' from Thursday → next week's Friday April 17."""
        assert parse_date_query("next friday", self.REF) == ["2026-04-17"]

    def test_next_thursday_from_thursday(self):
        """'next thursday' from Thursday → next Thursday April 16."""
        assert parse_date_query("next thursday", self.REF) == ["2026-04-16"]

    def test_next_saturday_from_thursday(self):
        """'next saturday' from Thursday → next week's Saturday April 18."""
        assert parse_date_query("next saturday", self.REF) == ["2026-04-18"]

    def test_next_wednesday_from_thursday(self):
        """'next wednesday' from Thursday → next Wednesday April 15."""
        assert parse_date_query("next wednesday", self.REF) == ["2026-04-15"]

    def test_next_tuesday_from_thursday(self):
        """'next tuesday' from Thursday → next Tuesday April 14."""
        assert parse_date_query("next tuesday", self.REF) == ["2026-04-14"]

    def test_next_sunday_from_thursday(self):
        """'next sunday' from Thursday → next week's Sunday April 19."""
        assert parse_date_query("next sunday", self.REF) == ["2026-04-19"]

    # --- Case insensitivity and whitespace ---

    def test_case_insensitive_next_monday(self):
        assert parse_date_query("Next Monday", self.REF) == ["2026-04-13"]

    def test_case_insensitive_tomorrow(self):
        assert parse_date_query("TOMORROW", self.REF) == ["2026-04-10"]

    def test_whitespace_trimmed(self):
        assert parse_date_query("  next monday  ", self.REF) == ["2026-04-13"]

    # --- Edge cases ---

    def test_empty_string(self):
        assert parse_date_query("", self.REF) == []

    def test_gibberish(self):
        assert parse_date_query("asdfgh", self.REF) == []

    # --- Different reference days to ensure correctness across the week ---

    def test_next_monday_from_monday(self):
        ref = date(2026, 4, 6)  # Monday
        assert parse_date_query("next monday", ref) == ["2026-04-13"]

    def test_next_monday_from_tuesday(self):
        ref = date(2026, 4, 7)  # Tuesday
        assert parse_date_query("next monday", ref) == ["2026-04-13"]

    def test_next_monday_from_wednesday(self):
        ref = date(2026, 4, 8)  # Wednesday
        assert parse_date_query("next monday", ref) == ["2026-04-13"]

    def test_next_monday_from_friday(self):
        ref = date(2026, 4, 10)  # Friday
        assert parse_date_query("next monday", ref) == ["2026-04-13"]

    def test_next_monday_from_saturday(self):
        ref = date(2026, 4, 11)  # Saturday
        assert parse_date_query("next monday", ref) == ["2026-04-13"]

    def test_next_monday_from_sunday(self):
        ref = date(2026, 4, 12)  # Sunday
        assert parse_date_query("next monday", ref) == ["2026-04-13"]

    def test_next_friday_from_monday(self):
        """'next friday' from Monday → next week's Friday (skip this week's)."""
        ref = date(2026, 4, 6)  # Monday
        assert parse_date_query("next friday", ref) == ["2026-04-17"]

    def test_next_friday_from_saturday(self):
        """'next friday' from Saturday → next Friday (6 days)."""
        ref = date(2026, 4, 11)  # Saturday
        assert parse_date_query("next friday", ref) == ["2026-04-17"]


# =============================================================================
# parse_dates — the entry point that resolves lists of expressions
# =============================================================================


class TestParseDates:
    """Tests for parse_dates which handles lists and defaults."""

    REF = date(2026, 4, 9)  # Thursday

    def test_none_defaults_to_tomorrow(self):
        result = parse_dates(None, reference_date=self.REF)
        assert result == ["2026-04-10"]

    def test_empty_list_defaults_to_tomorrow(self):
        result = parse_dates([], reference_date=self.REF)
        assert result == ["2026-04-10"]

    def test_single_explicit_date(self):
        result = parse_dates(["2026-04-15"], reference_date=self.REF)
        assert result == ["2026-04-15"]

    def test_multiple_explicit_dates_sorted(self):
        result = parse_dates(["2026-04-20", "2026-04-15"], reference_date=self.REF)
        assert result == ["2026-04-15", "2026-04-20"]

    def test_natural_language_date(self):
        result = parse_dates(["tomorrow"], reference_date=self.REF)
        assert result == ["2026-04-10"]

    def test_this_week_expands_to_7_dates(self):
        result = parse_dates(["this week"], reference_date=self.REF)
        assert len(result) == 7
        assert result[0] == "2026-04-06"
        assert result[-1] == "2026-04-12"

    def test_next_monday_resolves_correctly(self):
        result = parse_dates(["next monday"], reference_date=self.REF)
        assert result == ["2026-04-13"]

    def test_mixed_expressions_deduped_and_sorted(self):
        result = parse_dates(["tomorrow", "2026-04-10"], reference_date=self.REF)
        assert result == ["2026-04-10"]  # deduplicated

    def test_invalid_input_falls_back_to_tomorrow(self):
        result = parse_dates(["gibberish"], reference_date=self.REF)
        assert result == ["2026-04-10"]

    def test_mixed_valid_and_invalid(self):
        result = parse_dates(["gibberish", "tomorrow"], reference_date=self.REF)
        assert result == ["2026-04-10"]

    def test_single_string_coerced_by_pydantic_then_parsed(self):
        """Simulates LLM passing a bare string that gets coerced to list."""
        result = parse_dates(["this week"], reference_date=self.REF)
        assert len(result) == 7
