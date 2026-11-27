"""Payments (SIM_BASELINE.md §3.4-3.6): invoices on delivery, compressed payment terms, late payments.

An invoice has a public `expected_day` (what the "money owed" list shows) and a hidden
`arrival_day` (when the cash really lands). Policies may only read `expected_day`.
"""
from dataclasses import dataclass

from .rng import stream


@dataclass
class Invoice:
    id: str
    amount: float          # net $
    delivered_day: int
    expected_day: int      # shown to the player
    arrival_day: int       # hidden: includes any lateness
    source: str = "job"    # job / receivable / advance


def make_invoice(cfg, seed, job, day, gross, fast_invoicer=None):
    """Invoice for a job delivered on `day`. `fast_invoicer` = the effect's params, or None."""
    clients, rng = cfg["clients"], stream(seed, "payment", job.id)
    c = clients[job.offer.client]
    delay = round(rng.uniform(c["pay_days_min"], c["pay_days_max"]))
    late_roll, late_extra = rng.random(), rng.randint(clients["late_days_min"], clients["late_days_max"])
    net = gross * cfg["work"]["net_factor"]
    if job.late:
        net *= 1 - cfg["reputation"]["late_payment_penalty"]
    if fast_invoicer and job.offer.client == "slow_agency":
        delay = min(delay, round(fast_invoicer["slow_pay_days"]))
        net *= 1 - fast_invoicer["fee"]
    expected = day + delay
    if job.offer.story:
        expected = max(cfg["story_job"]["pay_day"], day + 7)
        late_roll = 1.0  # the story delay *is* the lateness
    arrival = expected + (late_extra if late_roll < clients["late_share"] else 0)
    return Invoice(id=job.id, amount=net, delivered_day=day, expected_day=expected, arrival_day=arrival)


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
