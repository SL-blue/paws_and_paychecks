"""Unit tests for the economy rules (spec v0.3): payments, regular clients and fixed jobs, costs,
stress, effects (stacking, caps, synergies), lifelines, the loan and the parents' ending, endings, book."""
import pytest

from sim.src import book, costs, effects, engine, lifelines, metrics, offers, payments, policies, stress
from sim.src import game_calendar as cal
from sim.src.config import load_economy, load_policies, with_overrides
from sim.src.payments import Invoice

NO_TERMS = {"slow_pay_days": None, "late_factor": 1.0, "regular_faster": 0}


@pytest.fixture
def cfg():
    return load_economy()


def make_offer(client="standard_agency", kind="standard", words=1000, regular=None, fixed=None, size="small",
               rush=False, job_id="j1", rate=0.10):
    return offers.Offer(id=job_id, day=1, client=client, kind=kind, rush=rush, words=words, rate=rate,
                        deadline_day=5, size=size, regular=regular, fixed=fixed,
                        rolls={"drop": 0.9, "niche": 0.9, "large": 0.9, "extra": 0.9})


def make_job(late=False, **kw):
    job = offers.Job(offer=make_offer(**kw), accepted_day=1, words_left=0)
    job.late = late
    return job


def new_state(cfg, cash=1000):
    st = engine.new_state(with_overrides(cfg, {"start.cash": cash}), seed=1)
    st.invoices = []
    return st


def invoice(cfg, seed=1, day=10, gross=100, terms=NO_TERMS, **kw):
    return payments.make_invoice(cfg, seed, make_job(**kw), day, gross, terms)


# --- calendar --------------------------------------------------------------------------------

def test_calendar_day1_is_monday_and_working_days_skip_weekends():
    assert cal.weekday(1) == 1 and cal.is_weekend(6) and cal.is_weekend(7)
    assert cal.add_working_days(5, 1) == 8   # Friday + 1 working day = Monday
    assert cal.week_of(29) == 5 and cal.week_of(35) == 5


# --- payment timing --------------------------------------------------------------------------

@pytest.mark.parametrize("client,lo,hi", [("direct", 2, 3), ("standard_agency", 7, 7), ("slow_agency", 14, 14)])
def test_payment_delay_by_client_type(cfg, client, lo, hi):
    no_late = with_overrides(cfg, {"clients.late_share": 0.0})
    for i in range(30):
        inv = invoice(no_late, seed=i, client=client, job_id=f"j{i}")
        assert lo <= inv.arrival_day - 10 <= hi and inv.arrival_day == inv.expected_day


@pytest.mark.parametrize("regular,client,days", [("A", "standard_agency", 5), ("C", "slow_agency", 10)])
def test_regular_clients_pay_faster(cfg, regular, client, days):
    no_late = with_overrides(cfg, {"clients.late_share": 0.0})
    assert invoice(no_late, regular=regular, client=client).expected_day == 10 + days


def test_net_factor_and_late_delivery_penalty(cfg):
    assert invoice(cfg, gross=1000).amount == pytest.approx(780)
    assert invoice(cfg, gross=1000, late=True).amount == pytest.approx(780 * 0.8)


def test_late_payments_share_and_size(cfg):
    extra = [invoice(cfg, seed=s, job_id=f"x{s}") for s in range(4000)]
    lates = [inv.arrival_day - inv.expected_day for inv in extra if inv.arrival_day > inv.expected_day]
    assert 0.17 < len(lates) / len(extra) < 0.23
    assert min(lates) >= 3 and max(lates) <= 7


def test_invoice_reminders_halve_lateness_rounded_up(cfg):
    terms = dict(NO_TERMS, late_factor=0.5)
    pairs = [(invoice(cfg, seed=s, job_id=f"x{s}"), invoice(cfg, seed=s, job_id=f"x{s}", terms=terms)) for s in range(300)]
    for full, half in pairs:
        late = full.arrival_day - full.expected_day
        assert half.arrival_day - half.expected_day == (late + 1) // 2


def test_fast_invoicer_and_steady_hands_terms(cfg):
    no_late = with_overrides(cfg, {"clients.late_share": 0.0})
    fast = dict(NO_TERMS, slow_pay_days=7)
    assert invoice(no_late, client="slow_agency", terms=fast).expected_day == 17
    assert invoice(no_late, client="slow_agency", terms=fast).amount == pytest.approx(78)   # no fee in v0.3
    steady = dict(NO_TERMS, regular_faster=2)
    assert invoice(no_late, regular="A", terms=steady).expected_day == 13


def test_fixed_jobs_pay_on_schedule(cfg):
    story = payments.make_invoice(cfg, 1, make_job(fixed="story", regular="A"), 20, 1000, NO_TERMS)
    assert story.arrival_day == story.expected_day == 33
    day1 = payments.make_invoice(cfg, 1, make_job(fixed="day1", regular="B", client="direct"), 2, 100, NO_TERMS)
    assert day1.arrival_day == 4


def test_deposit_is_deducted_from_the_invoice(cfg):
    job = make_job(size="large", words=10000)
    dep = payments.deposit(cfg, job.offer, 0.3, 1.0)
    inv = payments.make_invoice(cfg, 1, job, 10, job.offer.gross, NO_TERMS, already_paid=dep)
    assert dep == pytest.approx(1000 * 0.78 * 0.3) and inv.amount == pytest.approx(1000 * 0.78 * 0.7)


def test_pre_move_receivables_arrive_on_their_days(cfg):
    invs = payments.receivable_invoices(cfg)
    assert [(i.arrival_day, i.amount) for i in invs] == [(6, 600), (13, 900), (24, 500)]


# --- offers: regular clients and fixed jobs ----------------------------------------------------

def test_fixed_jobs_are_in_the_stream(cfg):
    s = offers.generate_stream(cfg, 5)
    day1 = next(o for o in s["by_day"][1] if o.fixed == "day1")
    story = next(o for o in s["by_day"][8] if o.fixed == "story")
    assert (day1.regular, day1.words, day1.deadline_day) == ("B", 1200, 2)
    assert day1.rate == pytest.approx(0.14 * 1.1) and story.regular == "A" and story.words == 12500


def test_regular_client_habits(cfg):
    weeks = cfg["calendar"]["days"] // 7
    counts = {"A": 0, "B": 0, "C": 0}
    for seed in range(400):
        s = offers.generate_stream(cfg, seed)
        for day, day_offers in s["by_day"].items():
            for o in day_offers:
                if o.regular and not o.fixed and not o.needs:
                    counts[o.regular] += 1
                    assert not cal.is_weekend(day) and not o.rush
                    if o.regular == "A":
                        assert cal.weekday(day) in (1, 2) and o.kind == ("post_edit" if day >= s["pe_switch_day"] else "standard")
                    if o.regular == "B":
                        assert cal.weekday(day) in (3, 4, 5) and o.size == "small"
    per_week = {k: v / 400 / weeks for k, v in counts.items()}
    # day 41-42 are closed, so week 6 loses a few late-week habit jobs
    assert per_week["A"] == pytest.approx(0.9, abs=0.05) and per_week["B"] == pytest.approx(0.8 * 0.95, abs=0.06)
    assert per_week["C"] == pytest.approx(0.45, abs=0.05)


def test_declined_story_job_halves_client_a_offers(cfg):
    st = new_state(cfg)
    a_offer = make_offer(regular="A")
    a_offer.rolls["drop"] = 0.3
    assert offers.visible(cfg, a_offer, [], False, {}, 10, effects)
    assert not offers.visible(cfg, a_offer, [], True, {}, 10, effects)
    a_offer.rolls["drop"] = 0.7
    assert offers.visible(cfg, a_offer, [], True, {}, 10, effects)


def test_extra_offers_need_their_effect(cfg):
    extra = make_offer(client="direct")
    extra.needs, extra.rolls["extra"] = "direct_network", 0.5
    assert not offers.visible(cfg, extra, [], False, {}, 10, effects)
    assert offers.visible(cfg, extra, ["direct_network"], False, {}, 10, effects)


def test_regular_client_reputation_counts_double(cfg):
    st = new_state(cfg)
    job = offers.Job(offer=make_offer(regular="A"), accepted_day=1, words_left=100)
    job.offer.deadline_day = 10
    st.jobs = [job]
    engine.check_deadlines(cfg, st, 10)
    assert st.reputation_until["A"] == 24
    st.held, job.late = ["invoice_reminders"], False
    engine.check_deadlines(cfg, st, 10)
    assert st.reputation_until["A"] == 31


# --- costs -------------------------------------------------------------------------------------

def test_rent_and_fixed_bills(cfg):
    assert costs.rent_due(cfg, 31) == 1500 and costs.rent_due(cfg, 30) == 0
    assert dict(costs.scheduled_costs(cfg, 3))["vet first exam + vaccines"] == 150
    assert costs.pet_food(cfg, 14) == 2 and costs.pet_food(cfg, 15) == 3
    assert dict(costs.scheduled_costs(cfg, 5, living_saving=6))["living"] == 42


def test_transformation_tier_depends_on_care_and_odds_scale(cfg):
    good = [costs.transformation_bill(cfg, s, 0) for s in range(3000)]
    bad = [costs.transformation_bill(cfg, s, 10) for s in range(3000)]
    assert sum(good) / len(good) < sum(bad) / len(bad)
    worse = with_overrides(cfg, {"costs.transformation_odds_scale": 1.25})
    assert costs.tier_probs(worse, cfg["costs"]["transformation_tier_probs"][0]) == pytest.approx([0.5, 0.375, 0.125])


# --- stress ----------------------------------------------------------------------------------

def test_stress_drivers(cfg):
    base = cfg["stress"]["natural_recovery"]
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=8)) == pytest.approx(4 + base)
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=8, work_hour_over=1)) == pytest.approx(2 + base)
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, sleep_cut=2, short_night_streak=2)) == pytest.approx(8 + 3 + base)
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, deadlines_tomorrow=1, rush_deadlines_tomorrow=1)) == pytest.approx(13 + base)
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, rush_in_progress=True, rush_extra=2)) == pytest.approx(5 + base)
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, loan_open=True)) == pytest.approx(3 + base)
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=0)) == pytest.approx(-6 + base)
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, leisure_hours=2, leisure_multiplier=1.2)) == pytest.approx(-4.8 + base)


def test_stress_is_clamped_and_reduces_efficiency(cfg):
    assert stress.apply(cfg, 95, 20) == 100 and stress.apply(cfg, 3, -10) == 0
    assert stress.efficiency(cfg, 40) == 1.0 and stress.efficiency(cfg, 70) == pytest.approx(0.8)


# --- effects: pool, stacking, caps, synergies ----------------------------------------------------

def test_pool_has_30_offered_and_6_shop_effects(cfg):
    assert len(effects.offerable(cfg)) == 30 and len(effects.shop_items(cfg)) == 6
    assert "her_spreadsheet" not in cfg["effects"]["pool"]
    book_effects = sorted(e for e, v in cfg["effects"]["pool"].items() if v.get("book_speed"))
    assert book_effects == ["deep_focus", "margin_notes", "pe_veteran", "quiet_company", "reading_aloud", "writing_group"]


def ctx(**kw):
    base = {"paid_projects": 1, "tasks": 1, "paid_hours": 6, "coworking": False, "planning_active": False}
    return dict(base, **kw)


def test_efficiency_effects_add_within_category_and_cap(cfg):
    held = ["deep_focus", "morning_person", "pomodoro", "sunday_planning"]
    raw = effects.segment_efficiency(cfg, held, 0, ctx(planning_active=True))
    assert raw == pytest.approx(0.08 + 0.08 + 0.06 + 0.05)
    big = with_overrides(cfg, {"effects.size_scale": 2.0})
    raw2 = effects.segment_efficiency(big, held, 0, ctx(planning_active=True))
    bonus, hit = effects.job_efficiency(big, held, raw2, "standard", ctx())
    assert bonus == pytest.approx(0.40) and hit


def test_style_effects_have_downsides(cfg):
    assert effects.segment_efficiency(cfg, ["deep_focus"], 1, ctx(paid_projects=2, tasks=2)) == pytest.approx(-0.06)
    assert effects.segment_efficiency(cfg, ["context_switcher"], 1, ctx()) == pytest.approx(-0.05)
    assert effects.segment_efficiency(cfg, ["night_owl"], 0, ctx()) == pytest.approx(-0.05)
    assert effects.segment_efficiency(cfg, ["pomodoro"], 2, ctx(paid_hours=10)) == pytest.approx(-0.06)
    assert effects.segment_efficiency(cfg, ["pomodoro"], 1, ctx(paid_hours=7.5)) == 0


def test_throughput_cap_and_categories_multiply(cfg):
    held = ["cat_tool", "second_monitor", "termbase"]
    assert effects.throughput_bonus(cfg, held, make_offer(regular="A")) == (pytest.approx(0.15), True)
    assert effects.throughput_bonus(cfg, ["cat_tool"], make_offer(kind="post_edit")) == (pytest.approx(0.10), False)
    assert effects.throughput_bonus(cfg, ["pe_veteran"], make_offer(kind="post_edit"))[0] == pytest.approx(0.15)
    eff, _ = effects.job_efficiency(cfg, ["pe_veteran"], 0.0, "standard", ctx())
    assert eff == pytest.approx(-0.04)


def test_rate_effects_and_cap(cfg):
    assert effects.rate_bonus(cfg, ["specialist_niche"], make_offer()) == pytest.approx(0.15)
    assert effects.rate_bonus(cfg, ["specialist_niche", "loyal_client"], make_offer(regular="A")) == pytest.approx(0.05)
    rush = effects.rate_bonus(cfg, ["specialist_niche", "rush_specialist"], make_offer(rush=True))
    assert rush == pytest.approx(min(0.25, 0.15 + 1.4 / 1.25 - 1))


def test_stress_relief_multiplier_cap(cfg):
    relief, hit = effects.book_relief_per_hour(cfg, ["morning_pages", "reading_aloud"])
    assert relief == pytest.approx(2.5 * 1.5) and hit     # 2.5 + 1 + 0.5 = 4.0 > cap 3.75
    assert effects.book_relief_per_hour(cfg, ["margin_notes"])[0] == pytest.approx(2.0)
    assert effects.book_relief_per_hour(cfg, ["writing_group"], session=True)[0] == pytest.approx(3.75)


def test_book_speed_only_from_book_effects_and_capped(cfg):
    book_ctx = {"paid_projects": 1, "writing_week": True}
    assert effects.book_speed_bonus(cfg, ["morning_person", "cat_tool"], book_ctx)[0] == 0
    bonus, hit = effects.book_speed_bonus(cfg, ["deep_focus", "margin_notes", "writing_group"], book_ctx)
    assert bonus == pytest.approx(0.20) and hit   # 0.08 + 0.08 + 0.10 = 0.26 > cap 0.20
    assert effects.book_speed_bonus(cfg, ["pe_veteran"], book_ctx)[0] == pytest.approx(-0.05)


def test_synergies(cfg):
    held = ["deep_focus", "headphones"]
    bonus, _ = effects.job_efficiency(cfg, held, 0.40, "standard", ctx())
    assert bonus == pytest.approx(0.44)                       # quiet house goes above the cap
    assert effects.job_efficiency(cfg, held, 0.40, "standard", ctx(paid_projects=2))[0] == pytest.approx(0.40)
    assert effects.reading_aloud_hours(cfg, ["reading_aloud"], 2) == 0.5
    assert effects.reading_aloud_hours(cfg, ["reading_aloud", "walk_routine"], 2) == 1.0   # first audience
    assert effects.pay_terms(cfg, ["loyal_client", "termbase"])["regular_faster"] == 2   # steady hands


def test_effect_offers_exclude_held_and_shop_items(cfg):
    held = ["deep_focus", "cat_tool"]
    for i in range(200):
        choices = effects.draw_offer(cfg, 1, i, 10, held)
        assert len(choices) == 3 and len(set(choices)) == 3
        assert not set(choices) & set(held + effects.shop_items(cfg))


def test_time_costs_of_effects(cfg):
    assert effects.time_costs(cfg, ["morning_pages", "frugal_cooking"], 3, False) == (1.0, 0.0)
    assert effects.time_costs(cfg, ["side_class"], 6, False) == (4, 4)            # Saturday class counts as paid
    assert effects.time_costs(cfg, ["sunday_planning", "fast_invoicer"], 7, False) == (1, 0)
    assert effects.time_costs(cfg, ["puppy_class"], 13, False) == (2, 0)          # Saturday of week 2
    assert effects.time_costs(cfg, ["puppy_class"], 34, False) == (0, 0)          # week 5: no class


def test_fit_plan_takes_effect_time_from_free_time_then_paid(cfg):
    st = new_state(cfg)
    st.held = ["side_class"]
    plan = engine.Plan(paid_hours=6, book_hours=0, pet_hours=2.5, her_hours=0, sleep_hours=8)
    fit = engine.fit_plan(cfg, st, plan, 6, napped=False)       # Saturday: 4 h class
    assert plan.paid_hours == 6 and fit["leisure"] == pytest.approx(24 - 8 - 2 - 1 - 2.5 - 4 - 6)
    plan = engine.Plan(paid_hours=10, book_hours=0, pet_hours=2.5, her_hours=0, sleep_hours=8)
    engine.fit_plan(cfg, st, plan, 6, napped=False)             # 8+2+1+2.5+4+10 = 27.5 -> 3.5 h less paid
    assert plan.paid_hours == pytest.approx(6.5)


def test_overlaps_free_time(cfg):
    st = new_state(cfg)
    st.held = ["quiet_company", "evening_walks", "reading_aloud"]
    plan = engine.Plan(paid_hours=6, book_hours=1.5, pet_hours=2.25, her_hours=2, sleep_hours=8)
    fit = engine.fit_plan(cfg, st, plan, 2, napped=False)
    assert (fit["read"], fit["quiet"], fit["walks"]) == (0.5, 1, 1)
    assert fit["pet_given"] == pytest.approx(2.25)
    # alone: pet 2.25 - 0.5 - 1 = 0.75; book 1.5 - 1 = 0.5 separate
    assert fit["leisure"] == pytest.approx(24 - 8 - 2 - 1 - 0.75 - 6 - 0.5 - 2)


def test_her_effects(cfg):
    assert effects.crunch_evenings(cfg, ["shared_calendar"]) == [2, 4, 5]
    from sim.src import time_demands
    assert time_demands.count_her_time(cfg, 6, 3, effects.half_day_hours(cfg, ["sunday_brunch"])) == "half_day"
    assert time_demands.count_her_time(cfg, 6, 3) == "evening"


# --- lifelines, the loan, the parents' ending ----------------------------------------------------

def test_rent_late_defers_rent_with_fee(cfg):
    st = new_state(cfg, cash=-200)
    st.rent_paid_today = 1500
    lifelines.resolve_crisis(cfg, st, 31, ["early_payment", "borrow"])
    assert st.cash == 1300 and st.deferred_rent == {"amount": 1575, "due_day": 38}


def test_early_payment_picks_covering_invoice_at_fee(cfg):
    st = new_state(cfg, cash=-100)
    st.invoices = [Invoice("a", 500, 5, 12, 12), Invoice("b", 200, 5, 12, 12), Invoice("r", 900, 0, 13, 13, "receivable")]
    lifelines.resolve_crisis(cfg, st, 10, ["early_payment", "borrow"])
    assert st.cash == pytest.approx(-100 + 180) and [i.id for i in st.invoices] == ["a", "r"]


def test_borrowing_is_last_and_raises_stress(cfg):
    st = new_state(cfg, cash=-250)
    st.stress = 20
    st.invoices = [Invoice("a", 500, 5, 12, 12)]
    lifelines.resolve_crisis(cfg, st, 10, ["borrow", "early_payment"])   # order asks to borrow first
    assert st.loan is None and st.cash == pytest.approx(200)
    st.cash = -100
    lifelines.resolve_crisis(cfg, st, 11, ["borrow", "early_payment"])
    assert st.loan["amount"] == 300 and st.cash == 200 and st.loan["due_day"] == 18 and st.stress == 35


def test_parents_ending_when_loan_is_overdue(cfg):
    st = new_state(cfg, cash=-100)
    lifelines.resolve_crisis(cfg, st, 10, ["borrow"])
    assert lifelines.parents_reason(cfg, st, 16) is None
    lifelines.repay_loan(st, 100, 16)
    assert lifelines.parents_reason(cfg, st, 17) == "loan"
    lifelines.repay_loan(st, 1000, 17)
    assert lifelines.parents_reason(cfg, st, 17) is None and st.loan["repaid_day"] == 17


def test_parents_ending_below_floor_only_without_lifelines(cfg):
    st = new_state(cfg, cash=-400)
    assert lifelines.parents_reason(cfg, st, 10) is None          # borrowing is still possible
    lifelines.resolve_crisis(cfg, st, 10, ["borrow"])
    assert st.cash == 200
    st.cash = -250
    assert lifelines.parents_reason(cfg, st, 11) is None          # below 0, above the floor
    st.cash = -301
    assert lifelines.parents_reason(cfg, st, 12) == "floor"


def test_parents_ending_stops_the_run(cfg):
    broke = with_overrides(cfg, {"start.cash": -2000})
    result = engine.run(broke, policies.make("careful", load_policies()), seed=1)
    assert result["parents"] and result["parents_day"] == 1 and result["tier"] == "parents"
    assert len(result["cash_series"]) == 1


def test_policies_repay_the_loan_keeping_a_reserve(cfg):
    st = new_state(cfg, cash=500)
    st.day, st.loan = 12, {"amount": 400, "left": 400, "day": 10, "due_day": 17}
    pol = policies.make("careful", load_policies())
    assert pol.loan_repayment(cfg, st) == pytest.approx(500 - 2 * costs.daily_running_cost(cfg, 12))
    st.day = 17
    assert pol.loan_repayment(cfg, st) == 500


# --- endings ---------------------------------------------------------------------------------------

def test_ending_tiers():
    all_met = dict.fromkeys(metrics.GOALS, True)
    assert metrics.ending_tier(all_met, False) == "best"
    assert metrics.ending_tier(dict(all_met, book=False), False) == "good"
    assert metrics.ending_tier(dict(all_met, pet=False), False) == "mixed"
    assert metrics.ending_tier(dict(all_met, pet=False, stress=False, book=False), False) == "hard"
    assert metrics.ending_tier(all_met, True) == "parents"


def test_finance_and_stress_goals(cfg):
    st = new_state(cfg)
    assert metrics.finance_tier(cfg, st, 1500) == "good" and metrics.finance_tier(cfg, st, 1499) == "okay"
    st.loan = {"amount": 100, "left": 50, "day": 40, "due_day": 47}
    assert metrics.finance_tier(cfg, st, 3000) == "okay"
    series = [10] * 35 + [60] * 7
    assert metrics.stress_goal(cfg, series)[0]
    assert not metrics.stress_goal(cfg, [75] * 7 + [10] * 35)[0]          # 7 days above 70


# --- book ------------------------------------------------------------------------------------

def test_book_sized_by_h_and_milestones(cfg):
    h = cfg["book"]["remaining_hours"]
    for seed in range(50):
        b = book.new_book(cfg, seed)
        assert h * 0.95 - 1e-9 <= b.remaining_hours_nominal <= h * 1.05 + 1e-9
    b = book.new_book(cfg, 1)
    third = b.words_left / 3
    assert book.work(b, third, 10, day=5) == 1
    assert book.work(b, third, 10, day=6) == 1
    book.work(b, third * 0.6, 6, day=7)
    assert b.near_finished(0.5) and not b.finished
    assert book.work(b, third, 20, day=9) == 1 and b.finished and not b.near_finished(0.5)


# --- determinism and policy visibility -------------------------------------------------------

def test_runs_are_deterministic(cfg):
    pcfg = load_policies()
    for name in ("careful", "careless", "grinder", "book_heavy"):
        a = engine.run(cfg, policies.make(name, pcfg), seed=7)
        b = engine.run(cfg, policies.make(name, pcfg), seed=7)
        assert a == b


def test_offer_stream_does_not_depend_on_policy(cfg):
    a = offers.generate_stream(cfg, 3)
    b = offers.generate_stream(cfg, 3)
    assert [o.id for d in a["by_day"].values() for o in d] == [o.id for d in b["by_day"].values() for o in d]


def test_only_greedy_reads_the_offer_stream():
    pcfg = load_policies()
    assert not any(policies.make(n, pcfg).uses_foresight for n in ("careful", "book_heavy", "grinder", "careless"))
    assert all(c.uses_foresight for c in policies.greedy_candidates(pcfg))


def test_day1_job_always_taken_and_story_variant(cfg):
    pcfg = load_policies()
    forced = with_overrides(cfg, {"story_job.always_taken": True})
    for seed in range(20):
        r = engine.run(forced, policies.make("book_heavy", pcfg), seed)
        assert r["story_decision"] == "forced" and r["regular_jobs"]["B"] >= 1
