"""The day loop. One run = (config, policy, seed) -> summary dict. Deterministic.

Order of a day:
 1. payments arrive          6. paid work, deliveries, work-milestone effect offers
 2. shop                     7. book work, book milestones (advance, effect offer)
 3. offers, acceptance       8. costs (living, fixed, rent, random, subscriptions, deferred rent)
 4. day plan                 9. missed deadlines, stress, relationship and pet bookkeeping
 5. illness, interruptions  10. weekly reflection; end-of-day crisis check and lifelines
"""
from . import book as book_mod
from . import costs, effects, lifelines, offers, payments, stress, time_demands
from . import game_calendar as cal
from .metrics import summarize
from .rng import stream
from .state import Plan, State


def new_state(cfg, seed):
    st = State(seed=seed, cash=cfg["start"]["cash"], stress=cfg["start"]["stress"],
               book=book_mod.new_book(cfg, seed))
    st.invoices = payments.receivable_invoices(cfg)
    return st


def run(cfg, policy, seed):
    st = new_state(cfg, seed)
    offer_stream = offers.generate_stream(cfg, seed)
    policy.start(cfg, st, seed, offer_stream if policy.uses_foresight else None)
    for day in range(1, cfg["calendar"]["days"] + 1):
        st.day = day
        step(cfg, st, policy, offer_stream)
    return summarize(cfg, st, policy)


# --- 1-3: money in, shop, offers -------------------------------------------------------------

def receive_payments(st, day):
    paid, st.invoices = payments.due_today(st.invoices, day)
    for inv in paid:
        st.cash += inv.amount
        st.record_payment(day, inv, inv.amount)


def acquire_effect(cfg, st, eid, day):
    st.held.append(eid)
    st.effect_day[eid] = day
    st.cash -= effects.one_off_price(cfg, eid)
    if effects.weekly_price(cfg, eid):
        st.subscriptions[eid] = day   # first week charged today (in costs)


def offer_effect(cfg, st, policy, source, day):
    if not cfg["effects"]["enabled"]:
        return
    st.effect_offer_count += 1
    choices = effects.draw_offer(cfg, st.seed, st.effect_offer_count, day, st.held, st.had_evening_with_her)
    st.log["offers_by_source"][source] += 1
    if not choices:
        st.log["pool_exhausted"] += 1
        return
    pick = policy.pick_effect(cfg, st, choices, source)
    st.log["picks"].append({"day": day, "source": source, "choices": choices, "pick": pick})
    acquire_effect(cfg, st, pick, day)


def shop(cfg, st, policy, day):
    if not cfg["effects"]["enabled"]:
        return
    for eid in policy.shop(cfg, st):
        if eid in st.held:
            continue
        acquire_effect(cfg, st, eid, day)
        st.log["offers_by_source"]["shop"] += 1
        st.log["shop_buys"].append({"day": day, "effect": eid})


def take_offers(cfg, st, policy, offer_stream, day):
    if day >= cfg["calendar"]["no_new_work_from_day"]:
        return
    mult = effects.direct_offer_multiplier(cfg, st.held)
    seen = offers.offers_for_day(cfg, offer_stream, day, st.reputation_until, mult)
    st.log["offers_seen"] += len(seen)
    for offer in policy.choose_offers(cfg, st, seen):
        extra = effects.revision_hours(cfg, st.held, offer.client) * cfg["work"]["throughput"][offer.kind]
        st.jobs.append(offers.accept(offer, day, st.reputation_until, cfg, extra_words=extra))
        st.log["offers_accepted"] += 1


# --- 4-5: plan, illness, interruptions -------------------------------------------------------

def fit_plan(cfg, st, plan):
    """Trim a plan to 24 hours: her time first, then book, then paid work."""
    lunch = cfg["day"]["lunch_hours"] if plan.paid_hours > 0 else 0.0
    fixed = plan.sleep_hours + cfg["day"]["routine_hours"] + lunch + plan.pet_hours + effects.daily_time_cost(cfg, st.held)
    for attr in ("her_hours", "book_hours", "paid_hours"):
        over = fixed + plan.paid_hours + plan.book_hours + plan.her_hours - 24
        if over <= 0:
            break
        setattr(plan, attr, max(0.0, getattr(plan, attr) - over))
    return max(0.0, 24 - fixed - plan.paid_hours - plan.book_hours - plan.her_hours)


def illness_today(cfg, st, day):
    if not stress.illness_possible(cfg, st.high_stress_streak):
        return False
    return stream(st.seed, "illness", day).random() < cfg["stress"]["illness_chance"]


def interruption_share(cfg, st, day, coworking):
    d = cfg["day"]
    base = stream(st.seed, "interruptions", day).uniform(d["interruption_min"], d["interruption_max"])
    return base * effects.interruption_factor(cfg, st.held, coworking)


# --- 6-7: work -------------------------------------------------------------------------------

def segments(cfg, start, hours):
    """Split [start, start+hours) of the work day into (hours, part) with part 0/1/2 =
    morning (before 13:00) / midday / evening (after 19:00)."""
    bounds = [0, cfg["day"]["morning_work_hours"], cfg["day"]["evening_after_hours"], float("inf")]
    out = []
    for part in range(3):
        lo, hi = max(start, bounds[part]), min(start + hours, bounds[part + 1])
        if hi > lo:
            out.append((hi - lo, part))
    return out


def edf(jobs):
    return sorted(jobs, key=lambda j: (j.deadline_day, j.accepted_day, j.id))


def count_projects(cfg, st, hours, base):
    left, count = hours, 0
    for job in edf(st.jobs):
        if left <= 1e-9:
            break
        rate = cfg["work"]["throughput"][job.kind] * base * effects.throughput_multiplier(cfg, st.held, job.kind)
        count += 1
        left -= job.words_left / rate
    return count


def do_paid_work(cfg, st, hours, base, bonuses):
    """Work EDF through the jobs. Returns (jobs finished today, mean effect multiplier)."""
    queue = edf(st.jobs)
    done, weighted = [], 0.0
    for seg_hours, part in segments(cfg, 0, hours):
        bonus = effects.capped(cfg, bonuses[part])
        st.log["cap_hits"] += bonuses[part] > cfg["effects"]["caps"]["efficiency"] + 1e-9
        while seg_hours > 1e-9 and queue:
            job = queue[0]
            effect_mult = (1 + bonus) * effects.throughput_multiplier(cfg, st.held, job.kind)
            rate = cfg["work"]["throughput"][job.kind] * base * effect_mult
            use = min(seg_hours, job.words_left / rate)
            job.words_left -= use * rate
            job.hours_worked += use
            seg_hours -= use
            weighted += use * effect_mult
            if job.words_left <= 1e-6:
                done.append(queue.pop(0))
    return done, (weighted / hours if hours > 0 else None)


def deliver(cfg, st, policy, jobs, day):
    for job in jobs:
        st.jobs.remove(job)
        gross = offers.job_gross(job)
        st.invoices.append(payments.make_invoice(cfg, st.seed, job, day, gross, effects.fast_invoicer(cfg, st.held)))
        st.completed_jobs += 1
        st.late_jobs += job.late
        st.log["jobs_delivered"].append({"day": day, "id": job.id, "gross": gross, "late": job.late, "story": job.offer.story})
        if st.completed_jobs % cfg["effects"]["work_milestone_every"] == 0:
            offer_effect(cfg, st, policy, "work_milestone", day)


def do_book_work(cfg, st, policy, start, hours, base, bonuses, day):
    if hours <= 0 or st.book.finished:
        return
    words = sum(h * cfg["book"]["words_per_hour"] * base * (1 + effects.capped(cfg, bonuses[part]))
                for h, part in segments(cfg, start, hours))
    for _ in range(book_mod.work(st.book, words, hours, day)):
        if cfg["book"]["advance_enabled"]:
            st.cash += cfg["book"]["advance_per_milestone"] * cfg["work"]["net_factor"]
            st.log["payments"].append({"day": day, "amount": cfg["book"]["advance_per_milestone"] * cfg["work"]["net_factor"], "source": "advance", "delay": None})
        offer_effect(cfg, st, policy, "book_milestone", day)


# --- 8: costs --------------------------------------------------------------------------------

def pay(st, label, amount):
    st.cash -= amount
    st.log["costs"][label] += amount


def pay_costs(cfg, st, policy, day, ill, pet_deficit_weight):
    for label, amount in costs.scheduled_costs(cfg, day):
        pay(st, label, amount)
    st.rent_paid_today = costs.rent_due(cfg, day)
    if st.rent_paid_today:
        pay(st, "rent", st.rent_paid_today)
    if day == cfg["costs"]["transformation_day"]:
        pay(st, "pet transformation", costs.transformation_bill(cfg, st.seed, st.pet_deficit_weighted))
    for label, amount in costs.random_costs(cfg, st.seed, day, pet_deficit_weight):
        pay(st, label, amount)
    if ill:
        c = cfg["costs"]
        pay(st, "illness", stream(st.seed, "illness_cost", day).uniform(c["illness_cost_min"], c["illness_cost_max"]))
    for eid, next_day in list(st.subscriptions.items()):
        if day >= next_day:
            pay(st, eid, effects.weekly_price(cfg, eid))
            st.subscriptions[eid] = next_day + 7
    if st.deferred_rent and (day >= st.deferred_rent["due_day"] or policy.pay_deferred_rent(cfg, st)):
        pay(st, "rent (late)", st.deferred_rent["amount"])
        st.deferred_rent = None


# --- 9: deadlines, stress, her, pet ----------------------------------------------------------

def check_deadlines(cfg, st, day):
    for job in st.jobs:
        if job.deadline_day == day and not job.late:
            job.late = True
            st.reputation_until[job.offer.client] = day + cfg["reputation"]["penalty_days"]


def update_stress(cfg, st, plan, leisure, day):
    default_sleep = cfg["day"]["default_sleep_hours"]
    cut = max(0.0, default_sleep - plan.sleep_hours)
    st.short_night_streak = st.short_night_streak + 1 if plan.sleep_hours < cfg["stress"]["short_night_hours"] else 0
    runway = st.cash < cfg["stress"]["runway_days"] * costs.daily_running_cost(cfg, day)
    d = stress.StressDay(
        paid_hours=plan.paid_hours, sleep_cut=cut, short_night_streak=st.short_night_streak,
        deadlines_tomorrow=sum(1 for j in st.jobs if j.deadline_day == day + 1 and j.words_left > 0),
        low_runway=runway, rush_in_progress=any(j.offer.rush for j in st.jobs),
        leisure_hours=plan.her_hours + min(leisure, cfg["day"]["leisure_hours_cap"]),
        book_hours=plan.book_hours, book_relief_per_hour=effects.book_relief_per_hour(cfg, st.held),
        extra_relief=effects.daily_stress_relief(cfg, st.held, plan.pet_hours),
        extra_sleep_cut_stress=effects.extra_sleep_cut_stress(cfg, st.held),
    )
    st.stress = stress.apply(cfg, st.stress, stress.daily_delta(cfg, d))
    st.high_stress_streak = st.high_stress_streak + 1 if st.stress > cfg["stress"]["illness_threshold"] else 0
    st.last_sleep_cut = cut


def track_her(cfg, st, plan, day):
    kind = time_demands.count_her_time(cfg, day, plan.her_hours)
    if kind:
        st.had_evening_with_her = True
        st.week_evenings += kind == "evening"
        st.week_half_days += kind == "half_day"
    if cal.is_week_end(day):
        met = time_demands.week_met(cfg, st.week_evenings, st.week_half_days)
        st.rel_missed_streak = 0 if met else st.rel_missed_streak + 1
        st.log["rel_weeks"].append({"week": cal.week_of(day), "met": met, "strong": st.rel_missed_streak >= 2})
        st.week_evenings = st.week_half_days = 0


def track_pet(cfg, st, plan, day):
    """Returns the deficit weight of today (0 if care was enough)."""
    need = time_demands.pet_care_need(cfg, day, plan.coworking and "coworking" in st.held,
                                      effects.param(cfg, "coworking", "extra_pet_care_hours"))
    if plan.pet_hours + 1e-9 >= need:
        return 0.0
    st.log["pet_deficit_days"] += 1
    weight = effects.pet_deficit_weight(cfg, st.held)
    if day < cfg["costs"]["transformation_day"]:
        st.pet_deficit_weighted += weight
    return weight


# --- the day ---------------------------------------------------------------------------------

def step(cfg, st, policy, offer_stream):
    day = st.day
    receive_payments(st, day)
    shop(cfg, st, policy, day)
    take_offers(cfg, st, policy, offer_stream, day)

    plan = policy.plan_day(cfg, st)
    leisure = fit_plan(cfg, st, plan)
    ill = illness_today(cfg, st, day)
    if ill:
        st.log["illness_days"] += 1
        leisure += plan.paid_hours + plan.book_hours
        plan.paid_hours = plan.book_hours = 0.0
    lost = interruption_share(cfg, st, day, plan.coworking)
    paid_eff, book_eff = plan.paid_hours * (1 - lost), plan.book_hours * (1 - lost)

    base = stress.efficiency(cfg, st.stress) * (1 - cfg["stress"]["sleep_cut_efficiency"] * st.last_sleep_cut)
    projects = count_projects(cfg, st, paid_eff, base) if paid_eff > 0 else 0
    tasks = projects + (1 if book_eff > 0 and not st.book.finished else 0)
    bonuses = effects.efficiency_segments(cfg, st.held, projects, tasks, plan.coworking)
    finished, effect_mult = do_paid_work(cfg, st, paid_eff, base, bonuses) if paid_eff > 0 else ([], None)
    deliver(cfg, st, policy, finished, day)
    do_book_work(cfg, st, policy, paid_eff, book_eff, base, bonuses, day)
    if paid_eff > 0:
        st.workdays += 1
        st.single_project_days += projects == 1
    st.multi_task_days += tasks >= 2

    deficit_weight = track_pet(cfg, st, plan, day)
    pay_costs(cfg, st, policy, day, ill, deficit_weight)
    check_deadlines(cfg, st, day)
    update_stress(cfg, st, plan, leisure, day)
    track_her(cfg, st, plan, day)

    if day in cfg["effects"]["weekly_reflection_days"]:
        offer_effect(cfg, st, policy, "weekly_reflection", day)
    end_of_day_cash(cfg, st, policy, day)
    log_day(st, plan, effect_mult)


def end_of_day_cash(cfg, st, policy, day):
    st.log["cash_pre_lifeline"].append(st.cash)
    if st.cash < 0:
        st.log["crisis_days"].append(day)
        if not st.bankrupt and lifelines.resolve_crisis(cfg, st, day, policy.lifeline_order(cfg, st)):
            st.bankrupt, st.bankrupt_day = True, day
    st.rent_paid_today = 0


def log_day(st, plan, effect_mult):
    st.log["cash"].append(st.cash)
    st.log["stress"].append(st.stress)
    st.log["paid_hours"].append(plan.paid_hours)
    st.log["book_hours"].append(plan.book_hours)
    st.log["effect_mult"].append(effect_mult)


__all__ = ["run", "Plan"]
