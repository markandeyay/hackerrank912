"""Task 2: exact-interval projection variants vs the current rule, on the 25 samples.

Run:  .venv/Scripts/python code/notes/improve2/exact_interval_variants.py
Read-only against the engine (subclasses StateBuilder; deterministic evidence path,
use_llm=False, so the concurrent cache rebuild does not matter).

Variants (short-cycle = median gap < 28 days, as the engine classifies them):
  current      engine: step = round(median gap), skip an occurrence on request_date,
               bring every short-cycle series forward to payday-1 if its first
               occurrence would fall on/after the first payday
  E_last       next = last event + last observed gap, repeated; no skip, no bring-forward
  E_mode       same with the modal gap
  E_last_skip  E_last + request-date skip
  E_mode_skip  E_mode + request-date skip
  H            hybrid: exact interval (no skip/no bring-forward) for constant-gap
               series, current rule for irregular ones
  H_skip       hybrid keeping the request-date skip for constant-gap series
  E_mon        E_last + monthly series projected at last + last gap instead of same DOM
"""
from __future__ import annotations

import statistics
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR))

from data import Dataset  # noqa: E402
from explain import template_explanation  # noqa: E402
from pipeline import decision_row, load_adjustments, load_image_amounts  # noqa: E402
from planner import decide  # noqa: E402
from state import NON_RECURRING_CATEGORIES, NON_RECURRING_TYPES, StateBuilder  # noqa: E402

COLS = ["amount_safe_to_pay", "affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed"]
FOCUS = ["request_02", "request_03", "request_04", "request_06", "request_18", "request_20", "request_21", "request_23"]


def _close(a, b, tol):
    try:
        x, y = float(a), float(b)
    except ValueError:
        return a == b
    return abs(x - y) <= tol * max(1.0, abs(y))


class ExactBuilder(StateBuilder):
    """gap_rule: engine | last | mode ; skip: request-date skip for re-projected series;
    hybrid: only re-project constant-gap series; monthly_lastgap: monthly series at last + last gap."""

    def __init__(self, *a, gap_rule="engine", skip=False, hybrid=False, monthly_lastgap=False, **k):
        super().__init__(*a, **k)
        self.gap_rule, self.skip, self.hybrid, self.monthly_lastgap = gap_rule, skip, hybrid, monthly_lastgap
        self.reprojected = set()

    def _build_debit_series(self, st, hist, linked_targets, adjs):
        super()._build_debit_series(st, hist, linked_targets, adjs)
        if self.gap_rule == "engine":
            return
        rq, end = st.request_date, st.horizon_end
        groups = defaultdict(list)
        for e in hist:
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
                continue
            if e.linked_event_id or e.event_id in linked_targets:
                continue
            if self.opt.get("exclude_image_rows_from_mean") and e.amount_source != "csv":
                continue
            groups[e.category].append(e.settlement_date or e.event_date)
        for s in st.series:
            dates = sorted(groups[s.category])
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            constant = len(set(gaps)) == 1
            if s.cadence == "monthly" and not self.monthly_lastgap:
                continue
            if self.hybrid and not constant:
                continue  # keep the engine projection (median gap + skip + bring-forward)
            step = gaps[-1] if self.gap_rule == "last" else Counter(gaps).most_common(1)[0][0]
            t = dates[-1] + timedelta(days=step)
            if self.skip:
                while t <= rq:
                    t += timedelta(days=step)
            else:
                while t < rq:
                    t += timedelta(days=step)
            proj = []
            while t <= end:
                proj.append(t)
                t += timedelta(days=step)
            s.dates = proj
            s.step_days = step
            if s.cadence == "monthly":
                s.cadence = "periodic_month"  # not "periodic": stays outside the bring-forward rule
            self.reprojected.add((st.request.request_id, s.category))

    def build(self, req):
        st = super().build(req)
        return st


VARIANTS = {
    "current": dict(gap_rule="engine", options={}),
    "E_last": dict(gap_rule="last", skip=False, options={"periodic_at_least_once_before_payday": False}),
    "E_mode": dict(gap_rule="mode", skip=False, options={"periodic_at_least_once_before_payday": False}),
    "E_last_skip": dict(gap_rule="last", skip=True, options={"periodic_at_least_once_before_payday": False}),
    "E_mode_skip": dict(gap_rule="mode", skip=True, options={"periodic_at_least_once_before_payday": False}),
    "E_last_skip_bf": dict(gap_rule="last", skip=True, options={}),  # == current if all gaps constant
    "H": dict(gap_rule="last", skip=False, hybrid=True, options={"periodic_at_least_once_before_payday": False}),
    "H_skip": dict(gap_rule="last", skip=True, hybrid=True, options={"periodic_at_least_once_before_payday": False}),
    "E_mon": dict(gap_rule="last", skip=False, monthly_lastgap=True, options={"periodic_at_least_once_before_payday": False}),
    "E_mon_skip_bf": dict(gap_rule="last", skip=True, monthly_lastgap=True, options={}),
}


def evaluate(ds, reqs, images, adjs, spec):
    opts = dict(spec.get("options") or {})
    b = ExactBuilder(ds, images, adjs, options=opts, gap_rule=spec["gap_rule"], skip=spec.get("skip", False), hybrid=spec.get("hybrid", False), monthly_lastgap=spec.get("monthly_lastgap", False))
    rows = {}
    for req in reqs:
        st = b.build(req)
        dec = decide(st, ds.options_by_request.get(req.request_id, []))
        row = decision_row(dec, template_explanation(dec))
        rows[req.request_id] = (row, req, st)
    return rows


def summarize(name, rows, base_rows=None):
    exact = Counter()
    w1 = w2 = 0
    tot = 0.0
    lost = []
    gained = []
    for rid, (row, req, st) in rows.items():
        exp = req.expected
        for c in COLS:
            ok = row[c] == exp[c]
            if ok:
                exact[c] += 1
            if base_rows is not None:
                bok = base_rows[rid][0][c] == exp[c]
                if bok and not ok:
                    lost.append(f"{rid}:{c}")
                if ok and not bok:
                    gained.append(f"{rid}:{c}")
        got, want = float(row["amount_safe_to_pay"]), float(exp["amount_safe_to_pay"])
        tot += abs(got - want)
        w1 += _close(row["amount_safe_to_pay"], exp["amount_safe_to_pay"], 0.01)
        w2 += _close(row["amount_safe_to_pay"], exp["amount_safe_to_pay"], 0.02)
    total = sum(exact.values())
    cols = " ".join(f"{exact[c]:2d}" for c in COLS)
    print(f"{name:16s} exact[amt st meth plan earl chg]={cols}  overall={total}/150  within1%={w1:2d}  within2%={w2:2d}  total|gap|={tot:,.2f}")
    if base_rows is not None:
        print(f"{'':16s}   lost vs current: {lost or 'none'} | gained: {gained or 'none'}")
    return exact, w1, w2, tot


def per_sample(name, rows, ids):
    print(f"\n-- {name}: focus samples")
    print(f"{'request':11s} {'got':>14s} {'want':>14s} {'gap':>13s} {'gap%res':>8s}  st meth plan earl chg   periodic dates before first payday")
    for rid in ids:
        row, req, st = rows[rid]
        exp = req.expected
        got, want = float(row["amount_safe_to_pay"]), float(exp["amount_safe_to_pay"])
        prof = st.profile
        res = prof.current_available_balance - prof.minimum_balance_to_keep - want
        marks = " ".join("ok" if row[c] == exp[c] else "XX" for c in COLS[1:])
        payday = min(st.salary_dates) if st.salary_dates else None
        occ = []
        for s in st.series:
            if s.cadence != "monthly":
                before = [d for d in s.dates if payday is None or d < payday]
                on_after = [d for d in s.dates if payday is not None and payday <= d <= payday + timedelta(days=1)]
                occ.append(f"{s.category[:5]}/{s.step_days}d:{len(before)}" + (f"(+{len(on_after)}@payday)" if on_after else ""))
        print(f"{rid:11s} {got:14.2f} {want:14.2f} {got-want:+13.2f} {100*(got-want)/res if res else 0:+7.2f}%  {marks}   payday={payday} {' '.join(occ)}")


def main():
    ds = Dataset()
    reqs = ds.load_requests("sample_requests.csv")
    images = load_image_amounts(ds, False)
    adjs = load_adjustments(ds, False)
    results = {}
    for name, spec in VARIANTS.items():
        results[name] = evaluate(ds, reqs, images, adjs, spec)
    print("== summary (25 samples, deterministic evidence path)")
    base = results["current"]
    for name in VARIANTS:
        summarize(name, results[name], None if name == "current" else base)
    # identical-output check between gap rules
    for a, b in (("E_last", "E_mode"), ("E_last_skip", "E_mode_skip"), ("E_last_skip_bf", "current"), ("H", "E_last"), ("H_skip", "E_last_skip")):
        same = all(results[a][r][0][c] == results[b][r][0][c] for r in results[a] for c in COLS)
        print(f"   {a} == {b} on all six columns: {same}")
    for name in ("current", "E_last", "E_last_skip", "E_mon"):
        per_sample(name, results[name], FOCUS)
    # full per-sample amount table
    print("\n== per-sample amount error (got - want) by variant")
    names = ["current", "E_last", "E_last_skip", "E_mon"]
    print(f"{'request':11s} {'want':>14s} " + " ".join(f"{n:>16s}" for n in names))
    for r in reqs:
        want = float(r.expected["amount_safe_to_pay"])
        cells = []
        for n in names:
            row = results[n][r.request_id][0]
            got = float(row["amount_safe_to_pay"])
            nm = sum(1 for c in COLS[1:] if row[c] == r.expected[c])
            cells.append(f"{got-want:+13.2f}/{nm}")
        print(f"{r.request_id:11s} {want:14.2f} " + " ".join(f"{c:>16s}" for c in cells))


if __name__ == "__main__":
    main()
