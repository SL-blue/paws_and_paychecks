"""Turn run results into the numbers the report needs: targets (SIM_BASELINE.md §9.3, §10.5),
the starting-cash and H searches, effects analysis, sensitivity.

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


# (policy, label, metric key, test, lo, hi): lo/hi give the distance to the target when missed
ENDING_TARGETS = [
    ("careful", "Finishes book ~40-50%", "book_finished", 0.40, 0.50),
    ("careful", "Best ~25-35%", "best", 0.25, 0.35),
    ("careful", "Good or better ~70-80%", "good_or_better", 0.70, 0.80),
    ("careful", "Parents' ending <= 8%", "parents", 0.0, 0.08),
    ("book_heavy", "Finishes book ~85-95%", "book_finished", 0.85, 0.95),
    ("book_heavy", "Best ~45-55%", "best", 0.45, 0.55),
    ("book_heavy", "Good or better ~60-70%", "good_or_better", 0.60, 0.70),
    ("book_heavy", "Parents' ending 15-30%", "parents", 0.15, 0.30),
    ("grinder", "Finishes book ~0% (<= 2%)", "book_finished", 0.0, NEAR_ZERO),
    ("grinder", "Best 0%", "best", 0.0, ZERO),
    ("grinder", "Good or better <= 10%", "good_or_better", 0.0, 0.10),
    ("grinder", "Parents' ending <= 5%", "parents", 0.0, 0.05),
    ("careless", "Finishes book ~0-5%", "book_finished", 0.0, 0.05),
    ("careless", "Best ~0% (<= 2%)", "best", 0.0, NEAR_ZERO),
    ("careless", "Good or better <= 10%", "good_or_better", 0.0, 0.10),
    ("careless", "Parents' ending >= 60%", "parents", 0.60, 1.0),
    ("greedy_optimal", "Best 0%", "best", 0.0, ZERO),
    ("greedy_optimal", "Good or better 0%", "good_or_better", 0.0, ZERO),
]


def metric(a, key):
    return a["tiers"]["best"] if key == "best" else a[key]


def miss(value, lo, hi):
    return max(0.0, lo - value) + max(0.0, value - hi)


def ending_rows(agg_by_policy):
    rows = []
    for pol, label, key, lo, hi in ENDING_TARGETS:
        if pol not in agg_by_policy:
            continue
        v = metric(agg_by_policy[pol], key)
        rows.append((pol, label, f"{v:.1%}", miss(v, lo, hi) <= 1e-9, miss(v, lo, hi)))
    return rows


FEEDBACK_SHARE = 0.90


def check_targets(agg, eff):
    """All §10.5 rows: (policy, target, value text, met). `eff` = effects_summary()."""
    rows = [r[:4] for r in ending_rows(agg)]
    c = agg["careful"]
    rows.append(("careful", "Lowest cash in days 28-35 in >= 60% of runs", f"{c['low_day_28_35']:.1%}", c["low_day_28_35"] >= 0.60))
    held = eff["held_mean"]
    rows.append(("careful", "Holds 7-9 effects at the end", f"{held['careful']:.1f}", band(7, 9)(held["careful"])))
    for pol in ("grinder", "careless"):
        rows.append((pol, "Holds 5-6 effects (or its natural count; report)", f"{held[pol]:.1f}", band(5, 6)(held[pol])))
    worst = eff["worst_top_share"]
    rows.append(("effects", "No single offered effect in > 70% of top-decile runs (any policy)",
                 f"highest: {worst[0]} for {worst[1]}, {worst[2]:.0%}", worst[2] <= 0.70))
    cat = eff["cat_pick_careful"]
    rows.append(("careful", "CAT tool picked 40-60% of the time when offered", f"{cat:.0%}", band(0.40, 0.60)(cat)))
    dead = eff["dead"]
    rows.append(("effects", "No dead effects", ", ".join(dead) if dead else "none", not dead))
    rows.append(("careful", "Effect boost: average +10-20%", f"{c['avg_effect_boost']:+.1%}", band(0.10, 0.20)(c["avg_effect_boost"])))
    rows.append(("careful", "Effect boost: last 5 workdays +20-35%", f"{c['end_effect_boost']:+.1%}", band(0.20, 0.35)(c["end_effect_boost"])))
    for pol in ("careful", "book_heavy", "grinder"):
        a = agg[pol]
        rows.append((pol, "Feedback: a job payment in each of weeks 1-6 in >= 90% of runs",
                     f"{a['every_week_paid_job']:.0%}", a["every_week_paid_job"] >= FEEDBACK_SHARE))
    rows.append(("careful", "Story job accepted in >= 70% of runs (declinable)", f"{c['story_job_taken']:.0%}", c["story_job_taken"] >= 0.70))
    return rows


# --- searches -----------------------------------------------------------------------------------

def cash_score(agg_by_policy):
    """(ending/low-day targets met, total distance) for the starting-cash search. Book-finish rows
    are left out (H sets them). Higher met wins, then lower distance."""
    rows = [r for r in ending_rows(agg_by_policy) if "book" not in r[1].lower()]
    c = agg_by_policy["careful"]
    low_miss = max(0.0, 0.60 - c["low_day_28_35"])
    met = sum(1 for r in rows if r[3]) + (low_miss <= 1e-9)
    return met, sum(r[4] for r in rows) + low_miss, len(rows) + 1


def pick_cash(search):
    """search: {cash: agg_by_policy}. Most targets met, then smallest distance, then lowest cash."""
    return min(search, key=lambda cash: (-cash_score(search[cash])[0], cash_score(search[cash])[1], cash))


def pick_h(search, target=0.45):
    """search: {H: agg_by_policy}. Careful's book-finish share closest to the target (ties: larger H)."""
    return min(search, key=lambda h: (abs(search[h]["careful"]["book_finished"] - target), -h))


# --- effects analysis -------------------------------------------------------------------------

def top_decile(runs, key="end_value"):
    cut = np.percentile([r[key] for r in runs], 90)
    return [r for r in runs if r[key] >= cut]


def picked_effects(run):
    return sorted({p["pick"] for p in run["picks"]})


def shares(runs, items_fn):
    counts = Counter(e for r in runs for e in items_fn(r))
    return {e: counts[e] / len(runs) for e in sorted(counts)}


def effects_report(runs, cfg):
    """Per-policy effects numbers. Top-decile shares count only effects picked from offers;
    shop buys follow fixed policy rules and are reported separately."""
    top = top_decile(runs)
    offered, picked = Counter(), Counter()
    for r in runs:
        for p in r["picks"]:
            offered.update(p["choices"])
            picked[p["pick"]] += 1
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
        "pick_rate": {e: picked[e] / offered[e] for e in offered},
        "top_pairs": sorted(lift.items(), key=lambda kv: (-kv[1], kv[0]))[:5],
        "sources": {k: v / len(runs) for k, v in sources.items()},
        "held_mean": float(np.mean([r["effects_count"] for r in runs])),
        "pool_exhausted": float(np.mean([r["pool_exhausted"] for r in runs])),
        "synergy_share": synergies,
        "cap_hit_share": {c: sum(1 for r in runs if r["cap_hits"].get(c)) / len(runs) for c in cats},
    }


VALUE_PICKERS = ["careful", "book_heavy", "grinder", "greedy_optimal"]   # careless picks at random


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
    return {"reports": reports, "worst_top_share": worst, "dead": dead,
            "held_mean": {p: rep["held_mean"] for p, rep in reports.items()},
            "cat_pick_careful": reports["careful"]["pick_rate"].get("cat_tool", float("nan"))}


# --- sensitivity ------------------------------------------------------------------------------

SWING_KEYS = ("parents", "best", "good_or_better")


def swing(base, side):
    return max(abs(metric(side[p], k) - metric(base[p], k)) for p in base for k in SWING_KEYS)


def sensitivity_rank(base, sweep):
    """sweep: {param: {side label: agg_by_policy}}. Rank by the largest change in any policy's
    parents' / best / good-or-better share (percentage points)."""
    rows = [(param, max(swing(base, side) for side in sides.values())) for param, sides in sweep.items()]
    return sorted(rows, key=lambda r: (-r[1], r[0]))


def agg_policies(results_by_policy):
    return {p: aggregate(runs) for p, runs in results_by_policy.items()}
