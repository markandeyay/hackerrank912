"""planner: partial rule, installments, spending changes, ranking."""
from datetime import date, timedelta

import pytest
from conftest import make_option, make_profile, make_request, make_state

from planner import Plan, decide, greedy_changes, installment_eligible, spending_change_candidates
from state import Series, SpendingChange

RQ = date(2024, 4, 1)
FLOWS = [(10, -300.0), (20, 500.0), (40, 1000.0)]  # trough 700 -> safe 500; 1200 from day 20


def state(requested=600.0, allows_partial=True, desired_days=30, methods=("full_payment", "partial_payment", "installments"), flows=FLOWS, **prof):
    req = make_request(request_date=RQ, requested_amount=requested, allows_partial_payment=allows_partial, desired_completion_date=RQ + timedelta(days=desired_days))
    p = make_profile(current_available_balance=1000.0, minimum_balance_to_keep=200.0, methods=list(methods), **prof)
    return make_state(balance=1000.0, min_balance=200.0, flows=flows, request=req, profile=p)


# ---- partial payment --------------------------------------------------------------
def test_partial_payment_two_payments_summing_to_requested():
    dec = decide(state(), [])
    assert dec.safe_amount == 500 and dec.earliest == RQ + timedelta(days=20)
    assert dec.plan.method == "partial_payment" and dec.plan.status == "affordable_with_plan"
    assert dec.plan.payments == [(RQ, 500.0), (RQ + timedelta(days=20), 100.0)]
    assert dec.plan.plan_string() == "2024-04-01:500|2024-04-21:100"


def test_partial_not_when_request_disallows():
    dec = decide(state(allows_partial=False), [])
    assert dec.plan.method == "wait" and dec.plan.status == "affordable_later"
    assert dec.plan.payments == [(RQ + timedelta(days=20), 600.0)]


def test_partial_not_when_user_rejects_method():
    dec = decide(state(methods=("full_payment",)), [])
    assert dec.plan.method == "wait"
    assert all(p.method != "partial_payment" for p in dec.candidates)


def test_partial_not_when_earliest_after_deadline():
    dec = decide(state(desired_days=15), [])
    assert all(p.method != "partial_payment" for p in dec.candidates)
    assert dec.plan.method == "wait" and not dec.plan.completes_by_deadline


def test_partial_not_when_nothing_safe_today():
    st = state()
    st.min_balance = 700.0  # trough == min -> safe 0
    dec = decide(st, [])
    assert dec.safe_amount == 0 and all(p.method != "partial_payment" for p in dec.candidates)


def test_full_payment_when_safe_today():
    dec = decide(state(requested=400.0), [])
    assert dec.plan.method == "full_payment" and dec.plan.status == "affordable_now"
    assert dec.earliest == RQ and dec.safe_amount == 400


def test_not_recommended_when_nothing_works():
    dec = decide(state(requested=5000.0), [])
    assert dec.plan.method == "not_recommended" and dec.plan.status == "not_affordable" and dec.plan.plan_string() == "none"
    assert dec.earliest is None


def test_wait_only_if_user_accepts_full_payment():
    dec = decide(state(methods=("installments",)), [])
    assert dec.plan.method == "not_recommended"


# ---- installments -----------------------------------------------------------------
def test_installment_eligibility_rules():
    opt = make_option(number_of_payments=3)
    assert installment_eligible(opt, make_profile(max_installment_months=3))
    assert not installment_eligible(opt, make_profile(max_installment_months=2))
    assert not installment_eligible(opt, make_profile(max_installment_months=None))  # blank max => never
    assert not installment_eligible(opt, make_profile(methods=["full_payment"]))
    assert not installment_eligible(make_option(payment_method="full_payment", number_of_payments=1), make_profile())


def test_installment_plan_follows_supplied_option_exactly():
    opt = make_option(payment_amount=210.0, number_of_payments=3, first_payment_date=RQ + timedelta(days=2), payment_frequency_days=30, total_payable_amount=630.0)
    dec = decide(state(allows_partial=False, desired_days=70, methods=("installments",)), [opt])
    assert dec.plan.method == "installments" and dec.plan.option is opt
    assert dec.plan.payments == opt.schedule()
    assert dec.plan.plan_string() == "2024-04-03:210|2024-05-03:210|2024-06-02:210"


def test_installments_rejected_beyond_max_months():
    opt = make_option(number_of_payments=4, payment_amount=150.0)
    dec = decide(state(allows_partial=False, methods=("installments",), max_installment_months=3), [opt])
    assert dec.plan.method == "not_recommended"


def test_installment_starting_before_request_date_is_skipped():
    opt = make_option(first_payment_date=RQ - timedelta(days=1))
    dec = decide(state(allows_partial=False, methods=("installments",)), [opt])
    assert dec.plan.method == "not_recommended"


def test_cheaper_total_wins_over_earlier_start():
    # partial completes today at cost 600; installments cost 630 -> partial wins on total paid
    opt = make_option(payment_amount=210.0, total_payable_amount=630.0)
    dec = decide(state(), [opt])
    assert dec.plan.method == "partial_payment"
    # a fee-free installment option that starts today ties on total and start, loses on payment count
    opt2 = make_option(payment_amount=200.0, first_payment_date=RQ, total_payable_amount=600.0)
    dec2 = decide(state(), [opt2])
    assert dec2.plan.method == "partial_payment"


# ---- spending changes ---------------------------------------------------------------
def series(cat, amount, days, flex="stoppable", min_amt=None, eid=None):
    return Series(cat, f"{cat} spend", amount, "periodic", 30, [RQ + timedelta(days=d) for d in days], flex, eid or f"e_{cat}", min_amt, 4)


def test_spending_change_candidates_rules():
    st = state(protect=["rent"], reduce=["dining", "both"], stop=["subscriptions", "both", "streaming"])
    st.series = [
        series("rent", 500, [5], "stoppable"),  # protected
        series("dining", 100, [5], "reducible", 40),  # reduce_to 40
        series("subscriptions", 30, [5], "stoppable"),  # stop
        series("both", 80, [5], "reducible_or_stoppable", 20),  # reduce preferred, never both
        series("streaming", 20, [5], "fixed"),  # not flexible
        series("dining", 60, [5], "stoppable", eid="e_dining2"),  # stoppable but user won't stop dining
        series("groceries", 90, [5], "reducible", 50),  # reducible but not permitted
        series("subscriptions", 10, [5], "reducible", 5, eid="e_sub2"),  # permitted to stop, not reduce
    ]
    cands = spending_change_candidates(st)
    assert [(c.action, c.series.category, c.new_amount) for c in cands] == [("stop", "subscriptions", None), ("reduce_to", "both", 20), ("reduce_to", "dining", 40)]
    assert [c.as_string() for c in cands] == ["stop:e_subscriptions", "reduce_to:e_both:20", "reduce_to:e_dining:40"]
    assert cands[0].saving_per_occurrence == 30 and cands[1].saving_per_occurrence == 60


def test_reduce_requires_minimum_below_current_amount():
    st = state(reduce=["dining"])
    st.series = [series("dining", 100, [5], "reducible", 100), series("dining", 100, [5], "reducible", None, eid="x")]
    assert spending_change_candidates(st) == []


def test_greedy_skips_changes_that_do_not_help():
    st = state(flows=[(30, 1000.0)], stop=["big", "late"])
    st.series = [series("big", 600, [1]), series("late", 50, [60])]  # trough is day 1 (-300); 'late' cannot raise it
    ch = greedy_changes(st, [(RQ, 700.0)])
    assert [c.series.category for c in ch] == ["big"]


def test_greedy_returns_empty_when_already_safe_and_none_when_over_three():
    st = state(flows=[], stop=["a", "b", "c", "d"])
    st.series = [series(c, 200, [1]) for c in "abcd"]
    assert greedy_changes(st, [(RQ, 0.0)]) == []
    assert greedy_changes(st, [(RQ, 700.0)]) is None  # needs four stops
    ch = greedy_changes(st, [(RQ, 500.0)])
    assert ch is not None and len(ch) == 3
    assert len({c.series.category for c in ch}) == 3


def test_full_payment_with_changes_is_affordable_with_plan():
    st = state(requested=800.0, allows_partial=False, methods=("full_payment",), flows=[], stop=["sub"])
    st.series = [series("sub", 100, [1, 31, 61])]
    dec = decide(st, [])
    assert dec.plan.method == "full_payment" and dec.plan.status == "affordable_with_plan"
    assert dec.plan.changes_string() == "stop:e_sub"
    assert dec.safe_amount == pytest.approx(500.0)  # before optional changes: trough 700 (three debits) - 200


# ---- ranking -------------------------------------------------------------------------
def plan(method="wait", payments=None, changes=False, completes=True, total=100.0, option=None):
    ch = [SpendingChange("stop", series("s", 1, [1]), None)] if changes else []
    return Plan(method, "x", payments or [(RQ, total)], changes=ch, option=option, completes_by_deadline=completes, total_paid=total)


def best(*plans):
    return sorted(plans, key=lambda p: p.rank_key(1))[0]


def test_rank_key_order():
    late = plan(completes=False, total=50.0)
    ok = plan(total=200.0)
    assert best(late, ok) is ok  # deadline first
    with_ch = plan(total=50.0, changes=True)
    assert best(with_ch, ok) is ok  # no changes beats cheaper with changes
    cheap = plan(total=150.0, payments=[(RQ + timedelta(days=5), 150.0)])
    assert best(ok, cheap) is cheap  # total paid before start
    early = plan(total=200.0, payments=[(RQ, 100.0), (RQ + timedelta(days=1), 100.0)])
    later_single = plan(total=200.0, payments=[(RQ + timedelta(days=1), 200.0)])
    assert best(later_single, early) is early  # start before count
    two = plan(total=200.0, payments=[(RQ, 100.0), (RQ + timedelta(days=1), 100.0)])
    one = plan(total=200.0, payments=[(RQ, 200.0)])
    assert best(two, one) is one  # fewer payments
    o2 = make_option(payment_option_id="payment_option_02")
    o3 = make_option(payment_option_id="payment_option_03")
    a = plan(total=200.0, payments=[(RQ, 200.0)], option=o3)
    b = plan(total=200.0, payments=[(RQ, 200.0)], option=o2)
    assert best(a, b) is b  # lowest option id
    assert o2.option_num == 2 and o3.option_num == 3
