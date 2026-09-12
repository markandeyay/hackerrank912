"""Daily balance projection and the safety checks built on it."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from state import Flow, State

EPS = 1e-6


def daily_balances(st: State, extra: list[Flow] | None = None) -> list[tuple[date, float]]:
    """End-of-day balance for every day from request_date to horizon_end.

    Credits and debits on the same day are netted, i.e. income landing on a
    payday is available for that day's debits (salary-first ordering)."""
    net: dict[date, float] = defaultdict(float)
    deb: dict[date, float] = defaultdict(float)
    for f in st.all_flows(extra):
        if st.request_date <= f.date <= st.horizon_end:
            net[f.date] += f.amount
            if f.amount < 0:
                deb[f.date] += f.amount
    out = []
    bal = st.balance
    t = st.request_date
    debit_first = getattr(st, "debit_first", False)
    while t <= st.horizon_end:
        if debit_first:
            # intra-day low point: debits are applied before that day's credits
            low = bal + deb.get(t, 0.0)
            bal += net.get(t, 0.0)
            out.append((t, min(low, bal)))
        else:
            bal += net.get(t, 0.0)
            out.append((t, bal))
        t += timedelta(days=1)
    return out


def trough(st: State, extra: list[Flow] | None = None) -> float:
    return min(b for _, b in daily_balances(st, extra))


def is_safe(st: State, payments: list[tuple[date, float]], extra: list[Flow] | None = None) -> bool:
    """True when the balance never falls below the minimum with `payments` applied."""
    flows = list(extra or [])
    for d, a in payments:
        flows.append(Flow(d, -a, "payment", "payment"))
    return trough(st, flows) + EPS >= st.min_balance


def amount_safe_to_pay(st: State, requested: float, extra: list[Flow] | None = None) -> float:
    """Largest X in [0, requested] such that paying X on request_date is safe.

    Paying X today lowers every projected balance by X, so the exact answer is
    trough - minimum, clipped.  A binary search over `is_safe` gives the same
    value; the closed form is used and verified."""
    x = trough(st, extra) - st.min_balance
    x = max(0.0, min(requested, x))
    x = round(x + 1e-9, 2)
    while x > 0 and not is_safe(st, [(st.request_date, x)], extra):
        x = round(x - 0.01, 2)
    return max(0.0, x)


def earliest_full_payment_date(st: State, requested: float, extra: list[Flow] | None = None) -> date | None:
    """First day D in the window where one full payment on D keeps the balance
    at or above the minimum for every day from D to the end of the window."""
    series = daily_balances(st, extra)
    suffix_min = [0.0] * len(series)
    m = float("inf")
    for i in range(len(series) - 1, -1, -1):
        m = min(m, series[i][1])
        suffix_min[i] = m
    for i, (d, _) in enumerate(series):
        if suffix_min[i] - requested + EPS >= st.min_balance:
            return d
    return None
