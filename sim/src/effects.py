"""Effects, the roguelike layer (SIM_BASELINE.md §8): offers, the pool, and what held effects do.

Rules implemented here:
- An offer is "pick 1 of 3" drawn from the pool without effects already held.
- Shop effects (marked `shop: true`) are only bought, never drawn in offers.
- Within a category, bonuses add and are capped; categories multiply.
- `effects.size_scale` scales every up- and downside (not prices) for the sensitivity sweep.
"""
from .rng import stream

# Parameters that are effect *sizes* and scale with effects.size_scale.
SCALED = {
    "single_bonus", "multi_penalty", "multi_bonus", "single_penalty", "morning_bonus",
    "evening_penalty", "evening_bonus", "interruption_reduction", "bonus",
    "pet_interruption_reduction", "daily_relief", "pet_hour_relief",
}


def pool(cfg):
    return cfg["effects"]["pool"]


def param(cfg, eid, key):
    value = pool(cfg)[eid][key]
    scale = cfg["effects"]["size_scale"]
    if key in SCALED:
        return value * scale
    if key == "direct_offer_multiplier":
        return 1 + (value - 1) * scale
    if key == "book_hour_relief":
        base = -cfg["stress"]["book_hour"]
        return base + (value - base) * scale
    return value


def category(cfg, eid):
    return pool(cfg)[eid]["category"]


def shop_items(cfg):
    return [eid for eid, e in pool(cfg).items() if e.get("shop")]


# --- offers -----------------------------------------------------------------------------------

def eligible(cfg, held, had_evening_with_her):
    out = []
    for eid, e in pool(cfg).items():
        if eid in held or e.get("shop"):
            continue
        if e.get("requires_evening_with_her") and not had_evening_with_her:
            continue
        out.append(eid)
    return out


def draw_weight(cfg, eid, day):
    e = cfg["effects"]
    if day >= e["late_offer_from_day"] and category(cfg, eid) in ("efficiency", "throughput"):
        return e["late_offer_efficiency_weight"]
    return 1.0


def draw_offer(cfg, seed, offer_index, day, held, had_evening_with_her):
    """Up to `offer_size` distinct effect ids, weighted draw without replacement."""
    rng = stream(seed, "effect_offer", offer_index)
    candidates = eligible(cfg, held, had_evening_with_her)
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


# --- what held effects do ---------------------------------------------------------------------

def efficiency_segments(cfg, held, paid_projects, tasks, coworking_today):
    """Raw (uncapped) efficiency bonus for the (morning, midday, evening) parts of the work day."""
    flat = 0.0
    if "deep_focus" in held and paid_projects >= 1:
        flat += param(cfg, "deep_focus", "single_bonus") if paid_projects == 1 else -param(cfg, "deep_focus", "multi_penalty")
    if "context_switcher" in held and tasks >= 1:
        flat += param(cfg, "context_switcher", "multi_bonus") if tasks >= 2 else -param(cfg, "context_switcher", "single_penalty")
    if "coworking" in held and coworking_today:
        flat += param(cfg, "coworking", "bonus")
    morning, midday, evening = flat, flat, flat
    if "morning_person" in held:
        morning += param(cfg, "morning_person", "morning_bonus")
        evening -= param(cfg, "morning_person", "evening_penalty")
    if "night_owl" in held:
        evening += param(cfg, "night_owl", "evening_bonus")
    return morning, midday, evening


def capped(cfg, bonus, cat="efficiency"):
    return min(cfg["effects"]["caps"][cat], bonus)


def throughput_multiplier(cfg, held, kind):
    if "cat_tool" in held and kind in ("standard", "post_edit"):
        return 1 + param(cfg, "cat_tool", "bonus")
    return 1.0


def interruption_factor(cfg, held, coworking_today):
    """Multiplier on the share of work time lost to interruptions."""
    factor = 1.0
    if "headphones" in held:
        factor *= 1 - param(cfg, "headphones", "interruption_reduction")
    if "coworking" in held and coworking_today:
        pet_share = cfg["day"]["pet_interruption_share"]
        factor *= 1 - pet_share * param(cfg, "coworking", "pet_interruption_reduction")
    return max(0.0, factor)


def direct_offer_multiplier(cfg, held):
    return param(cfg, "direct_network", "direct_offer_multiplier") if "direct_network" in held else 1.0


def revision_hours(cfg, held, client):
    if "direct_network" in held and client == "direct":
        return param(cfg, "direct_network", "revision_hours")
    return 0.0


def fast_invoicer(cfg, held):
    if "fast_invoicer" not in held:
        return None
    return {"slow_pay_days": param(cfg, "fast_invoicer", "slow_pay_days"), "fee": param(cfg, "fast_invoicer", "fee")}


def book_relief_per_hour(cfg, held):
    """Stress relief per book hour (positive), capped by the stress-relief multiplier cap."""
    base = -cfg["stress"]["book_hour"]
    if "morning_pages" not in held:
        return base
    cap = base * (1 + cfg["effects"]["caps"]["stress_relief"])
    return min(cap, param(cfg, "morning_pages", "book_hour_relief"))


def daily_stress_relief(cfg, held, pet_hours):
    relief = 0.0
    if "morning_pages" in held:
        relief += param(cfg, "morning_pages", "daily_relief")
    if "walk_routine" in held:
        relief += param(cfg, "walk_routine", "pet_hour_relief") * pet_hours
    return relief


def extra_sleep_cut_stress(cfg, held):
    return param(cfg, "night_owl", "sleep_cut_extra_stress") if "night_owl" in held else 0.0


def daily_time_cost(cfg, held):
    return param(cfg, "morning_pages", "time_hours") if "morning_pages" in held else 0.0


def pet_deficit_weight(cfg, held):
    return param(cfg, "walk_routine", "skipped_walk_deficit_weight") if "walk_routine" in held else 1.0


def weekly_price(cfg, eid):
    return pool(cfg)[eid].get("price_per_week", 0)


def one_off_price(cfg, eid):
    return pool(cfg)[eid].get("price", 0)
