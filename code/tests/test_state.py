"""StateBuilder: recurrence detection, pending/cancelled/linked handling."""
from datetime import date, timedelta

import pytest
from conftest import FakeDataset, make_event, make_profile, make_request

from state import StateBuilder, add_months

RQ = date(2024, 4, 1)


def build(events, request=None, profile=None, adjustments=None, options=None):
    prof = profile or make_profile()
    req = request or make_request(request_date=RQ)
    ds = FakeDataset([prof], events)
    return StateBuilder(ds, {}, adjustments or {}, options=options).build(req)


def monthly_rows(cat="rent", dom=5, months=((2023, 11), (2023, 12), (2024, 1), (2024, 2), (2024, 3)), amount=500.0, **kw):
    return [make_event(category=cat, description=f"{cat} bill", amount=amount, event_date=date(y, m, dom), **kw) for y, m in months]


def periodic_rows(step, n=4, start=date(2024, 3, 1), cat="groceries", amount=100.0, **kw):
    return [make_event(category=cat, amount=amount, event_date=start + timedelta(days=step * i), **kw) for i in range(n)]


# ---- add_months ----------------------------------------------------------------
def test_add_months_clamps_day():
    assert add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)
    assert add_months(date(2023, 1, 31), 1) == date(2023, 2, 28)
    assert add_months(date(2024, 11, 15), 3) == date(2025, 2, 15)


# ---- recurrence ---------------------------------------------------------------
def test_monthly_series_same_dom_includes_request_date_occurrence():
    st = build(monthly_rows(dom=1), make_request(request_date=RQ))  # RQ = 2024-04-01, same DOM
    assert len(st.series) == 1
    s = st.series[0]
    assert s.cadence == "monthly"
    assert s.amount == pytest.approx(500.0)
    assert s.dates[0] == RQ  # occurrence on request_date is counted
    assert s.dates == [date(2024, 4, 1), date(2024, 5, 1), date(2024, 6, 1)]  # 84-day window
    assert s.latest_event_id.startswith("ev")


def test_monthly_series_amount_is_mean_in_home_currency():
    rows = monthly_rows(amount=400.0)
    rows[-1].amount = 700.0
    st = build(rows, options={"clamp_to_band": False})
    assert st.series[0].amount == pytest.approx((400 * 4 + 700) / 5)


def test_monthly_series_amount_clamped_into_noise_band():
    # observed = nominal x U(1-a, 1+a) => nominal in [max/(1+a), min/(1-a)]; the mean is
    # clamped into that interval when it falls outside (band derived from the data itself)
    rows = monthly_rows(amount=400.0)
    rows[-1].amount = 700.0
    st = build(rows)
    a = 0.28  # (700-400)/(700+400) = 0.273 rounded up to 0.02
    lo, hi = 700 / (1 + a), 400 / (1 - a)
    assert lo - 1e-6 <= st.series[0].amount <= hi + 1e-6


@pytest.mark.parametrize("step", [7, 10, 14])
def test_periodic_series_at_last_plus_step_skips_request_date(step):
    # last occurrence such that the next one lands exactly on request_date
    start = RQ - timedelta(days=4 * step)
    rows = periodic_rows(step, n=4, start=start)  # last row = RQ - step
    st = build(rows, make_request(request_date=RQ))
    assert len(st.series) == 1
    s = st.series[0]
    assert s.cadence == "periodic" and s.step_days == step
    assert s.dates[0] == RQ + timedelta(days=step)  # request-date occurrence skipped
    assert all((b - a).days == step for a, b in zip(s.dates, s.dates[1:]))
    assert s.dates[-1] <= RQ + timedelta(days=84)


def test_periodic_series_not_skipped_when_option_off():
    rows = periodic_rows(7, start=RQ - timedelta(days=28))
    st = build(rows, options={"periodic_skip_request_date": False, "periodic_at_least_once_before_payday": False})
    assert st.series[0].dates[0] == RQ


def test_fewer_than_three_rows_is_not_a_series():
    st = build(periodic_rows(7, n=2))
    assert st.series == []


def test_gap_over_45_days_is_not_a_series():
    rows = [make_event(category="travel", event_date=date(2023, 6, 1)), make_event(category="travel", event_date=date(2023, 9, 1)), make_event(category="travel", event_date=date(2023, 12, 1))]
    assert build(rows).series == []


def test_non_recurring_categories_and_types_are_skipped():
    inv = periodic_rows(7, cat="investment")
    ref = periodic_rows(7, cat="shopping", event_type="refund")
    assert build(inv + ref).series == []


def test_periodic_series_reserved_at_least_once_before_first_payday():
    # groceries every 7 days, next occurrence 2024-04-08; salary scheduled 2024-04-05
    rows = periodic_rows(7, start=RQ - timedelta(days=28))
    salary = make_event(category="salary", description="Payroll credit", direction="credit", amount=5000.0, event_date=date(2024, 4, 5), status="scheduled")
    st = build(rows + [salary])
    assert st.salary_dates[0] == date(2024, 4, 5)
    s = st.series[0]
    assert s.dates[0] == date(2024, 4, 4)  # brought forward to the day before payday
    assert s.dates[1] == date(2024, 4, 15)  # rest of the cycle unchanged
    st2 = build(rows + [salary], options={"periodic_at_least_once_before_payday": False})
    assert st2.series[0].dates[0] == date(2024, 4, 8)


def test_periodic_series_before_payday_is_left_alone():
    rows = periodic_rows(7, start=RQ - timedelta(days=28))  # next 2024-04-08
    salary = make_event(category="salary", description="Payroll credit", direction="credit", amount=5000.0, event_date=date(2024, 4, 20), status="scheduled")
    st = build(rows + [salary])
    assert st.series[0].dates[0] == date(2024, 4, 8)


# ---- pending / failed / cancelled ---------------------------------------------
def _debits(st):
    return [(f.date, f.amount) for f in st.flows if f.amount < 0]


def test_pending_debit_reserved_at_settlement_date():
    e = make_event(amount=250.0, event_date=date(2024, 3, 30), settlement_date=date(2024, 4, 3), status="pending")
    st = build([e])
    assert _debits(st) == [(date(2024, 4, 3), -250.0)]


def test_pending_debit_settling_before_request_date_is_reserved_today():
    e = make_event(amount=250.0, event_date=date(2024, 3, 28), settlement_date=date(2024, 3, 30), status="pending")
    st = build([e])
    assert _debits(st) == [(RQ, -250.0)]


def test_pending_credit_is_ignored():
    e = make_event(direction="credit", amount=900.0, event_date=date(2024, 3, 30), settlement_date=date(2024, 4, 3), status="pending", category="salary", description="Bonus")
    st = build([e])
    assert st.flows == [] and any("pending credit" in n for n in st.notes)


@pytest.mark.parametrize("status", ["failed", "cancelled", "unrealized"])
def test_failed_cancelled_unrealized_are_ignored(status):
    rows = periodic_rows(7, n=3, start=RQ - timedelta(days=21), status=status)
    fut = make_event(amount=300.0, event_date=date(2024, 4, 5), status=status)
    st = build(rows + [fut])
    assert st.flows == [] and st.series == []


def test_non_cash_rows_are_ignored():
    e = make_event(direction="non_cash", event_type="investment_valuation", category="investment", amount=99999.0, event_date=date(2024, 3, 31))
    assert build([e]).flows == []


def test_pending_duplicate_card_charge_is_ignored():
    orig = make_event(amount=120.0, event_date=date(2024, 3, 30), category="dining")
    dup = make_event(amount=120.0, event_date=date(2024, 3, 30), settlement_date=date(2024, 4, 2), status="pending", category="dining", description="Possible duplicate card charge", linked_event_id=orig.event_id)
    st = build([orig, dup])
    assert st.flows == [] and any("duplicate" in n for n in st.notes)


def test_scheduled_debit_reserved_and_scheduled_non_salary_credit_ignored():
    d = make_event(amount=80.0, event_date=date(2024, 4, 10), status="scheduled")
    c = make_event(direction="credit", amount=80.0, event_date=date(2024, 4, 10), status="scheduled", category="refund", description="Refund", event_type="refund")
    st = build([d, c])
    assert _debits(st) == [(date(2024, 4, 10), -80.0)]
    assert [f for f in st.flows if f.amount > 0] == []


# ---- linked events -----------------------------------------------------------
def test_scheduled_retry_of_failed_debit_reserved_once():
    failed = make_event(amount=130.0, event_date=date(2024, 3, 28), status="failed", category="utilities")
    retry = make_event(amount=130.0, event_date=date(2024, 4, 4), status="scheduled", category="utilities", linked_event_id=failed.event_id)
    st = build([failed, retry])
    assert _debits(st) == [(date(2024, 4, 4), -130.0)]


def test_payment_delayed_message_reserves_failed_debit_without_retry_row_once():
    failed = make_event(amount=130.0, event_date=date(2024, 3, 28), status="failed", category="utilities")
    adj = {"u1": [{"adjustment_type": "payment_delayed", "related_event_id": failed.event_id}]}
    st = build([failed], adjustments=adj)
    assert _debits(st) == [(RQ, -130.0)]
    # with the scheduled retry row present the message must not double count
    retry = make_event(amount=130.0, event_date=date(2024, 4, 4), status="scheduled", category="utilities", linked_event_id=failed.event_id)
    st2 = build([failed, retry], adjustments=adj)
    assert _debits(st2) == [(date(2024, 4, 4), -130.0)]


def test_refund_pair_excluded_from_recurrence_history():
    rows = periodic_rows(7, n=3, start=RQ - timedelta(days=21), cat="shopping")
    refund = make_event(direction="credit", event_type="refund", category="shopping", amount=100.0, event_date=RQ - timedelta(days=5), linked_event_id=rows[0].event_id)
    st = build(rows + [refund])
    assert st.series == []  # only two unlinked purchases remain
    rows4 = periodic_rows(7, n=4, start=RQ - timedelta(days=28), cat="shopping", amount=50.0)
    rows4[0].amount = 999.0  # the refunded one must not enter the mean
    refund4 = make_event(direction="credit", event_type="refund", category="shopping", amount=999.0, event_date=RQ - timedelta(days=5), linked_event_id=rows4[0].event_id)
    st4 = build(rows4 + [refund4])
    assert len(st4.series) == 1 and st4.series[0].amount == pytest.approx(50.0) and st4.series[0].n_hist == 3


def test_missing_amount_without_image_is_ignored_not_zero():
    e = make_event(amount=None, event_date=date(2024, 4, 3), status="pending")
    e.amount_source = "image"
    st = build([e])
    assert st.flows == [] and any("missing amount" in n for n in st.notes)


def test_missing_amount_filled_from_image_extraction():
    e = make_event(amount=None, event_date=date(2024, 4, 3), status="pending")
    ds = FakeDataset([make_profile()], [e])
    st = StateBuilder(ds, {e.event_id: 77.0}, {}).build(make_request(request_date=RQ))
    assert _debits(st) == [(date(2024, 4, 3), -77.0)]


def test_foreign_currency_event_converted_on_settlement_date():
    e = make_event(amount=10.0, currency="USD", event_date=date(2024, 4, 2), settlement_date=date(2024, 4, 4), status="pending")
    ds = FakeDataset([make_profile()], [e], rates={(date(2024, 4, 2), "USD", "INR"): 80.0, (date(2024, 4, 4), "USD", "INR"): 85.0})
    st = StateBuilder(ds, {}, {}).build(make_request(request_date=RQ))
    assert _debits(st) == [(date(2024, 4, 4), -850.0)]


def test_scheduled_salary_projected_monthly():
    salary = make_event(category="salary", description="Payroll credit", direction="credit", amount=5000.0, event_date=date(2024, 4, 25), status="scheduled")
    st = build([salary])
    assert st.salary_dates == [date(2024, 4, 25), date(2024, 5, 25)]  # 2024-06-25 is past the 84-day window
    assert st.salary_amount == pytest.approx(5000.0)
