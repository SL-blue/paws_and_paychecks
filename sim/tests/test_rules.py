"""Unit tests for the economy rules (spec v0.4): payments, regular clients and fixed jobs, costs,
two-layer stress and conversion, effects (stacking, caps, synergies, skip, shop), lifelines, the loan and
the parents' ending, money tiers and endings, book, policies (imperfect careful)."""
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
    assert day1.rate == pytest.approx(0.14 * 1.1) and story.regular == "A" and story.words == 9000
    assert story.size == "medium"                     # 9,000 words: between the medium and large tables


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

def test_short_term_stress_drivers(cfg):
    sd = stress.ShortDay
    assert stress.short_delta(cfg, sd(paid_hours=8)) == pytest.approx(4)
    assert stress.short_delta(cfg, sd(paid_hours=8, work_hour_over=1)) == pytest.approx(2)
    assert stress.short_delta(cfg, sd(paid_hours=6, sleep_cut=2, short_night_streak=2)) == pytest.approx(8 + 3)
    assert stress.short_delta(cfg, sd(paid_hours=6, deadlines_tomorrow=1, rush_deadlines_tomorrow=1)) == pytest.approx(13)
    assert stress.short_delta(cfg, sd(paid_hours=6, rush_in_progress=True, rush_extra=2)) == pytest.approx(5)
    assert stress.short_delta(cfg, sd(paid_hours=6, bad_interruption=True)) == pytest.approx(2)
    assert stress.short_delta(cfg, sd(paid_hours=0)) == pytest.approx(-6)
    assert stress.short_delta(cfg, sd(paid_hours=6, her_hours=2, book_hours=1)) == pytest.approx(-4 - 2)
    # leisure: -2/h for the first 2 h, then -1/h; boundaries' multiplier scales it
    assert stress.short_delta(cfg, sd(paid_hours=6, leisure_hours=3)) == pytest.approx(-5)
    assert stress.short_delta(cfg, sd(paid_hours=6, leisure_hours=2, leisure_multiplier=1.2)) == pytest.approx(-4.8)


def test_long_term_stress_drivers(cfg):
    lg = cfg["stress"]["long"]
    ld = stress.LongDay
    assert stress.long_delta(cfg, ld(runway_days=10)) == lg["runway_low"]
    assert stress.long_delta(cfg, ld(runway_days=5)) == lg["runway_very_low"]          # instead of, not plus
    assert stress.long_delta(cfg, ld(rent_due_soon_short=True, loan_open=True, crunch_week=True, pet_deficit=2)) == \
        pytest.approx(lg["rent_due"] + lg["loan_open"] + lg["her_crunch_day"] + 2 * lg["pet_deficit_day"])
    # payments relieve L, at most payment_relief_max per day; other events add up
    many = int(lg["payment_relief_max"] / -lg["payment_arrives"]) + 2
    events = [("payment", lg["payment_arrives"])] * many + [("rent_paid", lg["rent_paid"])]
    assert stress.long_delta(cfg, ld(events=events)) == pytest.approx(-lg["payment_relief_max"] + lg["rent_paid"])
    assert stress.long_delta(cfg, ld(extra_relief=0.5)) == -0.5


def levels(cfg, short=0.0, long=0.0):
    return stress.Levels(short=short, long=long, cap=cfg["stress"]["max"])


def test_conversion_too_much_and_too_long(cfg):
    c = cfg["stress"]["conversion"]
    lv = levels(cfg, short=c["threshold"] + 20, long=10)
    stress.convert(cfg, lv)
    assert lv.short == pytest.approx(c["threshold"] + 20 * (1 - c["share"]))
    assert lv.long == pytest.approx(10 + 20 * c["share"]) and lv.conversions == 1
    no_excess = with_overrides(cfg, {"stress.conversion.threshold": 100})   # only the "too long" rule
    lv = levels(cfg, short=c["sustained_level"] + 1, long=0)
    for day in range(1, c["sustained_days"] + 2):
        before = lv.long
        stress.convert(no_excess, lv)
        gained = lv.long - before
        assert gained == pytest.approx(c["sustained_per_day"] if day >= c["sustained_days"] else 0.0)


def test_day_and_night_order(cfg):
    """S and L change, conversion, calm-day recovery; the day's T is recorded; sleep lowers S after."""
    lg, s = cfg["stress"]["long"], cfg["stress"]["short"]
    lv = levels(cfg, short=10, long=20)
    t = stress.end_of_day(cfg, lv, stress.ShortDay(paid_hours=8), stress.LongDay())
    assert lv.short == pytest.approx(14) and lv.long == pytest.approx(20 + lg["calm_day"])
    assert t == pytest.approx(lv.short + lv.long)
    stress.sleep_recovery(cfg, lv, 8)
    assert lv.short == pytest.approx(14 * (1 - s["sleep_recovery_full"]))
    stress.sleep_recovery(cfg, lv, 6)
    assert lv.short == pytest.approx(14 * (1 - s["sleep_recovery_full"]) * (1 - s["sleep_recovery_short"]))


def test_no_calm_day_recovery_when_short_term_stress_is_high(cfg):
    cfg = with_overrides(cfg, {"stress.conversion.threshold": 100})       # keep conversion out of it
    lg = cfg["stress"]["long"]
    lv = levels(cfg, short=lg["calm_day_below"] + 5, long=20)
    stress.end_of_day(cfg, lv, stress.ShortDay(paid_hours=6), stress.LongDay())
    assert lv.long == pytest.approx(20)


def test_stress_is_clamped_and_reduces_efficiency(cfg):
    lv = levels(cfg, short=95, long=0)
    stress.end_of_day(cfg, lv, stress.ShortDay(paid_hours=12, sleep_cut=4), stress.LongDay(runway_days=0))
    assert lv.short <= 100 and lv.total <= 100
    lv = levels(cfg, short=3, long=0)
    stress.end_of_day(cfg, lv, stress.ShortDay(paid_hours=0, leisure_hours=4), stress.LongDay())
    assert lv.short == 0 and lv.long == 0
    assert levels(cfg, short=70, long=60).total == 100
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
    base = -cfg["stress"]["short"]["book_hour"]
    capped = base * (1 + cfg["effects"]["caps"]["stress_relief"])
    relief, hit = effects.book_relief_per_hour(cfg, ["morning_pages", "reading_aloud"])
    assert relief == pytest.approx(capped) and hit       # 2 + 1 + 0.5 = 3.5 > cap 2.6
    assert effects.book_relief_per_hour(cfg, ["reading_aloud"]) == (pytest.approx(2.5), False)
    assert effects.book_relief_per_hour(cfg, ["margin_notes"])[0] == pytest.approx(1.5)
    assert effects.book_relief_per_hour(cfg, ["writing_group"], session=True)[0] == pytest.approx(capped)


def test_stress_effects_map_to_the_two_layers(cfg):
    assert effects.daily_long_relief(cfg, ["morning_pages"]) == 0.5 and effects.daily_long_relief(cfg, ["boundaries"]) == 0
    assert effects.daily_relief(cfg, ["morning_pages", "boundaries"], 0, False) == 2
    assert effects.nap_today(cfg, ["nap_habit"], 51) and not effects.nap_today(cfg, ["nap_habit"], 50)


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


def test_borrowing_is_last_and_raises_short_term_stress(cfg):
    st = new_state(cfg, cash=-250)
    st.levels.short = 20
    st.invoices = [Invoice("a", 500, 5, 12, 12)]
    lifelines.resolve_crisis(cfg, st, 10, ["borrow", "early_payment"])   # order asks to borrow first
    assert st.loan is None and st.cash == pytest.approx(200)
    st.cash = -100
    lifelines.resolve_crisis(cfg, st, 11, ["borrow", "early_payment"])
    assert st.loan["amount"] == 300 and st.cash == 200 and st.loan["due_day"] == 18
    assert st.levels.short == 20 + cfg["stress"]["short"]["borrow_once"]


def test_loan_is_capped(cfg):
    st = new_state(cfg, cash=-900)
    lifelines.borrow(cfg, st, 10)
    assert st.loan["amount"] == cfg["lifelines"]["borrow_max"] == 400


def test_parents_ending_when_loan_is_overdue(cfg):
    st = new_state(cfg, cash=-100)
    lifelines.resolve_crisis(cfg, st, 10, ["borrow"])
    assert lifelines.parents_reason(cfg, st, 16) is None
    lifelines.repay_loan(cfg, st, 100, 16)
    assert lifelines.parents_reason(cfg, st, 17) == "loan"
    lifelines.repay_loan(cfg, st, 1000, 17)
    assert lifelines.parents_reason(cfg, st, 17) is None and st.loan["repaid_day"] == 17
    assert ("loan_repaid", cfg["stress"]["long"]["loan_repaid"]) in st.long_events


def test_parents_ending_below_floor_only_without_lifelines(cfg):
    st = new_state(cfg, cash=-400)
    assert lifelines.parents_reason(cfg, st, 10) is None          # borrowing is still possible
    lifelines.resolve_crisis(cfg, st, 10, ["borrow"])
    assert st.cash == pytest.approx(-400 + 400)                   # capped at 400
    st.cash = -99
    assert lifelines.parents_reason(cfg, st, 11) is None          # below 0, above the floor
    st.cash = -101
    assert lifelines.parents_reason(cfg, st, 12) == "floor"


def test_rent_late_withdraws_the_rent_paid_relief(cfg):
    st = new_state(cfg, cash=-200)
    st.rent_paid_today = 1500
    st.add_long("rent_paid", -5)
    lifelines.resolve_crisis(cfg, st, 31, ["early_payment", "borrow"])
    assert not any(label == "rent_paid" for label, _ in st.long_events)


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


def test_money_tiers(cfg):
    st = new_state(cfg)
    bar = cfg["endings"]["finance_good_min_value"]
    assert bar == 750
    assert metrics.finance_tier(cfg, st, bar) == "good" and metrics.finance_tier(cfg, st, bar - 1) == "okay"
    st.loan = {"amount": 100, "left": 50, "day": 40, "due_day": 47}        # open, not yet due on day 42
    assert metrics.finance_tier(cfg, st, 3000) == "poor"
    st.loan, st.deferred_rent = None, {"amount": 1575, "due_day": 45}
    assert metrics.finance_tier(cfg, st, 3000) == "poor"
    st.parents_day = 20
    assert metrics.finance_tier(cfg, st, 3000) == "parents"


def test_stress_goal_uses_total_and_long_term_stress(cfg):
    low_l = [5] * 42
    assert metrics.stress_goal(cfg, [10] * 35 + [60] * 7, low_l)[0]
    assert not metrics.stress_goal(cfg, [75] * 7 + [10] * 35, low_l)[0]          # 7 days above 70
    assert not metrics.stress_goal(cfg, [30] * 42, [5] * 41 + [41])[0]            # L above 40 on day 42


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


# --- v0.4: changed effects, skip, shop, imperfect careful ------------------------------------------

def test_deposit_terms_medium_and_large_with_later_remainder(cfg):
    assert effects.deposit_share(cfg, ["deposit_terms"], make_offer(size="medium")) == pytest.approx(0.30)
    assert effects.deposit_share(cfg, ["deposit_terms"], make_offer(size="small")) == 0
    no_late = with_overrides(cfg, {"clients.late_share": 0.0})
    job = make_job(size="medium", words=4000)
    inv = payments.make_invoice(no_late, 1, job, 10, job.offer.gross, NO_TERMS, 100, effects.deposit_extra_days(cfg, 100))
    assert inv.expected_day == 10 + 7 + 3
    large = make_offer(size="large")
    large.rolls["large"] = 0.0                                    # no offer penalty any more
    assert offers.visible(cfg, large, ["deposit_terms"], False, {}, 10, effects)


def test_neighbor_costs_two_hours_the_following_sunday(cfg):
    assert "price_per_use" not in cfg["effects"]["pool"]["neighbor_sitter"]
    assert effects.time_costs(cfg, ["neighbor_sitter"], 7, False, neighbor_help=2) == (2, 0)
    assert effects.time_costs(cfg, ["neighbor_sitter"], 6, False, neighbor_help=2) == (0, 0)


def test_side_class_and_brunch_changes(cfg):
    assert effects.saturday_income(cfg, ["side_class"], 6) == 60
    assert effects.half_day_hours(cfg, ["sunday_brunch"]) == 2


def test_skip_when_no_effect_beats_the_skip_reward(cfg, monkeypatch):
    from sim.src import effect_value
    pol = policies.make("careful", load_policies())
    st = new_state(cfg)
    reward = effect_value.skip_value(cfg, pol.p)
    assert reward == cfg["effects"]["skip_long_relief"] * pol.p["value_weights"]["stress_per_point"]
    monkeypatch.setattr(effect_value, "value", lambda cfg, st, eid, p, shop=False: reward - 1)
    assert pol.pick_effect(cfg, st, ["deep_focus", "cat_tool", "night_owl"], "weekly_reflection") is None
    monkeypatch.setattr(effect_value, "value", lambda cfg, st, eid, p, shop=False: reward + (eid == "cat_tool"))
    assert pol.pick_effect(cfg, st, ["deep_focus", "cat_tool", "night_owl"], "weekly_reflection") == "cat_tool"


def test_skipping_lowers_long_term_stress(cfg):
    class Skipper(policies.Careful):
        def pick_effect(self, cfg, st, choices, source):
            return None
    st = new_state(cfg)
    engine.offer_effect(cfg, st, Skipper("careful", load_policies()["careful"]), "weekly_reflection", 7)
    assert st.held == [] and st.long_events == [("skip", -cfg["effects"]["skip_long_relief"])]


def test_shop_buys_by_value_and_keeps_a_reserve(cfg, monkeypatch):
    from sim.src import effect_value
    pol = policies.make("careful", load_policies())
    st = new_state(cfg, cash=5000)
    st.day = 5
    monkeypatch.setattr(effect_value, "value", lambda cfg, st, eid, p, shop=False: 130 if eid == "headphones" else 0)
    assert pol.shop(cfg, st) == ["headphones"]                       # 130 > price 120
    st.cash = 120 + 14 * 50 - 1                                       # would dip below 14 days of costs
    assert pol.shop(cfg, st) == []
    assert effect_value.price_now(cfg, st, "coworking") == 60 * 6     # weekly price x weeks left (days 5-42)


def test_imperfect_careful_inherits_careful(cfg):
    pcfg = load_policies()
    p = policies.params("imperfect_careful", pcfg)
    assert p["weekday_paid_hours"] == pcfg["careful"]["weekday_paid_hours"] and p["her_skip_chance"] == 0.30
    assert "inherits" not in p


def test_imperfect_careful_slips_only_under_pressure(cfg):
    pcfg = load_policies()
    pol = policies.make("imperfect_careful", pcfg)
    calm, pressed = [], []
    for seed in range(400):
        st = new_state(cfg)
        st.seed, st.day = seed, 3                                     # Wednesday: a planned evening with her
        calm.append(pol.plan_day(cfg, st))
        st.levels.long = pcfg["imperfect_careful"]["pressure_stress"] + 1
        pressed.append(pol.plan_day(cfg, st))
    assert not any(p.her_slip or p.pet_slip for p in calm)
    her = sum(p.her_slip for p in pressed) / 400
    pet = sum(p.pet_slip for p in pressed) / 400
    assert 0.24 < her < 0.36 and 0.15 < pet < 0.25
    assert all(p.her_hours == 0 for p in pressed if p.her_slip)


def test_imperfect_careful_accepts_one_unfit_job_in_a_slip_week(cfg):
    pcfg = load_policies()
    pol = policies.make("imperfect_careful", pcfg)
    huge = make_offer(words=60000, job_id="huge")
    huge.deadline_day = 3
    slips = 0
    for seed in range(300):
        st = new_state(cfg)
        st.seed, st.day = seed, 2
        first = pol.choose_offers(cfg, st, [huge])
        again = pol.choose_offers(cfg, st, [huge])                    # at most one per week
        slips += len(first)
        assert not again
    assert 0.10 < slips / 300 < 0.20
