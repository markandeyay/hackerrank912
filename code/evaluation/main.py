"""Score the pipeline against dataset/sample_requests.csv, column by column.

Run:  python code/evaluation/main.py [--llm] [--horizon N] [--verbose]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CODE_DIR))

from data import Dataset  # noqa: E402
from pipeline import run  # noqa: E402
from state import HORIZON_DAYS  # noqa: E402

COLS = [
    "amount_safe_to_pay",
    "affordability_status",
    "recommended_payment_method",
    "payment_plan",
    "earliest_date_for_full_payment",
    "spending_changes_needed",
]


def _close(a: str, b: str, tol: float) -> bool:
    try:
        x, y = float(a), float(b)
    except ValueError:
        return a == b
    return abs(x - y) <= tol * max(1.0, abs(y))


def score(results, verbose: bool = False, tol: float = 0.02) -> dict:
    exact = {c: 0 for c in COLS}
    close = 0
    n = 0
    rows = []
    for dec, row in results:
        exp = dec.request.expected
        if not exp:
            continue
        n += 1
        diffs = []
        for c in COLS:
            if row[c] == exp[c]:
                exact[c] += 1
            else:
                diffs.append((c, row[c], exp[c]))
        if _close(row["amount_safe_to_pay"], exp["amount_safe_to_pay"], tol):
            close += 1
        rows.append((dec.request.request_id, diffs))
        if verbose and diffs:
            print(f"--- {dec.request.request_id} ({dec.request.user_id}) requested {dec.request.requested_amount} trough-safe {row['amount_safe_to_pay']}")
            for c, got, want in diffs:
                print(f"    {c:32s} got={got!s:40s} want={want}")
            for note in dec.state.notes[:6]:
                print(f"      note: {note}")
    summary = {c: f"{exact[c]}/{n}" for c in COLS}
    summary["amount_safe_to_pay_within_2pct"] = f"{close}/{n}"
    total = sum(exact.values())
    summary["overall_exact"] = f"{total}/{n * len(COLS)} ({100.0 * total / (n * len(COLS)):.1f}%)"
    return summary


def table(results, ds) -> None:
    """All sample rows: got/want amount, numeric gap, and per-column match marks."""
    print(f"{'request':11s} {'got_safe':>14s} {'want_safe':>14s} {'gap':>12s} {'gap%req':>8s} {'gap%res':>8s} {'want_res':>12s}  status meth plan earl chg")
    tot = 0.0
    for dec, row in results:
        exp = dec.request.expected
        if not exp:
            continue
        got, want = float(row["amount_safe_to_pay"]), float(exp["amount_safe_to_pay"])
        prof = ds.profiles[dec.request.user_id]
        head = prof.current_available_balance - prof.minimum_balance_to_keep
        want_res = head - want
        gap = got - want
        tot += abs(gap)
        marks = " ".join("ok " if row[c] == exp[c] else "XX " for c in COLS[1:])
        capped = " (capped)" if want >= dec.request.requested_amount - 1e-6 else ""
        print(f"{dec.request.request_id:11s} {got:14.2f} {want:14.2f} {gap:+12.2f} {100*gap/dec.request.requested_amount:+7.2f}% {(100*gap/want_res if want_res else 0):+7.2f}% {want_res:12.2f}  {marks}{capped}")
    print(f"total |gap| = {tot:,.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", action="store_true", help="print all sample rows with the numeric gap")
    ap.add_argument("--llm", action="store_true", help="use the cached/model evidence extraction instead of the deterministic fallback")
    ap.add_argument("--horizon", type=int, default=HORIZON_DAYS)
    ap.add_argument("--verbose", "-v", action="store_true")
    ap.add_argument("--tol", type=float, default=0.02)
    args = ap.parse_args()
    ds = Dataset()
    reqs = ds.load_requests("sample_requests.csv")
    results = run(reqs, ds, use_llm=args.llm, horizon_days=args.horizon)
    if args.table:
        table(results, ds)
    summary = score(results, verbose=args.verbose, tol=args.tol)
    for k, v in summary.items():
        print(f"{k:36s} {v}")


if __name__ == "__main__":
    main()
