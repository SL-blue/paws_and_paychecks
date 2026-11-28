"""Payments (SIM_BASELINE.md §3.3, §3.5-3.6): invoices on delivery, compressed payment terms,
regular-client terms, late payments, deposits (the rest of a deposit job is paid later).

An invoice has a public `expected_day` (what the "money owed" list shows) and a hidden
`arrival_day` (when the cash really lands). Policies may only read `expected_day`.
"""
import math
from dataclasses import dataclass

from .rng import stream


@dataclass
class Invoice:
    id: str
    amount: float          # net $
    delivered_day: int
    expected_day: int      # shown to the player
    arrival_day: int       # hidden: includes any lateness
    source: str = "job"    # job / deposit / receivable


def base_delay(cfg, rng, offer, terms):
    """Days from delivery to the expected payment, before lateness."""
    c = cfg["clients"][offer.client]
    delay = round(rng.uniform(c["pay_days_min"], c["pay_days_max"]))
    if offer.regular:
        rc = cfg["regular_clients"]
        own = rc[offer.regular]["pay_days"]
        if own is not None:
            delay = round(own * rc["pay_days_scale"])
        delay = max(1, delay - terms["regular_faster"])
    if terms["slow_pay_days"] is not None and offer.client == "slow_agency":
        delay = min(delay, round(terms["slow_pay_days"]))
    return delay


def make_invoice(cfg, seed, job, day, gross, terms, already_paid=0.0, extra_days=0):
    """Invoice for a job delivered on `day`. `terms` = effects.pay_terms(); `already_paid` = a
    deposit received at acceptance (net $), deducted from this invoice; `extra_days` = days added to
    the normal terms (deposit terms pay the remainder later)."""
    clients, offer = cfg["clients"], job.offer
    rng = stream(seed, "payment", job.id)
    delay = base_delay(cfg, rng, offer, terms)
    late_roll, late_extra = rng.random(), rng.randint(clients["late_days_min"], clients["late_days_max"])
    net = gross * cfg["work"]["net_factor"]
    if job.late:
        net *= 1 - cfg["reputation"]["late_payment_penalty"]
    net = max(0.0, net - already_paid)
    expected = day + delay + extra_days
    if offer.fixed == "story":
        expected = max(cfg["story_job"]["pay_day"], day + 7)
        late_roll = 1.0  # the story delay *is* the lateness
    elif offer.fixed == "day1":
        expected = day + cfg["day1_job"]["pay_days"]
        late_roll = 1.0  # the tutorial job pays on time
    late = math.ceil(late_extra * terms["late_factor"]) if late_roll < clients["late_share"] else 0
    return Invoice(id=job.id, amount=net, delivered_day=day, expected_day=expected, arrival_day=expected + late)


def deposit(cfg, offer, share, rate_multiplier):
    """Net $ paid at acceptance under deposit terms (share of the job's net pay)."""
    return offer.gross * rate_multiplier * cfg["work"]["net_factor"] * share


def receivable_invoices(cfg):
    return [
        Invoice(id=f"pre{r['day']}", amount=r["amount"], delivered_day=0, expected_day=r["day"],
                arrival_day=r["day"], source="receivable")
        for r in cfg["pre_move_receivables"]
    ]


def due_today(invoices, day):
    """Split invoices into (paid today, still outstanding)."""
    paid = [inv for inv in invoices if inv.arrival_day <= day]
    open_ = [inv for inv in invoices if inv.arrival_day > day]
    return paid, open_
