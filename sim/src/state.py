"""The run state, plus the per-day log the metrics are computed from.

Visibility: policies receive this object but may only read what a player sees: cash, debt,
stress, held effects, accepted jobs, invoice `expected_day`s, the book, the calendar and
config numbers. Never `Invoice.arrival_day` or the offer stream (only greedy-optimal gets
that, explicitly, through `Policy.start`).
"""
from collections import Counter
from dataclasses import dataclass, field

from .book import Book


@dataclass
class Plan:
    paid_hours: float = 0.0
    book_hours: float = 0.0
    pet_hours: float = 0.0
    her_hours: float = 0.0
    sleep_hours: float = 8.0
    coworking: bool = False


@dataclass
class State:
    seed: int
    cash: float
    stress: float
    book: Book
    day: int = 0
    debt: float = 0.0
    deferred_rent: dict = None
    rent_paid_today: float = 0.0
    high_stress_streak: int = 0
    short_night_streak: int = 0
    last_sleep_cut: float = 0.0
    jobs: list = field(default_factory=list)          # accepted, not yet delivered
    invoices: list = field(default_factory=list)      # delivered / receivable, not yet paid
    completed_jobs: int = 0
    late_jobs: int = 0
    reputation_until: dict = field(default_factory=dict)
    held: list = field(default_factory=list)          # effect ids, in pick order
    effect_day: dict = field(default_factory=dict)    # effect id -> day acquired
    subscriptions: dict = field(default_factory=dict)  # effect id -> next charge day
    lifelines_used: list = field(default_factory=list)
    bankrupt: bool = False
    bankrupt_day: int = None
    had_evening_with_her: bool = False
    week_evenings: int = 0
    week_half_days: int = 0
    rel_missed_streak: int = 0
    pet_deficit_weighted: float = 0.0    # deficit days, weighted (walk routine doubles skipped walks)
    # observable history used by policies to value effects
    workdays: int = 0
    single_project_days: int = 0
    multi_task_days: int = 0
    effect_offer_count: int = 0
    log: dict = field(default_factory=lambda: {
        "cash": [], "cash_pre_lifeline": [], "stress": [], "paid_hours": [], "book_hours": [],
        "effect_mult": [], "payments": [], "costs": Counter(), "offers_by_source": Counter(),
        "picks": [], "rel_weeks": [], "pet_deficit_days": 0, "illness_days": 0, "crisis_days": [],
        "offers_seen": 0, "offers_accepted": 0, "jobs_delivered": [], "cap_hits": 0, "shop_buys": [],
        "pool_exhausted": 0,
    })

    def record_payment(self, day, invoice, amount):
        delay = day - invoice.delivered_day if invoice.source == "job" else None
        self.log["payments"].append({"day": day, "amount": amount, "source": invoice.source, "delay": delay})

    def receivables(self):
        return sum(inv.amount for inv in self.invoices)
