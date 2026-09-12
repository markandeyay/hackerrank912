"""Dataset.convert: direct rate, inverse pair, nearest-date fallback, same currency."""
from datetime import date

import pytest
from conftest import FakeDataset

D0 = date(2024, 3, 15)


def _ds(rates):
    return FakeDataset(profiles=[], events=[], rates=rates)


def test_same_currency_needs_no_rate():
    assert _ds({}).convert(123.45, "INR", "INR", D0) == 123.45


def test_direct_rate_on_settlement_date():
    ds = _ds({(D0, "USD", "INR"): 83.0})
    assert ds.convert(10, "USD", "INR", D0) == pytest.approx(830.0)


def test_inverse_pair_fallback():
    ds = _ds({(D0, "USD", "EUR"): 0.92})
    assert ds.convert(92, "EUR", "USD", D0) == pytest.approx(100.0)


def test_direct_rate_wins_over_inverse_when_both_exist():
    ds = _ds({(D0, "EUR", "USD"): 1.10, (D0, "USD", "EUR"): 0.92})
    assert ds.convert(1, "EUR", "USD", D0) == pytest.approx(1.10)


def test_nearest_earlier_date_fallback():
    ds = _ds({(date(2024, 3, 1), "USD", "INR"): 80.0, (date(2024, 4, 1), "USD", "INR"): 90.0})
    # latest rate dated on/before the settlement date
    assert ds.convert(1, "USD", "INR", date(2024, 3, 20)) == pytest.approx(80.0)
    # exact later date
    assert ds.convert(1, "USD", "INR", date(2024, 4, 1)) == pytest.approx(90.0)
    # after the last dated rate: the latest one
    assert ds.convert(1, "USD", "INR", date(2024, 6, 1)) == pytest.approx(90.0)


def test_nearest_date_fallback_before_first_rate_uses_earliest():
    ds = _ds({(date(2024, 3, 1), "USD", "INR"): 80.0, (date(2024, 4, 1), "USD", "INR"): 90.0})
    assert ds.convert(1, "USD", "INR", date(2024, 1, 1)) == pytest.approx(80.0)


def test_nearest_date_fallback_via_inverse_pair():
    ds = _ds({(date(2024, 3, 1), "USD", "EUR"): 0.8})
    assert ds.convert(8, "EUR", "USD", date(2024, 3, 9)) == pytest.approx(10.0)


def test_missing_pair_raises():
    with pytest.raises(KeyError):
        _ds({(D0, "USD", "INR"): 83.0}).convert(1, "GBP", "INR", D0)


def test_real_dataset_pairs(ds):
    # EUR->ZAR is 20 on 2023-10-15; USD->EUR is 0.92 on that date
    assert ds.convert(1, "EUR", "ZAR", date(2023, 10, 15)) == pytest.approx(20.0)
    assert ds.convert(20, "ZAR", "EUR", date(2023, 10, 15)) == pytest.approx(1.0)
    assert ds.convert(1, "USD", "EUR", date(2023, 10, 15)) == pytest.approx(0.92)
