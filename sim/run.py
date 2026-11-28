"""Run the economy simulation (SIM_BASELINE.md §10, v0.3) and write the report.

    python -m sim.run --all          # everything: searches, matrix, sensitivity, recommended overlay, report
    python -m sim.run --report       # rebuild the report from saved results only
    python -m sim.run --recommended  # re-run only the recommended overlay on saved results, then report
    python -m sim.run --all --seeds 200   # quicker, smaller run (not the committed report)

Tuning order (§10.3): starting-cash search -> tune H for careful's book target -> check the CAT
price against its pick-rate target -> re-check starting cash once. The searches, the CAT check
and the sensitivity sweep run the four player policies only; greedy-optimal (a 12-plan search per
seed, ~12x the cost) runs in the main matrix and the recommended re-run.
"""
import argparse
import pickle
import time

from sim.src import analysis, experiments
from sim.src.config import ROOT, deep_merge, get_path, load_economy, load_policies, load_yaml, with_overrides

REPORTS = ROOT / "sim" / "reports"
RAW = REPORTS / "raw"
RECOMMENDED_PATH = ROOT / "data" / "economy.recommended.yaml"

CASH_VALUES = list(range(800, 2401, 100))
H_VALUES = [50 + 2.5 * i for i in range(13)]          # 50 ... 80 hours
CAT_PRICES = list(range(30, 101, 5))
CAT_TARGET = (0.40, 0.60)

PLUS_MINUS = (("-25%", 0.75), ("+25%", 1.25))
SENSITIVITY = {   # label: (dotted config paths scaled together, sides)
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
    """Careful's CAT-tool pick rate at each price. Returns ({price: rate}, chosen price)."""
    rates = {}
    for price in CAT_PRICES:
        runs = experiments.run_batch(main_variant(with_overrides(cfg, {"effects.pool.cat_tool.price_per_week": price})),
                                     pcfg, "careful", seeds, keep=True)
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
    search1 = cash_search(base_cfg, pcfg, seeds, t0, "first pass")
    cash1 = analysis.pick_cash(search1)
    cfg = with_overrides(base_cfg, {"start.cash": cash1})
    hsearch = h_search(cfg, pcfg, seeds, t0)
    h = analysis.pick_h(hsearch)
    cfg = with_overrides(cfg, {"book.remaining_hours": h})
    cat_rates, cat_price = cat_search(cfg, pcfg, seeds, t0)
    cfg = with_overrides(cfg, {"effects.pool.cat_tool.price_per_week": cat_price})
    search2 = cash_search(cfg, pcfg, seeds, t0, "re-check")
    cash2 = analysis.pick_cash(search2)
    cfg = with_overrides(cfg, {"start.cash": cash2})
    return cfg, {"cash_search_1": search1, "cash_1": cash1, "h_search": hsearch, "h": h,
                 "cat_rates": cat_rates, "cat_price": cat_price, "cash_search_2": search2, "cash_2": cash2}


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
