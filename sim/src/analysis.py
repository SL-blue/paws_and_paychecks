"""Turn run results into the numbers the report needs: targets (SIM_BASELINE.md §7.6, §9.3, §10.5,
v0.4), the stress, starting-cash and H searches, effects analysis, sensitivity.

Reading of the targets' wording (listed in the report's Open issues):
"~a-b%" = the range a-b; "0%" = below 0.5% of runs; "~0%" = at most 2%; "~0-5%" = at most 5%.
"""
from collections import Counter
from itertools import combinations

import numpy as np

from .metrics import aggregate

ZERO, NEAR_ZERO = 0.005, 0.02


def band(lo, hi):
    return lambda x: lo - 1e-9 <= x <= hi + 1e-9


def at_most(hi):
    return lambda x: x <= hi + 1e-9


def at_least(lo):
    return lambda x: x >= lo - 1e-9


# (policy, label, metric key, lo, hi): lo/hi give the distance to the target when missed (§9.3, v0.4)
ENDING_TARGETS = [
    ("imperfect_careful", "Finishes book ~40-50%", "book_finished", 0.40, 0.50),
    ("imperfect_careful", "Best ~25-35%", "best", 0.25, 0.35),
    ("imperfect_careful", "Good or better ~70-80%", "good_or_better", 0.70, 0.80),
    ("imperfect_careful", "Parents' ending <= 8%", "parents", 0.0, 0.08),
    ("careful", "Parents' ending <= 2%", "parents", 0.0, NEAR_ZERO),
    ("book_heavy", "Finishes book >= 95%", "book_finished", 0.95, 1.0),
    ("book_heavy", "Best ~45-55%", "best", 0.45, 0.55),
    ("book_heavy", "Good or better = best (good ending <= 2%)", "good", 0.0, NEAR_ZERO),
    ("book_heavy", "Parents' ending or poor finances 15-30%", "parents_or_poor", 0.15, 0.30),
    ("grinder", "Finishes book ~0% (<= 2%)", "book_finished", 0.0, NEAR_ZERO),
    ("grinder", "Best 0%", "best", 0.0, ZERO),
    ("grinder", "Good or better <= 10%", "good_or_better", 0.0, 0.10),
    ("grinder", "Parents' ending <= 5%", "parents", 0.0, 0.05),
    ("careless", "Finishes book ~0-5%", "book_finished", 0.0, 0.05),
    ("careless", "Best ~0% (<= 2%)", "best", 0.0, NEAR_ZERO),
    ("careless", "Good or better <= 10%", "good_or_better", 0.0, 0.10),
    ("careless", "Parents' ending or poor finances >= 60%", "parents_or_poor", 0.60, 1.0),
    ("greedy_optimal", "Best 0%", "best", 0.0, ZERO),
    ("greedy_optimal", "Good or better 0%", "good_or_better", 0.0, ZERO),
]

# §7.6 stress targets: (policy, label, metric key, lo, hi, scale). `scale` turns a miss into the same
# units as a share (stress points / 100), so misses can be summed.
STRESS_TARGETS = [
    ("imperfect_careful", "Average T over the run 25-40", "mean_stress", 25, 40, 100),
    ("imperfect_careful", "Median peak T in days 29-35 55-75", "peak_stress_w5_p50", 55, 75, 100),
    ("imperfect_careful", "Misses the stress goal in 10-15% of runs", "stress_goal_missed", 0.10, 0.15, 1),
    ("careful", "Average T 15-35", "mean_stress", 15, 35, 100),
    ("careful", "Meets the stress goal in >= 95% of runs", "stress_goal_met", 0.95, 1.0, 1),
    ("book_heavy", "Average T 20-40", "mean_stress", 20, 40, 100),
    ("grinder", "L >= 40 on day 42 in >= 80% of runs", "long_end_40", 0.80, 1.0, 1),
    ("grinder", "Fails the stress goal in >= 80% of runs", "stress_goal_missed", 0.80, 1.0, 1),
]


def metric(a, key):
    if key in ("best", "good"):
        return a["tiers"][key]
    if key == "stress_goal_met":
        return 1 - a["stress_goal_missed"]
    return a[key]


def miss(value, lo, hi):
    return max(0.0, lo - value) + max(0.0, value - hi)


def fmt(key, v):
    return f"{v:.1f}" if key in ("mean_stress", "peak_stress_w5_p50") else f"{v:.1%}"


def target_rows(targets, agg_by_policy):
    """[(policy, label, value text, met, distance)] for the policies present."""
    rows = []
    for pol, label, key, lo, hi, *scale in targets:
        if pol not in agg_by_policy:
            continue
        v = metric(agg_by_policy[pol], key)
        d = miss(v, lo, hi) / (scale[0] if scale else 1)
        rows.append((pol, label, fmt(key, v), d <= 1e-9, d))
    return rows


def ending_rows(agg_by_policy):
    return target_rows(ENDING_TARGETS, agg_by_policy)


def stress_rows(agg_by_policy):
    return target_rows(STRESS_TARGETS, agg_by_policy)


FEEDBACK_SHARE = 0.80
MAIN_PLAYER = "imperfect_careful"


def check_targets(agg, eff):
    """All §10.5 rows: (policy, target, value text, met). `eff` = effects_summary()."""
    rows = [r[:4] for r in ending_rows(agg)] + [r[:4] for r in stress_rows(agg)]
    c = agg[MAIN_PLAYER]
    rows.append((MAIN_PLAYER, "Lowest cash in days 28-35 in >= 60% of runs", f"{c['low_day_28_35']:.1%}", c["low_day_28_35"] >= 0.60))
    held = eff["held_mean"]
    rows.append((MAIN_PLAYER, "Holds 7-9 effects at the end", f"{held[MAIN_PLAYER]:.1f}", band(7, 9)(held[MAIN_PLAYER])))
    worst = eff["worst_top_share"]
    rows.append(("effects", "No single offered effect in > 70% of top-decile runs (any policy)",
                 f"highest: {worst[0]} for {worst[1]}, {worst[2]:.0%}", worst[2] <= 0.70))
    cat = eff["cat_pick"]
    rows.append((MAIN_PLAYER, "CAT tool picked 40-60% of the time when offered", f"{cat:.0%}", band(0.40, 0.60)(cat)))
    dead = eff["dead"]
    rows.append(("effects", "No dead effects", ", ".join(dead) if dead else "none", not dead))
    unsold = eff["unsold_shop"]
    rows.append(("effects", "Every shop item bought by a value-based policy in >= 10% of runs",
                 ", ".join(unsold) + " below 10%" if unsold else "all", not unsold))
    rows.append((MAIN_PLAYER, "Effect boost: average +5-12%", f"{c['avg_effect_boost']:+.1%}", band(0.05, 0.12)(c["avg_effect_boost"])))
    rows.append((MAIN_PLAYER, "Effect boost: last 5 workdays +10-20%", f"{c['end_effect_boost']:+.1%}", band(0.10, 0.20)(c["end_effect_boost"])))
    for pol in (MAIN_PLAYER, "book_heavy", "grinder"):
        a = agg[pol]
        rows.append((pol, "Feedback: a job payment in each of weeks 1-6 in >= 80% of runs",
                     f"{a['every_week_paid_job']:.0%}", a["every_week_paid_job"] >= FEEDBACK_SHARE))
    rows.append((MAIN_PLAYER, "Story job accepted in >= 70% of runs (declinable)", f"{c['story_job_taken']:.0%}", c["story_job_taken"] >= 0.70))
    return rows


# --- searches -----------------------------------------------------------------------------------

def score(rows):
    """(targets met, total distance, number of rows)."""
    return sum(1 for r in rows if r[3]), sum(r[4] for r in rows), len(rows)


def stress_score(agg_by_policy):
    return score(stress_rows(agg_by_policy))


def cash_score(agg_by_policy):
    """(ending/low-day targets met, total distance) for the starting-cash search. Book-finish rows
    are left out (H sets them). Higher met wins, then lower distance."""
    rows = [r for r in ending_rows(agg_by_policy) if "book" not in r[1].lower()]
    c = agg_by_policy[MAIN_PLAYER]
    low_miss = max(0.0, 0.60 - c["low_day_28_35"])
    met = sum(1 for r in rows if r[3]) + (low_miss <= 1e-9)
    return met, sum(r[4] for r in rows) + low_miss, len(rows) + 1


def pick_closest(search, score_fn, prefer):
    """search: {value: agg_by_policy}. Smallest total distance to the targets, then most targets met,
    then closest to `prefer` (the current value). Distance first, because the stress targets pull
    against each other (a higher average T vs. fewer stress-goal misses)."""
    return min(search, key=lambda v: (round(score_fn(search[v])[1], 6), -score_fn(search[v])[0], abs(v - prefer), v))


def pick_cash(search):
    """Most targets met, then smallest distance, then lowest cash."""
    return min(search, key=lambda cash: (-cash_score(search[cash])[0], cash_score(search[cash])[1], cash))


def pick_h(search, target=0.45):
    """search: {H: agg_by_policy}. Imperfect careful's book-finish share closest to the target (ties: larger H)."""
    return min(search, key=lambda h: (abs(search[h][MAIN_PLAYER]["book_finished"] - target), -h))


# --- effects analysis -------------------------------------------------------------------------

def top_decile(runs, key="end_value"):
    cut = np.percentile([r[key] for r in runs], 90)
    return [r for r in runs if r[key] >= cut]


def picked_effects(run):
    return sorted({p["pick"] for p in run["picks"] if p["pick"]})


def shares(runs, items_fn):
    counts = Counter(e for r in runs for e in items_fn(r))
    return {e: counts[e] / len(runs) for e in sorted(counts)}


def effects_report(runs, cfg):
    """Per-policy effects numbers. Top-decile shares count only effects picked from offers ("offered
    effects"); shop buys are reported separately, as the share of runs that bought each item."""
    top = top_decile(runs)
    offered, picked, made, skipped = Counter(), Counter(), Counter(), Counter()
    for r in runs:
        for p in r["picks"]:
            offered.update(p["choices"])
            made[p["source"]] += 1
            if p["pick"]:
                picked[p["pick"]] += 1
            else:
                skipped[p["source"]] += 1
    bought = Counter(b["effect"] for r in runs for b in r["shop_buys"])
    sources = Counter()
    for r in runs:
        sources.update(r["offers_by_source"])
    pairs_all, pairs_top = Counter(), Counter()
    for group, counter in ((runs, pairs_all), (top, pairs_top)):
        for r in group:
            counter.update(combinations(sorted(set(r["effects_held"])), 2))
    lift = {pair: (pairs_top[pair] / len(top)) / (pairs_all[pair] / len(runs))
            for pair in pairs_top if pairs_all[pair] / len(runs) >= 0.05}
    synergies = {name: sum(1 for r in runs if all(e in r["effects_held"] for e in s["effects"])) / len(runs)
                 for name, s in cfg["effects"]["synergies"].items()}
    cats = ["efficiency", "throughput", "rate", "stress_relief", "book"]
    return {
        "all_share": shares(runs, lambda r: set(r["effects_held"])),
        "top_share": shares(top, picked_effects),
        "offered": offered, "picked": picked, "bought": bought,
        "buy_rate": {e: bought[e] / len(runs) for e in cfg["effects"]["pool"] if cfg["effects"]["pool"][e].get("shop")},
        "skip_rate": sum(skipped.values()) / max(1, sum(made.values())),
        "skip_by_source": {s: skipped[s] / made[s] for s in made},
        "pick_rate": {e: picked[e] / offered[e] for e in offered},
        "top_pairs": sorted(lift.items(), key=lambda kv: (-kv[1], kv[0]))[:5],
        "sources": {k: v / len(runs) for k, v in sources.items()},
        "held_mean": float(np.mean([r["effects_count"] for r in runs])),
        "pool_exhausted": float(np.mean([r["pool_exhausted"] for r in runs])),
        "synergy_share": synergies,
        "cap_hit_share": {c: sum(1 for r in runs if r["cap_hits"].get(c)) / len(runs) for c in cats},
    }


VALUE_PICKERS = ["imperfect_careful", "careful", "book_heavy", "grinder", "greedy_optimal"]   # careless: random


def effects_summary(matrix_slice, cfg):
    """matrix_slice: {policy: runs}. Cross-policy effect checks for the targets."""
    reports = {p: effects_report(runs, cfg) for p, runs in matrix_slice.items()}
    worst = ("-", "-", 0.0)
    for pol in sorted(reports):
        for e, s in reports[pol]["top_share"].items():
            if s > worst[2]:
                worst = (e, pol, s)
    pool = cfg["effects"]["pool"]
    dead = []
    for e in sorted(pool):
        held_any = any(rep["all_share"].get(e, 0) > 0 for rep in reports.values())
        if not held_any:
            dead.append(e)
        elif not pool[e].get("shop"):
            rates = [reports[p]["pick_rate"].get(e) for p in VALUE_PICKERS if p in reports]
            if rates and all(r is not None and r < 0.10 for r in rates):
                dead.append(e)
    value_based = [p for p in VALUE_PICKERS if p in reports]
    unsold = [e for e in effects_shop(cfg) if max(reports[p]["buy_rate"][e] for p in value_based) < 0.10]
    return {"reports": reports, "worst_top_share": worst, "dead": dead, "unsold_shop": unsold,
            "held_mean": {p: rep["held_mean"] for p, rep in reports.items()},
            "cat_pick": reports[MAIN_PLAYER]["pick_rate"].get("cat_tool", float("nan"))}


def effects_shop(cfg):
    return [e for e, v in cfg["effects"]["pool"].items() if v.get("shop")]


# --- sensitivity ------------------------------------------------------------------------------

SWING_KEYS = ("parents", "best", "good_or_better", "stress_goal_missed")


def swing(base, side):
    return max(abs(metric(side[p], k) - metric(base[p], k)) for p in base for k in SWING_KEYS)


def sensitivity_rank(base, sweep):
    """sweep: {param: {side label: agg_by_policy}}. Rank by the largest change in any policy's
    parents' / best / good-or-better / stress-goal-missed share (percentage points)."""
    rows = [(param, max(swing(base, side) for side in sides.values())) for param, sides in sweep.items()]
    return sorted(rows, key=lambda r: (-r[1], r[0]))


def agg_policies(results_by_policy):
    return {p: aggregate(runs) for p, runs in results_by_policy.items()}
