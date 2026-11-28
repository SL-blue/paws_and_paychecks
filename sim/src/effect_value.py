"""How value-based policies rate an offered effect (SIM_BASELINE.md §8.5).

Method: a short analytic estimate of what the effect would change over the rest of the run for
*this* player's schedule, in five currencies: money ($), stress points avoided, book hours
gained, free hours gained, and risk (expected extra pet-deficit days or missed weeks with her).
The policy's hand-set weights (`value_weights` in data/policies.yaml) turn these into one number,
and the policy picks the highest. Only player-visible information is used: the calendar, the
config, the policy's own plan, the jobs it has accepted so far and its current state.
"""
from . import effects
from . import game_calendar as cal
from . import time_demands

AVG_WORDS = 4325          # mean offer size from the size table (0.5 x 1,000 + 0.35 x 4,500 + 0.15 x 15,000)


def context(cfg, st, p):
    """Numbers about the rest of the run that most effect estimates need."""
    days = range(st.day + 1, cfg["calendar"]["days"] + 1)
    weekday_paid, weekend_paid = p.get("weekday_paid_hours", 0), p.get("weekend_paid_hours", 0)
    paid = sum(weekend_paid if cal.is_weekend(d) else weekday_paid for d in days)
    book = 0.0 if st.book.finished else sum(
        p.get("book_weekend_hours", 0) if cal.is_weekend(d) else p.get("book_weekday_hours", 0) for d in days)
    book *= p.get("book_chance", 1.0)
    w = cfg["work"]
    hourly = w["throughput"]["standard"] * w["rate"]["standard_agency"] * w["net_factor"]
    jobs = [j["regular"] for j in st.log["jobs_delivered"]] + [j.offer.regular for j in st.jobs]
    kinds = [j.offer.kind for j in st.jobs]
    recent = st.log["paid_hours"][-7:]
    planned_recent = sum(weekend_paid if cal.is_weekend(d) else weekday_paid for d in range(max(1, st.day - 6), st.day + 1))
    t = weekday_paid + p.get("book_weekday_hours", 0)
    return {
        "D": len(days), "W": len(days) / 7, "paid": paid, "book": book, "hourly": hourly,
        "weekdays": sum(1 for d in days if not cal.is_weekend(d)),
        "saturdays": sum(1 for d in days if cal.weekday(d) == 6), "sundays": sum(1 for d in days if cal.weekday(d) == 7),
        "mondays": sum(1 for d in days if cal.weekday(d) == 1),
        "crunch_weeks_left": sum(1 for wk in cfg["her"]["crunch_weeks"] if wk * 7 > st.day),
        "single": st.single_project_days / st.workdays if st.workdays >= 3 else 0.6,
        "multi": st.multi_task_days / max(1, st.day) if st.day >= 3 else 0.5,
        "morning": min(cfg["day"]["morning_work_hours"], t) / t if t else 0.0,
        "evening": max(0.0, t - cfg["day"]["evening_after_hours"]) / t if t else 0.0,
        "short_days": 1.0 if weekday_paid <= 7 else 0.0,
        "regular": sum(1 for r in jobs if r) / len(jobs) if len(jobs) >= 3 else 0.4,
        "pe": sum(1 for k in kinds if k == "post_edit") / len(kinds) if len(kinds) >= 2 else 0.3,
        "idle": min(1.0, max(0.0, 1 - sum(recent) / planned_recent)) if planned_recent > 0 else 0.5,
        "her_evenings_left": 3 * len(days) / 7 if p.get("her") == "meet" else 1.5 * len(days) / 7,
        "pet_short": p.get("pet_care") != "meet",
        "max_extra": max(0.0, weekday_paid + p.get("extra_paid_hours", 0) - 8),
        "has_weekend_work": weekend_paid > 0,
        "high_stress_share": sum(1 for s in st.log["stress"] if s > 50) / max(1, len(st.log["stress"])),
    }


def marginal_throughput(cfg, st, bonus, kind_share):
    """Throughput gain after the cap, given what is already held (standard-job view)."""
    held = sum(effects.param(cfg, e, "bonus") for e in ("cat_tool", "second_monitor") if e in st.held)
    cap = effects.cap(cfg, "throughput")
    return max(0.0, min(cap, held + bonus) - min(cap, held)) * kind_share


def estimate(cfg, st, eid, p, c):
    """{money, stress, book, hours, risk} for one effect. Positive = good for the player."""
    par = lambda key: effects.param(cfg, eid, key)  # noqa: E731
    P, B, H, D, W = c["paid"], c["book"], c["hourly"], c["D"], c["W"]
    v = {"money": 0.0, "stress": 0.0, "book": 0.0, "hours": 0.0, "risk": 0.0}
    offer_net = AVG_WORDS * 0.11 * cfg["work"]["net_factor"]
    gain = {
        "deep_focus": lambda: c["single"] * par("single_bonus") - (1 - c["single"]) * par("multi_penalty"),
        "context_switcher": lambda: c["multi"] * par("multi_bonus") - (1 - c["multi"]) * par("single_penalty"),
        "morning_person": lambda: c["morning"] * par("morning_bonus") - c["evening"] * par("evening_penalty"),
        "night_owl": lambda: c["evening"] * par("evening_bonus") - c["morning"] * par("morning_penalty"),
        "pomodoro": lambda: c["short_days"] * par("short_day_bonus") - c["evening"] * par("evening_penalty"),
        "sunday_planning": lambda: par("bonus") * max(0.0, D - 7) / max(1, D),
    }.get(eid)
    if gain:
        g = gain()
        v["money"] += g * P * H
        if eid == "deep_focus":
            v["book"] += g * B
    if eid == "sunday_planning":
        v["hours"] -= par("time_sunday") * c["sundays"]
    elif eid == "cat_tool":
        v["money"] += marginal_throughput(cfg, st, par("bonus"), 1.0) * P * H - effects.weekly_price(cfg, eid) * W
    elif eid == "termbase":
        v["money"] += marginal_throughput(cfg, st, par("bonus"), c["regular"]) * P * H - 3 * par("first_job_extra_hours") * H
    elif eid == "pe_veteran":
        v["money"] += (marginal_throughput(cfg, st, par("pe_bonus"), c["pe"])
                       - par("standard_efficiency_penalty") * (1 - c["pe"])) * P * H
        v["book"] -= par("book_penalty") * B
    elif eid == "direct_network":
        extra = cfg["offers"]["per_weekday_mean"] * cfg["clients"]["direct"]["share"] * c["weekdays"]
        v["money"] += extra * c["idle"] * offer_net * 1.4 - 0.3 * P / 8 * par("revision_hours") * H
    elif eid == "specialist_niche":
        v["money"] += par("standard_rate_bonus") * (1 - c["pe"]) * P * H
        v["money"] -= par("random_offer_drop") * (1 - c["regular"]) * P * H * max(c["idle"], 0.3)
    elif eid == "rush_specialist":
        extra = cfg["offers"]["per_weekday_mean"] * 0.7 * cfg["work"]["rush_share"] * c["weekdays"]
        v["money"] += extra * c["idle"] * offer_net * 1.4 + 0.12 * 0.1 * P * H
        v["stress"] -= par("rush_extra_stress") * 0.3 * D
    elif eid == "loyal_client":
        extra = sum(cfg["regular_clients"][k]["prob_per_week"] for k in "ABC") * (par("regular_job_multiplier") - 1) * W
        v["money"] += extra * c["idle"] * offer_net - par("regular_rate_penalty") * c["regular"] * P * H
    elif eid == "fast_invoicer":
        v["money"] += p["value_weights"].get("liquidity", 0) * D / 42
        v["hours"] -= par("time_monday") * c["mondays"]
    elif eid == "invoice_reminders":
        v["money"] += 0.3 * p["value_weights"].get("liquidity", 0) * D / 42
    elif eid == "deposit_terms":
        v["money"] += 0.5 * p["value_weights"].get("liquidity", 0) * D / 42
        v["money"] -= par("large_offer_drop") * 0.35 * P * H * max(c["idle"], 0.3)
    elif eid == "side_class":
        v["money"] += par("saturday_income") * c["saturdays"]
        v["hours"] -= par("time_saturday") * c["saturdays"]
        v["stress"] -= 0 if c["has_weekend_work"] else -cfg["stress"]["no_paid_work_day"] * c["saturdays"]
    elif eid == "frugal_cooking":
        v["money"] += par("living_saving") * D
        v["hours"] -= par("time_daily") * D
    elif eid == "morning_pages":
        relief = effects.book_relief_per_hour(cfg, [eid])[0] + cfg["stress"]["book_hour"]
        v["stress"] += par("daily_relief") * D + relief * B
        v["hours"] -= par("time_daily") * D
    elif eid == "nap_habit":
        days = c["high_stress_share"] * D
        v["stress"] += par("nap_relief") * days
        v["hours"] -= par("time_nap") * days
    elif eid == "boundaries":
        v["stress"] += par("daily_relief") * D + (par("leisure_relief_multiplier") - 1) * 2 * 3 * D
        v["money"] -= c["max_extra"] * 0.5 * c["weekdays"] * H
    elif eid == "shared_calendar":
        v["hours"] += 2 * c["crunch_weeks_left"]
    elif eid == "sunday_brunch":
        uses = c["crunch_weeks_left"] if p.get("her") == "meet" else 0.5 * W
        v["hours"] += (cfg["her"]["half_day_hours"] - par("half_day_hours")) * uses
        v["money"] -= effects.per_use_price(cfg, eid) * uses
    elif eid == "quiet_company":
        evenings = c["her_evenings_left"] if B > 0 else 0
        v["hours"] += par("overlap_hours") * evenings
        v["stress"] -= 1.5 * par("overlap_hours") * evenings
    elif eid == "evening_walks":
        v["hours"] += par("overlap_hours") * c["her_evenings_left"] - par("extra_pet_care_hours") * D
    elif eid == "walk_routine":
        v["stress"] += par("pet_hour_relief") * time_demands.base_pet_need(cfg, st.day) * D
        v["risk"] -= (D / 3 if c["pet_short"] else 0.0)
    elif eid == "reading_aloud":
        book_days = D if B > 0 else 0
        v["hours"] += par("overlap_hours") * book_days
        v["stress"] += par("book_relief_extra") * B
        v["book"] -= par("overlap_speed_penalty") * par("overlap_hours") * book_days
    elif eid == "neighbor_sitter":
        v["hours"] += 2 * W
        v["money"] -= effects.per_use_price(cfg, eid) * W
        v["risk"] += W if c["pet_short"] else 0.0
    elif eid == "margin_notes":
        v["book"] += par("book_bonus") * B
        v["stress"] -= (-cfg["stress"]["book_hour"] - par("book_hour_relief")) * B
    elif eid == "writing_group":
        v["book"] += par("week_book_bonus") * B
        v["stress"] += 2.5 * W if B > 0 else 0.0
    return v


def value(cfg, st, eid, p):
    w = p["value_weights"]
    v = estimate(cfg, st, eid, p, context(cfg, st, p))
    total = (w["money"] * v["money"] + w["stress_per_point"] * v["stress"] + w["book_per_hour"] * v["book"]
             + w.get("hour", 0) * v["hours"] + w.get("risk", 0) * v["risk"])
    only = p.get("category_only")
    if only and effects.category(cfg, eid) not in only:
        total = total * 0.05 - 1000   # grinder: efficiency/throughput/rate first, others only as a last resort
    return total
