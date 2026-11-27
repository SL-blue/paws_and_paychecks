"""Offers and jobs (SIM_BASELINE.md §3.1-3.2, §3.4 story job).

The whole offer stream for a seed is generated up front from its own random stream, so it does
not depend on what the player does. Reputation and the direct-client network then filter it
day by day (see `offers_for_day`). Only the greedy-optimal policy may look at future days.
"""
import math
from dataclasses import dataclass

from . import game_calendar as cal
from .rng import poisson, stream, weighted_choice


@dataclass
class Offer:
    id: str
    day: int
    client: str            # direct / standard_agency / slow_agency
    kind: str              # standard / post_edit
    rush: bool
    words: int
    rate: float            # gross $/word, incl. rush premium
    deadline_day: int
    story: bool = False
    extra_direct: bool = False   # only exists if the direct-client network effect is held
    drop_roll: float = 0.0       # pre-drawn roll for the reputation filter

    @property
    def gross(self):
        return self.words * self.rate


@dataclass
class Job:
    offer: Offer
    accepted_day: int
    words_left: float
    late: bool = False
    hours_worked: float = 0.0
    rate_multiplier: float = 1.0   # reputation penalty applied at acceptance

    @property
    def id(self):
        return self.offer.id

    @property
    def kind(self):
        return self.offer.kind

    @property
    def deadline_day(self):
        return self.offer.deadline_day


def pe_share(cfg, day, switch_day):
    """Share of offers that are post-editing on a day (story hook: the regular client switches)."""
    o = cfg["offers"]
    start, end = o["pe_share_start"], o["pe_share_end"]
    if day < switch_day:
        return start
    end_day = o["pe_share_end_day"]
    if day >= end_day or end_day <= switch_day:
        return end
    return start + (end - start) * (day - switch_day) / (end_day - switch_day)


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


def draw_offer(cfg, rng, offer_id, day, pe, client=None):
    o, w = cfg["offers"], cfg["work"]
    sizes = list(o["sizes"].values())
    size = weighted_choice(rng, sizes, [s["share"] for s in sizes])
    words = rng.randint(size["min_words"], size["max_words"])
    clients = [c for c in cfg["clients"] if isinstance(cfg["clients"][c], dict)]
    client_roll = weighted_choice(rng, clients, [cfg["clients"][c]["share"] for c in clients])
    client = client or client_roll
    kind = "post_edit" if rng.random() < pe else "standard"
    rush = kind == "standard" and rng.random() < w["rush_share"]
    rate = base_rate(cfg, client, kind) * (w["rush_rate_multiplier"] if rush else 1.0)
    est_hours = words / w["throughput"][kind]
    factor = rng.uniform(o["deadline_factor_min"], o["deadline_factor_max"])
    return Offer(
        id=offer_id, day=day, client=client, kind=kind, rush=rush, words=words, rate=rate,
        deadline_day=deadline_day(cfg, day, est_hours, factor, rush), drop_roll=rng.random(),
    )


def story_offer(cfg, seed):
    s, w = cfg["story_job"], cfg["work"]
    rng = stream(seed, "story_job")
    est_hours = s["words"] / w["throughput"]["standard"]
    factor = rng.uniform(cfg["offers"]["deadline_factor_min"], cfg["offers"]["deadline_factor_max"])
    return Offer(
        id="story", day=s["offer_day"], client=s["client"], kind="standard", rush=False,
        words=s["words"], rate=base_rate(cfg, s["client"], "standard"),
        deadline_day=deadline_day(cfg, s["offer_day"], est_hours, factor, False), story=True,
    )


def generate_stream(cfg, seed):
    """All offers of the run, by day: {day: [Offer, ...]}. Includes the story job."""
    rng = stream(seed, "offers")
    switch_day = rng.randint(cfg["offers"]["pe_switch_day_min"], cfg["offers"]["pe_switch_day_max"])
    direct_mean = cfg["offers"]["per_weekday_mean"] * cfg["clients"]["direct"]["share"]
    by_day = {}
    for day in range(1, cfg["calendar"]["days"] + 1):
        offers = []
        if not cal.is_weekend(day) and day < cfg["calendar"]["no_new_work_from_day"]:
            pe = pe_share(cfg, day, switch_day)
            for i in range(poisson(rng, cfg["offers"]["per_weekday_mean"])):
                offers.append(draw_offer(cfg, rng, f"d{day}o{i}", day, pe))
            # Extra direct-client offers, only visible with the direct-client network effect.
            for i in range(poisson(rng, direct_mean)):
                extra = draw_offer(cfg, rng, f"d{day}x{i}", day, pe, client="direct")
                extra.extra_direct = True
                offers.append(extra)
        by_day[day] = offers
    story = story_offer(cfg, seed)
    by_day.setdefault(story.day, []).insert(0, story)
    return {"by_day": by_day, "pe_switch_day": switch_day}


def offers_for_day(cfg, offer_stream, day, reputation_until, extra_direct_multiplier):
    """The offers the player actually sees today, after reputation and effects."""
    seen = []
    rep = cfg["reputation"]
    for offer in offer_stream["by_day"].get(day, []):
        if offer.extra_direct and extra_direct_multiplier < 2.0 - 1e-9:
            # partial multipliers (sensitivity sweep) keep a matching share of extra offers
            if offer.drop_roll >= max(0.0, extra_direct_multiplier - 1.0):
                continue
        cool = reputation_until.get(offer.client, 0) >= day
        if cool and not offer.story and offer.drop_roll < rep["offer_drop_chance"]:
            continue
        seen.append(offer)
    return seen


def accept(offer, day, reputation_until, cfg, extra_words=0.0):
    cool = reputation_until.get(offer.client, 0) >= day
    mult = cfg["reputation"]["rate_multiplier"] if cool and not offer.story else 1.0
    return Job(offer=offer, accepted_day=day, words_left=offer.words + extra_words, rate_multiplier=mult)


def job_gross(job):
    return job.offer.gross * job.rate_multiplier


def est_hours(cfg, words, kind, efficiency=1.0):
    return words / (cfg["work"]["throughput"][kind] * efficiency)

