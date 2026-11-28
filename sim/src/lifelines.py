"""Money crisis, lifelines, her loan and the parents' ending (SIM_BASELINE.md §6, v0.3).

Called at the end of a day when cash < 0 ("crisis"). Lifelines, each usable once:
1. Pay rent late, if rent fell due today (the rent is owed with a fee within `rent_late_days`).
2. Ask a client to pay early (lose `early_payment_fee` of the smallest job invoice that covers the gap).
3. Borrow from her, always last: shortfall + buffer, up to `borrow_max`. Stress +15 at once
   (+3/day while unpaid is handled by the stress system); due in full within `loan_repay_days`.

The parents' ending (the run ends that day) happens when the loan is not repaid by its
deadline, or when cash is below `parents_floor` at the end of a day with no lifeline left.
"""


def used(state, name):
    return any(n == name for n, _ in state.lifelines_used)


def rent_late(cfg, state, day):
    lf = cfg["lifelines"]
    state.cash += state.rent_paid_today
    state.deferred_rent = {"amount": state.rent_paid_today + lf["rent_late_fee"], "due_day": day + lf["rent_late_days"]}
    state.rent_paid_today = 0
    state.lifelines_used.append(("rent_late", day))
    return True


def early_payment_candidates(state):
    return [inv for inv in state.invoices if inv.source == "job"]


def early_payment(cfg, state, day):
    candidates = early_payment_candidates(state)
    if not candidates:
        return False
    keep = 1 - cfg["lifelines"]["early_payment_fee"]
    covering = [inv for inv in candidates if inv.amount * keep >= -state.cash]
    invoice = min(covering, key=lambda i: (i.amount, i.id)) if covering else max(candidates, key=lambda i: (i.amount, i.id))
    state.invoices.remove(invoice)
    state.cash += invoice.amount * keep
    state.record_payment(day, invoice, invoice.amount * keep)
    state.lifelines_used.append(("early_payment", day))
    return True


def borrow(cfg, state, day):
    lf = cfg["lifelines"]
    amount = min(lf["borrow_max"], -state.cash + lf["borrow_buffer"])
    state.cash += amount
    state.loan = {"amount": amount, "left": amount, "day": day, "due_day": day + round(lf["loan_repay_days"])}
    state.stress = min(cfg["stress"]["max"], state.stress + lf["loan_stress_once"])
    state.lifelines_used.append(("borrow", day))
    return True


def available(state, day, name):
    if used(state, name):
        return False
    if name == "rent_late":
        return state.rent_paid_today > 0
    if name == "early_payment":
        return bool(early_payment_candidates(state))
    return True


ACTIONS = {"rent_late": rent_late, "early_payment": early_payment, "borrow": borrow}


def resolve_crisis(cfg, state, day, order):
    """Apply lifelines in order (rent-late first if possible, borrowing last) until cash >= 0."""
    order = ["rent_late"] + [n for n in order if n not in ("rent_late", "borrow")] + ["borrow"]
    for name in order:
        if state.cash >= 0:
            break
        if available(state, day, name):
            ACTIONS[name](cfg, state, day)


def any_left(state, day):
    return any(available(state, day, n) for n in ACTIONS)


def repay_loan(state, amount, day):
    pay = min(amount, state.loan["left"])
    if pay <= 0:
        return 0.0
    state.cash -= pay
    state.loan["left"] -= pay
    if state.loan["left"] <= 1e-9:
        state.loan["repaid_day"] = day
    return pay


def loan_open(state):
    return bool(state.loan) and state.loan["left"] > 1e-9


def parents_reason(cfg, state, day):
    """'loan' / 'floor' if the parents' ending happens at the end of today, else None."""
    if loan_open(state) and day >= state.loan["due_day"]:
        return "loan"
    if state.cash < cfg["lifelines"]["parents_floor"] and not any_left(state, day):
        return "floor"
    return None
