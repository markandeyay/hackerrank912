"""Loading and joining of the dataset files (dataset/ relative to repo root)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = REPO_ROOT / "dataset"
IMAGE_DIR = DATASET_DIR / "media" / "images"


def parse_date(s) -> date | None:
    if s is None:
        return None
    s = str(s).strip()
    if not s or s.lower() == "nan":
        return None
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _split_list(s) -> list[str]:
    if s is None:
        return []
    s = str(s).strip()
    if not s or s.lower() == "nan":
        return []
    return [p.strip() for p in s.split("|") if p.strip()]


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATASET_DIR / name, dtype=str, keep_default_na=False)


def _num(s) -> float | None:
    s = "" if s is None else str(s).strip()
    if s == "" or s.lower() == "nan":
        return None
    return float(s)


@dataclass
class Profile:
    user_id: str
    home_currency: str
    current_available_balance: float
    minimum_balance_to_keep: float
    financial_priorities: list[str]
    protect: list[str]
    reduce: list[str]
    stop: list[str]
    methods: list[str]
    max_installment_months: int | None


@dataclass
class Event:
    event_id: str
    user_id: str
    event_type: str
    description: str
    category: str
    direction: str
    amount: float | None
    currency: str
    event_date: date
    settlement_date: date | None
    status: str
    linked_event_id: str | None
    flexibility: str
    minimum_allowed_amount: float | None
    amount_source: str = "csv"  # csv | image | missing


@dataclass
class PaymentOption:
    payment_option_id: str
    request_id: str
    payment_method: str
    payment_amount: float
    number_of_payments: int
    first_payment_date: date
    payment_frequency_days: int | None
    financing_fee: float
    total_payable_amount: float

    @property
    def option_num(self) -> int:
        return int(self.payment_option_id.rsplit("_", 1)[1])

    def schedule(self) -> list[tuple[date, float]]:
        out = []
        for k in range(self.number_of_payments):
            d = self.first_payment_date + timedelta(days=k * (self.payment_frequency_days or 0))
            out.append((d, self.payment_amount))
        return out


@dataclass
class Request:
    request_id: str
    user_id: str
    request_date: date
    request_type: str
    requested_amount: float
    desired_completion_date: date
    allows_partial_payment: bool
    request_text: str
    expected: dict = field(default_factory=dict)  # sample-only fields


@dataclass
class Message:
    message_id: str
    user_id: str
    request_id: str | None
    related_event_id: str | None
    sent_at: datetime
    source_type: str
    message_text: str


@dataclass
class ImageRef:
    image_id: str
    user_id: str
    request_id: str | None
    related_event_id: str | None

    @property
    def path(self) -> Path:
        return IMAGE_DIR / f"{self.image_id}.png"


EXPECTED_COLS = [
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
    "decision_explanation",
]


class Dataset:
    def __init__(self, dataset_dir: Path | None = None):
        global DATASET_DIR, IMAGE_DIR
        if dataset_dir is not None:
            DATASET_DIR = Path(dataset_dir)
            IMAGE_DIR = DATASET_DIR / "media" / "images"
        self.profiles: dict[str, Profile] = {}
        for r in _read("financial_profiles.csv").to_dict("records"):
            mim = r.get("max_installment_months", "").strip()
            self.profiles[r["user_id"]] = Profile(
                user_id=r["user_id"],
                home_currency=r["home_currency"].strip(),
                current_available_balance=float(r["current_available_balance"]),
                minimum_balance_to_keep=float(r["minimum_balance_to_keep"]),
                financial_priorities=_split_list(r["financial_priorities"]),
                protect=_split_list(r["expense_categories_to_protect"]),
                reduce=_split_list(r["expense_categories_user_is_willing_to_reduce"]),
                stop=_split_list(r["expense_categories_user_is_willing_to_stop"]),
                methods=_split_list(r["payment_methods_user_will_consider"]),
                max_installment_months=int(float(mim)) if mim else None,
            )

        self.events: dict[str, Event] = {}
        self.events_by_user: dict[str, list[Event]] = {}
        for r in _read("financial_events.csv").to_dict("records"):
            ev = Event(
                event_id=r["event_id"],
                user_id=r["user_id"],
                event_type=r["event_type"].strip(),
                description=r["description"].strip(),
                category=r["category"].strip(),
                direction=r["direction"].strip(),
                amount=_num(r["amount"]),
                currency=r["currency"].strip(),
                event_date=parse_date(r["event_date"]),
                settlement_date=parse_date(r["settlement_date"]),
                status=r["status"].strip(),
                linked_event_id=(r["linked_event_id"].strip() or None),
                flexibility=r["flexibility"].strip(),
                minimum_allowed_amount=_num(r["minimum_allowed_amount"]),
            )
            if ev.amount is None:
                ev.amount_source = "image"  # filled later from the image extraction
            self.events[ev.event_id] = ev
            self.events_by_user.setdefault(ev.user_id, []).append(ev)

        self.rates: dict[tuple[date, str, str], float] = {}
        for r in _read("exchange_rates.csv").to_dict("records"):
            self.rates[(parse_date(r["rate_date"]), r["from_currency"].strip(), r["to_currency"].strip())] = float(r["rate"])

        self.options_by_request: dict[str, list[PaymentOption]] = {}
        for r in _read("request_payment_options.csv").to_dict("records"):
            freq = r["payment_frequency_days"].strip()
            po = PaymentOption(
                payment_option_id=r["payment_option_id"],
                request_id=r["request_id"],
                payment_method=r["payment_method"].strip(),
                payment_amount=float(r["payment_amount"]),
                number_of_payments=int(float(r["number_of_payments"])),
                first_payment_date=parse_date(r["first_payment_date"]),
                payment_frequency_days=int(float(freq)) if freq else None,
                financing_fee=_num(r["financing_fee"]) or 0.0,
                total_payable_amount=float(r["total_payable_amount"]),
            )
            self.options_by_request.setdefault(po.request_id, []).append(po)
        for lst in self.options_by_request.values():
            lst.sort(key=lambda o: o.option_num)

        self.messages: list[Message] = []
        for r in _read("messages.csv").to_dict("records"):
            self.messages.append(
                Message(
                    message_id=r["message_id"],
                    user_id=r["user_id"],
                    request_id=r["request_id"].strip() or None,
                    related_event_id=r["related_event_id"].strip() or None,
                    sent_at=datetime.strptime(r["sent_at"].strip().replace("Z", ""), "%Y-%m-%dT%H:%M:%S"),
                    source_type=r["source_type"].strip(),
                    message_text=r["message_text"],
                )
            )
        self.messages_by_user: dict[str, list[Message]] = {}
        for m in self.messages:
            self.messages_by_user.setdefault(m.user_id, []).append(m)

        self.images: list[ImageRef] = []
        for r in _read("images.csv").to_dict("records"):
            self.images.append(
                ImageRef(
                    image_id=r["image_id"],
                    user_id=r["user_id"],
                    request_id=r["request_id"].strip() or None,
                    related_event_id=r["related_event_id"].strip() or None,
                )
            )
        self.images_by_event: dict[str, list[ImageRef]] = {}
        self.images_by_user: dict[str, list[ImageRef]] = {}
        for im in self.images:
            if im.related_event_id:
                self.images_by_event.setdefault(im.related_event_id, []).append(im)
            self.images_by_user.setdefault(im.user_id, []).append(im)

    # ---- requests -------------------------------------------------------
    def load_requests(self, name: str = "requests.csv") -> list[Request]:
        out = []
        for r in _read(name).to_dict("records"):
            req = Request(
                request_id=r["request_id"],
                user_id=r["user_id"],
                request_date=parse_date(r["request_date"]),
                request_type=r["request_type"].strip(),
                requested_amount=float(r["requested_amount"]),
                desired_completion_date=parse_date(r["desired_completion_date"]),
                allows_partial_payment=str(r["allows_partial_payment"]).strip().lower() == "true",
                request_text=r["request_text"],
            )
            if all(c in r for c in EXPECTED_COLS):
                req.expected = {c: r[c] for c in EXPECTED_COLS}
            out.append(req)
        return out

    # ---- helpers --------------------------------------------------------
    def convert(self, amount: float, from_cur: str, to_cur: str, on: date) -> float:
        """Convert using the fixed rate row for (date, from, to); fall back to
        the inverse pair and finally to the nearest dated rate for the pair."""
        if from_cur == to_cur:
            return amount
        r = self.rates.get((on, from_cur, to_cur))
        if r is not None:
            return amount * r
        r = self.rates.get((on, to_cur, from_cur))
        if r is not None and r != 0:
            return amount / r
        cands = [(d, v, False) for (d, f, t), v in self.rates.items() if f == from_cur and t == to_cur]
        cands += [(d, v, True) for (d, f, t), v in self.rates.items() if f == to_cur and t == from_cur]
        if not cands:
            raise KeyError(f"no exchange rate for {from_cur}->{to_cur} on {on}")
        earlier = [c for c in cands if c[0] <= on]
        pick = max(earlier, key=lambda c: c[0]) if earlier else min(cands, key=lambda c: c[0])
        d, v, inv = pick
        return amount / v if inv else amount * v

    def messages_for(self, user_id: str, request_id: str | None = None) -> list[Message]:
        return [m for m in self.messages_by_user.get(user_id, []) if m.request_id in (None, request_id)]
