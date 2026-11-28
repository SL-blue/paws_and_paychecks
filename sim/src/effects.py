"""Effects, the roguelike layer (SIM_BASELINE.md §8, v0.3): offers, the pool, caps, synergies,
and what held effects do. The engine asks this module small questions ("what is the efficiency
bonus of this work segment?"); every number comes from `effects.pool` in data/economy.yaml.

Rules:
- An offer is "pick 1 of 3" from the offerable pool, without effects already held. Shop effects
  are only bought. From `late_offer_from_day`, efficiency/throughput effects get a lower weight.
- Within a category, bonuses add up to the category cap; categories multiply with each other.
- Designed synergies apply when both effects are held and may go above the caps.
- `effects.size_scale` scales every up- and downside (not prices, time costs, hours or days).
"""
from . import game_calendar as cal
from .rng import stream

# Parameter keys that are effect sizes: value x scale.
LINEAR = {
    "single_bonus", "multi_penalty", "multi_bonus", "single_penalty", "morning_bonus", "morning_penalty",
    "evening_bonus", "evening_penalty", "short_day_bonus", "bonus", "interruption_reduction",
    "pet_interruption_reduction", "pe_bonus", "standard_efficiency_penalty", "book_penalty",
    "standard_rate_bonus", "random_offer_drop", "rush_extra_stress", "regular_rate_penalty",
    "deposit_share", "large_offer_drop", "saturday_income", "living_saving", "daily_relief", "nap_relief",
    "pet_hour_relief", "book_relief_extra", "overlap_speed_penalty", "care_reduction", "book_bonus",
    "week_book_bonus", "single_project_efficiency",
}
# Multipliers: 1 + (value - 1) x scale.
MULTIPLIER = {"direct_offer_multiplier", "rush_offer_multiplier", "regular_job_multiplier",
              "leisure_relief_multiplier", "session_relief_multiplier"}
# Reductions given as a factor below 1: 1 - (1 - value) x scale.
FACTOR = {"late_factor", "damage_factor"}


def pool(cfg):
    return cfg["effects"]["pool"]


def param(cfg, eid, key):
    value, scale = pool(cfg)[eid][key], cfg["effects"]["size_scale"]
    if key in LINEAR:
        return value * scale
    if key in MULTIPLIER:
        return 1 + (value - 1) * scale
    if key in FACTOR:
        return 1 - (1 - value) * scale
    if key == "rush_rate_multiplier":
        base = cfg["work"]["rush_rate_multiplier"]
        return base + (value - base) * scale
    if key == "book_hour_relief":
        base = -cfg["stress"]["book_hour"]
        return base + (value - base) * scale
    return value


def category(cfg, eid):
    return pool(cfg)[eid]["category"]


def shop_items(cfg):
    return [eid for eid, e in pool(cfg).items() if e.get("shop")]


def offerable(cfg):
    return [eid for eid, e in pool(cfg).items() if not e.get("shop")]


def cap(cfg, cat):
    return cfg["effects"]["caps"][cat]


def synergy(cfg, held, name):
    """The synergy's config if both of its effects are held, else None."""
    s = cfg["effects"]["synergies"][name]
    return s if all(e in held for e in s["effects"]) else None


def synergy_param(cfg, name, key):
    return cfg["effects"]["synergies"][name][key] * (cfg["effects"]["size_scale"] if key == "single_project_efficiency" else 1)


def active_synergies(cfg, held):
    return [name for name in cfg["effects"]["synergies"] if synergy(cfg, held, name)]


# --- offers -----------------------------------------------------------------------------------

def draw_weight(cfg, eid, day):
    e = cfg["effects"]
    if day >= e["late_offer_from_day"] and category(cfg, eid) in ("efficiency", "throughput"):
        return e["late_offer_efficiency_weight"]
    return 1.0


def draw_offer(cfg, seed, offer_index, day, held):
    """Up to `offer_size` distinct effect ids, weighted draw without replacement."""
    rng = stream(seed, "effect_offer", offer_index)
    candidates = [eid for eid in offerable(cfg) if eid not in held]
    choices = []
    while candidates and len(choices) < cfg["effects"]["offer_size"]:
        weights = [draw_weight(cfg, eid, day) for eid in candidates]
        pick = rng.random() * sum(weights)
        for eid, weight in zip(candidates, weights):
            pick -= weight
            if pick < 0:
                break
        choices.append(eid)
        candidates.remove(eid)
    return choices


# --- work: efficiency, throughput, rate --------------------------------------------------------

def segment_efficiency(cfg, held, part, ctx):
    """Raw (uncapped) efficiency bonus of paid work in one part of the work day.
    part: 0 = first `morning_work_hours`, 1 = middle, 2 = beyond `evening_after_hours`.
    ctx: dict with paid_projects, tasks, paid_hours, coworking, planning_active."""
    p = lambda eid, key: param(cfg, eid, key)  # noqa: E731
    bonus = 0.0
    if "deep_focus" in held and ctx["paid_projects"] >= 1:
        bonus += p("deep_focus", "single_bonus") if ctx["paid_projects"] == 1 else -p("deep_focus", "multi_penalty")
    if "context_switcher" in held and ctx["tasks"] >= 1:
        bonus += p("context_switcher", "multi_bonus") if ctx["tasks"] >= 2 else -p("context_switcher", "single_penalty")
    if "coworking" in held and ctx["coworking"]:
        bonus += p("coworking", "bonus")
    if "sunday_planning" in held and ctx["planning_active"]:
        bonus += p("sunday_planning", "bonus")
    if "pomodoro" in held:
        if ctx["paid_hours"] <= p("pomodoro", "short_day_max_hours") + 1e-9:
            bonus += p("pomodoro", "short_day_bonus")
        elif part == 2:
            bonus -= p("pomodoro", "evening_penalty")
    if "morning_person" in held:
        bonus += p("morning_person", "morning_bonus") if part == 0 else (-p("morning_person", "evening_penalty") if part == 2 else 0)
    if "night_owl" in held:
        bonus += p("night_owl", "evening_bonus") if part == 2 else (-p("night_owl", "morning_penalty") if part == 0 else 0)
    return bonus


def job_efficiency(cfg, held, raw_segment, kind, ctx):
    """Capped efficiency bonus for a job kind in a segment, plus the quiet-house synergy.
    Returns (bonus, cap_hit)."""
    raw = raw_segment
    if "pe_veteran" in held and kind == "standard":
        raw -= param(cfg, "pe_veteran", "standard_efficiency_penalty")
    bonus = min(cap(cfg, "efficiency"), raw)
    if synergy(cfg, held, "quiet_house") and ctx["paid_projects"] == 1:
        bonus += synergy_param(cfg, "quiet_house", "single_project_efficiency")
    return bonus, raw > cap(cfg, "efficiency") + 1e-9


def throughput_bonus(cfg, held, offer):
    """Capped throughput bonus for a job. Returns (bonus, cap_hit)."""
    raw = 0.0
    if "cat_tool" in held:
        raw += param(cfg, "cat_tool", "bonus")
    if "second_monitor" in held and offer.kind == "standard":
        raw += param(cfg, "second_monitor", "bonus")
    if "termbase" in held and offer.regular:
        raw += param(cfg, "termbase", "bonus")
    if "pe_veteran" in held and offer.kind == "post_edit":
        raw += param(cfg, "pe_veteran", "pe_bonus")
    return min(cap(cfg, "throughput"), raw), raw > cap(cfg, "throughput") + 1e-9


def throughput_multiplier(cfg, held, offer):
    return 1 + throughput_bonus(cfg, held, offer)[0]


def rate_bonus_raw(cfg, held, offer):
    raw = 0.0
    if "specialist_niche" in held and offer.kind == "standard":
        raw += param(cfg, "specialist_niche", "standard_rate_bonus")
    if "loyal_client" in held and offer.regular:
        raw -= param(cfg, "loyal_client", "regular_rate_penalty")
    if "rush_specialist" in held and offer.rush:
        raw += param(cfg, "rush_specialist", "rush_rate_multiplier") / cfg["work"]["rush_rate_multiplier"] - 1
    return raw


def rate_bonus(cfg, held, offer):
    """Capped rate bonus applied to a job's pay at acceptance (fixed jobs included)."""
    return min(cap(cfg, "rate"), rate_bonus_raw(cfg, held, offer))


def extra_offer_share(cfg, eid):
    """Share of the pre-generated extra offers that an effect makes visible (1.0 at full size)."""
    key = {"direct_network": "direct_offer_multiplier", "rush_specialist": "rush_offer_multiplier",
           "loyal_client": "regular_job_multiplier"}[eid]
    return max(0.0, param(cfg, eid, key) - 1.0)


def extra_job_hours(cfg, st, offer):
    """Unpaid hours added to a job: direct-network revisions, and a new termbase's first job per regular client."""
    hours = 0.0
    if "direct_network" in st.held and offer.client == "direct":
        hours += param(cfg, "direct_network", "revision_hours")
    if "termbase" in st.held and offer.regular and offer.regular not in st.termbase_clients:
        hours += param(cfg, "termbase", "first_job_extra_hours")
    return hours


def interruption_factor(cfg, held, coworking_today):
    """Multiplier on the share of work time (paid and book) lost to interruptions."""
    factor = 1.0
    if "headphones" in held:
        factor *= 1 - param(cfg, "headphones", "interruption_reduction")
    if "coworking" in held and coworking_today:
        factor *= 1 - cfg["day"]["pet_interruption_share"] * param(cfg, "coworking", "pet_interruption_reduction")
    return max(0.0, factor)


def max_paid_hours(cfg, held):
    return param(cfg, "boundaries", "max_paid_hours") if "boundaries" in held else None


# --- the book ---------------------------------------------------------------------------------

def book_speed_bonus(cfg, held, ctx):
    """Capped book-speed bonus for book hours today (only effects marked book_speed).
    ctx: paid_projects, writing_week (a writing-group session this week). Returns (bonus, cap_hit)."""
    raw = 0.0
    if "deep_focus" in held and ctx["paid_projects"] >= 1:
        raw += param(cfg, "deep_focus", "single_bonus") if ctx["paid_projects"] == 1 else -param(cfg, "deep_focus", "multi_penalty")
    if "pe_veteran" in held:
        raw -= param(cfg, "pe_veteran", "book_penalty")
    if "margin_notes" in held:
        raw += param(cfg, "margin_notes", "book_bonus")
    if "writing_group" in held and ctx["writing_week"]:
        raw += param(cfg, "writing_group", "week_book_bonus")
    return min(cap(cfg, "book"), raw), raw > cap(cfg, "book") + 1e-9


def reading_aloud_hours(cfg, held, book_hours):
    """Book hours that also count as pet care (reading aloud; more with the first-audience synergy)."""
    if "reading_aloud" not in held:
        return 0.0
    limit = synergy_param(cfg, "first_audience", "pet_overlap_hours") if synergy(cfg, held, "first_audience") \
        else param(cfg, "reading_aloud", "overlap_hours")
    return min(limit, book_hours)


def reading_aloud_speed(cfg, held):
    return 1 - param(cfg, "reading_aloud", "overlap_speed_penalty") if "reading_aloud" in held else 1.0


# --- stress -----------------------------------------------------------------------------------

def relief_capped(cfg, base, value):
    """Clamp a relief rate to base x (1 + stress_relief cap)."""
    return min(value, base * (1 + cap(cfg, "stress_relief")))


def book_relief_per_hour(cfg, held, session=False):
    """Stress relief per book hour (positive number), with the stress-relief cap."""
    base = -cfg["stress"]["book_hour"]
    value = base
    if "morning_pages" in held:
        value += param(cfg, "morning_pages", "book_hour_relief") - base
    if "margin_notes" in held:
        value += param(cfg, "margin_notes", "book_hour_relief") - base
    if "reading_aloud" in held:
        value += param(cfg, "reading_aloud", "book_relief_extra")
    if session:
        value *= param(cfg, "writing_group", "session_relief_multiplier")
    return relief_capped(cfg, base, value), value > base * (1 + cap(cfg, "stress_relief")) + 1e-9


def leisure_multiplier(cfg, held):
    if "boundaries" not in held:
        return 1.0
    return min(1 + cap(cfg, "stress_relief"), param(cfg, "boundaries", "leisure_relief_multiplier"))


def work_hour_over(cfg, held):
    return param(cfg, "standing_desk", "work_hour_over") if "standing_desk" in held else cfg["stress"]["work_hour_over"]


def daily_relief(cfg, held, pet_hours, napped):
    """Extra stress relief today from effects (positive = less stress)."""
    relief = 0.0
    for eid in ("morning_pages", "boundaries"):
        if eid in held:
            relief += param(cfg, eid, "daily_relief")
    if "walk_routine" in held:
        relief += param(cfg, "walk_routine", "pet_hour_relief") * pet_hours
    if napped:
        relief += param(cfg, "nap_habit", "nap_relief")
    return relief


def rush_extra_stress(cfg, held):
    return param(cfg, "rush_specialist", "rush_extra_stress") if "rush_specialist" in held else 0.0


def nap_today(cfg, held, stress_level):
    return "nap_habit" in held and stress_level > param(cfg, "nap_habit", "stress_above")


# --- time costs, her, pet -----------------------------------------------------------------------

def time_costs(cfg, held, day, napped):
    """(hours taken from the day by effects, of which hours that count as paid work for stress)."""
    wd, hours, paid_like = cal.weekday(day), 0.0, 0.0
    for eid in ("frugal_cooking", "morning_pages"):
        if eid in held:
            hours += param(cfg, eid, "time_daily")
    if "sunday_planning" in held and wd == 7:
        hours += param(cfg, "sunday_planning", "time_sunday")
    if "fast_invoicer" in held and wd == 1:
        hours += param(cfg, "fast_invoicer", "time_monday")
    if "side_class" in held and wd == 6:
        hours += param(cfg, "side_class", "time_saturday")
        paid_like += param(cfg, "side_class", "time_saturday")
    if "puppy_class" in held and wd == 6 and cal.week_of(day) in param(cfg, "puppy_class", "saturday_weeks"):
        hours += param(cfg, "puppy_class", "time_saturday")
    if napped:
        hours += param(cfg, "nap_habit", "time_nap")
    return hours, paid_like


def crunch_evenings(cfg, held):
    return param(cfg, "shared_calendar", "crunch_evenings") if "shared_calendar" in held else cfg["her"]["crunch_evenings"]


def half_day_hours(cfg, held):
    return param(cfg, "sunday_brunch", "half_day_hours") if "sunday_brunch" in held else cfg["her"]["half_day_hours"]


def quiet_company_hours(cfg, held, book_hours, her_hours):
    if "quiet_company" not in held or her_hours < cfg["her"]["evening_hours"] - 1e-9:
        return 0.0
    return min(param(cfg, "quiet_company", "overlap_hours"), book_hours, her_hours)


def evening_walk_hours(cfg, held, pet_hours, her_hours_free):
    if "evening_walks" not in held or her_hours_free <= 0:
        return 0.0
    return min(param(cfg, "evening_walks", "overlap_hours"), pet_hours, her_hours_free)


def pet_need_change(cfg, held, day, coworking_today):
    """Hours added to (or, if negative, removed from) the daily pet-care need."""
    change = 0.0
    if "coworking" in held and coworking_today:
        change += param(cfg, "coworking", "extra_pet_care_hours")
    if "evening_walks" in held:
        change += param(cfg, "evening_walks", "extra_pet_care_hours")
    if "puppy_class" in held and day >= param(cfg, "puppy_class", "from_day"):
        change -= param(cfg, "puppy_class", "care_reduction")
    return change


def pet_deficit_weight(cfg, held):
    return param(cfg, "walk_routine", "skipped_walk_deficit_weight") if "walk_routine" in held else 1.0


def damage_factor(cfg, held):
    return param(cfg, "sturdy_toys", "damage_factor") if "sturdy_toys" in held else 1.0


# --- money ------------------------------------------------------------------------------------

def pay_terms(cfg, held):
    """Payment-term changes from effects, for payments.make_invoice."""
    return {
        "slow_pay_days": param(cfg, "fast_invoicer", "slow_pay_days") if "fast_invoicer" in held else None,
        "late_factor": param(cfg, "invoice_reminders", "late_factor") if "invoice_reminders" in held else 1.0,
        "regular_faster": synergy_param(cfg, "steady_hands", "regular_pay_days_faster") if synergy(cfg, held, "steady_hands") else 0,
    }


def regular_penalty_days(cfg, held):
    if "invoice_reminders" in held:
        return param(cfg, "invoice_reminders", "regular_penalty_days")
    return cfg["reputation"]["regular_penalty_days"]


def deposit_share(cfg, held, offer):
    if "deposit_terms" in held and offer.size == "large":
        return param(cfg, "deposit_terms", "deposit_share")
    return 0.0


def living_saving(cfg, held):
    return param(cfg, "frugal_cooking", "living_saving") if "frugal_cooking" in held else 0.0


def saturday_income(cfg, held, day):
    return param(cfg, "side_class", "saturday_income") if "side_class" in held and cal.weekday(day) == 6 else 0.0


def weekly_price(cfg, eid):
    return pool(cfg)[eid].get("price_per_week", 0)


def one_off_price(cfg, eid):
    return pool(cfg)[eid].get("price", 0)


def per_use_price(cfg, eid):
    return pool(cfg)[eid].get("price_per_use", 0)
