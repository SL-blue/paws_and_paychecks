"""Time demands (SIM_BASELINE.md §7): the relationship (evenings with her) and pet care.
Effects that change them (shared calendar, brunch, puppy class, ...) pass their numbers in."""
from . import game_calendar as cal


def her_available_evening(cfg, day, crunch_evenings=None):
    h = cfg["her"]
    if cal.is_weekend(day):
        return False
    if cal.week_of(day) in h["crunch_weeks"]:
        evenings = h["crunch_evenings"] if crunch_evenings is None else crunch_evenings
    else:
        evenings = h["weekday_evenings"]
    return cal.weekday(day) in evenings


def count_her_time(cfg, day, hours, half_day_hours=None, crunch_evenings=None):
    """Classify a day's time with her: ('evening'|'half_day'|None)."""
    h = cfg["her"]
    half = h["half_day_hours"] if half_day_hours is None else half_day_hours
    if cal.is_weekend(day):
        if hours >= half - 1e-9:
            return "half_day"
        return "evening" if hours >= h["evening_hours"] - 1e-9 else None
    if her_available_evening(cfg, day, crunch_evenings) and hours >= h["evening_hours"] - 1e-9:
        return "evening"
    return None


def week_met(cfg, evenings, half_days):
    h = cfg["her"]
    return evenings >= h["evenings_needed"] or (evenings >= h["evenings_with_half_day"] and half_days >= 1)


def base_pet_need(cfg, day):
    need = 0.0
    for row in cfg["pet"]["care_hours"]:
        if day >= row["from_day"]:
            need = row["hours"]
    return need


def pet_care_need(cfg, day, change=0.0):
    """Daily pet-care need in hours, after effect changes (never below 0)."""
    return max(0.0, base_pet_need(cfg, day) + change)
