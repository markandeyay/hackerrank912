"""pytest configuration: import the engine modules from code/ and provide
small synthetic fixtures.  pytest is a dev-only dependency (not in
code/requirements.txt)."""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

CODE_DIR = Path(__file__).resolve().parent.parent

# `python -m pytest` puts the cwd (repo root) on sys.path, where the empty
# code/__init__.py shadows the standard-library `code` module that pdb needs.
# Nothing imports `code` as a package, so drop those entries and make sure the
# stdlib module is the one registered.
import os  # noqa: E402

for _p in {"", ".", os.getcwd(), str(CODE_DIR.parent)}:
    while _p in sys.path:
        sys.path.remove(_p)
if "code" in sys.modules and not hasattr(sys.modules["code"], "InteractiveConsole"):
    del sys.modules["code"]
import code as _stdlib_code  # noqa: E402,F401

if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from data import Dataset, Event, PaymentOption, Profile, Request  # noqa: E402
from state import Flow, State  # noqa: E402


class FakeDataset:
    """Minimal stand-in for data.Dataset built from dataclasses in memory."""

    convert = Dataset.convert
    messages_for = Dataset.messages_for

    def __init__(self, profiles, events, rates=None, options=None):
        self.profiles = {p.user_id: p for p in profiles}
        self.events = {e.event_id: e for e in events}
        self.events_by_user: dict[str, list[Event]] = {}
        for e in events:
            self.events_by_user.setdefault(e.user_id, []).append(e)
        self.rates = dict(rates or {})
        self.options_by_request = dict(options or {})
        self.messages = []
        self.messages_by_user = {}
        self.images = []
        self.images_by_event = {}
        self.images_by_user = {}


def make_profile(**kw) -> Profile:
    base = dict(
        user_id="u1",
        home_currency="INR",
        current_available_balance=1000.0,
        minimum_balance_to_keep=200.0,
        financial_priorities=[],
        protect=[],
        reduce=[],
        stop=[],
        methods=["full_payment", "partial_payment", "installments"],
        max_installment_months=6,
    )
    base.update(kw)
    return Profile(**base)


_counter = {"n": 0}


def make_event(**kw) -> Event:
    _counter["n"] += 1
    base = dict(
        event_id=f"ev{_counter['n']}",
        user_id="u1",
        event_type="expense",
        description="Grocery run",
        category="groceries",
        direction="debit",
        amount=100.0,
        currency="INR",
        event_date=date(2024, 1, 5),
        settlement_date=None,
        status="settled",
        linked_event_id=None,
        flexibility="fixed",
        minimum_allowed_amount=None,
    )
    base.update(kw)
    if base["settlement_date"] is None:
        base["settlement_date"] = base["event_date"]
    return Event(**base)


def make_request(**kw) -> Request:
    base = dict(
        request_id="r1",
        user_id="u1",
        request_date=date(2024, 4, 1),
        request_type="purchase",
        requested_amount=600.0,
        desired_completion_date=date(2024, 5, 1),
        allows_partial_payment=True,
        request_text="Can I afford this?",
    )
    base.update(kw)
    return Request(**base)


def make_option(**kw) -> PaymentOption:
    base = dict(
        payment_option_id="payment_option_02",
        request_id="r1",
        payment_method="installments",
        payment_amount=200.0,
        number_of_payments=3,
        first_payment_date=date(2024, 4, 3),
        payment_frequency_days=30,
        financing_fee=0.0,
        total_payable_amount=600.0,
    )
    base.update(kw)
    return PaymentOption(**base)


def make_state(balance=1000.0, min_balance=200.0, flows=None, request=None, profile=None, horizon_days=84) -> State:
    """A State built directly from signed (day_offset, amount) flows."""
    req = request or make_request()
    prof = profile or make_profile(current_available_balance=balance, minimum_balance_to_keep=min_balance)
    rq = req.request_date
    st = State(req, prof, rq, rq + timedelta(days=horizon_days), balance, min_balance)
    for off, amt in flows or []:
        st.flows.append(Flow(rq + timedelta(days=off), amt, f"flow{off}", "known_credit" if amt > 0 else "known_debit"))
    return st


@pytest.fixture(scope="session")
def ds() -> Dataset:
    return Dataset()
