"""Candidate payment plans, spending changes and the ranking between them."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from data import PaymentOption, Request
from forecast import amount_safe_to_pay, earliest_full_payment_date, is_safe, trough
from state import Flow, Series, SpendingChange, State, fmt_amount

MAX_CHANGES = 3
STOPPABLE = {"stoppable", "reducible_or_stoppable"}
REDUCIBLE = {"reducible", "reducible_or_stoppable"}


@dataclass
class Plan:
    method: str  # full_payment | partial_payment | installments | wait | not_recommended
    status: str
    payments: list[tuple[date, float]]
    changes: list[SpendingChange] = field(default_factory=list)
    option: PaymentOption | None = None
    completes_by_deadline: bool = True
    total_paid: float = 0.0

    @property
    def start(self) -> date | None:
        return self.payments[0][0] if self.payments else None

    def plan_string(self) -> str:
        if not self.payments:
            return "none"
        return "|".join(f"{d.isoformat()}:{fmt_amount(a)}" for d, a in self.payments)

    def changes_string(self) -> str:
        return "|".join(c.as_string() for c in self.changes) if self.changes else "none"

    def rank_key(self, full_option_num: int):
        opt_num = self.option.option_num if self.option else full_option_num
        return (
            0 if self.completes_by_deadline else 1,
            1 if self.changes else 0,
            round(self.total_paid, 2),
            self.start or date.max,
            len(self.payments),
            opt_num,
        )


@dataclass
class Decision:
    request: Request
    safe_amount: float
    earliest: date | None
    plan: Plan
    candidates: list[Plan]
    state: State


# ------------------------------------------------------------------------------
def installment_eligible(opt: PaymentOption, prof) -> bool:
    if opt.payment_method != "installments" or "installments" not in prof.methods:
        return False
    if prof.max_installment_months is None:
        return False
    return opt.number_of_payments <= prof.max_installment_months


def spending_change_candidates(st: State) -> list[SpendingChange]:
    """Flexible recurring series the user permits changing, cheapest first;
    reduce is preferred over stop when both are allowed."""
    prof = st.profile
    cands: list[SpendingChange] = []
    for s in st.series:
        if not s.dates or s.category in prof.protect:
            continue
        can_reduce = s.flexibility in REDUCIBLE and s.category in prof.reduce and s.minimum_allowed_amount is not None and s.minimum_allowed_amount < s.amount
        can_stop = s.flexibility in STOPPABLE and s.category in prof.stop
        if can_reduce:
            cands.append(SpendingChange("reduce_to", s, s.minimum_allowed_amount))
        elif can_stop:
            cands.append(SpendingChange("stop", s, None))
    cands.sort(key=lambda c: (c.series.amount, c.series.latest_event_id))
    return cands


def greedy_changes(st: State, payments: list[tuple[date, float]]) -> list[SpendingChange] | None:
    """Smallest set (greedy, cheapest first, only changes that help) of at most
    three spending changes that makes `payments` safe.  None if impossible."""
    if is_safe(st, payments):
        return []
    pay_flows = [Flow(d, -a, "payment", "payment") for d, a in payments]
    chosen: list[SpendingChange] = []
    cur_trough = trough(st, pay_flows)
    for c in spending_change_candidates(st):
        if len(chosen) >= MAX_CHANGES:
            break
        if any(x.series is c.series for x in chosen):
            continue
        extra = pay_flows + [f for x in chosen for f in x.flows()] + c.flows()
        new_trough = trough(st, extra)
        if new_trough <= cur_trough + 1e-9:
            continue  # does not help before the failing trough
        chosen.append(c)
        cur_trough = new_trough
        if cur_trough + 1e-6 >= st.min_balance:
            return chosen
    return None


# ------------------------------------------------------------------------------
def decide(st: State, options: list[PaymentOption]) -> Decision:
    req, prof = st.request, st.profile
    requested = req.requested_amount
    rq = st.request_date
    safe = amount_safe_to_pay(st, requested)
    earliest = earliest_full_payment_date(st, requested)
    full_opts = [o for o in options if o.payment_method == "full_payment"]
    full_option_num = full_opts[0].option_num if full_opts else 0

    cands: list[Plan] = []
    accepts_full = "full_payment" in prof.methods

    # full payment today
    if accepts_full:
        pays = [(rq, requested)]
        if is_safe(st, pays):
            cands.append(Plan("full_payment", "affordable_now", pays, total_paid=requested))
        else:
            ch = greedy_changes(st, pays)
            if ch:
                cands.append(Plan("full_payment", "affordable_with_plan", pays, changes=ch, total_paid=requested))

    # installments matching a supplied option
    for o in options:
        if not installment_eligible(o, prof):
            continue
        sched = o.schedule()
        within = [(d, a) for d, a in sched if d <= st.horizon_end]
        if sched[0][0] < rq:
            continue
        completes = sched[-1][0] <= req.desired_completion_date
        if is_safe(st, within):
            cands.append(Plan("installments", "affordable_with_plan", sched, option=o, completes_by_deadline=completes, total_paid=o.total_payable_amount))
        else:
            ch = greedy_changes(st, within)
            if ch:
                cands.append(Plan("installments", "affordable_with_plan", sched, changes=ch, option=o, completes_by_deadline=completes, total_paid=o.total_payable_amount))

    # partial payment: exactly two payments
    if (
        req.allows_partial_payment
        and "partial_payment" in prof.methods
        and 0 < safe < requested
        and earliest is not None
        and earliest <= req.desired_completion_date
        and earliest > rq
    ):
        pays = [(rq, safe), (earliest, round(requested - safe + 1e-9, 2))]
        if is_safe(st, pays):
            cands.append(Plan("partial_payment", "affordable_with_plan", pays, total_paid=requested))

    # wait for a later full payment
    if accepts_full and earliest is not None and earliest > rq:
        pays = [(earliest, requested)]
        cands.append(Plan("wait", "affordable_later", pays, completes_by_deadline=earliest <= req.desired_completion_date, total_paid=requested))

    if cands:
        cands.sort(key=lambda p: p.rank_key(full_option_num))
        best = cands[0]
    else:
        best = Plan("not_recommended", "not_affordable", [], total_paid=0.0)
    return Decision(req, safe, earliest, best, cands, st)
