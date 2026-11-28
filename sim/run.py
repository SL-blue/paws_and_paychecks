"""Run the economy simulation (SIM_BASELINE.md §10, v0.4) and write the report.

    python -m sim.run --all          # everything: searches, matrix, sensitivity, recommended overlay, report
    python -m sim.run --report       # rebuild the report from saved results only
    python -m sim.run --recommended  # re-run only the recommended overlay on saved results, then report
    python -m sim.run --all --seeds 200   # quicker, smaller run (not the committed report)

Tuning order (§10.3):
 1. stress parameters (§7.6): a coordinate search over STRESS_SEARCH, in the spec's suggested
    order, with the four stress-target policies, at the provisional starting cash;
 2. starting cash, 800-2,400 in steps of 100 (§9.3 rows except book-finish);
 3. H for imperfect careful's book target;
 4. re-check starting cash once;
 5. CAT price (imperfect careful picks it 40-60% of the time when offered).
The searches, the CAT check and the sensitivity sweep run the five player policies only;
greedy-optimal (a 12-plan search per seed, ~12x the cost) runs in the main matrix and the
recommended re-run.
"""
import argparse
import pickle
import time

from sim.src import analysis, experiments
from sim.src.config import ROOT, deep_merge, get_path, load_economy, load_policies, load_yaml, with_overrides

REPORTS = ROOT / "sim" / "reports"
RAW = REPORTS / "raw"
RECOMMENDED_PATH = ROOT / "data" / "economy.recommended.yaml"

PROVISIONAL_CASH = 1200      # stress search only: the round-2 probe's cash (SIM_BASELINE.md §5), before step 2
STRESS_SEEDS = 600           # seeds per point of the stress search (it has ~70 points per pass)
STRESS_PASSES = 2
# (dotted path, candidate values), in the spec's suggested order (§7.6): sleep recovery shares,
# conversion threshold and rate, L load sizes, L relief sizes; then the starting levels (§5, "tune").
STRESS_SEARCH = [
    ("stress.short.sleep_recovery_full", [0.15, 0.2, 0.25, 0.3, 0.4, 0.5]),
    ("stress.short.sleep_recovery_short", [0.05, 0.1, 0.15, 0.2, 0.25]),
    ("stress.conversion.threshold", [40, 45, 50, 55, 60, 70]),
    ("stress.conversion.share", [0.1, 0.25, 0.4, 0.5]),
    ("stress.long.runway_low", [0.5, 1, 1.5, 2, 3]),
    ("stress.long.runway_very_low", [1, 2, 3, 4, 6]),
    ("stress.long.rent_due", [1, 2, 3, 4, 6]),
    ("stress.long.her_crunch_day", [0.5, 1, 1.5, 2, 2.5, 3, 4]),
    ("stress.long.payment_arrives", [-0.5, -1, -1.5, -2, -3]),
    ("stress.long.book_milestone", [-2, -4, -6, -8, -10]),
    ("stress.long.her_good_week", [-1, -2, -3, -4]),
    ("stress.long.calm_day", [0, -0.25, -0.5, -0.75, -1]),
    ("start.stress_long", [5, 10, 15, 20, 25, 30]),
]

CASH_VALUES = list(range(800, 2401, 100))
H_VALUES = [50 + 2.5 * i for i in range(13)]          # 50 ... 80 hours
CAT_PRICES = list(range(30, 101, 5))
CAT_TARGET = (0.40, 0.60)

PLUS_MINUS = (("-25%", 0.75), ("+25%", 1.25))
SUSTAINED = (("2 days", 2 / 3), ("4 days", 4 / 3))
SENSITIVITY = {   # label: (dotted config paths scaled together, sides)
    # new in v0.4
    "S sleep-recovery shares": (["stress.short.sleep_recovery_full", "stress.short.sleep_recovery_short"], PLUS_MINUS),
    "conversion threshold": (["stress.conversion.threshold"], PLUS_MINUS),
    "conversion rate": (["stress.conversion.share"], PLUS_MINUS),
    "sustained-S days": (["stress.conversion.sustained_days"], SUSTAINED),
    "L load: runway": (["stress.long.runway_low", "stress.long.runway_very_low"], PLUS_MINUS),
    "L load: rent": (["stress.long.rent_due"], PLUS_MINUS),
    "L load: her crunch": (["stress.long.her_crunch_day"], PLUS_MINUS),
    "L load: loan": (["stress.long.loan_open"], PLUS_MINUS),
    "L relief: payment": (["stress.long.payment_arrives"], PLUS_MINUS),
    "L relief: book milestone": (["stress.long.book_milestone"], PLUS_MINUS),
    "L relief: good week": (["stress.long.her_good_week"], PLUS_MINUS),
    "finance-good bar": (["endings.finance_good_min_value"], PLUS_MINUS),
    "loan cap": (["lifelines.borrow_max"], PLUS_MINUS),
    "skip reward": (["effects.skip_long_relief"], PLUS_MINUS),
    # kept from round 2
    "starting cash": (["start.cash"], PLUS_MINUS),
    "rent": (["costs.rent"], PLUS_MINUS),
    "random offer rate": (["offers.per_weekday_mean"], PLUS_MINUS),
    "regular-client job rate": (["regular_clients.prob_scale"], PLUS_MINUS),
    "regular-client rate bonus": (["regular_clients.rate_bonus_scale"], PLUS_MINUS),
    "regular-client payment days": (["regular_clients.pay_days_scale"], PLUS_MINUS),
    "PE share": (["offers.pe_share_start", "offers.pe_share_end"], PLUS_MINUS),
    "payment delays (client types)": ([f"clients.{c}.{k}" for c in ("direct", "standard_agency", "slow_agency")
                                       for k in ("pay_days_min", "pay_days_max")], PLUS_MINUS),
    "late-payment share": (["clients.late_share"], PLUS_MINUS),
    "story job size": (["story_job.words"], PLUS_MINUS),
    "effect sizes": (["effects.size_scale"], PLUS_MINUS),
    "book remaining hours H": (["book.remaining_hours"], PLUS_MINUS),
    "leisure cap": (["day.leisure_hours_cap"], PLUS_MINUS),
    "loan repayment window": (["lifelines.loan_repay_days"], (("5 days", 5 / 7), ("9 days", 9 / 7))),
    "parents'-ending cash floor": (["lifelines.parents_floor"], PLUS_MINUS),
    "transformation-bill odds": (["costs.transformation_odds_scale"], PLUS_MINUS),
}
REFERENCE_ROWS = {"NET factor (fixed; reference only)": (["work.net_factor"], PLUS_MINUS)}


def log(msg, t0):
    print(f"[{time.time() - t0:6.0f}s] {msg}", flush=True)


def by_policy(cfg, pcfg, seeds, names=experiments.PLAYER_POLICIES):
    return {p: experiments.run_batch(cfg, pcfg, p, seeds, keep=False) for p in names}


def main_variant(cfg):
    """The variant the targets are checked on: with effects, story job declinable."""
    return experiments.variant_cfg(cfg, True, False)


def agg_at(cfg, pcfg, seeds, overrides, names=experiments.PLAYER_POLICIES):
    return analysis.agg_policies(by_policy(main_variant(with_overrides(cfg, overrides)), pcfg, seeds, names))


def stress_search(base_cfg, pcfg, seeds, t0):
    """Coordinate search over STRESS_SEARCH (§10.3 step 1), scored on the §7.6 targets.
    Returns (tuned cfg, [{"pass", "path", "points": {value: agg}, "chosen"}])."""
    names = experiments.STRESS_POLICIES
    cfg = with_overrides(base_cfg, {"start.cash": PROVISIONAL_CASH})
    steps = []
    for n in range(1, STRESS_PASSES + 1):
        for path, values in STRESS_SEARCH:
            current = get_path(cfg, path)
            points = {v: agg_at(cfg, pcfg, seeds, {path: v}, names) for v in sorted(set(values) | {current})}
            chosen = analysis.pick_closest(points, analysis.stress_score, prefer=current)
            cfg = with_overrides(cfg, {path: chosen})
            steps.append({"pass": n, "path": path, "points": points, "chosen": chosen, "was": current})
        log(f"stress search, pass {n}", t0)
    return with_overrides(cfg, {"start.cash": get_path(base_cfg, "start.cash")}), steps


def cash_search(cfg, pcfg, seeds, t0, label):
    out = {}
    for cash in CASH_VALUES:
        out[cash] = agg_at(cfg, pcfg, seeds, {"start.cash": cash})
    log(f"cash search ({label})", t0)
    return out


def h_search(cfg, pcfg, seeds, t0):
    out = {h: agg_at(cfg, pcfg, seeds, {"book.remaining_hours": h}) for h in H_VALUES}
    log("H search", t0)
    return out


def cat_search(cfg, pcfg, seeds, t0):
    """Imperfect careful's CAT-tool pick rate at each price. Returns ({price: rate}, chosen price)."""
    rates = {}
    for price in CAT_PRICES:
        runs = experiments.run_batch(main_variant(with_overrides(cfg, {"effects.pool.cat_tool.price_per_week": price})),
                                     pcfg, analysis.MAIN_PLAYER, seeds, keep=True)
        rates[price] = analysis.effects_report(runs, cfg)["pick_rate"].get("cat_tool", float("nan"))
    current = cfg["effects"]["pool"]["cat_tool"]["price_per_week"]
    lo, hi = CAT_TARGET
    chosen = current if lo <= rates[current] <= hi else min(rates, key=lambda p: (abs(rates[p] - (lo + hi) / 2), p))
    log("CAT price check", t0)
    return rates, chosen


def scaled(cfg, paths, factor):
    return with_overrides(cfg, {p: get_path(cfg, p) * factor for p in paths})


def sensitivity(cfg, pcfg, seeds, t0, rows):
    out = {}
    for label, (paths, sides) in rows.items():
        out[label] = {side: analysis.agg_policies(by_policy(main_variant(scaled(cfg, paths, f)), pcfg, seeds))
                      for side, f in sides}
        log(f"sensitivity: {label}", t0)
    return out


def tune(base_cfg, pcfg, seeds, t0):
    """§10.3 tuning order: stress -> starting cash -> H -> starting cash again -> CAT price."""
    cfg, stress_steps = stress_search(base_cfg, pcfg, range(min(STRESS_SEEDS, len(seeds))), t0)
    search1 = cash_search(cfg, pcfg, seeds, t0, "first pass")
    cash1 = analysis.pick_cash(search1)
    cfg = with_overrides(cfg, {"start.cash": cash1})
    hsearch = h_search(cfg, pcfg, seeds, t0)
    h = analysis.pick_h(hsearch)
    cfg = with_overrides(cfg, {"book.remaining_hours": h})
    search2 = cash_search(cfg, pcfg, seeds, t0, "re-check")
    cash2 = analysis.pick_cash(search2)
    cfg = with_overrides(cfg, {"start.cash": cash2})
    cat_rates, cat_price = cat_search(cfg, pcfg, seeds, t0)
    cfg = with_overrides(cfg, {"effects.pool.cat_tool.price_per_week": cat_price})
    return cfg, {"stress_steps": stress_steps, "cash_search_1": search1, "cash_1": cash1, "h_search": hsearch,
                 "h": h, "cash_search_2": search2, "cash_2": cash2, "cat_rates": cat_rates, "cat_price": cat_price}


def simulate(n_seeds):
    t0 = time.time()
    base_cfg, pcfg = load_economy(), load_policies()
    seeds = range(n_seeds)
    cfg, tuning = tune(base_cfg, pcfg, seeds, t0)
    matrix = experiments.run_matrix(cfg, pcfg, seeds)
    log("main matrix", t0)
    sens = sensitivity(cfg, pcfg, seeds, t0, SENSITIVITY)
    ref = sensitivity(cfg, pcfg, seeds, t0, REFERENCE_ROWS)
    results = {"seeds": n_seeds, "config": cfg, "config_file": base_cfg, "tuning": tuning,
               "matrix": matrix, "sensitivity": sens, "reference_rows": ref}
    add_recommended(results, pcfg, t0)
    save(results)
    return results


def add_recommended(results, pcfg, t0):
    results.pop("recommended", None)
    if not RECOMMENDED_PATH.exists():
        return
    rec = load_yaml(RECOMMENDED_PATH)
    rec_cfg = deep_merge(results["config"], rec.get("changes", {}))
    results["recommended"] = {"overlay": rec, "config": rec_cfg,
                              "matrix": experiments.run_matrix(rec_cfg, pcfg, range(results["seeds"]))}
    log("recommended matrix", t0)


def save(results):
    RAW.mkdir(parents=True, exist_ok=True)
    with open(RAW / "results.pkl", "wb") as f:
        pickle.dump(results, f)


def load():
    with open(RAW / "results.pkl", "rb") as f:
        return pickle.load(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="run everything and write the report")
    ap.add_argument("--report", action="store_true", help="rebuild the report from saved results")
    ap.add_argument("--recommended", action="store_true", help="re-run the recommended overlay on saved results")
    ap.add_argument("--seeds", type=int, default=2000)
    args = ap.parse_args()
    if args.all:
        results = simulate(args.seeds)
    else:
        results = load()
        if args.recommended:
            add_recommended(results, load_policies(), time.time())
            save(results)
    from sim.src import report
    report.write(results, REPORTS)
    print(f"wrote {REPORTS / 'SIM_REPORT.md'}")


if __name__ == "__main__":
    main()
