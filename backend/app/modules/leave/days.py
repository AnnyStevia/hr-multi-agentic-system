"""Isolated leave day calculation — calendar days for V1; swap later for working days."""

from datetime import date


def calculate_requested_days(start_date: date, end_date: date) -> int:
    """Inclusive calendar-day count between start and end (no weekends/holidays)."""
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date")
    return (end_date - start_date).days + 1
