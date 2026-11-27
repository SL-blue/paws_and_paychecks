"""Per-run summary (SIM_BASELINE.md §9.4) and aggregation over many runs."""
import numpy as np

from . import game_calendar as cal


def summarize(cfg, st, policy):
    log, days = st.log, cfg["calendar"]["days"]
    pre = log["cash_pre_lifeline"]
    low_day = int(np.argmin(pre)) + 1
    high = cfg["ending"]["high_stress_level"]
    stress_series = log["stress"]
    w45 = [s for d, s in enumerate(stress_series, start=1) if cal.week_of(d) in (4, 5)]
    receivables = st.receivables()
    deferred = st.deferred_rent["amount"] if st.deferred_rent else 0.0
    debts = st.debt + deferred
    job_payments = [p for p in log["payments"] if p["source"] == "job"]
    weeks = days // 7
    pay_weeks_job = [sum(1 for p in job_payments if cal.week_of(p["day"]) == w) for w in range(1, weeks + 1)]
    pay_weeks_all = [sum(1 for p in log["payments"] if cal.week_of(p["day"]) == w) for w in range(1, weeks + 1)]
    mults = [m for m in log["effect_mult"] if m is not None]
    rel_missed = sum(1 for w in log["rel_weeks"] if not w["met"])
    high_days = sum(1 for s in stress_series if s > high)
    e = cfg["ending"]
    good_ending = (not st.bankrupt and rel_missed <= e["max_relationship_weeks_missed"]
                   and log["pet_deficit_days"] <= e["max_pet_deficit_days"] and high_days <= e["max_high_stress_days"])
    return {
        "seed": st.seed,
        "policy": policy.name,
        "params": getattr(policy, "search_point", None),
        "bankrupt": st.bankrupt,
        "bankrupt_day": st.bankrupt_day,
        "crisis": bool(log["crisis_days"]),
        "crisis_days": len(log["crisis_days"]),
        "lifelines": [name for name, _ in st.lifelines_used],
        "min_cash": float(min(pre)),
        "min_cash_day": low_day,
        "cash_series": [float(c) for c in pre],
        "end_cash": float(st.cash),
        "receivables": float(receivables),
        "debts": float(debts),
        "end_value": float(st.cash + 0.9 * receivables - debts),
        "high_stress_days": high_days,
        "high_stress_share_w45": sum(1 for s in w45 if s > high) / len(w45),
        "illness_days": log["illness_days"],
        "final_stress": float(st.stress),
        "mean_stress": float(np.mean(stress_series)),
        "rel_weeks_missed": rel_missed,
        "rel_strong_negatives": sum(1 for w in log["rel_weeks"] if w["strong"]),
        "pet_deficit_days": log["pet_deficit_days"],
        "book_milestones": st.book.milestones_done,
        "book_finished": st.book.finished,
        "book_hours": float(st.book.hours),
        "book_remaining_hours_start": float(st.book.remaining_hours_nominal),
        "effects_held": list(st.held),
        "effects_count": len(st.held),
        "offers_by_source": dict(log["offers_by_source"]),
        "picks": log["picks"],
        "shop_buys": log["shop_buys"],
        "pool_exhausted": log["pool_exhausted"],
        "cap_hits": log["cap_hits"],
        "avg_effect_boost": float(np.mean(mults) - 1) if mults else 0.0,
        "end_effect_boost": float(np.mean(mults[-5:]) - 1) if mults else 0.0,
        "pay_delays": [p["delay"] for p in job_payments],
        "payments_per_week_job": pay_weeks_job,
        "payments_per_week_all": pay_weeks_all,
        "paid_hours": float(sum(log["paid_hours"])),
        "jobs_completed": st.completed_jobs,
        "jobs_late": st.late_jobs,
        "offers_seen": log["offers_seen"],
        "offers_accepted": log["offers_accepted"],
        "gross_delivered": float(sum(j["gross"] for j in log["jobs_delivered"])),
        "story_job_taken": any(j["story"] for j in log["jobs_delivered"]) or any(j.offer.story for j in st.jobs),
        "costs": {k: float(v) for k, v in log["costs"].items()},
        "good_ending": good_ending,
    }


def pct(values, q):
    return float(np.percentile(values, q)) if len(values) else float("nan")


def aggregate(runs):
    """Headline numbers over a list of run summaries."""
    n = len(runs)
    mean = lambda key: float(np.mean([r[key] for r in runs]))  # noqa: E731
    share = lambda pred: sum(1 for r in runs if pred(r)) / n   # noqa: E731
    delays = [d for r in runs for d in r["pay_delays"]]
    return {
        "n": n,
        "bankrupt": share(lambda r: r["bankrupt"]),
        "crisis": share(lambda r: r["crisis"]),
        "lifelines_mean": float(np.mean([len(r["lifelines"]) for r in runs])),
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
        "high_stress_share_w45": mean("high_stress_share_w45"),
        "illness_days": mean("illness_days"),
        "rel_weeks_missed": mean("rel_weeks_missed"),
        "pet_deficit_days": mean("pet_deficit_days"),
        "book_milestones": mean("book_milestones"),
        "book_finished": share(lambda r: r["book_finished"]),
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
        "good_ending": share(lambda r: r["good_ending"]),
        "story_job_taken": share(lambda r: r["story_job_taken"]),
    }
