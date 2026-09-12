"""Probe 2: scan the binding day T; list certain items of the no-income samples; monthly-rate test.

Run: .venv/Scripts/python code/notes/improve3/1_probe2.py
"""
from __future__ import annotations

import importlib
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
bs = importlib.import_module("1_residual_backsolve")
from data import Dataset  # noqa: E402
from forecast import daily_balances  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402

BAND, GRID, fmt = bs.BAND, bs.GRID, bs.fmt


def t_scan(bench):
    """For every uncapped sample and every candidate binding day T in the window: is R(T) band-feasible with counts(T)?"""
    print("### binding-day scan: days T for which residual(T) lies inside the band-feasible interval of the unknown block")
    builder = bench["builder"]
    print("| req | engine T | payday | feasible T days (first..last, count) | exact-grid T days | residual at engine T inside? |")
    print("|---|---|---|---|---|---|")
    for req in bench["reqs"]:
        st = builder.build(req)
        prof = st.profile
        rq = st.request_date
        want = float(req.expected["amount_safe_to_pay"])
        if want >= req.requested_amount - 1e-6:
            continue
        head = prof.current_available_balance - prof.minimum_balance_to_keep
        bal = daily_balances(st)
        T0 = min(bal, key=lambda x: x[1])[0]
        paydays = sorted(d for d in st.salary_dates if d > rq)
        g = GRID[st.home]
        feas, exact = [], []
        T = rq
        while T <= st.horizon_end:
            known = sum(-f.amount for f in st.flows if f.amount < 0 and rq <= f.date <= T)
            credits = sum(f.amount for f in st.flows if f.amount > 0 and rq <= f.date <= T)
            certain = known
            unknown = []
            for s in st.series:
                occ = bs.occ_before(s, T, rq)
                if not occ:
                    continue
                kind = bs.series_kind(builder, st, s)
                if kind in ("constant", "leaked"):
                    certain += occ * s.amount
                else:
                    hist = st.hist_groups[s.category]
                    unknown.append(dict(cat=s.category, occ=occ, amount=s.amount, hist=[(str(r[0]), r[1]) for r in hist]))
            R = head - want + credits - certain
            L = U = 0.0
            for u in unknown:
                amts = [a for _, a in u["hist"]]
                a = BAND.get(u["cat"], 0.28)
                L += u["occ"] * max(amts) / (1 + a)
                U += u["occ"] * min(amts) / (1 - a)
            if unknown and L - 1e-6 <= R <= U + 1e-6:
                feas.append(T)
                n, _ = bs.exact_solutions(unknown, [u["occ"] for u in unknown], R, g)
                if n:
                    exact.append(T)
            T += timedelta(days=1)
        fe = f"{feas[0]}..{feas[-1]} ({len(feas)})" if feas else "none"
        ex = f"{exact[0]}..{exact[-1]} ({len(exact)})" if exact else "none"
        print(f"| {req.request_id[-2:]} | {T0} | {paydays[0] if paydays else '-'} | {fe} | {ex} | {'yes' if T0 in feas else 'NO'} |")


def certain_listing(bench, ids=("05", "10", "04", "15", "06")):
    print("\n### certain items and all flows up to horizon end for the structural samples")
    builder = bench["builder"]
    for req in bench["reqs"]:
        if req.request_id[-2:] not in ids:
            continue
        st = builder.build(req)
        bal = daily_balances(st)
        T0 = min(bal, key=lambda x: x[1])[0]
        print(f"\n{req.request_id} {st.home} rq={st.request_date} end={st.horizon_end} T={T0} paydays={st.salary_dates[:3]}")
        for f in sorted(st.flows, key=lambda f: f.date):
            print(f"  flow   {f.date} {f.amount:>15,.2f} {f.kind:12s} {f.label[:50]}")
        for s in st.series:
            kind = bs.series_kind(builder, st, s)
            print(f"  series {kind:8s} {s.category:13s} {s.cadence:8s} step={s.step_days:2d} amt={s.amount:>13,.2f} n={s.n_hist:2d} dates={[str(d) for d in s.dates]}")


def monthly_rate(bench, ids=("05", "10")):
    print("\n### no-income samples: residual vs k x monthly rate of the unknown block")
    builder = bench["builder"]
    for req in bench["reqs"]:
        if req.request_id[-2:] not in ids:
            continue
        st = builder.build(req)
        prof = st.profile
        bal = daily_balances(st)
        T0 = min(bal, key=lambda x: x[1])[0]
        head = prof.current_available_balance - prof.minimum_balance_to_keep
        want = float(req.expected["amount_safe_to_pay"])
        known = sum(-f.amount for f in st.flows if f.amount < 0 and st.request_date <= f.date <= T0)
        certain = known + sum(bs.occ_before(s, T0, st.request_date) * s.amount for s in st.series if bs.series_kind(builder, st, s) in ("constant", "leaked"))
        R = head - want - certain
        unknown = [s for s in st.series if bs.series_kind(builder, st, s) == "fixed"]
        for dpm in (30, 30.4375, 31):
            rate = sum(s.amount * (dpm / s.step_days if s.cadence == "periodic" else 1) for s in unknown)
            print(f"  {req.request_id} residual={fmt(R, st.home)} monthly rate ({dpm} d/m)={fmt(rate, st.home)} -> k={R/rate:.3f}; 3x={fmt(3*rate, st.home)} ({100*(3*rate-R)/R:+.1f}%)")
        for days in (84, 90, 91, 92):
            tot = sum(s.amount * (days / s.step_days if s.cadence == "periodic" else days / 30.4375) for s in unknown)
            print(f"  {req.request_id} continuous {days}-day rate: {fmt(tot, st.home)} ({100*(tot-R)/R:+.1f}%)")


if __name__ == "__main__":
    ds = Dataset()
    reqs = ds.load_requests("sample_requests.csv")
    images = load_image_amounts(ds, True)
    adjs = load_adjustments(ds, True)
    builder = bs.CaptureBuilder(ds, images, adjs)
    bench = dict(ds=ds, reqs=reqs, builder=builder)
    t_scan(bench)
    certain_listing(bench)
    monthly_rate(bench)
