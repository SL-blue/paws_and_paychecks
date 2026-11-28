"""Stress v0.4 (SIM_BASELINE.md §7): two layers, short-term S and long-term L. Total T = min(max, S + L).

One day, in order (`end_of_day`):
 1. S changes by the day's drivers (`short_delta`): work, sleep, deadlines, rush, interruptions,
    leisure, her, book, effects.
 2. L changes by the day's situation (`long_delta`) and by the day's events (payments, rent, the
    loan, milestones, ...), which the engine collects in a list as it goes.
 3. Conversion (§7.4): if S > threshold, a share of the excess moves from S to L; if S has been
    above the sustained level for N days in a row, L grows from the Nth day on.
 4. Calm-day recovery: -1 L when the day ends with S below the calm level.
The day's T is recorded here (before sleep). Then the night's sleep lowers S by a share
(`sleep_recovery`), so the next morning starts lower; efficiency and illness use that morning T.
"""
from dataclasses import dataclass, field


@dataclass
class ShortDay:
    """What happened to S on a day. Effects arrive as plain numbers."""
    paid_hours: float = 0.0          # incl. hours that "count as paid hours" (Saturday class)
    work_hour_over: float = None     # None = config default (standing desk changes it)
    sleep_cut: float = 0.0
    short_night_streak: int = 0      # consecutive short nights including tonight (0 if not short)
    deadlines_tomorrow: int = 0      # non-rush jobs due tomorrow with work remaining
    rush_deadlines_tomorrow: int = 0
    rush_in_progress: bool = False
    rush_extra: float = 0.0          # extra S/day while a rush job is in progress (rush specialist)
    bad_interruption: bool = False
    leisure_hours: float = 0.0       # free time (not her), already capped at day.leisure_hours_cap
    leisure_multiplier: float = 1.0
    her_hours: float = 0.0           # time with her, without the quiet-company overlap
    book_hours: float = 0.0          # book hours with the normal relief
    book_relief_per_hour: float = None  # None = config default (effects may change it)
    overlap_hours: float = 0.0       # quiet-company hours: book with her
    overlap_relief: float = 0.0      # relief per overlap hour (positive)
    session_hours: float = 0.0       # writing-group session hours (book hours with their own relief)
    session_relief_per_hour: float = 0.0
    extra_relief: float = 0.0        # from effects (positive number = less S)


@dataclass
class LongDay:
    """The situation at the end of a day, as far as L is concerned."""
    runway_days: float = 99.0        # cash / cost of a day
    rent_due_soon_short: bool = False   # rent due within the window and cash below it
    loan_open: bool = False
    crunch_week: bool = False        # her crunch weeks
    pet_deficit: float = 0.0         # today's pet-care deficit weight (0 = care was enough)
    extra_relief: float = 0.0        # from effects (morning pages), positive = less L
    events: list = field(default_factory=list)   # [(label, delta L)] collected during the day


@dataclass
class Levels:
    short: float
    long: float
    cap: float                       # stress.max from the config
    sustained_streak: int = 0        # days in a row ending with S above the sustained level
    conversions: int = 0             # days with an S -> L conversion ("too much")
    converted: float = 0.0           # S moved into L, in total

    @property
    def total(self):
        return min(self.cap, self.short + self.long)


def clamp(cfg, x):
    return min(cfg["stress"]["max"], max(0.0, x))


def leisure_relief(cfg, hours, multiplier=1.0):
    """S relief (positive) of free time: the first hours relieve more than later ones."""
    s = cfg["stress"]["short"]
    first = min(hours, s["leisure_first_hours"])
    later = max(0.0, hours - s["leisure_first_hours"])
    return -(first * s["leisure_first_hour"] + later * s["leisure_later_hour"]) * multiplier


def short_delta(cfg, d: ShortDay):
    s = cfg["stress"]["short"]
    over = s["work_hour_over"] if d.work_hour_over is None else d.work_hour_over
    delta = max(0.0, d.paid_hours - s["per_work_hour_beyond"]) * over
    delta += d.sleep_cut * s["sleep_cut_hour"]
    if d.short_night_streak > 1:
        delta += s["consecutive_short_night"]
    delta += d.deadlines_tomorrow * s["deadline_tomorrow"] + d.rush_deadlines_tomorrow * s["deadline_tomorrow_rush"]
    delta += s["rush_in_progress"] + d.rush_extra if d.rush_in_progress else 0
    delta += s["bad_interruption"] if d.bad_interruption else 0
    delta -= leisure_relief(cfg, d.leisure_hours, d.leisure_multiplier)
    delta += d.her_hours * s["her_hour"]
    book_relief = -s["book_hour"] if d.book_relief_per_hour is None else d.book_relief_per_hour
    delta -= d.book_hours * book_relief
    delta -= d.overlap_hours * d.overlap_relief
    delta -= d.session_hours * d.session_relief_per_hour
    delta += s["no_paid_work_day"] if d.paid_hours <= 0 else 0
    delta -= d.extra_relief
    return delta


def long_delta(cfg, d: LongDay):
    """Δ L from the day's situation and events. Payment relief is capped per day."""
    lg = cfg["stress"]["long"]
    delta = 0.0
    if d.runway_days < lg["runway_very_low_days"]:
        delta += lg["runway_very_low"]
    elif d.runway_days < lg["runway_low_days"]:
        delta += lg["runway_low"]
    delta += lg["rent_due"] if d.rent_due_soon_short else 0
    delta += lg["loan_open"] if d.loan_open else 0
    delta += lg["her_crunch_day"] if d.crunch_week else 0
    delta += lg["pet_deficit_day"] * d.pet_deficit
    payments = sum(v for label, v in d.events if label == "payment")
    delta += max(payments, -lg["payment_relief_max"])
    delta += sum(v for label, v in d.events if label != "payment")
    return delta - d.extra_relief


def convert(cfg, lv: Levels):
    """§7.4: too much S moves into L; S high for too long adds L."""
    c = cfg["stress"]["conversion"]
    excess = lv.short - c["threshold"]
    if excess > 0:
        moved = excess * c["share"]
        lv.short -= moved
        lv.long = clamp(cfg, lv.long + moved)
        lv.conversions += 1
        lv.converted += moved
    lv.sustained_streak = lv.sustained_streak + 1 if lv.short > c["sustained_level"] else 0
    if lv.sustained_streak >= c["sustained_days"]:
        lv.long = clamp(cfg, lv.long + c["sustained_per_day"])


def end_of_day(cfg, lv: Levels, short: ShortDay, long: LongDay):
    """Apply one day to the levels (steps 1-4 of the module docstring). Returns the day's T."""
    lv.short = clamp(cfg, lv.short + short_delta(cfg, short))
    lv.long = clamp(cfg, lv.long + long_delta(cfg, long))
    convert(cfg, lv)
    lg = cfg["stress"]["long"]
    if lv.short < lg["calm_day_below"]:
        lv.long = clamp(cfg, lv.long + lg["calm_day"])
    return lv.total


def sleep_recovery(cfg, lv: Levels, sleep_hours):
    """The night: S falls by a share, more with a full night."""
    s = cfg["stress"]["short"]
    full = sleep_hours >= cfg["day"]["default_sleep_hours"] - 1e-9
    lv.short *= 1 - (s["sleep_recovery_full"] if full else s["sleep_recovery_short"])


def efficiency(cfg, total_stress):
    s = cfg["stress"]
    return 1.0 - max(0.0, total_stress - s["efficiency_threshold"]) * s["efficiency_per_point"]


def illness_possible(cfg, high_streak):
    return high_streak >= cfg["stress"]["illness_after_days"]
