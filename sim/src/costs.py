"""Costs (SIM_BASELINE.md §4): rent, living costs, pet food, vet, transformation bill, random costs."""
from .rng import stream, weighted_choice


def pet_food(cfg, day):
    c = cfg["costs"]
    mult = c["pet_food_growth_multiplier"] if day > c["pet_food_growth_day"] else 1.0
    return c["pet_food_per_day"] * mult


def daily_running_cost(cfg, day, living_saving=0.0):
    """Living costs + pet food: the 'cost of a day' (cash-runway stress, loan-repayment reserve)."""
    return cfg["costs"]["living_per_day"] - living_saving + pet_food(cfg, day)


def scheduled_costs(cfg, day, living_saving=0.0):
    """Known, fixed costs for a day (excluding rent, which lifelines can defer): [(label, $)]."""
    items = [("living", cfg["costs"]["living_per_day"] - living_saving), ("pet food", pet_food(cfg, day))]
    items += [(f["label"], f["amount"]) for f in cfg["costs"]["fixed"] if f["day"] == day]
    return items


def rent_due(cfg, day):
    return cfg["costs"]["rent"] if day in cfg["costs"]["rent_days"] else 0


def tier_probs(cfg, row):
    """A row's tier odds, with the two higher tiers scaled by transformation_odds_scale."""
    scale = cfg["costs"]["transformation_odds_scale"]
    probs = [row["probs"][0]] + [p * scale for p in row["probs"][1:]]
    probs[0] = max(0.0, 1 - sum(probs[1:]))
    return probs


def transformation_bill(cfg, seed, deficit_days):
    c = cfg["costs"]
    rng = stream(seed, "transformation")
    for row in c["transformation_tier_probs"]:
        if deficit_days <= row["max_deficit_days"]:
            return weighted_choice(rng, c["transformation_tiers"], tier_probs(cfg, row))
    return c["transformation_tiers"][-1]


def random_costs(cfg, seed, day, pet_deficit_weight, damage_factor=1.0):
    """Random small costs from events, plus pet damage on care-deficit days. [(label, $)]."""
    c, rng = cfg["costs"], stream(seed, "costs", day)
    items = []
    event_roll, event_amount = rng.random(), rng.uniform(c["random_cost_min"], c["random_cost_max"])
    damage_roll, damage_amount = rng.random(), rng.uniform(c["random_cost_min"], c["random_cost_max"])
    if event_roll < c["random_cost_chance_per_day"]:
        items.append(("random event", event_amount))
    chance = min(1.0, c["pet_damage_chance_per_deficit_day"] * pet_deficit_weight * damage_factor)
    if pet_deficit_weight > 0 and damage_roll < chance:
        items.append(("pet damage", damage_amount))
    return items
