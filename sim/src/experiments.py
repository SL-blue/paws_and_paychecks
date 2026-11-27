"""Running many seeds: one run, a batch (in parallel), and the greedy-optimal search."""
import os
from concurrent.futures import ProcessPoolExecutor

from . import engine, policies
from .config import with_overrides
from .metrics import aggregate

POLICY_NAMES = ["careful", "book_heavy", "grinder", "careless", "greedy_optimal"]


def run_greedy_optimal(cfg, pcfg, seed):
    """SEARCH-BASED: simulate every candidate plan with this seed's real future and keep the
    run with the highest end money value. Uses hidden future state by design."""
    best = None
    for candidate in policies.greedy_candidates(pcfg):
        candidate.search_point = {"weekday": candidate.weekday_hours, "weekend": candidate.weekend_hours,
                                  "sleep": candidate.sleep}
        result = engine.run(cfg, candidate, seed)
        if best is None or result["end_value"] > best["end_value"]:
            best = result
    return best


def run_one(cfg, pcfg, policy_name, seed):
    if policy_name == "greedy_optimal":
        return run_greedy_optimal(cfg, pcfg, seed)
    return engine.run(cfg, policies.make(policy_name, pcfg), seed)


def _run_chunk(args):
    cfg, pcfg, policy_name, seeds, keep = args
    out = []
    for seed in seeds:
        result = run_one(cfg, pcfg, policy_name, seed)
        out.append(result if keep else slim(result))
    return out


def slim(result):
    """Drop the bulky per-day/per-pick fields for sweeps."""
    drop = {"cash_series", "picks", "shop_buys", "costs"}
    return {k: v for k, v in result.items() if k not in drop}


def variant_cfg(cfg, with_effects, advance):
    return with_overrides(cfg, {"effects.enabled": with_effects, "book.advance_enabled": advance})


_POOL = None


def pool():
    global _POOL
    if _POOL is None:
        _POOL = ProcessPoolExecutor(max_workers=max(1, (os.cpu_count() or 2) - 1))
    return _POOL


def run_batch(cfg, pcfg, policy_name, seeds, keep=True, chunk=50):
    seeds = list(seeds)
    chunks = [(cfg, pcfg, policy_name, seeds[i:i + chunk], keep) for i in range(0, len(seeds), chunk)]
    results = []
    for part in pool().map(_run_chunk, chunks):
        results.extend(part)
    return results


def run_matrix(cfg, pcfg, seeds, policy_names=POLICY_NAMES, keep=True):
    """{(policy, with_effects, advance): [run summaries]} for all variants of §9.3."""
    out = {}
    for name in policy_names:
        for with_effects in (True, False):
            for advance in (False, True):
                out[(name, with_effects, advance)] = run_batch(variant_cfg(cfg, with_effects, advance), pcfg, name, seeds, keep)
    return out


def summarize_matrix(matrix):
    return {key: aggregate(runs) for key, runs in matrix.items()}
