"""Time demands (SIM_BASELINE.md §7): the relationship (evenings with her) and pet care."""
from . import game_calendar as cal


def her_available_evening(cfg, day):
    h = cfg["her"]
    if cal.is_weekend(day):
        return False
    evenings = h["crunch_evenings"] if cal.week_of(day) in h["crunch_weeks"] else h["weekday_evenings"]
    return cal.weekday(day) in evenings


def her_available_half_day(day):
    return cal.is_weekend(day)


def count_her_time(cfg, day, hours):
    """Classify a day's time with her: ('evening'|'half_day'|None)."""
    h = cfg["her"]
    if cal.is_weekend(day):
        if hours >= h["half_day_hours"]:
            return "half_day"
        return "evening" if hours >= h["evening_hours"] else None
    if her_available_evening(cfg, day) and hours >= h["evening_hours"]:
        return "evening"
    return None


def week_met(cfg, evenings, half_days):
    h = cfg["her"]
    return evenings >= h["evenings_needed"] or (evenings >= h["evenings_with_half_day"] and half_days >= 1)


def pet_care_need(cfg, day, coworking=False, coworking_extra=0.0):
    need = 0.0
    for row in cfg["pet"]["care_hours"]:
        if day >= row["from_day"]:
            need = row["hours"]
    return need + (coworking_extra if coworking else 0.0)
