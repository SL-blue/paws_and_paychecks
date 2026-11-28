"""Player strategies (SIM_BASELINE.md §10.2). Numbers come from data/policies.yaml.

All policies except GreedyCandidate decide only from what a player can see (see state.py).
GreedyCandidate is the inner policy of the SEARCH-BASED greedy-optimal strategy: it reads the
run's full future offer stream. The search itself (trying every candidate per seed) lives in
experiments.run_greedy_optimal.

For every policy: the day-1 job is always taken (engine), the story job is a decision
(`decide_story`), her loan is repaid as soon as cash allows (`loan_repayment`), borrowing is
always the last lifeline. Value-based policies rate effects with effect_value.py, skip an offer
when no effect beats the skip reward, and buy a shop item when its value exceeds its price (v0.4).
ImperfectCareful (v0.4) is careful plus slips under pressure.
"""
from . import costs, effect_value, effects, offers, stress, time_demands
from . import game_calendar as cal
from .rng import stream
from .state import Plan

LAST_WORK_DAY = 42


# --- schedule helpers (shared) ---------------------------------------------------------------

def job_hours(cfg, st, job, eff):
    rate = cfg["work"]["throughput"][job.kind] * effects.throughput_multiplier(cfg, st.held, job.offer) * eff
    return job.words_left / rate


def offer_as_job(cfg, st, offer):
    return offers.accept(cfg, offer, st, effects)


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

    def capped(self, cfg, st, fn):
        limit = effects.max_paid_hours(cfg, st.held)
        return fn if limit is None else (lambda d: min(fn(d), limit))

    # offers
    def fits(self, cfg, st, jobs, hours_fn):
        eff = planning_efficiency(cfg, st, self.p["eff_margin"])
        return needed_today(cfg, st, jobs, hours_fn, eff) <= hours_fn(st.day) + 1e-9

    def choose_offers(self, cfg, st, seen):
        chosen, jobs = [], list(st.jobs)
        planned = self.capped(cfg, st, self.planned_paid)
        for offer in sorted(seen, key=lambda o: (-o.rate * cfg["work"]["throughput"][o.kind], o.id)):
            trial = jobs + [offer_as_job(cfg, st, offer)]
            if self.fits(cfg, st, trial, planned):
                chosen.append(offer)
                jobs = trial
        return chosen

    def decide_story(self, cfg, st, offer):
        """The story job is hard to refuse: take it if it fits with the extra hours the policy
        allows itself when behind (planned + extra), not only its planned hours."""
        return self.fits(cfg, st, st.jobs + [offer_as_job(cfg, st, offer)], self.capped(cfg, st, self.max_paid))

    # day plan
    def paid_hours_today(self, cfg, st):
        eff = planning_efficiency(cfg, st, self.p["eff_margin"])
        planned = self.capped(cfg, st, self.planned_paid)
        total = sum(job_hours(cfg, st, j, eff) for j in st.jobs)
        need = needed_today(cfg, st, st.jobs, planned, eff) if st.jobs else 0.0
        hours = min(max(planned(st.day), need), self.capped(cfg, st, self.max_paid)(st.day))
        behind = need > planned(st.day) + 1e-9
        return min(hours, total), behind

    def book_hours_today(self, st, behind):
        if st.book.finished or (behind and self.p.get("skip_book_when_behind")):
            return 0.0
        return self.p["book_weekend_hours"] if cal.is_weekend(st.day) else self.p["book_weekday_hours"]

    def sleep_today(self, st, behind):
        return self.p["sleep_hours"] - (self.p.get("cut_sleep_when_behind", 0) if behind else 0)

    def pet_need(self, cfg, st, coworking):
        return time_demands.pet_care_need(cfg, st.day, effects.pet_need_change(cfg, st.held, st.day, coworking))

    def pet_today(self, cfg, st, coworking):
        return self.pet_need(cfg, st, coworking)

    def her_today(self, cfg, st):
        """'meet': 3 evenings (Mon/Wed/Fri); in her crunch weeks every free evening, plus a
        weekend half-day if the week still needs one."""
        h, day = cfg["her"], st.day
        crunch = cal.week_of(day) in h["crunch_weeks"]
        evenings = effects.crunch_evenings(cfg, st.held)
        if time_demands.her_available_evening(cfg, day, evenings) and (crunch or cal.weekday(day) in (1, 3, 5)):
            return h["evening_hours"]
        if cal.weekday(day) == 6 and st.week_evenings < h["evenings_needed"]:
            return effects.half_day_hours(cfg, st.held)
        return 0.0

    def use_sitter(self, cfg, st, plan, behind):
        """The neighbor covers one day a week: on a day the policy is behind, or would fall short on care."""
        if "neighbor_sitter" not in st.held or st.sitter_week == cal.week_of(st.day):
            return False
        return behind or plan.pet_hours + 1e-9 < self.pet_need(cfg, st, plan.coworking)

    def writing_session(self, cfg, st, plan):
        """Writing group: one 2 h session a week, on the first weekday evening without her."""
        if "writing_group" not in st.held or st.book.finished or st.writing_week == cal.week_of(st.day):
            return False
        return not cal.is_weekend(st.day) and plan.her_hours == 0 and plan.book_hours > 0

    def plan_day(self, cfg, st):
        paid, behind = self.paid_hours_today(cfg, st)
        coworking = "coworking" in st.held and paid > 0 and not cal.is_weekend(st.day)
        self.behind_today = behind
        plan = Plan(paid_hours=paid, book_hours=self.book_hours_today(st, behind),
                    pet_hours=self.pet_today(cfg, st, coworking), her_hours=self.her_today(cfg, st),
                    sleep_hours=self.sleep_today(st, behind), coworking=coworking)
        plan.sitter = self.use_sitter(cfg, st, plan, behind)
        if self.writing_session(cfg, st, plan):
            plan.writing_session = True
            plan.book_hours = max(plan.book_hours, effects.param(cfg, "writing_group", "session_hours"))
        return plan

    # effects and shop
    def pick_effect(self, cfg, st, choices, source):
        """The highest-valued effect, or None (skip) if none beats the skip reward."""
        best = max(choices, key=lambda eid: (effect_value.value(cfg, st, eid, self.p), eid))
        return best if effect_value.value(cfg, st, best, self.p) > effect_value.skip_value(cfg, self.p) else None

    def shop(self, cfg, st):
        """Buy a shop item when its value exceeds its price (§8.5), if cash stays above a reserve."""
        reserve = self.p["shop_reserve_days"] * costs.daily_running_cost(cfg, st.day, effects.living_saving(cfg, st.held))
        buys, cash = [], st.cash
        for eid in effects.shop_items(cfg):
            if eid in st.held:
                continue
            price = effect_value.price_now(cfg, st, eid)
            if cash - price >= reserve and effect_value.value(cfg, st, eid, self.p, shop=True) > self.p["value_weights"]["money"] * price:
                buys.append(eid)
                cash -= effects.one_off_price(cfg, eid) + effects.weekly_price(cfg, eid)
        return buys

    # money
    def lifeline_order(self, cfg, st):
        return self.p["lifeline_order"]

    def pay_deferred_rent(self, cfg, st):
        return st.cash - st.deferred_rent["amount"] >= 300

    def loan_repayment(self, cfg, st):
        """Repay as soon as cash allows, keeping a reserve of a few days of costs; on the
        deadline day, pay whatever cash there is."""
        if st.day >= st.loan["due_day"]:
            return max(0.0, st.cash)
        reserve = cfg["lifelines"]["repay_reserve_days"] * costs.daily_running_cost(cfg, st.day, effects.living_saving(cfg, st.held))
        return max(0.0, st.cash - reserve)


class Careful(Policy):
    pass


class ImperfectCareful(Careful):
    """Careful plus realistic slips under pressure (§10.2):
    - on a day starting with T above `pressure_stress`, or with a deadline at risk, it skips a
      planned weekday evening with her with `her_skip_chance`, and drops `pet_drop_hours` of pet
      care with `pet_drop_chance`;
    - with `job_slip_chance` per week it accepts one job that doesn't fit its schedule check."""

    def plan_day(self, cfg, st):
        plan = super().plan_day(cfg, st)
        if st.stress <= self.p["pressure_stress"] and not self.behind_today:
            return plan
        rng = self.rng(st, "slip")
        her_roll, pet_roll = rng.random(), rng.random()
        evening = not cal.is_weekend(st.day) and plan.her_hours >= cfg["her"]["evening_hours"] - 1e-9
        if evening and her_roll < self.p["her_skip_chance"]:
            plan.her_hours, plan.her_slip = 0.0, True
        if plan.pet_hours > 0 and not plan.sitter and pet_roll < self.p["pet_drop_chance"]:
            plan.pet_hours, plan.pet_slip = max(0.0, plan.pet_hours - self.p["pet_drop_hours"]), True
        return plan

    def slip_week(self, st):
        week = cal.week_of(st.day)
        return st.week_slip_used != week and stream(st.seed, "policy", self.name, "job_slip", week).random() < self.p["job_slip_chance"]

    def choose_offers(self, cfg, st, seen):
        chosen = super().choose_offers(cfg, st, seen)
        taken = {o.id for o in chosen}
        rest = [o for o in seen if o.id not in taken]
        if rest and self.slip_week(st):
            st.week_slip_used = cal.week_of(st.day)
            st.log["slips"]["job"] += 1
            chosen.append(min(rest, key=lambda o: (-o.rate * cfg["work"]["throughput"][o.kind], o.id)))
        return chosen


class BookHeavy(Policy):
    pass


class Grinder(Policy):
    def sleep_today(self, st, behind):
        if cal.is_weekend(st.day):
            return self.p["sleep_hours"]
        return self.rng(st, "sleep").choice(self.p["sleep_weekday_choices"])

    def pet_today(self, cfg, st, coworking):
        need = self.pet_need(cfg, st, coworking)
        if self.rng(st, "pet").random() < self.p["pet_meet_chance"]:
            return need
        return max(0.0, need - self.p["pet_short_hours"])

    def her_today(self, cfg, st):
        h, day, rng = cfg["her"], st.day, self.rng(st, "her")
        if time_demands.her_available_evening(cfg, day, effects.crunch_evenings(cfg, st.held)):
            if st.week_evenings == 0 and cal.weekday(day) >= 3:
                return h["evening_hours"]
            if st.week_evenings == 1 and cal.weekday(day) == 5 and rng.random() < self.p["her_second_evening_chance"]:
                return h["evening_hours"]
        if cal.weekday(day) == 6 and rng.random() < self.p["her_half_day_chance"]:
            return effects.half_day_hours(cfg, st.held)
        return 0.0


class Careless(Policy):
    def choose_offers(self, cfg, st, seen):
        rng = self.rng(st, "accept")
        return [o for o in seen if rng.random() < self.p["accept_chance"]]

    def decide_story(self, cfg, st, offer):
        return self.rng(st, "story").random() < self.p["accept_chance"]

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
        need = self.pet_need(cfg, st, coworking)
        return need if self.rng(st, "pet").random() < self.p["pet_meet_chance"] else need / 2

    def her_today(self, cfg, st):
        h, day, rng = cfg["her"], st.day, self.rng(st, "her")
        if time_demands.her_available_evening(cfg, day, effects.crunch_evenings(cfg, st.held)) and rng.random() < self.p["her_evening_chance"]:
            return h["evening_hours"]
        if cal.weekday(day) == 6 and rng.random() < self.p["her_half_day_chance"]:
            return effects.half_day_hours(cfg, st.held)
        return 0.0

    def pick_effect(self, cfg, st, choices, source):
        """Random among the offered effects; careless never skips (sim choice)."""
        return self.rng(st, "effect", source, len(st.held)).choice(choices)

    def shop(self, cfg, st):
        rule, rng = self.p["shop"], self.rng(st, "shop")
        if st.cash >= rule["min_cash"] and rng.random() < rule["random_chance_per_day"]:
            options = [e for e in effects.shop_items(cfg) if e not in st.held]
            return [rng.choice(options)] if options else []
        return []

    def lifeline_order(self, cfg, st):
        return ["early_payment", "borrow"]   # random in round 1; borrowing is now always last (spec §6)


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
                      if not o.needs and o.day < cfg["calendar"]["no_new_work_from_day"]]
        candidates.sort(key=lambda o: (o.fixed != "day1", -o.rate * cfg["work"]["throughput"][o.kind], o.id))
        for offer in candidates:
            hours = offer.words / cfg["work"]["throughput"][offer.kind]
            window = range(offer.day, min(offer.deadline_day, days) + 1)
            if sum(capacity[d] for d in window) + 1e-9 < hours and offer.fixed != "day1":
                continue
            for d in window:
                use = min(capacity[d], hours)
                capacity[d] -= use
                hours -= use
            self.planned_ids.add(offer.id)

    def choose_offers(self, cfg, st, seen):
        planned = [o for o in seen if o.id in self.planned_ids]
        others = [o for o in seen if o.id not in self.planned_ids and o.needs]
        return planned + super().choose_offers(cfg, st, others)

    def decide_story(self, cfg, st, offer):
        return offer.id in self.planned_ids

    def paid_hours_today(self, cfg, st):
        total = sum(job_hours(cfg, st, j, self.p["eff_margin"]) for j in st.jobs)
        return min(self.capped(cfg, st, self.planned_paid)(st.day), total), False

    def book_hours_today(self, st, behind):
        return 0.0

    def sleep_today(self, st, behind):
        return self.sleep if not cal.is_weekend(st.day) else max(self.sleep, 8)

    def pet_today(self, cfg, st, coworking):
        return self.p["pet_care_hours"]

    def her_today(self, cfg, st):
        return 0.0


POLICY_CLASSES = {"imperfect_careful": ImperfectCareful, "careful": Careful, "book_heavy": BookHeavy,
                  "grinder": Grinder, "careless": Careless}


def params(name, policies_cfg):
    """A policy's numbers; `inherits: <other>` starts from another policy's numbers."""
    p = dict(policies_cfg[name])
    parent = p.pop("inherits", None)
    return dict(params(parent, policies_cfg), **p) if parent else p


def make(name, policies_cfg):
    return POLICY_CLASSES[name](name, params(name, policies_cfg))


def greedy_candidates(policies_cfg):
    p = policies_cfg["greedy_optimal"]
    for wd in p["search_weekday_hours"]:
        for we in p["search_weekend_hours"]:
            for sl in p["search_sleep_hours"]:
                yield GreedyCandidate("greedy_optimal", p, wd, we, sl)


__all__ = ["make", "greedy_candidates"]
