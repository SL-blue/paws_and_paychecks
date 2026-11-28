"""Stress v0.3 (SIM_BASELINE.md §7): daily change, efficiency multiplier, illness."""
from dataclasses import dataclass


@dataclass
class StressDay:
    """What happened on a day, as far as stress is concerned. Effects arrive as plain numbers."""
    paid_hours: float = 0.0          # incl. hours that "count as paid hours" (Saturday class)
    work_hour_over: float = None     # None = config default (standing desk changes it)
    sleep_cut: float = 0.0
    short_night_streak: int = 0      # consecutive short nights including tonight (0 if not short)
    deadlines_tomorrow: int = 0      # non-rush jobs due tomorrow with work remaining
    rush_deadlines_tomorrow: int = 0
    low_runway: bool = False
    rush_in_progress: bool = False
    rush_extra: float = 0.0          # extra stress/day while a rush job is in progress (rush specialist)
    loan_open: bool = False          # her loan unpaid at the end of the day
    leisure_hours: float = 0.0       # incl. time with her
    leisure_multiplier: float = 1.0
    book_hours: float = 0.0
    book_relief_per_hour: float = None  # None = config default (effects may change it)
    overlap_hours: float = 0.0       # quiet-company hours: book with her
    overlap_relief: float = 0.0      # relief per overlap hour (positive)
    session_hours: float = 0.0       # writing-group session hours (book hours with their own relief)
    session_relief_per_hour: float = 0.0
    extra_relief: float = 0.0        # from effects (positive number = less stress)


def daily_delta(cfg, d: StressDay):
    s = cfg["stress"]
    over = s["work_hour_over"] if d.work_hour_over is None else d.work_hour_over
    delta = max(0.0, d.paid_hours - s["per_work_hour_beyond"]) * over
    delta += d.sleep_cut * s["sleep_cut_hour"]
    if d.short_night_streak > 1:
        delta += s["consecutive_short_night"]
    delta += d.deadlines_tomorrow * s["deadline_tomorrow"] + d.rush_deadlines_tomorrow * s["deadline_tomorrow_rush"]
    delta += s["low_runway"] if d.low_runway else 0
    delta += s["rush_in_progress"] + d.rush_extra if d.rush_in_progress else 0
    delta += cfg["lifelines"]["loan_stress_per_day"] if d.loan_open else 0
    delta += d.leisure_hours * s["leisure_hour"] * d.leisure_multiplier
    book_relief = -s["book_hour"] if d.book_relief_per_hour is None else d.book_relief_per_hour
    delta -= d.book_hours * book_relief
    delta -= d.overlap_hours * d.overlap_relief
    delta -= d.session_hours * d.session_relief_per_hour
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
