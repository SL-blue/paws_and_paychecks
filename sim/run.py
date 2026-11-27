"""Run the economy simulation and write the report.

    python -m sim.run --all        # everything: search, matrix, sensitivity, recommendations, report
    python -m sim.run --report     # rebuild the report from saved results only
    python -m sim.run --recommended  # re-run only the recommended overlay on saved results, then report
    python -m sim.run --all --seeds 200   # quicker, smaller run (not the committed report)
"""
import argparse
import pickle
import time
from sim.src import analysis, experiments
from sim.src.config import ROOT, deep_merge, load_economy, load_policies, load_yaml, with_overrides

REPORTS = ROOT / "sim" / "reports"
RAW = REPORTS / "raw"
RECOMMENDED_PATH = ROOT / "data" / "economy.recommended.yaml"

CASH_VALUES = list(range(800, 2401, 200))
SENSITIVITY = {   # label: list of dotted config paths scaled together
    "starting cash": ["start.cash"],
    "rent": ["costs.rent"],
    "offer rate": ["offers.per_weekday_mean"],
    "PE share": ["offers.pe_share_start", "offers.pe_share_end"],
    "payment delays": [f"clients.{c}.{k}" for c in ("direct", "standard_agency", "slow_agency")
                       for k in ("pay_days_min", "pay_days_max")],
    "late-payment share": ["clients.late_share"],
    "week-2 story job size": ["story_job.words"],
    "NET factor": ["work.net_factor"],
    "effect sizes": ["effects.size_scale"],
    "book remaining work (inverse of starting progress)": ["book.remaining_hours_scale"],
}


def log(msg, t0):
    print(f"[{time.time() - t0:6.0f}s] {msg}", flush=True)


def by_policy(cfg, pcfg, seeds, keep=False):
    return {p: experiments.run_batch(cfg, pcfg, p, seeds, keep=keep) for p in experiments.POLICY_NAMES}


def cash_search(cfg, pcfg, seeds, t0):
    out = {}
    for cash in CASH_VALUES:
        out[cash] = analysis.agg_policies(by_policy(with_overrides(cfg, {"start.cash": cash}), pcfg, seeds))
        log(f"cash search {cash}", t0)
    return out


def scaled(cfg, paths, factor):
    from sim.src.config import get_path
    return with_overrides(cfg, {p: get_path(cfg, p) * factor for p in paths})


def sensitivity(cfg, pcfg, seeds, t0):
    out = {}
    for label, paths in SENSITIVITY.items():
        out[label] = {side: analysis.agg_policies(by_policy(scaled(cfg, paths, f), pcfg, seeds))
                      for side, f in (("-25%", 0.75), ("+25%", 1.25))}
        log(f"sensitivity {label}", t0)
    return out


def simulate(n_seeds):
    t0 = time.time()
    base_cfg, pcfg = load_economy(), load_policies()
    seeds = range(n_seeds)
    search = cash_search(base_cfg, pcfg, seeds, t0)
    chosen = analysis.pick_cash(search)
    cfg = with_overrides(base_cfg, {"start.cash": chosen})
    matrix = experiments.run_matrix(cfg, pcfg, seeds)
    log("baseline matrix", t0)
    sens = sensitivity(cfg, pcfg, seeds, t0)
    results = {"seeds": n_seeds, "config": cfg, "config_file_cash": base_cfg["start"]["cash"],
               "cash_search": search, "chosen_cash": chosen, "matrix": matrix, "sensitivity": sens}
    add_recommended(results, pcfg, t0)
    save(results)
    return results


def add_recommended(results, pcfg, t0):
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
