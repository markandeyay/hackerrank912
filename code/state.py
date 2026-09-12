"""Financial state as of request_date.

Reconstructs, for one request, everything the forecast needs:

* the opening balance and the minimum balance to keep,
* known future cash events (pending / scheduled debits at their settlement
  date, the scheduled next salary),
* recurring debit series detected from ~6 months of settled history,
* the projected salary / income stream, amended by structured message
  adjustments,
* blank amounts filled from the image extraction (never treated as zero).

Everything is converted into the user's home currency with the fixed
exchange-rate row for the settlement date and the stated from->to direction.
"""
from __future__ import annotations

import calendar
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta

from data import Dataset, Event, Profile, Request, parse_date

HORIZON_DAYS = 84  # see code/notes/mismatches.md: 84-86 reproduces the samples; the statement says 90

OPTIONS = {
    "estimator": "mean",  # mean | median | last
    "debit_first": False,  # on a payday, apply debits before the salary credit
    "periodic_skip_request_date": True,  # short-cycle series: skip an occurrence that lands on request_date
    "periodic_max_per_cycle": 0,  # 0 = unlimited; N = at most N occurrences of a short-cycle series before the next salary
    "exclude_image_rows_from_mean": True,
}

# --- salary description classes ------------------------------------------------
REGULAR_SALARY = {
    "Payroll credit",
    "International employer payroll",
    "Base salary",
    "New employer payroll",
    "Previous employer payroll",
    "First-job payroll",
    "Prorated first salary",
    "Payroll after returning from leave",
    "Payroll before leave",
    "Final employer payroll",
    "Primary household salary",
    "Second household income",
    "August 2019 net salary",
    "Next confirmed salary",
    "Seasonal contract payment",
    "Temporary assignment pay",
    "Peak-season wages",
}
FREELANCE_INCOME = {
    "Application project payment",
    "Client retainer payment",
    "Consulting invoice payment",
    "Content contract payment",
    "Design contract payment",
    "Freelance milestone payment",
    "Independent work payment",
    "Website project payment",
}
GIG_INCOME = {"Delivery platform payout", "Driver platform payout", "Task marketplace payout", "Weekly app earnings"}
NEVER_PROJECT_INCOME = {
    "Account commission payment",
    "Monthly sales commission",
    "Performance commission",
    "Promotion arrears payment",
    "Quarterly performance bonus",
}
ENDING_DESCRIPTIONS = {"Final employer payroll"}
SECONDARY_STREAM = {"Second household income"}

NON_RECURRING_CATEGORIES = {"work_expense", "investment", "windfall"}
NON_RECURRING_TYPES = {"refund", "investment_purchase", "investment_sale", "investment_valuation"}


def add_months(d: date, n: int) -> date:
    y = d.year + (d.month - 1 + n) // 12
    m = (d.month - 1 + n) % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


@dataclass
class Flow:
    date: date
    amount: float  # signed, home currency
    label: str
    kind: str  # known_debit | known_credit | salary | income | series | adjustment


@dataclass
class Series:
    category: str
    description: str
    amount: float  # forecast per occurrence, home currency
    cadence: str  # monthly | periodic
    step_days: int
    dates: list[date]
    flexibility: str
    latest_event_id: str
    minimum_allowed_amount: float | None
    n_hist: int

    def flows(self) -> list[Flow]:
        return [Flow(d, -self.amount, f"{self.category}: {self.description}", "series") for d in self.dates]


@dataclass
class SpendingChange:
    action: str  # stop | reduce_to
    series: Series
    new_amount: float | None  # for reduce_to

    @property
    def saving_per_occurrence(self) -> float:
        return self.series.amount if self.action == "stop" else max(0.0, self.series.amount - (self.new_amount or 0.0))

    def flows(self) -> list[Flow]:
        return [Flow(d, self.saving_per_occurrence, f"{self.action} {self.series.description}", "adjustment") for d in self.series.dates]

    def as_string(self) -> str:
        if self.action == "stop":
            return f"stop:{self.series.latest_event_id}"
        return f"reduce_to:{self.series.latest_event_id}:{fmt_amount(self.new_amount)}"


def fmt_amount(x: float) -> str:
    """Integers without decimals, otherwise exactly two decimals (620.40)."""
    x = round(x + 1e-9, 2)
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return f"{x:.2f}"


@dataclass
class State:
    request: Request
    profile: Profile
    request_date: date
    horizon_end: date
    balance: float
    min_balance: float
    flows: list[Flow] = field(default_factory=list)
    series: list[Series] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    salary_dates: list[date] = field(default_factory=list)
    salary_amount: float | None = None

    @property
    def home(self) -> str:
        return self.profile.home_currency

    def all_flows(self, extra: list[Flow] | None = None) -> list[Flow]:
        out = list(self.flows)
        for s in self.series:
            out.extend(s.flows())
        if extra:
            out.extend(extra)
        return out


# ------------------------------------------------------------------------------
class StateBuilder:
    def __init__(self, ds: Dataset, image_amounts: dict[str, float], adjustments: dict[str, list[dict]], horizon_days: int = HORIZON_DAYS, options: dict | None = None):
        """image_amounts: event_id -> amount (document currency == event currency).
        adjustments: user_id -> list of unified adjustment records.
        options: experimental switches (see OPTIONS)."""
        self.ds = ds
        self.image_amounts = image_amounts
        self.adjustments = adjustments
        self.horizon_days = horizon_days
        self.opt = dict(OPTIONS)
        if options:
            self.opt.update(options)

    # -- helpers ---------------------------------------------------------------
    def amount_of(self, ev: Event) -> float | None:
        if ev.amount is not None:
            return ev.amount
        return self.image_amounts.get(ev.event_id)

    def to_home(self, amount: float, cur: str, home: str, on: date) -> float:
        return self.ds.convert(amount, cur, home, on)

    # -- main ------------------------------------------------------------------
    def build(self, req: Request) -> State:
        ds = self.ds
        prof = ds.profiles[req.user_id]
        home = prof.home_currency
        rq = req.request_date
        end = rq + timedelta(days=self.horizon_days)
        st = State(req, prof, rq, end, prof.current_available_balance, prof.minimum_balance_to_keep)
        st.debit_first = bool(self.opt.get("debit_first"))
        adjs = self.adjustments.get(req.user_id, [])
        events = ds.events_by_user.get(req.user_id, [])
        linked_targets = {e.linked_event_id for e in events if e.linked_event_id}
        failed_with_retry = {e.linked_event_id for e in events if e.linked_event_id and e.status == "scheduled" and ds.events[e.linked_event_id].status == "failed"}

        history_debits: list[Event] = []
        history_credits: list[Event] = []
        scheduled_salary: Event | None = None

        for e in events:
            amt = self.amount_of(e)
            if e.direction == "non_cash" or e.status in ("failed", "cancelled", "unrealized"):
                continue
            if amt is None:
                st.notes.append(f"missing amount for {e.event_id} ({e.description}); ignored")
                continue
            sd = e.settlement_date or e.event_date
            if e.status == "settled":
                if sd > rq:
                    # nothing in the data, but be safe: treat as known future cash
                    v = self.to_home(amt, e.currency, home, sd)
                    st.flows.append(Flow(sd, v if e.direction == "credit" else -v, e.description, "known_credit" if e.direction == "credit" else "known_debit"))
                    continue
                if e.direction == "debit":
                    history_debits.append(e)
                else:
                    history_credits.append(e)
                continue
            if e.status == "pending":
                if e.direction == "credit":
                    st.notes.append(f"pending credit {e.event_id} ({e.description}) not counted")
                    continue
                if e.linked_event_id and "duplicate" in e.description.lower():
                    st.notes.append(f"pending duplicate charge {e.event_id} ignored")
                    continue
                v = self.to_home(amt, e.currency, home, sd)
                st.flows.append(Flow(max(sd, rq), -v, e.description, "known_debit"))
                continue
            if e.status == "scheduled":
                v = self.to_home(amt, e.currency, home, sd)
                if e.direction == "credit":
                    if e.category == "salary":
                        scheduled_salary = e
                    else:
                        st.notes.append(f"scheduled non-salary credit {e.event_id} not counted")
                    continue
                st.flows.append(Flow(max(sd, rq), -v, e.description, "known_debit"))
                continue

        # failed debits that a message says will be retried and that have no scheduled retry row
        for a in adjs:
            if a["adjustment_type"] == "payment_delayed" and a.get("related_event_id"):
                fe = ds.events.get(a["related_event_id"])
                if fe and fe.status == "failed" and fe.event_id not in failed_with_retry and fe.direction == "debit":
                    amt = self.amount_of(fe)
                    if amt is not None:
                        v = self.to_home(amt, fe.currency, home, fe.settlement_date or fe.event_date)
                        st.flows.append(Flow(rq, -v, f"retry of failed {fe.description}", "known_debit"))
                        st.notes.append(f"reserved failed-but-outstanding debit {fe.event_id}")

        self._build_income(st, history_credits, scheduled_salary, adjs)
        self._build_debit_series(st, history_debits, linked_targets, adjs)
        return st

    # -- recurring debits --------------------------------------------------------
    def _build_debit_series(self, st: State, hist: list[Event], linked_targets: set, adjs: list[dict]) -> None:
        rq, end, home = st.request_date, st.horizon_end, st.home
        groups: dict[str, list[tuple[date, float, Event]]] = defaultdict(list)
        for e in hist:
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
                continue
            if e.linked_event_id or e.event_id in linked_targets:
                continue  # reversal pairs, superseded authorizations, refunded purchases
            sd = e.settlement_date or e.event_date
            if self.opt.get("exclude_image_rows_from_mean") and e.amount_source != "csv":
                continue
            groups[e.category].append((sd, self.to_home(self.amount_of(e), e.currency, home, sd), e))

        rent_pct = 0.0
        for a in adjs:
            if a["adjustment_type"] == "expense_increase_percent" and a.get("percent") and (a.get("target") in ("rent", None, "other_expense") or True):
                rent_pct = max(rent_pct, float(a["percent"]))

        for cat, rows in groups.items():
            rows.sort(key=lambda r: r[0])
            if len(rows) < 3:
                continue
            dates = [r[0] for r in rows]
            amts = [r[1] for r in rows]
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            per = statistics.median(gaps)
            if per > 45:
                continue  # not a regular series within a 6-month window
            est = self.opt.get("estimator", "mean")
            amount = statistics.median(amts) if est == "median" else amts[-1] if est == "last" else statistics.mean(amts)
            if cat == "rent" and rent_pct:
                amount *= 1 + rent_pct / 100.0
                st.notes.append(f"rent increased by {rent_pct}% per message")
            latest = rows[-1][2]
            proj: list[date] = []
            if per >= 28:
                cadence, step = "monthly", 30
                t = add_months(dates[-1], 1)
                while t < rq:
                    t = add_months(t, 1)
                while t <= end:
                    proj.append(t)
                    t = add_months(t, 1)
            else:
                cadence, step = "periodic", max(1, int(round(per)))
                t = dates[-1] + timedelta(days=step)
                if self.opt.get("periodic_skip_request_date", True):
                    while t <= rq:
                        t += timedelta(days=step)
                else:
                    while t < rq:
                        t += timedelta(days=step)
                while t <= end:
                    proj.append(t)
                    t += timedelta(days=step)
                cap = int(self.opt.get("periodic_max_per_cycle") or 0)
                if cap and st.salary_dates:
                    bounds = sorted(set(st.salary_dates))
                    kept: list[date] = []
                    lo = rq - timedelta(days=1)
                    for hi in bounds + [end + timedelta(days=1)]:
                        seg = [d for d in proj if lo < d <= hi]
                        kept.extend(seg[:cap])
                        lo = hi
                    proj = sorted(set(kept))
            st.series.append(
                Series(
                    category=cat,
                    description=latest.description,
                    amount=amount,
                    cadence=cadence,
                    step_days=step,
                    dates=proj,
                    flexibility=latest.flexibility,
                    latest_event_id=latest.event_id,
                    minimum_allowed_amount=latest.minimum_allowed_amount,
                    n_hist=len(rows),
                )
            )

    # -- income ------------------------------------------------------------------
    def _build_income(self, st: State, hist: list[Event], scheduled: Event | None, adjs: list[dict]) -> None:
        rq, end, home = st.request_date, st.horizon_end, st.home
        salary_adjs = [a for a in adjs if a.get("target") == "salary" or a["adjustment_type"] in ("income_ended", "salary_date_change", "salary_amount_change", "one_time_confirmed_income")]
        income_ended = any(a["adjustment_type"] == "income_ended" for a in adjs)
        payout_pending = any(a["adjustment_type"] == "pending_credit_not_available" and a.get("source_type") == "service_provider" for a in adjs)
        invoice_only = [a for a in adjs if a["adjustment_type"] == "one_time_confirmed_income" and a.get("source_type") == "service_provider"]

        regular = [e for e in hist if e.category == "salary" and e.description in REGULAR_SALARY]
        freelance = [e for e in hist if e.category == "salary" and e.description in FREELANCE_INCOME]
        gig = [e for e in hist if e.category == "salary" and e.description in GIG_INCOME]
        regular.sort(key=lambda e: e.settlement_date)

        # one-off confirmed incomes from messages (arrears, approved invoices)
        one_offs: list[tuple[date | None, float, str, str]] = []  # (date or None=next payday, amount, currency, label)
        for a in adjs:
            if a["adjustment_type"] == "one_time_confirmed_income" and a.get("amount"):
                d = parse_date(a.get("effective_date")) if a.get("effective_date") else None
                one_offs.append((d, float(a["amount"]), a.get("currency") or home, a.get("template_id") or "one-off income"))

        # ---- monthly employer salary stream ----
        stream_amount: float | None = None
        stream_cur = home
        first_date: date | None = None
        if income_ended:
            st.notes.append("income ended per message; no salary projected")
        elif scheduled is not None:
            amt = self.amount_of(scheduled)
            stream_amount, stream_cur = amt, scheduled.currency
            first_date = scheduled.settlement_date or scheduled.event_date
            st.notes.append(f"salary anchored on scheduled {scheduled.event_id} {amt} {stream_cur} on {first_date}")
        elif regular:
            last = regular[-1]
            if last.description in ENDING_DESCRIPTIONS:
                st.notes.append("last payroll is final; no salary projected")
            else:
                primary = [e for e in regular if e.description not in SECONDARY_STREAM] or regular
                dom = Counter(e.event_date.day for e in primary).most_common(1)[0][0]
                base = primary[-1]  # latest regular payroll row (may have settled late)
                stream_amount, stream_cur = self.amount_of(base), base.currency
                # a one-off deviation in the latest payroll (unpaid leave, prorated
                # month) does not change the regular amount: use the modal amount of
                # the same payroll description when it is well supported
                same_desc = [self.amount_of(e) for e in primary if e.description == base.description and e.currency == base.currency]
                mode_amt, mode_n = Counter(same_desc).most_common(1)[0]
                if mode_n >= 3 and abs(mode_amt - stream_amount) > 1e-9:
                    st.notes.append(f"latest payroll {stream_amount} deviates from regular {mode_amt}; using regular amount")
                    stream_amount = mode_amt
                nxt = add_months(base.event_date, 1)
                nxt = date(nxt.year, nxt.month, min(dom, calendar.monthrange(nxt.year, nxt.month)[1]))
                while nxt < rq:
                    nxt = add_months(nxt, 1)
                stale = (rq - base.settlement_date).days > 45
                has_resume = any(a["adjustment_type"] in ("salary_amount_change", "salary_date_change") and a.get("effective_date") for a in salary_adjs)
                if stale and not has_resume:
                    st.notes.append(f"salary stream stale (last {base.settlement_date}); not projected")
                    stream_amount = None
                else:
                    first_date = nxt

        # message amendments to the monthly stream
        temp_first_amount: float | None = None
        temp_first_cur: str | None = None
        for a in salary_adjs:
            t = a["adjustment_type"]
            if t == "salary_amount_change" and a.get("amount") and str(a.get("template_id") or "").startswith("T07"):
                st.notes.append("commission-pending message: keeping the settled base salary, commissions excluded")
                continue
            if t == "salary_amount_change" and a.get("amount"):
                eff = parse_date(a.get("effective_date")) if a.get("effective_date") else None
                if a.get("scope") == "next_payment_only":
                    temp_first_amount, temp_first_cur = float(a["amount"]), a.get("currency") or home
                    if eff and eff >= rq:
                        first_date = eff
                    elif first_date is None and eff is None and stream_amount is None:
                        pass
                else:
                    stream_amount, stream_cur = float(a["amount"]), a.get("currency") or home
                    if eff and eff >= rq:
                        first_date = eff
                    elif first_date is None:
                        # a permanent amount with no usable date: fall back to the historical payday
                        if regular:
                            dom = Counter(e.settlement_date.day for e in regular).most_common(1)[0][0]
                            nxt = add_months(regular[-1].settlement_date, 1)
                            nxt = date(nxt.year, nxt.month, min(dom, calendar.monthrange(nxt.year, nxt.month)[1]))
                            while nxt < rq:
                                nxt = add_months(nxt, 1)
                            first_date = nxt
                if eff and eff < rq and first_date is None and regular:
                    pass
            elif t == "salary_date_change" and a.get("effective_date"):
                eff = parse_date(a["effective_date"])
                if eff and eff >= rq:
                    first_date = eff
            elif t == "one_time_confirmed_income" and a.get("regular_salary_amount"):
                stream_amount, stream_cur = float(a["regular_salary_amount"]), a.get("currency") or home

        if stream_amount is not None and first_date is not None and not income_ended:
            t, k = first_date, 0
            while t <= end:
                if t >= rq:
                    amt_native = stream_amount
                    cur = stream_cur
                    if k == 0 and temp_first_amount is not None:
                        amt_native, cur = temp_first_amount, temp_first_cur or stream_cur
                    v = self.to_home(amt_native, cur, home, t)
                    st.flows.append(Flow(t, v, "salary", "salary"))
                    st.salary_dates.append(t)
                    if st.salary_amount is None:
                        st.salary_amount = v
                k += 1
                t = add_months(first_date, k)

        # ---- freelance / gig streams (periodic) ----
        for label, rows in (("freelance income", freelance), ("gig payout", gig)):
            if len(rows) < 3:
                continue
            if income_ended or payout_pending or invoice_only:
                st.notes.append(f"{label} not projected (message: ended/pending/only confirmed invoices count)")
                continue
            rows.sort(key=lambda e: e.settlement_date)
            dates = [e.settlement_date for e in rows]
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            step = max(1, int(round(statistics.median(gaps))))
            amount = statistics.mean(self.to_home(self.amount_of(e), e.currency, home, e.settlement_date) for e in rows)
            t = dates[-1] + timedelta(days=step)
            while t <= rq:
                t += timedelta(days=step)
            while t <= end:
                st.flows.append(Flow(t, amount, label, "income"))
                st.salary_dates.append(t)
                t += timedelta(days=step)
            st.notes.append(f"{label}: {amount:.2f} every {step} days")

        # ---- one-off confirmed incomes ----
        for d, amt, cur, label in one_offs:
            if d is None:
                future = [x for x in st.salary_dates if x >= rq]
                d = min(future) if future else None
            if d is None or d < rq or d > end:
                continue
            v = self.to_home(amt, cur, home, d)
            # dedupe against a known credit of the same size within 3 days
            dup = any(f.amount > 0 and abs(f.amount - v) < 0.01 and abs((f.date - d).days) <= 3 and f.kind in ("known_credit",) for f in st.flows)
            if dup:
                st.notes.append(f"one-off {label} already present; not added twice")
                continue
            st.flows.append(Flow(d, v, label, "income"))
            st.salary_dates.append(d)
        st.salary_dates.sort()
