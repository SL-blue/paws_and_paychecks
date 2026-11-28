"""The day loop. One run = (config, policy, seed) -> summary dict. Deterministic.

Order of a day:
 1. payments arrive (late ones    7. book work, book milestones (effect offer)
    noticed)                      8. pet care, costs (living, fixed, rent, random, effect prices)
 2. shop                          9. missed deadlines, relationship bookkeeping
 3. offers: fixed jobs, the      10. weekly reflection (effect offer)
    story job, acceptance        11. loan repayment; crisis check and lifelines;
 4. day plan, effect time            the parents' ending (the run stops that day)
 5. illness, interruptions       12. stress: S and L for the day, conversion, then the night's sleep
 6. paid work, deliveries,       13. log
    work-milestone effect offers
Events that move long-term stress (payments, rent, the loan, milestones, her week, ...) are
collected during the day with `st.add_long` and applied in step 12.
"""
from . import book as book_mod
from . import costs, effects, lifelines, offers, payments, stress, time_demands
from . import game_calendar as cal
from .metrics import summarize
from .rng import stream
from .state import Plan, State


def new_state(cfg, seed):
    levels = stress.Levels(short=cfg["start"]["stress_short"], long=cfg["start"]["stress_long"], cap=cfg["stress"]["max"])
    st = State(seed=seed, cash=cfg["start"]["cash"], levels=levels, book=book_mod.new_book(cfg, seed))
    st.invoices = payments.receivable_invoices(cfg)
    return st


def run(cfg, policy, seed):
    st = new_state(cfg, seed)
    offer_stream = offers.generate_stream(cfg, seed)
    policy.start(cfg, st, seed, offer_stream if policy.uses_foresight else None)
    for day in range(1, cfg["calendar"]["days"] + 1):
        st.day = day
        step(cfg, st, policy, offer_stream)
        if st.parents:
            break
    return summarize(cfg, st, policy)


# --- 1-3: money in, shop, offers -------------------------------------------------------------

def receive_payments(cfg, st, day):
    """Invoices due today arrive (each lowers L, capped per day). An invoice that was expected
    today but doesn't arrive is noticed as late (+L once)."""
    lg = cfg["stress"]["long"]
    paid, st.invoices = payments.due_today(st.invoices, day)
    for inv in paid:
        st.cash += inv.amount
        st.record_payment(day, inv, inv.amount)
        st.add_long("payment", lg["payment_arrives"])
    for inv in st.invoices:
        if inv.expected_day == day:
            st.add_long("payment_late", lg["payment_late"])


def acquire_effect(cfg, st, eid, day):
    st.held.append(eid)
    st.effect_day[eid] = day
    st.cash -= effects.one_off_price(cfg, eid)
    st.log["costs"][eid] += effects.one_off_price(cfg, eid)
    if effects.weekly_price(cfg, eid):
        st.subscriptions[eid] = day   # first week charged today (in costs)


def offer_effect(cfg, st, policy, source, day):
    if not cfg["effects"]["enabled"]:
        return
    st.effect_offer_count += 1
    choices = effects.draw_offer(cfg, st.seed, st.effect_offer_count, day, st.held)
    st.log["offers_by_source"][source] += 1
    if not choices:
        st.log["pool_exhausted"] += 1
        return
    pick = policy.pick_effect(cfg, st, choices, source)
    st.log["picks"].append({"day": day, "source": source, "choices": choices, "pick": pick})
    if pick is None:   # skip: "keeping life simple"
        st.log["skips"].append({"day": day, "source": source})
        st.add_long("skip", -cfg["effects"]["skip_long_relief"])
        return
    acquire_effect(cfg, st, pick, day)


def shop(cfg, st, policy, day):
    if not cfg["effects"]["enabled"]:
        return
    for eid in policy.shop(cfg, st):
        if eid not in st.held:
            acquire_effect(cfg, st, eid, day)
            st.log["offers_by_source"]["shop"] += 1
            st.log["shop_buys"].append({"day": day, "effect": eid})


def accept_offer(cfg, st, offer, day):
    job = offers.accept(cfg, offer, st, effects)
    if offer.regular and "termbase" in st.held:
        st.termbase_clients.add(offer.regular)
    share = effects.deposit_share(cfg, st.held, offer)
    if share:
        job.deposit = payments.deposit(cfg, offer, share, job.rate_multiplier)
        st.cash += job.deposit
        st.log["payments"].append({"day": day, "amount": job.deposit, "source": "deposit", "delay": None})
    st.cap_hit("rate", effects.rate_bonus_raw(cfg, st.held, offer) > effects.cap(cfg, "rate") + 1e-9)
    st.jobs.append(job)
    st.log["offers_accepted"] += 1
    if offer.regular:
        st.log["regular_jobs"][offer.regular] += 1


def take_offers(cfg, st, policy, offer_stream, day):
    if day >= cfg["calendar"]["no_new_work_from_day"]:
        return
    seen = offers.offers_for_day(cfg, offer_stream, day, st, effects)
    st.log["offers_seen"] += len(seen)
    rest = []
    for offer in seen:
        if offer.fixed == "day1":
            accept_offer(cfg, st, offer, day)
        elif offer.fixed == "story":
            forced = cfg["story_job"]["always_taken"]
            take = forced or policy.decide_story(cfg, st, offer)
            st.story_decision = "forced" if forced else ("taken" if take else "declined")
            st.story_declined = not take
            if take:
                accept_offer(cfg, st, offer, day)
        else:
            rest.append(offer)
    for offer in policy.choose_offers(cfg, st, rest):
        accept_offer(cfg, st, offer, day)


# --- 4-5: plan, effect time, overlaps, illness, interruptions -------------------------------------

def pet_change(cfg, st, plan, day):
    return effects.pet_need_change(cfg, st.held, day, plan.coworking)


def fit_plan(cfg, st, plan, day, napped):
    """Fit the plan into 24 hours. Effect time comes from free time first, then paid time; any
    other overflow trims her time, then book, then paid work. Returns a dict with the day's
    leisure, overlaps and pet care given."""
    cap_paid = effects.max_paid_hours(cfg, st.held)
    if cap_paid is not None:
        plan.paid_hours = min(plan.paid_hours, cap_paid)
    help_due = st.sitter_help_due if cal.weekday(day) == 7 else 0.0
    effect_time, paid_like = effects.time_costs(cfg, st.held, day, napped, help_due)
    planned_her = plan.her_hours
    pet_target = 0.0 if plan.sitter else plan.pet_hours

    def overlaps():
        read = effects.reading_aloud_hours(cfg, st.held, plan.book_hours)
        quiet = effects.quiet_company_hours(cfg, st.held, plan.book_hours, plan.her_hours)
        walks = effects.evening_walk_hours(cfg, st.held, max(0.0, pet_target - read), plan.her_hours - quiet)
        return read, quiet, walks

    def used(read, quiet, walks):
        lunch = cfg["day"]["lunch_hours"] if plan.paid_hours > 0 else 0.0
        pet_alone = max(0.0, pet_target - read - walks)
        return (plan.sleep_hours + cfg["day"]["routine_hours"] + lunch + effect_time + pet_alone
                + plan.paid_hours + plan.book_hours - quiet + plan.her_hours)

    over = used(*overlaps()) - 24
    if over > 0:
        take = min(over, effect_time, plan.paid_hours)
        plan.paid_hours -= take
        for attr in ("her_hours", "book_hours", "paid_hours"):
            over = used(*overlaps()) - 24
            if over <= 0:
                break
            setattr(plan, attr, max(0.0, getattr(plan, attr) - over))
    read, quiet, walks = overlaps()
    skipped = planned_her >= cfg["her"]["evening_hours"] - 1e-9 and plan.her_hours < cfg["her"]["evening_hours"] - 1e-9
    pet_given = max(pet_target, read + walks)
    st.log["effect_time_hours"] += effect_time
    st.log["overlap_hours"].update({"reading_aloud": read, "quiet_company": quiet, "evening_walks": walks})
    need = time_demands.pet_care_need(cfg, day, pet_change(cfg, st, plan, day))   # fixed at planning time
    return {"leisure": max(0.0, 24 - used(read, quiet, walks)), "read": read, "quiet": quiet, "pet_need": need,
            "walks": walks, "pet_given": pet_given, "paid_like": paid_like, "her_skipped": skipped}


def bad_interruption(cfg, st, day, paid_hours):
    """One of the day's interruptions is a bad one (only on days with paid work)."""
    chance = cfg["stress"]["short"]["bad_interruption_chance"]
    return paid_hours > 0 and stream(st.seed, "bad_interruption", day).random() < chance


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
    morning (first `morning_work_hours`) / middle / evening (beyond `evening_after_hours`)."""
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
        rate = cfg["work"]["throughput"][job.kind] * base * effects.throughput_multiplier(cfg, st.held, job.offer)
        count += 1
        left -= job.words_left / rate
    return count


def planning_active(st, day):
    """Sunday planning works from the first Sunday after it was taken (the planning session)."""
    if "sunday_planning" not in st.held:
        return False
    taken = st.effect_day["sunday_planning"]
    first_sunday = taken + (7 - cal.weekday(taken)) % 7
    return day > first_sunday


def do_paid_work(cfg, st, hours, base, ctx):
    """Work EDF through the jobs. Returns (jobs finished today, mean effect boost on pay per hour:
    efficiency x throughput x rate effects, averaged over the hours worked)."""
    queue = edf(st.jobs)
    done, weighted = [], 0.0
    for seg_hours, part in segments(cfg, 0, hours):
        raw = effects.segment_efficiency(cfg, st.held, part, ctx)
        while seg_hours > 1e-9 and queue:
            job = queue[0]
            eff, eff_hit = effects.job_efficiency(cfg, st.held, raw, job.kind, ctx)
            thr, thr_hit = effects.throughput_bonus(cfg, st.held, job.offer)
            st.cap_hit("efficiency", eff_hit)
            st.cap_hit("throughput", thr_hit)
            mult = (1 + eff) * (1 + thr)
            rate = cfg["work"]["throughput"][job.kind] * base * mult
            use = min(seg_hours, job.words_left / rate)
            job.words_left -= use * rate
            job.hours_worked += use
            seg_hours -= use
            weighted += use * mult * (1 + job.rate_bonus)
            if job.words_left <= 1e-6:
                done.append(queue.pop(0))
    return done, (weighted / hours if hours > 0 else None)


def deliver(cfg, st, policy, jobs, day):
    terms = effects.pay_terms(cfg, st.held)
    for job in jobs:
        st.jobs.remove(job)
        gross = offers.job_gross(job)
        extra = effects.deposit_extra_days(cfg, job.deposit)
        st.invoices.append(payments.make_invoice(cfg, st.seed, job, day, gross, terms, job.deposit, extra))
        st.completed_jobs += 1
        st.late_jobs += job.late
        st.log["jobs_delivered"].append({"day": day, "id": job.id, "gross": gross, "late": job.late,
                                         "fixed": job.offer.fixed, "regular": job.offer.regular})
        if st.completed_jobs % cfg["effects"]["work_milestone_every"] == 0:
            offer_effect(cfg, st, policy, "work_milestone", day)


def do_book_work(cfg, st, policy, hours, read_hours, base, ctx, day):
    if hours <= 0 or st.book.finished:
        return
    bonus, hit = effects.book_speed_bonus(cfg, st.held, ctx)
    st.cap_hit("book", hit)
    speed = cfg["book"]["words_per_hour"] * base * (1 + bonus)
    read = min(read_hours, hours)
    words = (hours - read) * speed + read * speed * effects.reading_aloud_speed(cfg, st.held)
    for _ in range(book_mod.work(st.book, words, hours, day)):
        st.add_long("book_milestone", cfg["stress"]["long"]["book_milestone"])
        offer_effect(cfg, st, policy, "book_milestone", day)


# --- 8: pet care and costs -------------------------------------------------------------------

def pay(st, label, amount):
    st.cash -= amount
    st.log["costs"][label] += amount


def track_pet(cfg, st, plan, fit, day):
    """Returns today's deficit weight (0 if care was enough or the neighbor covered it)."""
    if plan.sitter or fit["pet_given"] + 1e-9 >= fit["pet_need"]:
        return 0.0
    st.log["pet_deficit_days"] += 1
    weight = effects.pet_deficit_weight(cfg, st.held)
    st.pet_deficit_weighted += weight
    if day < cfg["costs"]["transformation_day"]:
        st.pet_deficit_before_bill += weight
    return weight


def pay_costs(cfg, st, policy, plan, day, ill, deficit_weight):
    saving = effects.living_saving(cfg, st.held)
    for label, amount in costs.scheduled_costs(cfg, day, saving):
        pay(st, label, amount)
    lg = cfg["stress"]["long"]
    st.rent_paid_today = costs.rent_due(cfg, day)
    if st.rent_paid_today:
        pay(st, "rent", st.rent_paid_today)
        st.add_long("rent_paid", lg["rent_paid"])   # withdrawn if rent is paid late tonight (lifelines)
    if day == cfg["costs"]["transformation_day"]:
        st.add_long("pet_event_start", lg["pet_event_start"])
        pay(st, "pet transformation", costs.transformation_bill(cfg, st.seed, st.pet_deficit_before_bill))
        st.add_long("pet_bill_paid", lg["pet_bill_paid"])
    for label, amount in costs.random_costs(cfg, st.seed, day, deficit_weight, effects.damage_factor(cfg, st.held)):
        pay(st, label, amount)
    if ill:
        c = cfg["costs"]
        pay(st, "illness", stream(st.seed, "illness_cost", day).uniform(c["illness_cost_min"], c["illness_cost_max"]))
    for eid, next_day in list(st.subscriptions.items()):
        if day >= next_day:
            pay(st, eid, effects.weekly_price(cfg, eid))
            st.subscriptions[eid] = next_day + 7
    income = effects.saturday_income(cfg, st.held, day)
    if income:
        st.cash += income
        st.log["payments"].append({"day": day, "amount": income, "source": "side_class", "delay": None})
    if st.deferred_rent and (day >= st.deferred_rent["due_day"] or policy.pay_deferred_rent(cfg, st)):
        pay(st, "rent (late)", st.deferred_rent["amount"])
        st.add_long("rent_paid", lg["rent_paid"])
        st.deferred_rent = None


# --- 9: deadlines, her -----------------------------------------------------------------------

def check_deadlines(cfg, st, day):
    for job in st.jobs:
        if job.deadline_day == day and not job.late:
            job.late = True
            days = effects.regular_penalty_days(cfg, st.held) if job.offer.regular else cfg["reputation"]["penalty_days"]
            st.reputation_until[job.offer.rep_key] = day + days


def track_her(cfg, st, plan, fit, day):
    kind = time_demands.count_her_time(cfg, day, plan.her_hours, effects.half_day_hours(cfg, st.held),
                                       effects.crunch_evenings(cfg, st.held))
    if kind == "half_day" and "sunday_brunch" in st.held:
        pay(st, "sunday_brunch", effects.per_use_price(cfg, "sunday_brunch"))
    st.week_evenings += kind == "evening"
    st.week_half_days += kind == "half_day"
    if fit["her_skipped"] and "shared_calendar" in st.held:
        st.log["her_skipped_weeks"].add(cal.week_of(day))
    if cal.is_week_end(day):
        week = cal.week_of(day)
        met = time_demands.week_met(cfg, st.week_evenings, st.week_half_days) and week not in st.log["her_skipped_weeks"]
        st.rel_missed_streak = 0 if met else st.rel_missed_streak + 1
        st.log["rel_weeks"].append({"week": week, "met": met, "streak": st.rel_missed_streak})
        lg = cfg["stress"]["long"]
        st.add_long("her_good_week" if met else "her_week_missed", lg["her_good_week"] if met else lg["her_week_missed"])
        st.week_evenings = st.week_half_days = 0


# --- 11: end of day: loan, crisis, parents' ending ---------------------------------------------

def end_of_day_cash(cfg, st, policy, day):
    if lifelines.loan_open(st):
        lifelines.repay_loan(cfg, st, policy.loan_repayment(cfg, st), day)
    st.log["cash_pre_lifeline"].append(st.cash)
    if st.cash < 0:
        st.log["crisis_days"].append(day)
        lifelines.resolve_crisis(cfg, st, day, policy.lifeline_order(cfg, st))
    reason = lifelines.parents_reason(cfg, st, day)
    if reason:
        st.parents_day, st.parents_reason = day, reason
    st.rent_paid_today = 0


# --- 12: stress --------------------------------------------------------------------------------

def short_day(cfg, st, plan, fit, day, napped, bad):
    """The day's S drivers (§7.2), from the plan as fitted into the day."""
    cut = max(0.0, cfg["day"]["default_sleep_hours"] - plan.sleep_hours)
    short_night = plan.sleep_hours < cfg["stress"]["short"]["short_night_hours"]
    st.short_night_streak = st.short_night_streak + 1 if short_night else 0
    due = [j for j in st.jobs if j.deadline_day == day + 1 and j.words_left > 0]
    session = min(effects.param(cfg, "writing_group", "session_hours"), plan.book_hours) if plan.writing_session else 0.0
    book_relief, hit = effects.book_relief_per_hour(cfg, st.held)
    session_relief, session_hit = effects.book_relief_per_hour(cfg, st.held, session=True)
    st.cap_hit("stress_relief", hit or (session > 0 and session_hit))
    st.last_sleep_cut = cut
    return stress.ShortDay(
        paid_hours=plan.paid_hours + fit["paid_like"], work_hour_over=effects.work_hour_over(cfg, st.held),
        sleep_cut=cut, short_night_streak=st.short_night_streak,
        deadlines_tomorrow=sum(1 for j in due if not j.offer.rush), rush_deadlines_tomorrow=sum(1 for j in due if j.offer.rush),
        rush_in_progress=any(j.offer.rush for j in st.jobs), rush_extra=effects.rush_extra_stress(cfg, st.held),
        bad_interruption=bad,
        leisure_hours=min(fit["leisure"], cfg["day"]["leisure_hours_cap"]),
        leisure_multiplier=effects.leisure_multiplier(cfg, st.held),
        her_hours=plan.her_hours - fit["quiet"],
        book_hours=plan.book_hours - fit["quiet"] - session, book_relief_per_hour=book_relief,
        overlap_hours=fit["quiet"], overlap_relief=effects.param(cfg, "quiet_company", "overlap_relief"),
        session_hours=session, session_relief_per_hour=session_relief,
        extra_relief=effects.daily_relief(cfg, st.held, fit["pet_given"], napped),
    )


def rent_due_soon_short(cfg, st, day):
    """Rent (or deferred rent) due within the window, and cash below it."""
    window = cfg["stress"]["long"]["rent_window_days"]
    due = [cfg["costs"]["rent"] for r in cfg["costs"]["rent_days"] if 1 <= r - day <= window]
    if st.deferred_rent and st.deferred_rent["due_day"] - day <= window:
        due.append(st.deferred_rent["amount"])
    return any(st.cash < amount for amount in due)


def long_day(cfg, st, day, deficit_weight):
    """The day's L drivers (§7.3): the situation at the end of the day, plus the collected events."""
    cost = costs.daily_running_cost(cfg, day, effects.living_saving(cfg, st.held))
    return stress.LongDay(
        runway_days=st.cash / cost, rent_due_soon_short=rent_due_soon_short(cfg, st, day),
        loan_open=lifelines.loan_open(st), crunch_week=cal.week_of(day) in cfg["her"]["crunch_weeks"],
        pet_deficit=deficit_weight, extra_relief=effects.daily_long_relief(cfg, st.held), events=st.long_events,
    )


def update_stress(cfg, st, plan, fit, day, napped, bad, deficit_weight):
    lv = st.levels
    st.stress_today = stress.end_of_day(cfg, lv, short_day(cfg, st, plan, fit, day, napped, bad),
                                        long_day(cfg, st, day, deficit_weight))
    for label, delta in st.long_events:
        st.log["long_events"][label] += delta
    st.long_events = []
    st.log["short"].append(lv.short)
    st.log["long"].append(lv.long)
    st.high_stress_streak = st.high_stress_streak + 1 if st.stress_today > cfg["stress"]["illness_threshold"] else 0
    stress.sleep_recovery(cfg, lv, plan.sleep_hours)


# --- the day ---------------------------------------------------------------------------------

def step(cfg, st, policy, offer_stream):
    day = st.day
    receive_payments(cfg, st, day)
    if day == offer_stream["pe_switch_day"]:
        st.add_long("pe_switch", cfg["stress"]["long"]["pe_switch"])
    shop(cfg, st, policy, day)
    take_offers(cfg, st, policy, offer_stream, day)

    plan = policy.plan_day(cfg, st)
    st.log["slips"].update({"her": plan.her_slip, "pet": plan.pet_slip})
    napped = effects.nap_today(cfg, st.held, st.levels.short)
    fit = fit_plan(cfg, st, plan, day, napped)
    if cal.weekday(day) == 7:
        st.sitter_help_due = 0.0
    if plan.sitter:
        st.sitter_week = cal.week_of(day)
        st.sitter_help_due += effects.param(cfg, "neighbor_sitter", "help_hours_next_sunday")
    if plan.writing_session and plan.book_hours > 0:
        st.writing_week = cal.week_of(day)
    ill = illness_today(cfg, st, day)
    if ill:
        st.log["illness_days"] += 1
        fit["leisure"] += plan.paid_hours + plan.book_hours
        plan.paid_hours = plan.book_hours = 0.0
    lost = interruption_share(cfg, st, day, plan.coworking)
    bad = bad_interruption(cfg, st, day, plan.paid_hours)
    paid_eff, book_eff = plan.paid_hours * (1 - lost), plan.book_hours * (1 - lost)

    base = stress.efficiency(cfg, st.stress) * (1 - cfg["stress"]["sleep_cut_efficiency"] * st.last_sleep_cut)
    projects = count_projects(cfg, st, paid_eff, base) if paid_eff > 0 else 0
    tasks = projects + (1 if book_eff > 0 and not st.book.finished else 0)
    ctx = {"paid_projects": projects, "tasks": tasks, "paid_hours": plan.paid_hours, "coworking": plan.coworking,
           "planning_active": planning_active(st, day), "writing_week": st.writing_week == cal.week_of(day)}
    finished, effect_mult = do_paid_work(cfg, st, paid_eff, base, ctx) if paid_eff > 0 else ([], None)
    deliver(cfg, st, policy, finished, day)
    do_book_work(cfg, st, policy, book_eff, fit["read"] * (1 - lost), base, ctx, day)
    if paid_eff > 0:
        st.workdays += 1
        st.single_project_days += projects == 1
    st.multi_task_days += tasks >= 2
    for name in effects.active_synergies(cfg, st.held):
        st.log["synergy_days"][name] += 1

    deficit_weight = track_pet(cfg, st, plan, fit, day)
    pay_costs(cfg, st, policy, plan, day, ill, deficit_weight)
    check_deadlines(cfg, st, day)
    track_her(cfg, st, plan, fit, day)

    if day in cfg["effects"]["weekly_reflection_days"]:
        offer_effect(cfg, st, policy, "weekly_reflection", day)
    end_of_day_cash(cfg, st, policy, day)
    update_stress(cfg, st, plan, fit, day, napped, bad, deficit_weight)
    log_day(st, plan, effect_mult)


def log_day(st, plan, effect_mult):
    st.log["cash"].append(st.cash)
    st.log["stress"].append(st.stress_today)
    st.log["paid_hours"].append(plan.paid_hours)
    st.log["book_hours"].append(plan.book_hours)
    st.log["effect_mult"].append(effect_mult)


__all__ = ["run", "Plan"]
