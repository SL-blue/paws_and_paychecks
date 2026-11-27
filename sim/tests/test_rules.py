"""Unit tests for the economy rules: payments, costs, stress, effects, lifelines, bankruptcy, book."""
import pytest

from sim.src import book, costs, effects, engine, lifelines, offers, payments, policies, stress
from sim.src import game_calendar as cal
from sim.src.config import load_economy, load_policies, with_overrides
from sim.src.payments import Invoice


@pytest.fixture
def cfg():
    return load_economy()


def make_job(client="standard_agency", kind="standard", words=1000, story=False, late=False, job_id="j1"):
    offer = offers.Offer(id=job_id, day=1, client=client, kind=kind, rush=False, words=words,
                         rate=0.10, deadline_day=5, story=story)
    job = offers.Job(offer=offer, accepted_day=1, words_left=0)
    job.late = late
    return job


def new_state(cfg, cash=1000):
    st = engine.new_state(with_overrides(cfg, {"start.cash": cash}), seed=1)
    st.invoices = []
    return st


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
        inv = payments.make_invoice(no_late, seed=i, job=make_job(client, job_id=f"j{i}"), day=10, gross=100)
        assert lo <= inv.arrival_day - 10 <= hi
        assert inv.arrival_day == inv.expected_day


def test_net_factor_and_late_delivery_penalty(cfg):
    on_time = payments.make_invoice(cfg, 1, make_job(), 10, gross=1000)
    late = payments.make_invoice(cfg, 1, make_job(late=True), 10, gross=1000)
    assert on_time.amount == pytest.approx(780)
    assert late.amount == pytest.approx(780 * 0.8)


def test_late_payments_share_and_size(cfg):
    extra = [payments.make_invoice(cfg, s, make_job(job_id=f"x{s}"), 10, 100) for s in range(4000)]
    lates = [inv.arrival_day - inv.expected_day for inv in extra if inv.arrival_day > inv.expected_day]
    assert 0.17 < len(lates) / len(extra) < 0.23
    assert min(lates) >= 3 and max(lates) <= 7


def test_fast_invoicer_shortens_slow_agency_and_costs_fee(cfg):
    fi = {"slow_pay_days": 7, "fee": 0.03}
    no_late = with_overrides(cfg, {"clients.late_share": 0.0})
    inv = payments.make_invoice(no_late, 1, make_job("slow_agency"), 10, 1000, fast_invoicer=fi)
    assert inv.arrival_day == 17 and inv.amount == pytest.approx(780 * 0.97)


def test_story_job_is_paid_in_week_5(cfg):
    inv = payments.make_invoice(cfg, 1, make_job(story=True), day=18, gross=1250)
    assert inv.arrival_day == cfg["story_job"]["pay_day"] and cal.week_of(inv.arrival_day) == 5
    later = payments.make_invoice(cfg, 1, make_job(story=True), day=30, gross=1250)
    assert later.arrival_day == 37   # delivered too late for day 33: 7 days after delivery


def test_pre_move_receivables_arrive_on_their_days(cfg):
    st = engine.new_state(cfg, 1)
    arrivals = {inv.arrival_day: inv.amount for inv in st.invoices}
    assert arrivals == {6: 600, 13: 900, 24: 500}


# --- rent and bills --------------------------------------------------------------------------

def test_rent_and_fixed_bills(cfg):
    assert costs.rent_due(cfg, 31) == 1500 and costs.rent_due(cfg, 1) == 0   # day-1 rent paid before start
    day3 = dict(costs.scheduled_costs(cfg, 3))
    assert day3["vet first exam + vaccines"] == 150 and day3["living"] == 48 and day3["pet food"] == 2
    assert dict(costs.scheduled_costs(cfg, 15))["pet food"] == 3   # +50% after growth stage


def test_transformation_tier_depends_on_care(cfg):
    good = [costs.transformation_bill(cfg, s, 0) for s in range(2000)]
    bad = [costs.transformation_bill(cfg, s, 10) for s in range(2000)]
    assert set(good) <= {300, 500, 800}
    assert sum(good) / len(good) < sum(bad) / len(bad)


def test_total_fixed_costs_over_a_run(cfg):
    total = sum(a for d in range(1, 43) for _, a in costs.scheduled_costs(cfg, d)) + costs.rent_due(cfg, 31)
    pet_food = 14 * 2 + 28 * 3
    assert total == pytest.approx(42 * 48 + pet_food + 250 + 150 + 100 + 100 + 1500)


# --- stress ----------------------------------------------------------------------------------

def test_stress_drivers(cfg):
    base = stress.daily_delta(cfg, stress.StressDay(paid_hours=6))
    assert base == -3                                                     # natural recovery only
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=9)) == -3 + 6
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, sleep_cut=2, short_night_streak=2)) == -3 + 8 + 3
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, deadlines_tomorrow=2)) == -3 + 10
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, low_runway=True, rush_in_progress=True)) == -3 + 6
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=6, leisure_hours=2, book_hours=2)) == -3 - 4 - 5
    assert stress.daily_delta(cfg, stress.StressDay(paid_hours=0)) == -3 - 6


def test_stress_is_clamped_and_reduces_efficiency(cfg):
    assert stress.apply(cfg, 95, 20) == 100 and stress.apply(cfg, 3, -10) == 0
    assert stress.efficiency(cfg, 40) == 1.0
    assert stress.efficiency(cfg, 80) == pytest.approx(0.70)


# --- effects: stacking and caps --------------------------------------------------------------

def test_efficiency_effects_add_within_category_and_cap(cfg):
    held = ["deep_focus", "morning_person", "coworking"]
    morning, midday, evening = effects.efficiency_segments(cfg, held, paid_projects=1, tasks=1, coworking_today=True)
    assert morning == pytest.approx(0.15 + 0.15 + 0.10)
    assert midday == pytest.approx(0.25) and evening == pytest.approx(0.15)
    big = effects.efficiency_segments(with_overrides(cfg, {"effects.size_scale": 2.0}), held, 1, 1, True)[0]
    assert effects.capped(cfg, big) == pytest.approx(0.40)


def test_style_effects_have_downsides(cfg):
    assert effects.efficiency_segments(cfg, ["deep_focus"], 2, 2, False)[1] == pytest.approx(-0.10)
    assert effects.efficiency_segments(cfg, ["context_switcher"], 1, 1, False)[1] == pytest.approx(-0.08)


def test_categories_multiply(cfg):
    st = new_state(cfg)
    st.held = ["deep_focus", "cat_tool"]
    job = make_job(words=10_000)
    job.words_left = 10_000
    st.jobs = [job]
    bonuses = effects.efficiency_segments(cfg, st.held, 1, 1, False)
    engine.do_paid_work(cfg, st, hours=1, base=1.0, bonuses=bonuses)
    assert 10_000 - job.words_left == pytest.approx(310 * 1.15 * 1.15)


def test_stress_relief_multiplier_cap(cfg):
    assert effects.book_relief_per_hour(cfg, []) == 2.5
    assert effects.book_relief_per_hour(cfg, ["morning_pages"]) == 3.5
    strong = with_overrides(cfg, {"effects.size_scale": 3.0})
    assert effects.book_relief_per_hour(strong, ["morning_pages"]) == pytest.approx(2.5 * 1.5)


def test_effect_offers_exclude_held_and_shop_items(cfg):
    held = ["deep_focus", "night_owl"]
    for i in range(200):
        choices = effects.draw_offer(cfg, 1, i, 10, held, had_evening_with_her=False)
        assert len(choices) == 3 and len(set(choices)) == 3
        assert not set(choices) & set(held + effects.shop_items(cfg) + ["her_spreadsheet"])


# --- lifelines and bankruptcy ----------------------------------------------------------------

def test_rent_late_defers_rent_with_fee(cfg):
    st = new_state(cfg, cash=-200)
    st.rent_paid_today = 1500
    bankrupt = lifelines.resolve_crisis(cfg, st, 31, ["early_payment", "borrow"])
    assert not bankrupt and st.cash == 1300
    assert st.deferred_rent == {"amount": 1575, "due_day": 38}


def test_early_payment_picks_covering_invoice_at_fee(cfg):
    st = new_state(cfg, cash=-100)
    st.invoices = [Invoice("a", 500, 5, 12, 12), Invoice("b", 200, 5, 12, 12), Invoice("r", 900, 0, 13, 13, "receivable")]
    lifelines.resolve_crisis(cfg, st, 10, ["early_payment", "borrow"])
    assert st.cash == pytest.approx(-100 + 180) and [i.id for i in st.invoices] == ["a", "r"]


def test_borrow_up_to_max_and_each_lifeline_once(cfg):
    st = new_state(cfg, cash=-250)
    lifelines.resolve_crisis(cfg, st, 10, ["borrow", "early_payment"])
    assert st.debt == 450 and st.cash == 200
    st.cash = -50
    assert lifelines.resolve_crisis(cfg, st, 12, ["borrow", "early_payment"])   # nothing left -> bankrupt


def test_bankrupt_below_floor_even_with_lifelines(cfg):
    st = new_state(cfg, cash=-301)
    assert lifelines.resolve_crisis(cfg, st, 10, ["borrow"])


def test_bankruptcy_is_an_ending_path_run_continues(cfg):
    broke = with_overrides(cfg, {"start.cash": -2000})
    result = engine.run(broke, policies.make("careful", load_policies()), seed=1)
    assert result["bankrupt"] and result["bankrupt_day"] == 1
    assert len(result["cash_series"]) == 42


# --- book ------------------------------------------------------------------------------------

def test_book_sized_by_hours_and_milestones(cfg):
    for seed in range(50):
        b = book.new_book(cfg, seed)
        assert 60 - 1e-9 <= b.remaining_hours_nominal <= 80 + 1e-9
        assert 9000 - 1e-6 <= b.words_left <= 12000 + 1e-6
    b = book.new_book(cfg, 1)
    third = b.words_left / 3
    assert book.work(b, third, 10, day=5) == 1
    assert book.work(b, 2 * third, 20, day=9) == 2 and b.finished


# --- determinism and policy visibility -------------------------------------------------------

def test_runs_are_deterministic(cfg):
    pcfg = load_policies()
    for name in ("careful", "careless", "grinder"):
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
