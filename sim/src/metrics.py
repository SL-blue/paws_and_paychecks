"""Per-run summary, the five ending goals and the ending tier (SIM_BASELINE.md §9, §10.4), and
aggregation over many runs. A run that ends in the parents' ending is measured up to that day."""
from collections import Counter

import numpy as np

from . import game_calendar as cal

GOALS = ["pet", "relationship", "book", "stress", "finances"]
TIERS = ["best", "good", "mixed", "hard", "parents"]


def stress_goal(cfg, series):
    e = cfg["endings"]
    lo, hi = e["stress_end_days"]
    window = series[lo - 1:hi] or series[-(hi - lo + 1):]   # run ended early: its last week
    high_days = sum(1 for s in series if s > e["high_stress_level"])
    return float(np.mean(window)) <= e["stress_end_max_avg"] and high_days <= e["stress_max_high_days"], float(np.mean(window)), high_days


def relationship_goal(cfg, st):
    e = cfg["endings"]
    missed = sum(1 for w in st.log["rel_weeks"] if not w["met"])
    worst_streak = max([w["streak"] for w in st.log["rel_weeks"]] or [0])
    loan_overdue = st.parents_reason == "loan"
    return missed <= e["rel_max_weeks_missed"] and worst_streak <= e["rel_max_missed_in_a_row"] and not loan_overdue, missed, worst_streak


def finance_tier(cfg, st, end_value):
    if st.parents:
        return "parents"
    if st.debt <= 1e-9 and end_value >= cfg["endings"]["finance_good_min_value"]:
        return "good"
    return "okay"


def ending_tier(goals, parents):
    if parents:
        return "parents"
    met = sum(goals.values())
    if met == len(goals):
        return "best"
    if all(goals[g] for g in ("pet", "relationship", "stress", "finances")):
        return "good"
    return "mixed" if met >= 3 else "hard"


def weekly_counts(payments, sources, weeks):
    return [sum(1 for p in payments if p["source"] in sources and cal.week_of(p["day"]) == w) for w in range(1, weeks + 1)]


def summarize(cfg, st, policy):
    log = st.log
    pre, stress_series = log["cash_pre_lifeline"], log["stress"]
    receivables = st.receivables()
    end_value = st.cash + 0.9 * receivables - st.debt
    stress_ok, stress_end_avg, high_days = stress_goal(cfg, stress_series)
    rel_ok, rel_missed, rel_streak = relationship_goal(cfg, st)
    fin = finance_tier(cfg, st, end_value)
    near = st.book.near_finished(cfg["book"]["near_finished_last_share"])
    goals = {"pet": st.pet_deficit_weighted <= cfg["endings"]["pet_max_deficit_days"], "relationship": rel_ok,
             "book": st.book.finished, "stress": stress_ok, "finances": fin == "good"}
    weeks = cfg["calendar"]["days"] // 7
    job_payments = [p for p in log["payments"] if p["source"] == "job"]
    mults = [m for m in log["effect_mult"] if m is not None]
    w45 = [s for d, s in enumerate(stress_series, start=1) if cal.week_of(d) in (4, 5)]
    high = cfg["endings"]["high_stress_level"]
    loan = st.loan or {}
    return {
        "seed": st.seed, "policy": policy.name, "params": getattr(policy, "search_point", None),
        "end_day": st.day,
        # endings
        "tier": ending_tier(goals, st.parents), "goals": goals, "finance_tier": fin,
        "parents": st.parents, "parents_day": st.parents_day, "parents_reason": st.parents_reason,
        # money
        "crisis": bool(log["crisis_days"]), "crisis_days": len(log["crisis_days"]),
        "lifelines": [name for name, _ in st.lifelines_used],
        "loan_taken": bool(st.loan), "loan_amount": float(loan.get("amount", 0.0)),
        "loan_repaid_on_time": bool(st.loan) and loan.get("repaid_day") is not None and loan["repaid_day"] <= loan["due_day"],
        "min_cash": float(min(pre)), "min_cash_day": int(np.argmin(pre)) + 1,
        "cash_series": [float(c) for c in pre],
        "end_cash": float(st.cash), "receivables": float(receivables), "debts": float(st.debt),
        "end_value": float(end_value),
        # stress, her, pet
        "high_stress_days": high_days, "stress_end_avg": stress_end_avg,
        "high_stress_share_w45": sum(1 for s in w45 if s > high) / len(w45) if w45 else float("nan"),
        "illness_days": log["illness_days"], "mean_stress": float(np.mean(stress_series)),
        "rel_weeks_missed": rel_missed, "rel_worst_streak": rel_streak,
        "pet_deficit_days": log["pet_deficit_days"], "pet_deficit_weighted": float(st.pet_deficit_weighted),
        # book
        "book_milestones": st.book.milestones_done, "book_finished": st.book.finished, "book_near_finished": near,
        "book_hours": float(st.book.hours), "book_remaining_hours_start": float(st.book.remaining_hours_nominal),
        # effects
        "effects_held": list(st.held), "effects_count": len(st.held),
        "offers_by_source": dict(log["offers_by_source"]), "picks": log["picks"], "shop_buys": log["shop_buys"],
        "pool_exhausted": log["pool_exhausted"], "cap_hits": dict(log["cap_hits"]),
        "synergy_days": dict(log["synergy_days"]),
        "avg_effect_boost": float(np.mean(mults) - 1) if mults else 0.0,
        "end_effect_boost": float(np.mean(mults[-5:]) - 1) if mults else 0.0,
        "effect_time_hours": float(log["effect_time_hours"]), "overlap_hours": dict(log["overlap_hours"]),
        # work and feedback
        "pay_delays": [p["delay"] for p in job_payments],
        "payments_per_week_job": weekly_counts(log["payments"], ("job", "deposit"), weeks),
        "payments_per_week_all": weekly_counts(log["payments"], ("job", "deposit", "receivable"), weeks),
        "paid_hours": float(sum(log["paid_hours"])), "jobs_completed": st.completed_jobs, "jobs_late": st.late_jobs,
        "offers_seen": log["offers_seen"], "offers_accepted": log["offers_accepted"],
        "gross_delivered": float(sum(j["gross"] for j in log["jobs_delivered"])),
        "regular_jobs": dict(log["regular_jobs"]), "story_decision": st.story_decision,
        "story_job_taken": st.story_decision in ("taken", "forced"),
        "costs": {k: float(v) for k, v in log["costs"].items()},
    }


def pct(values, q):
    return float(np.percentile(values, q)) if len(values) else float("nan")


def most_missed(runs):
    """The goal missed most often among runs that did not end with the parents."""
    counts = Counter(g for r in runs if not r["parents"] for g in GOALS if not r["goals"][g])
    if not counts:
        return "-", 0.0
    goal, n = max(sorted(counts.items()), key=lambda kv: kv[1])
    return goal, n / len(runs)


def aggregate(runs):
    """Headline numbers over a list of run summaries."""
    n = len(runs)
    mean = lambda key: float(np.mean([r[key] for r in runs]))  # noqa: E731
    share = lambda pred: sum(1 for r in runs if pred(r)) / n   # noqa: E731
    delays = [d for r in runs for d in r["pay_delays"]]
    parents_days = [r["parents_day"] for r in runs if r["parents"]]
    loans = [r for r in runs if r["loan_taken"]]
    goal, goal_share = most_missed(runs)
    out = {
        "n": n,
        "tiers": {t: share(lambda r, t=t: r["tier"] == t) for t in TIERS},
        "goals": {g: share(lambda r, g=g: r["goals"][g]) for g in GOALS},
        "most_missed": goal, "most_missed_share": goal_share,
        "parents": share(lambda r: r["parents"]),
        "parents_loan": share(lambda r: r["parents_reason"] == "loan"),
        "parents_floor": share(lambda r: r["parents_reason"] == "floor"),
        "parents_day_median": float(np.median(parents_days)) if parents_days else float("nan"),
        "finance_good": share(lambda r: r["finance_tier"] == "good"),
        "finance_okay": share(lambda r: r["finance_tier"] == "okay"),
        "crisis": share(lambda r: r["crisis"]),
        "lifelines_mean": float(np.mean([len(r["lifelines"]) for r in runs])),
        "lifeline_use": {k: share(lambda r, k=k: k in r["lifelines"]) for k in ("rent_late", "early_payment", "borrow")},
        "loan_taken": len(loans) / n,
        "loan_on_time": (sum(1 for r in loans if r["loan_repaid_on_time"]) / len(loans)) if loans else float("nan"),
        "low_day_28_35": share(lambda r: 28 <= r["min_cash_day"] <= 35),
        "min_cash_p50": pct([r["min_cash"] for r in runs], 50),
        "min_cash_p10": pct([r["min_cash"] for r in runs], 10),
        "end_value_p50": pct([r["end_value"] for r in runs], 50),
        "end_value_p10": pct([r["end_value"] for r in runs], 10),
        "end_value_p90": pct([r["end_value"] for r in runs], 90),
        "end_cash_p50": pct([r["end_cash"] for r in runs], 50),
        "receivables_p50": pct([r["receivables"] for r in runs], 50),
        "debts_mean": mean("debts"),
        "high_stress_days": mean("high_stress_days"),
        "stress_end_avg": mean("stress_end_avg"),
        "high_stress_share_w45": float(np.nanmean([r["high_stress_share_w45"] for r in runs])),
        "illness_days": mean("illness_days"),
        "rel_weeks_missed": mean("rel_weeks_missed"),
        "pet_deficit_days": mean("pet_deficit_weighted"),
        "book_milestones": mean("book_milestones"),
        "book_finished": share(lambda r: r["book_finished"]),
        "book_near_finished": share(lambda r: r["book_near_finished"]),
        "book_hours": mean("book_hours"),
        "effects_count": mean("effects_count"),
        "avg_effect_boost": mean("avg_effect_boost"),
        "end_effect_boost": mean("end_effect_boost"),
        "pay_delay_median": float(np.median(delays)) if delays else float("nan"),
        "payments_per_week_job": [float(np.mean([r["payments_per_week_job"][w] for r in runs])) for w in range(6)],
        "every_week_paid_job": share(lambda r: min(r["payments_per_week_job"]) >= 1),
        "every_week_paid_all": share(lambda r: min(r["payments_per_week_all"]) >= 1),
        "paid_hours": mean("paid_hours"),
        "jobs_completed": mean("jobs_completed"),
        "jobs_late": mean("jobs_late"),
        "regular_jobs": {k: float(np.mean([r["regular_jobs"].get(k, 0) for r in runs])) for k in "ABC"},
        "story_job_taken": share(lambda r: r["story_job_taken"]),
        "story_declined": share(lambda r: r["story_decision"] == "declined"),
    }
    out["good_or_better"] = out["tiers"]["best"] + out["tiers"]["good"]
    return out
