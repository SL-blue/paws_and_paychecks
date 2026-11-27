"""Stress v0 (SIM_BASELINE.md §7): daily change, efficiency multiplier, illness."""
from dataclasses import dataclass


@dataclass
class StressDay:
    """What happened on a day, as far as stress is concerned."""
    paid_hours: float = 0.0
    sleep_cut: float = 0.0
    short_night_streak: int = 0      # consecutive short nights including tonight (0 if not short)
    deadlines_tomorrow: int = 0      # jobs due tomorrow with work remaining
    low_runway: bool = False
    rush_in_progress: bool = False
    leisure_hours: float = 0.0       # incl. time with her
    book_hours: float = 0.0
    book_relief_per_hour: float = None  # None = config default (effects may change it)
    extra_relief: float = 0.0        # from effects (positive number = less stress)
    extra_sleep_cut_stress: float = 0.0  # per hour cut, from effects


def daily_delta(cfg, d: StressDay):
    s = cfg["stress"]
    delta = max(0.0, d.paid_hours - s["per_work_hour_beyond"]) * s["work_hour_over"]
    delta += d.sleep_cut * (s["sleep_cut_hour"] + d.extra_sleep_cut_stress)
    if d.short_night_streak > 1:
        delta += s["consecutive_short_night"]
    delta += d.deadlines_tomorrow * s["deadline_tomorrow"]
    delta += s["low_runway"] if d.low_runway else 0
    delta += s["rush_in_progress"] if d.rush_in_progress else 0
    delta += d.leisure_hours * s["leisure_hour"]
    book_relief = s["book_hour"] if d.book_relief_per_hour is None else -d.book_relief_per_hour
    delta += d.book_hours * book_relief
    delta += s["no_paid_work_day"] if d.paid_hours <= 0 else 0
    delta += s["natural_recovery"]
    delta -= d.extra_relief
    return delta


def apply(cfg, stress, delta):
    return min(cfg["stress"]["max"], max(0.0, stress + delta))


def efficiency(cfg, stress):
    s = cfg["stress"]
    return 1.0 - max(0.0, stress - s["efficiency_threshold"]) * s["efficiency_per_point"]


def illness_possible(cfg, high_streak):
    return high_streak >= cfg["stress"]["illness_after_days"]
