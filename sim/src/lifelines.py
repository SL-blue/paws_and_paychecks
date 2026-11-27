"""Money crisis, lifelines and bankruptcy (SIM_BASELINE.md §6).

Called at the end of a day when cash < 0 ("crisis"). Order of resolution:
1. Pay rent late, if rent fell due today and that lifeline is unused (the rent is simply not paid
   yet; it is owed with a fee within `rent_late_days`).
2. If cash is still below `bankrupt_floor` -> bankrupt (too deep for the remaining lifelines).
3. The policy's order of the other lifelines (ask a client to pay early, borrow from her),
   each usable once, until cash >= 0.
4. Still below 0 -> bankrupt. Bankruptcy is an ending path: the run continues to day 42.
"""


def rent_late(cfg, state, day):
    lf = cfg["lifelines"]
    state.cash += state.rent_paid_today
    state.deferred_rent = {"amount": state.rent_paid_today + lf["rent_late_fee"], "due_day": day + lf["rent_late_days"]}
    state.rent_paid_today = 0
    state.lifelines_used.append(("rent_late", day))


def early_payment_candidates(state):
    return [inv for inv in state.invoices if inv.source == "job"]


def early_payment(cfg, state, day):
    candidates = early_payment_candidates(state)
    if not candidates:
        return False
    keep = 1 - cfg["lifelines"]["early_payment_fee"]
    shortfall = -state.cash
    covering = [inv for inv in candidates if inv.amount * keep >= shortfall]
    invoice = min(covering, key=lambda i: i.amount) if covering else max(candidates, key=lambda i: i.amount)
    state.invoices.remove(invoice)
    state.cash += invoice.amount * keep
    state.record_payment(day, invoice, invoice.amount * keep)
    state.lifelines_used.append(("early_payment", day))
    return True


def borrow(cfg, state, day):
    lf = cfg["lifelines"]
    amount = min(lf["borrow_max"], -state.cash + lf["borrow_buffer"])
    state.cash += amount
    state.debt += amount
    state.lifelines_used.append(("borrow", day))
    return True


def used(state, name):
    return any(n == name for n, _ in state.lifelines_used)


def resolve_crisis(cfg, state, day, order):
    """Apply lifelines; set state.bankrupt if they cannot fix the day. Returns True if bankrupt now."""
    if state.rent_paid_today > 0 and not used(state, "rent_late"):
        rent_late(cfg, state, day)
    if state.cash < cfg["lifelines"]["bankrupt_floor"]:
        return True
    actions = {"early_payment": early_payment, "borrow": borrow}
    for name in order:
        if state.cash >= 0:
            break
        if name in actions and not used(state, name):
            actions[name](cfg, state, day)
    return state.cash < 0
