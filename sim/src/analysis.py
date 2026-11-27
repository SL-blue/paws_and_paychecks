"""Turn run results into the numbers the report needs: targets, effects analysis, sensitivity."""
from collections import Counter
from itertools import combinations

import numpy as np

from .metrics import aggregate

# --- acceptance targets (SIM_BASELINE.md §9.5), evaluated with effects --------------------------

TARGETS = [
    ("careful", "Bankrupt <= 8%", lambda a: a["bankrupt"] <= 0.08, lambda a: f"{a['bankrupt']:.1%}"),
    ("careful", "Lowest cash in days 28-35 in >= 60% of runs", lambda a: a["low_day_28_35"] >= 0.60, lambda a: f"{a['low_day_28_35']:.1%}"),
    ("careful", "Book finished >= 30%", lambda a: a["book_finished"] >= 0.30, lambda a: f"{a['book_finished']:.1%}"),
    ("book_heavy", "Bankrupt 15-30%", lambda a: 0.15 <= a["bankrupt"] <= 0.30, lambda a: f"{a['bankrupt']:.1%}"),
    ("book_heavy", "Book finished >= 70%", lambda a: a["book_finished"] >= 0.70, lambda a: f"{a['book_finished']:.1%}"),
    ("grinder", "Bankrupt <= 5%", lambda a: a["bankrupt"] <= 0.05, lambda a: f"{a['bankrupt']:.1%}"),
    ("grinder", "Stress > 70 on >= 40% of days in weeks 4-5", lambda a: a["high_stress_share_w45"] >= 0.40, lambda a: f"{a['high_stress_share_w45']:.1%} of days (mean)"),
    ("grinder", "Relationship needs missed >= 2 weeks", lambda a: a["rel_weeks_missed"] >= 2, lambda a: f"{a['rel_weeks_missed']:.1f} weeks (mean)"),
    ("careless", "Bankrupt >= 60%", lambda a: a["bankrupt"] >= 0.60, lambda a: f"{a['bankrupt']:.1%}"),
    ("greedy_optimal", "Does not dominate the combined ending", lambda a: a["good_ending"] <= 0.10, lambda a: f"good combined ending in {a['good_ending']:.1%} of runs"),
]

FEEDBACK_SHARE = 0.90   # "every policy that works receives a payment each week": in >= 90% of runs


def check_targets(agg_by_policy, effects_top_share, cap_hit_share):
    """Rows of (policy, target, value text, met)."""
    rows = [(p, name, show(agg_by_policy[p]), ok(agg_by_policy[p])) for p, name, ok, show in TARGETS]
    worst = max(sorted(effects_top_share.items()), key=lambda kv: kv[1][1])   # ties: first by name
    rows.append(("effects", "No single effect in > 70% of top-decile runs",
                 f"highest: {worst[0]} ({worst[1][0]}) {worst[1][1]:.0%}", worst[1][1] <= 0.70))
    rows.append(("effects", "No combo exceeds caps (no designed synergies exist yet)",
                 f"caps enforced by clamping; the efficiency cap was reached in {cap_hit_share:.1%} of runs", True))
    for p, a in agg_by_policy.items():
        rows.append((p, "Feedback: a job payment in each of weeks 1-6 (>= 90% of runs)",
                     f"{a['every_week_paid_job']:.0%} (incl. pre-move invoices: {a['every_week_paid_all']:.0%})",
                     a["every_week_paid_job"] >= FEEDBACK_SHARE))
    return rows


# --- starting-cash search ---------------------------------------------------------------------

def cash_score(agg_by_policy):
    """(targets met, distance) for the cash-sensitive targets. Higher met, lower distance wins."""
    c, b, g, x = (agg_by_policy[k] for k in ("careful", "book_heavy", "grinder", "careless"))
    misses = [
        max(0.0, c["bankrupt"] - 0.08),
        max(0.0, 0.60 - c["low_day_28_35"]),
        max(0.0, 0.15 - b["bankrupt"]) + max(0.0, b["bankrupt"] - 0.30),
        max(0.0, g["bankrupt"] - 0.05),
        max(0.0, 0.60 - x["bankrupt"]),
    ]
    met = sum(1 for m in misses if m <= 1e-12)
    # tie-break: book-heavy bankruptcy near the middle of its band
    return met, sum(misses), abs(b["bankrupt"] - 0.225)


def pick_cash(search):
    """search: {cash: agg_by_policy}. Returns the best cash value."""
    return min(search, key=lambda cash: (-cash_score(search[cash])[0], cash_score(search[cash])[1], cash_score(search[cash])[2]))


# --- effects analysis -------------------------------------------------------------------------

def top_decile(runs, key="end_value"):
    cut = np.percentile([r[key] for r in runs], 90)
    return [r for r in runs if r[key] >= cut]


def effect_shares(runs):
    n = len(runs)
    counts = Counter(e for r in runs for e in sorted(set(r["effects_held"])))
    return {e: counts[e] / n for e in sorted(counts)}


def effects_report(runs):
    top = top_decile(runs)
    all_share, top_share = effect_shares(runs), effect_shares(top)
    offered, picked = Counter(), Counter()
    for r in runs:
        for p in r["picks"]:
            offered.update(p["choices"])
            picked[p["pick"]] += 1
    bought = Counter(b["effect"] for r in runs for b in r["shop_buys"])
    pairs_all, pairs_top = Counter(), Counter()
    for group, counter in ((runs, pairs_all), (top, pairs_top)):
        for r in group:
            counter.update(combinations(sorted(set(r["effects_held"])), 2))
    lift = {pair: (pairs_top[pair] / len(top)) / (pairs_all[pair] / len(runs))
            for pair in pairs_top if pairs_all[pair] / len(runs) >= 0.05}
    sources = Counter()
    for r in runs:
        sources.update(r["offers_by_source"])
    return {
        "all_share": all_share, "top_share": top_share,
        "offered": offered, "picked": picked, "bought": bought,
        "pick_rate": {e: picked[e] / offered[e] for e in offered},
        "top_pairs": sorted(lift.items(), key=lambda kv: -kv[1])[:5],
        "sources": {k: v / len(runs) for k, v in sources.items()},
        "held_mean": float(np.mean([r["effects_count"] for r in runs])),
        "held_dist": Counter(r["effects_count"] for r in runs),
        "pool_exhausted": float(np.mean([r["pool_exhausted"] for r in runs])),
        "cap_hit_runs": sum(1 for r in runs if r["cap_hits"]) / len(runs),
    }


# --- sensitivity ------------------------------------------------------------------------------

SENS_METRICS = [
    ("careful", "bankrupt"), ("book_heavy", "bankrupt"), ("grinder", "bankrupt"), ("careless", "bankrupt"),
    ("careful", "low_day_28_35"), ("careful", "book_finished"), ("careful", "end_value_p50"),
    ("grinder", "high_stress_share_w45"),
]


def sensitivity_rank(base, sweep):
    """sweep: {param: {"-25%": agg_by_policy, "+25%": agg_by_policy}}.
    Rank params by the largest bankruptcy-rate swing across policies (percentage points)."""
    rows = []
    for param, sides in sweep.items():
        swing = max(abs(sides[s][p]["bankrupt"] - base[p]["bankrupt"]) for s in sides
                    for p in ("careful", "book_heavy", "grinder", "careless"))
        value_swing = max(abs(sides[s]["careful"]["end_value_p50"] - base["careful"]["end_value_p50"]) for s in sides)
        rows.append((param, swing, value_swing))
    return sorted(rows, key=lambda r: -r[1])


def agg_policies(results_by_policy):
    return {p: aggregate(runs) for p, runs in results_by_policy.items()}
