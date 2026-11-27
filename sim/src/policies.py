"""Player strategies (SIM_BASELINE.md §9.2). Numbers come from data/policies.yaml.

All policies except GreedyCandidate decide only from what a player can see (see state.py).
GreedyCandidate is the inner policy of the SEARCH-BASED greedy-optimal strategy: it reads the
run's full future offer stream. The search itself (trying every candidate per seed) lives in
experiments.run_greedy_optimal.
"""
from . import effects, offers, stress, time_demands
from . import game_calendar as cal
from .rng import stream
from .state import Plan

LAST_WORK_DAY = 42


# --- schedule helpers (shared) ---------------------------------------------------------------

def job_hours(cfg, st, job, eff):
    rate = cfg["work"]["throughput"][job.kind] * effects.throughput_multiplier(cfg, st.held, job.kind) * eff
    return job.words_left / rate


def offer_as_job(cfg, st, offer):
    extra = effects.revision_hours(cfg, st.held, offer.client) * cfg["work"]["throughput"][offer.kind]
    return offers.accept(offer, st.day, st.reputation_until, cfg, extra_words=extra)


def needed_today(cfg, st, jobs, hours_fn, eff):
    """Minimum paid hours today so every job can still meet its deadline (EDF check)."""
    jobs = sorted(jobs, key=lambda j: (j.deadline_day, j.accepted_day, j.id))
    day, cum, need = st.day, 0.0, 0.0
    for job in jobs:
        cum += job_hours(cfg, st, job, eff)
        last = max(day, min(job.deadline_day, LAST_WORK_DAY))
        capacity_after = sum(hours_fn(d) for d in range(day + 1, last + 1))
        need = max(need, cum - capacity_after)
    return need


def planning_efficiency(cfg, st, margin):
    return margin * stress.efficiency(cfg, st.stress)


# --- effect valuation ("highest expected value") ---------------------------------------------

def work_hours_left(st, p, cfg):
    days = range(st.day + 1, cfg["calendar"]["days"] + 1)
    paid = sum(p.get("weekend_paid_hours", 0) if cal.is_weekend(d) else p.get("weekday_paid_hours", 0) for d in days)
    book = 0.0 if st.book.finished else sum(
        p.get("book_weekend_hours", 0) if cal.is_weekend(d) else p.get("book_weekday_hours", 0) for d in days)
    return paid, book


def efficiency_gain(cfg, st, eid, p):
    """Rough expected efficiency bonus (fraction) of an effect for this player."""
    t = p.get("weekday_paid_hours", 0) + p.get("book_weekday_hours", 0)
    morning = min(cfg["day"]["morning_work_hours"], t) / t if t else 0
    evening = max(0.0, t - cfg["day"]["evening_after_hours"]) / t if t else 0
    single = st.single_project_days / st.workdays if st.workdays >= 3 else 0.6
    multi = st.multi_task_days / max(1, st.day - 1) if st.day > 3 else 0.5
    par = lambda k: effects.param(cfg, eid, k)  # noqa: E731
    return {
        "deep_focus": lambda: single * par("single_bonus") - (1 - single) * par("multi_penalty"),
        "context_switcher": lambda: multi * par("multi_bonus") - (1 - multi) * par("single_penalty"),
        "morning_person": lambda: morning * par("morning_bonus") - evening * par("evening_penalty"),
        "night_owl": lambda: evening * par("evening_bonus"),
    }.get(eid, lambda: 0.0)()


def effect_value(cfg, st, eid, p):
    w = p["value_weights"]
    days_left = cfg["calendar"]["days"] - st.day
    weeks_left = days_left / 7
    paid_h, book_h = work_hours_left(st, p, cfg)
    hourly = cfg["work"]["throughput"]["standard"] * cfg["work"]["rate"]["standard_agency"] * cfg["work"]["net_factor"]
    money, stress_pts, book_gain, extra = 0.0, 0.0, 0.0, 0.0
    gain = efficiency_gain(cfg, st, eid, p)
    money += gain * paid_h * hourly
    book_gain += gain * book_h
    if eid == "cat_tool":
        money += effects.param(cfg, eid, "bonus") * paid_h * hourly - effects.weekly_price(cfg, eid) * weeks_left
    elif eid == "direct_network":
        money += 0.1 * paid_h * hourly - 0.1 * days_left * effects.param(cfg, eid, "revision_hours") * hourly
    elif eid == "fast_invoicer":
        money -= effects.param(cfg, eid, "fee") * 0.25 * paid_h * hourly
        extra += w["liquidity"] * days_left / 42
    elif eid == "morning_pages":
        relief_gain = effects.book_relief_per_hour(cfg, [eid]) + cfg["stress"]["book_hour"]
        stress_pts += effects.param(cfg, eid, "daily_relief") * days_left + relief_gain * book_h
    elif eid == "walk_routine":
        pet = time_demands.pet_care_need(cfg, st.day)
        stress_pts += effects.param(cfg, eid, "pet_hour_relief") * pet * days_left
    elif eid == "her_spreadsheet":
        extra += w["info"]
    value = w["money"] * money + w["stress_per_point"] * stress_pts + w["book_per_hour"] * book_gain + extra
    only = p.get("category_only")
    if only and effects.category(cfg, eid) not in only:
        value = value * 0.05 - 1000   # grinder: efficiency/rate first, others only as a last resort
    return value


# --- base policy -----------------------------------------------------------------------------

class Policy:
    uses_foresight = False

    def __init__(self, name, params):
        self.name, self.p = name, params

    def rng(self, st, *keys):
        return stream(st.seed, "policy", self.name, st.day, *keys)

    def start(self, cfg, st, seed, offer_stream):
        pass

    # hours this policy plans to work on a day (without "behind schedule" extras)
    def planned_paid(self, day):
        return self.p["weekend_paid_hours"] if cal.is_weekend(day) else self.p["weekday_paid_hours"]

    def max_paid(self, day):
        extra = self.p["weekend_extra_hours"] if cal.is_weekend(day) else self.p["extra_paid_hours"]
        return self.planned_paid(day) + extra

    # offers
    def choose_offers(self, cfg, st, seen):
        eff = planning_efficiency(cfg, st, self.p["eff_margin"])
        chosen, jobs = [], list(st.jobs)
        for offer in sorted(seen, key=lambda o: -o.rate * cfg["work"]["throughput"][o.kind]):
            trial = jobs + [offer_as_job(cfg, st, offer)]
            if needed_today(cfg, st, trial, self.planned_paid, eff) <= self.planned_paid(st.day) + 1e-9:
                chosen.append(offer)
                jobs = trial
        return chosen

    # day plan
    def paid_hours_today(self, cfg, st):
        eff = planning_efficiency(cfg, st, self.p["eff_margin"])
        total = sum(job_hours(cfg, st, j, eff) for j in st.jobs)
        need = needed_today(cfg, st, st.jobs, self.planned_paid, eff) if st.jobs else 0.0
        hours = min(max(self.planned_paid(st.day), need), self.max_paid(st.day))
        behind = need > self.planned_paid(st.day) + 1e-9
        return min(hours, total), behind

    def book_hours_today(self, st, behind):
        if st.book.finished or (behind and self.p.get("skip_book_when_behind")):
            return 0.0
        return self.p["book_weekend_hours"] if cal.is_weekend(st.day) else self.p["book_weekday_hours"]

    def sleep_today(self, st, behind):
        return self.p["sleep_hours"] - (self.p.get("cut_sleep_when_behind", 0) if behind else 0)

    def pet_today(self, cfg, st, coworking):
        return time_demands.pet_care_need(cfg, st.day, coworking and "coworking" in st.held,
                                          effects.param(cfg, "coworking", "extra_pet_care_hours"))

    def her_today(self, cfg, st):
        """'meet': 3 evenings (Mon/Wed/Fri); in her crunch weeks both free evenings + Saturday half-day."""
        h, day = cfg["her"], st.day
        crunch = cal.week_of(day) in h["crunch_weeks"]
        if time_demands.her_available_evening(cfg, day) and (crunch or cal.weekday(day) in (1, 3, 5)):
            return h["evening_hours"]
        if cal.weekday(day) == 6 and st.week_evenings < h["evenings_needed"]:
            return h["half_day_hours"]
        return 0.0

    def plan_day(self, cfg, st):
        paid, behind = self.paid_hours_today(cfg, st)
        coworking = "coworking" in st.held and paid > 0 and not cal.is_weekend(st.day)
        return Plan(paid_hours=paid, book_hours=self.book_hours_today(st, behind),
                    pet_hours=self.pet_today(cfg, st, coworking), her_hours=self.her_today(cfg, st),
                    sleep_hours=self.sleep_today(st, behind), coworking=coworking)

    # effects and shop
    def pick_effect(self, cfg, st, choices, source):
        return max(choices, key=lambda eid: (effect_value(cfg, st, eid, self.p), eid))

    def shop(self, cfg, st):
        buys = []
        for eid, rule in self.p.get("shop", {}).items():
            if eid not in st.held and st.cash >= rule["min_cash"] and st.day <= 28:
                buys.append(eid)
        return buys

    # money
    def lifeline_order(self, cfg, st):
        return self.p["lifeline_order"]

    def pay_deferred_rent(self, cfg, st):
        return st.cash - st.deferred_rent["amount"] >= 300


class Careful(Policy):
    pass


class BookHeavy(Policy):
    pass


class Grinder(Policy):
    def sleep_today(self, st, behind):
        if cal.is_weekend(st.day):
            return self.p["sleep_hours"]
        return self.rng(st, "sleep").choice(self.p["sleep_weekday_choices"])

    def pet_today(self, cfg, st, coworking):
        need = super().pet_today(cfg, st, coworking)
        if self.rng(st, "pet").random() < self.p["pet_meet_chance"]:
            return need
        return max(0.0, need - self.p["pet_short_hours"])

    def her_today(self, cfg, st):
        h, day, rng = cfg["her"], st.day, self.rng(st, "her")
        if time_demands.her_available_evening(cfg, day):
            if st.week_evenings == 0 and cal.weekday(day) >= 3:
                return h["evening_hours"]
            if st.week_evenings == 1 and cal.weekday(day) == 5 and rng.random() < self.p["her_second_evening_chance"]:
                return h["evening_hours"]
        if cal.weekday(day) == 6 and rng.random() < self.p["her_half_day_chance"]:
            return h["half_day_hours"]
        return 0.0


class Careless(Policy):
    def choose_offers(self, cfg, st, seen):
        rng = self.rng(st, "accept")
        return [o for o in seen if rng.random() < self.p["accept_chance"]]

    def paid_hours_today(self, cfg, st):
        if cal.is_weekend(st.day) or not st.jobs:
            return 0.0, False
        total = sum(job_hours(cfg, st, j, 1.0) for j in st.jobs)
        return min(self.p["weekday_paid_hours"], total), False

    def book_hours_today(self, st, behind):
        if st.book.finished or self.rng(st, "book").random() >= self.p["book_chance"]:
            return 0.0
        return self.p["book_weekend_hours"] if cal.is_weekend(st.day) else self.p["book_weekday_hours"]

    def sleep_today(self, st, behind):
        rng = self.rng(st, "sleep")
        if rng.random() < self.p["sleep_cut_chance"]:
            return self.p["sleep_hours"] - rng.choice(self.p["sleep_cut_choices"])
        return self.p["sleep_hours"]

    def pet_today(self, cfg, st, coworking):
        need = super().pet_today(cfg, st, coworking)
        return need if self.rng(st, "pet").random() < self.p["pet_meet_chance"] else need / 2

    def her_today(self, cfg, st):
        h, day, rng = cfg["her"], st.day, self.rng(st, "her")
        if time_demands.her_available_evening(cfg, day) and rng.random() < self.p["her_evening_chance"]:
            return h["evening_hours"]
        if cal.weekday(day) == 6 and rng.random() < self.p["her_half_day_chance"]:
            return h["half_day_hours"]
        return 0.0

    def pick_effect(self, cfg, st, choices, source):
        return self.rng(st, "effect", source, len(st.held)).choice(choices)

    def shop(self, cfg, st):
        rule, rng = self.p["shop"], self.rng(st, "shop")
        if st.cash >= rule["min_cash"] and rng.random() < rule["random_chance_per_day"]:
            options = [e for e in effects.shop_items(cfg) if e not in st.held]
            return [rng.choice(options)] if options else []
        return []

    def lifeline_order(self, cfg, st):
        order = ["early_payment", "borrow"]
        self.rng(st, "lifelines").shuffle(order)
        return order


class GreedyCandidate(Policy):
    """One point of the greedy-optimal search. SEARCH-BASED: reads the future offer stream."""
    uses_foresight = True

    def __init__(self, name, params, weekday_hours, weekend_hours, sleep_hours):
        super().__init__(name, dict(params, weekday_paid_hours=weekday_hours, weekend_paid_hours=weekend_hours))
        self.weekday_hours, self.weekend_hours, self.sleep = weekday_hours, weekend_hours, sleep_hours
        self.planned_ids = set()

    def planned_paid(self, day):
        return self.weekend_hours if cal.is_weekend(day) else self.weekday_hours

    def max_paid(self, day):
        return self.planned_paid(day)

    def start(self, cfg, st, seed, offer_stream):
        """Plan the whole run's job set from the known offers: best net $/hour first,
        kept only if it fits the remaining capacity between its offer day and deadline."""
        eff = self.p["eff_margin"]
        days = cfg["calendar"]["days"]
        capacity = {d: self.planned_paid(d) * eff for d in range(1, days + 1)}
        candidates = [o for day_offers in offer_stream["by_day"].values() for o in day_offers
                      if not o.extra_direct and o.day < cfg["calendar"]["no_new_work_from_day"]]
        candidates.sort(key=lambda o: (-o.rate * cfg["work"]["throughput"][o.kind], o.id))
        for offer in candidates:
            hours = offer.words / cfg["work"]["throughput"][offer.kind]
            window = range(offer.day, min(offer.deadline_day, days) + 1)
            if sum(capacity[d] for d in window) + 1e-9 < hours:
                continue
            for d in window:
                use = min(capacity[d], hours)
                capacity[d] -= use
                hours -= use
            self.planned_ids.add(offer.id)

    def choose_offers(self, cfg, st, seen):
        planned = [o for o in seen if o.id in self.planned_ids]
        others = [o for o in seen if o.id not in self.planned_ids and o.extra_direct]
        return planned + super().choose_offers(cfg, st, others)

    def paid_hours_today(self, cfg, st):
        total = sum(job_hours(cfg, st, j, self.p["eff_margin"]) for j in st.jobs)
        return min(self.planned_paid(st.day), total), False

    def book_hours_today(self, st, behind):
        return 0.0

    def sleep_today(self, st, behind):
        return self.sleep if not cal.is_weekend(st.day) else max(self.sleep, 8)

    def pet_today(self, cfg, st, coworking):
        return self.p["pet_care_hours"]

    def her_today(self, cfg, st):
        return 0.0


POLICY_CLASSES = {"careful": Careful, "book_heavy": BookHeavy, "grinder": Grinder, "careless": Careless}


def make(name, policies_cfg):
    return POLICY_CLASSES[name](name, policies_cfg[name])


def greedy_candidates(policies_cfg):
    p = policies_cfg["greedy_optimal"]
    for wd in p["search_weekday_hours"]:
        for we in p["search_weekend_hours"]:
            for sl in p["search_sleep_hours"]:
                yield GreedyCandidate("greedy_optimal", p, wd, we, sl)


__all__ = ["make", "greedy_candidates"]
