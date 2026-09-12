"""forecast: daily balances, amount_safe_to_pay, earliest_full_payment_date."""
from datetime import timedelta

import pytest
from conftest import make_state

from forecast import amount_safe_to_pay, daily_balances, earliest_full_payment_date, is_safe, trough

# balance 1000, min 200: -300 on day 10, +500 on day 20, +1000 on day 40
FLOWS = [(10, -300.0), (20, 500.0), (40, 1000.0)]


def bisect_safe(st, requested, tol=0.01):
    lo, hi = 0.0, requested
    if is_safe(st, [(st.request_date, hi)]):
        return hi
    while hi - lo > tol / 4:
        mid = (lo + hi) / 2
        if is_safe(st, [(st.request_date, mid)]):
            lo = mid
        else:
            hi = mid
    return lo


def test_daily_balances_net_same_day():
    st = make_state(flows=FLOWS)
    bal = dict(daily_balances(st))
    rq = st.request_date
    assert bal[rq] == 1000 and bal[rq + timedelta(days=10)] == 700 and bal[rq + timedelta(days=20)] == 1200 and bal[rq + timedelta(days=40)] == 2200
    assert len(bal) == 85  # request_date .. horizon_end inclusive (84 days)
    assert trough(st) == 700


def test_flows_outside_window_ignored():
    st = make_state(flows=[(-1, -5000.0), (85, -5000.0)])
    assert trough(st) == 1000


def test_amount_safe_equals_trough_minus_min_clipped():
    st = make_state(flows=FLOWS)
    assert amount_safe_to_pay(st, 10000) == pytest.approx(500.0)  # 700 - 200
    assert amount_safe_to_pay(st, 300) == pytest.approx(300.0)  # capped at requested
    st2 = make_state(balance=100.0, flows=FLOWS)
    assert amount_safe_to_pay(st2, 500) == 0.0  # trough below min -> nothing safe


def test_amount_safe_is_consistent_with_is_safe():
    st = make_state(flows=FLOWS)
    safe = amount_safe_to_pay(st, 10000)
    assert is_safe(st, [(st.request_date, safe)])
    assert not is_safe(st, [(st.request_date, safe + 0.02)])


@pytest.mark.parametrize(
    "balance,flows,requested",
    [
        (1000.0, FLOWS, 10000),
        (1000.0, FLOWS, 450),
        (1234.56, [(3, -321.09), (7, 12.5), (50, -400.0)], 5000),
        (500.0, [(1, -800.0), (2, 900.0)], 5000),
    ],
)
def test_closed_form_matches_bisection(balance, flows, requested):
    st = make_state(balance=balance, flows=flows)
    assert abs(amount_safe_to_pay(st, requested) - bisect_safe(st, requested)) <= 0.01


def test_earliest_full_payment_date():
    st = make_state(flows=FLOWS)
    rq = st.request_date
    assert earliest_full_payment_date(st, 600) == rq + timedelta(days=20)  # balance 1200 from day 20
    assert earliest_full_payment_date(st, 1500) == rq + timedelta(days=40)
    assert earliest_full_payment_date(st, 5000) is None


def test_earliest_is_request_date_when_safe_today():
    st = make_state(flows=FLOWS)
    assert amount_safe_to_pay(st, 400) == 400
    assert earliest_full_payment_date(st, 400) == st.request_date


def test_earliest_payment_keeps_rest_of_window_safe():
    # a later dip means the earliest date must be after the dip, not before it
    st = make_state(flows=[(5, 1000.0), (30, -1500.0), (60, 2000.0)])
    rq = st.request_date
    d = earliest_full_payment_date(st, 1000)
    assert d == rq + timedelta(days=60)
    assert is_safe(st, [(d, 1000)])
    assert not is_safe(st, [(d - timedelta(days=1), 1000)])
