"""Offers and jobs (SIM_BASELINE.md §3.1-3.3, §3.6): random offers, regular clients, fixed jobs.

The whole offer stream of a seed is generated up front from its own random streams, so it does
not depend on what the player does. Effects, reputation and a declined story job then filter it
day by day (`offers_for_day`). Offers that only exist with an effect (extra direct, rush or
regular-client offers) are pre-generated too and marked with `needs`. Only the greedy-optimal
policy may look at future days.
"""
import math
from dataclasses import dataclass, field

from . import game_calendar as cal
from .rng import poisson, stream, weighted_choice


@dataclass
class Offer:
    id: str
    day: int
    client: str            # client type: direct / standard_agency / slow_agency
    kind: str              # standard / post_edit
    rush: bool
    words: int
    rate: float            # gross $/word, incl. rush premium and a regular client's rate bonus
    deadline_day: int
    size: str = "small"
    regular: str = None    # "A" / "B" / "C" for regular clients, else None
    fixed: str = None      # "day1" / "story" for fixed jobs, else None
    needs: str = None      # effect id this offer depends on (extra offers), else None
    rolls: dict = field(default_factory=dict)   # pre-drawn rolls for filters (see offers_for_day)

    @property
    def gross(self):
        return self.words * self.rate

    @property
    def story(self):
        return self.fixed == "story"

    @property
    def rep_key(self):
        """Reputation is tracked per regular client, otherwise per client type."""
        return self.regular or self.client


@dataclass
class Job:
    offer: Offer
    accepted_day: int
    words_left: float
    late: bool = False
    hours_worked: float = 0.0
    rate_multiplier: float = 1.0   # reputation penalty x rate effects, fixed at acceptance
    deposit: float = 0.0           # net $ already paid at acceptance (deposit terms)
    rate_bonus: float = 0.0        # the capped rate-effect bonus inside rate_multiplier (for the boost metric)

    @property
    def id(self):
        return self.offer.id

    @property
    def kind(self):
        return self.offer.kind

    @property
    def deadline_day(self):
        return self.offer.deadline_day


# --- building offers --------------------------------------------------------------------------

def pe_share(cfg, day, switch_day):
    """Share of random offers that are post-editing on a day."""
    o = cfg["offers"]
    start, end, end_day = o["pe_share_start"], o["pe_share_end"], o["pe_share_end_day"]
    ramp_from = switch_day if o["pe_ramp_from_switch"] else 1
    if day < ramp_from:
        return start
    if day >= end_day or end_day <= ramp_from:
        return end
    return start + (end - start) * (day - ramp_from) / (end_day - ramp_from)


def deadline_day(cfg, offer_day, est_hours, factor, rush):
    o = cfg["offers"]
    days = math.ceil(est_hours / o["deadline_hours_per_day"] * factor)
    if rush:
        days = math.ceil(days * cfg["work"]["rush_deadline_factor"])
    days = max(o["deadline_min_days"], days)
    return cal.add_working_days(offer_day, days)


def base_rate(cfg, client, kind):
    rates = cfg["work"]["rate"]
    if kind == "post_edit":
        return rates["post_edit"]
    return rates["standard_direct"] if client == "direct" else rates["standard_agency"]


def regular_rate_bonus(cfg, regular):
    rc = cfg["regular_clients"]
    return rc[regular]["rate_bonus"] * rc["rate_bonus_scale"] if regular else 0.0


def draw_rolls(seed, offer_id):
    rng = stream(seed, "offer_rolls", offer_id)
    return {k: rng.random() for k in ("drop", "niche", "large", "extra")}


def make_offer(cfg, rng, seed, offer_id, day, size_name, client, kind, rush, regular=None):
    o, w = cfg["offers"], cfg["work"]
    size = o["sizes"][size_name]
    words = rng.randint(size["min_words"], size["max_words"])
    rate = base_rate(cfg, client, kind) * (w["rush_rate_multiplier"] if rush else 1.0)
    rate *= 1 + regular_rate_bonus(cfg, regular)
    factor = rng.uniform(o["deadline_factor_min"], o["deadline_factor_max"])
    return Offer(id=offer_id, day=day, client=client, kind=kind, rush=rush, words=words, rate=rate,
                 deadline_day=deadline_day(cfg, day, words / w["throughput"][kind], factor, rush),
                 size=size_name, regular=regular, rolls=draw_rolls(seed, offer_id))


def random_offer(cfg, rng, seed, offer_id, day, pe, client=None, rush=None):
    o, w = cfg["offers"], cfg["work"]
    sizes = list(o["sizes"])
    size = weighted_choice(rng, sizes, [o["sizes"][s]["share"] for s in sizes])
    types = [c for c in cfg["clients"] if isinstance(cfg["clients"][c], dict)]
    client_roll = weighted_choice(rng, types, [cfg["clients"][c]["share"] for c in types])
    kind = "post_edit" if rng.random() < pe else "standard"
    rush_roll = kind == "standard" and rng.random() < w["rush_share"]
    if rush:                      # extra rush offers (rush specialist) are always standard rush jobs
        kind, rush_roll = "standard", True
    return make_offer(cfg, rng, seed, offer_id, day, size, client or client_roll, kind, rush_roll)


def random_offers(cfg, seed, switch_day):
    """Random offers per weekday, plus the extra offers that only effects make visible."""
    rng, o = stream(seed, "offers"), cfg["offers"]
    mean = o["per_weekday_mean"]
    direct_mean = mean * cfg["clients"]["direct"]["share"]
    by_day = {}
    for day in range(1, cfg["calendar"]["days"] + 1):
        if cal.is_weekend(day) or day >= cfg["calendar"]["no_new_work_from_day"]:
            continue
        pe = pe_share(cfg, day, switch_day)
        rush_mean = mean * (1 - pe) * cfg["work"]["rush_share"]
        day_offers = [random_offer(cfg, rng, seed, f"d{day}o{i}", day, pe) for i in range(poisson(rng, mean))]
        for i in range(poisson(rng, direct_mean)):
            day_offers.append(random_offer(cfg, rng, seed, f"d{day}x{i}", day, pe, client="direct"))
            day_offers[-1].needs = "direct_network"
        for i in range(poisson(rng, rush_mean)):
            day_offers.append(random_offer(cfg, rng, seed, f"d{day}r{i}", day, pe, rush=True))
            day_offers[-1].needs = "rush_specialist"
        by_day[day] = day_offers
    return by_day


def habit_day(cfg, rng, week, client_cfg):
    """A regular client's offer day in a week: usual weekday +- jitter, or any weekday."""
    usual = client_cfg["usual_weekday"]
    wd = rng.randint(1, 5) if usual is None else usual + rng.randint(-client_cfg["weekday_jitter"], client_cfg["weekday_jitter"])
    return (week - 1) * 7 + min(5, max(1, wd))


def regular_offers(cfg, seed, switch_day):
    """Habit jobs of the regular clients. A second, independent draw per week is the
    'loyal client' extra job (only visible with that effect)."""
    rc, out = cfg["regular_clients"], []
    for name in ("A", "B", "C"):
        c = rc[name]
        rng = stream(seed, "regular", name)
        prob = min(1.0, c["prob_per_week"] * rc["prob_scale"])
        for week in range(1, cfg["calendar"]["days"] // 7 + 1):
            for copy in ("", "L"):
                hit, day = rng.random() < prob, habit_day(cfg, rng, week, c)
                sizes = [s for s in c["size_weights"]]
                size = weighted_choice(rng, sizes, [c["size_weights"][s] for s in sizes])
                kind = "post_edit" if c["switches_to_pe"] and day >= switch_day else "standard"
                offer = make_offer(cfg, rng, seed, f"{name}{week}{copy}", day, size, c["type"], kind, False, regular=name)
                if not hit or day >= cfg["calendar"]["no_new_work_from_day"]:
                    continue
                offer.needs = "loyal_client" if copy else None
                out.append(offer)
    return out


def fixed_offer(cfg, seed, which):
    w = cfg["work"]
    spec = cfg["day1_job"] if which == "day1" else cfg["story_job"]
    regular = spec["client"]
    client = cfg["regular_clients"][regular]["type"]
    rate = base_rate(cfg, client, "standard") * (1 + regular_rate_bonus(cfg, regular))
    if which == "day1":
        deadline = spec["deadline_day"]
    else:
        factor = stream(seed, "story_job").uniform(cfg["offers"]["deadline_factor_min"], cfg["offers"]["deadline_factor_max"])
        deadline = deadline_day(cfg, spec["offer_day"], spec["words"] / w["throughput"]["standard"], factor, False)
    sizes = cfg["offers"]["sizes"]
    size = "large" if spec["words"] >= sizes["large"]["min_words"] else (
        "medium" if spec["words"] >= sizes["medium"]["min_words"] else "small")
    return Offer(id=which, day=spec["offer_day"], client=client, kind="standard", rush=False,
                 words=spec["words"], rate=rate, deadline_day=deadline, size=size, regular=regular,
                 fixed=which, rolls=draw_rolls(seed, which))


def generate_stream(cfg, seed):
    """All offers of the run: {"by_day": {day: [Offer, ...]}, "pe_switch_day": int}."""
    o = cfg["offers"]
    switch_day = stream(seed, "pe_switch").randint(o["pe_switch_day_min"], o["pe_switch_day_max"])
    by_day = random_offers(cfg, seed, switch_day)
    for offer in regular_offers(cfg, seed, switch_day):
        by_day.setdefault(offer.day, []).append(offer)
    for which in ("day1", "story"):
        offer = fixed_offer(cfg, seed, which)
        by_day.setdefault(offer.day, []).insert(0, offer)
    return {"by_day": by_day, "pe_switch_day": switch_day}


# --- what the player sees today ---------------------------------------------------------------

def visible(cfg, offer, held, story_declined, reputation_until, day, fx):
    """Filters, in order: effect-only extras, effect thinning, a declined story job, reputation."""
    if offer.fixed:
        return True
    if offer.needs:
        if offer.needs not in held or offer.rolls["extra"] >= fx.extra_offer_share(cfg, offer.needs):
            return False
    if not offer.regular and "specialist_niche" in held and offer.rolls["niche"] < fx.param(cfg, "specialist_niche", "random_offer_drop"):
        return False
    if offer.regular == "A" and story_declined and offer.rolls["drop"] < cfg["story_job"]["decline_offer_drop"]:
        return False
    cool = reputation_until.get(offer.rep_key, 0) >= day
    return not (cool and offer.rolls["drop"] < cfg["reputation"]["offer_drop_chance"])


def offers_for_day(cfg, offer_stream, day, st, fx):
    """The offers the player actually sees today. `fx` is the effects module (avoids an import cycle)."""
    return [o for o in offer_stream["by_day"].get(day, [])
            if visible(cfg, o, st.held, st.story_declined, st.reputation_until, day, fx)]


def accept(cfg, offer, st, fx):
    """Turn an offer into a job. Rate effects and reputation are fixed now; unpaid extra hours
    (revisions, a new termbase) are added as extra words at the job's base throughput."""
    cool = st.reputation_until.get(offer.rep_key, 0) >= st.day and not offer.fixed
    bonus = fx.rate_bonus(cfg, st.held, offer)
    mult = (cfg["reputation"]["rate_multiplier"] if cool else 1.0) * (1 + bonus)
    extra_hours = fx.extra_job_hours(cfg, st, offer)
    words = offer.words + extra_hours * cfg["work"]["throughput"][offer.kind]
    return Job(offer=offer, accepted_day=st.day, words_left=words, rate_multiplier=mult, rate_bonus=bonus)


def job_gross(job):
    return job.offer.gross * job.rate_multiplier
