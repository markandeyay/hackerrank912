"""Output formatting, validate_rows on the samples, and the sample-pipeline regression."""
import csv

import pytest

from data import DATASET_DIR
from pipeline import fmt_safe, run
from state import fmt_amount
from validate import COLUMNS, validate_rows

# Current scores of the --no-llm pipeline on sample_requests.csv (regression floor).
FLOOR = {
    "amount_safe_to_pay": 4,
    "affordability_status": 24,
    "recommended_payment_method": 24,
    "payment_plan": 23,
    "earliest_date_for_full_payment": 23,
    "spending_changes_needed": 23,
}
FLOOR_WITHIN_2PCT = 16


@pytest.mark.parametrize("x,s", [(620.4, "620.40"), (25256, "25256"), (25256.0, "25256"), (23.5, "23.50"), (0.004, "0"), (1852.114, "1852.11"), (99.995, "100")])
def test_fmt_amount(x, s):
    assert fmt_amount(x) == s


@pytest.mark.parametrize("x,s", [(17229139.2, "17229139.2"), (25256.0, "25256"), (0.0, "0"), (1234.56, "1234.56"), (0.5, "0.5")])
def test_fmt_safe(x, s):
    assert fmt_safe(x) == s


def _sample_rows():
    with open(DATASET_DIR / "sample_requests.csv", "r", encoding="utf-8", newline="") as f:
        return [{c: r[c] for c in COLUMNS} for r in csv.DictReader(f)]


def test_validate_rows_accepts_sample_rows(ds):
    rows = _sample_rows()
    assert len(rows) == 25
    assert validate_rows(rows, ds, "sample_requests.csv") == []


def test_validate_rows_flags_broken_rows(ds):
    rows = _sample_rows()
    rows[0]["affordability_status"] = "affordable_later"  # full_payment with wrong status
    rows[1]["payment_plan"] = "2025-08-08:1"  # installments not matching an option
    rows[2]["amount_safe_to_pay"] = "-1"
    probs = validate_rows(rows[:3], ds, "sample_requests.csv")
    assert any("request_01" in p for p in probs) and any("request_02" in p for p in probs) and any("request_03" in p for p in probs)
    assert any("missing 22 request ids" in p for p in probs)


def test_dataset_shape(ds):
    reqs = ds.load_requests()
    assert len(reqs) == 250 and len({r.request_id for r in reqs}) == 250
    assert all(2 <= len(ds.options_by_request.get(r.request_id, [])) <= 4 for r in reqs)
    assert all(r.user_id in ds.profiles for r in reqs)
    blank = [e for e in ds.events.values() if e.amount is None]
    assert blank and all(e.event_id in ds.images_by_event for e in blank)


def test_sample_pipeline_regression(ds):
    reqs = ds.load_requests("sample_requests.csv")
    results = run(reqs, ds, use_llm=False)
    rows = [row for _, row in results]
    assert validate_rows(rows, ds, "sample_requests.csv") == []
    exact = {c: 0 for c in FLOOR}
    close = 0
    for dec, row in results:
        exp = dec.request.expected
        for c in FLOOR:
            exact[c] += row[c] == exp[c]
        close += abs(float(row["amount_safe_to_pay"]) - float(exp["amount_safe_to_pay"])) <= 0.02 * max(1.0, float(exp["amount_safe_to_pay"]))
    for c, floor in FLOOR.items():
        assert exact[c] >= floor, f"{c}: {exact[c]}/25 < floor {floor}"
    assert close >= FLOOR_WITHIN_2PCT
    # a second run is deterministic
    rows2 = [row for _, row in run(reqs, ds, use_llm=False)]
    assert rows2 == rows


def test_regex_adjustment_on_dataset_message(ds):
    from messages_regex import regex_adjustment

    m = next(m for m in ds.messages if m.message_id == "message_01")
    rec = regex_adjustment(m)
    assert rec["adjustment_type"] == "salary_amount_change" and rec["scope"] == "permanent"
    assert rec["amount"] == 42750000.0 and rec["currency"] == "IDR" and rec["effective_date"] == "2025-08-15"
    assert rec["template_id"].startswith("T01")
