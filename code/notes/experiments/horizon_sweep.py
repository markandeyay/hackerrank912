"""Scratch experiment: re-test the forecast window against all 25 samples.

Run: .venv/Scripts/python code/notes/experiments/horizon_sweep.py
Does not modify the engine; monkeypatches forecast.daily_balances only for the
'request_date excluded' variant (h90x).
"""
from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE))

import forecast  # noqa: E402
from data import Dataset  # noqa: E402
from pipeline import fmt_safe, load_adjustments, load_image_amounts  # noqa: E402
from planner import decide  # noqa: E402
from state import StateBuilder  # noqa: E402

COLS = ["amount_safe_to_pay", "affordability_status", "recommended_payment_method", "payment_plan",
        "earliest_date_for_full_payment", "spending_changes_needed"]
ORIG_DB = forecast.daily_balances


def db_excl_request_date(st, extra=None):
    out = ORIG_DB(st, extra)
    if out:
        out[0] = (out[0][0], float("inf"))
    return out


def run_variant(ds, reqs, horizon, excl=False):
    builder = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True), horizon_days=horizon)
    forecast.daily_balances = db_excl_request_date if excl else ORIG_DB
    try:
        res = {}
        for req in reqs:
            st = builder.build(req)
            dec = decide(st, ds.options_by_request.get(req.request_id, []))
            bal = ORIG_DB(st)
            row = {
                "amount_safe_to_pay": fmt_safe(dec.safe_amount),
                "affordability_status": dec.plan.status,
                "recommended_payment_method": dec.plan.method,
                "payment_plan": dec.plan.plan_string(),
                "earliest_date_for_full_payment": dec.earliest.isoformat() if dec.earliest else "",
                "spending_changes_needed": dec.plan.changes_string(),
            }
            tmin = min(b for _, b in bal)
            tdays = [d for d, b in bal if abs(b - tmin) < 1e-6]
            res[req.request_id] = dict(row=row, safe=dec.safe_amount, trough=tmin, trough_days=tdays,
                                       bal=bal, st=st, req=req)
        return res
    finally:
        forecast.daily_balances = ORIG_DB


def main():
    ds = Dataset()
    reqs = ds.load_requests("sample_requests.csv")
    variants = [(f"h{n}", n, False) for n in range(84, 91)] + [("h90x", 90, True)]
    R = {name: run_variant(ds, reqs, n, excl) for name, n, excl in variants}
    names = [v[0] for v in variants]

    print("## amount_safe_to_pay per horizon (got)")
    hdr = f"{'req':11s} {'want':>14s} " + " ".join(f"{n:>14s}" for n in names)
    print(hdr)
    for req in reqs:
        want = float(req.expected["amount_safe_to_pay"])
        cells = [f"{R[n][req.request_id]['safe']:14.2f}" for n in names]
        print(f"{req.request_id:11s} {want:14.2f} " + " ".join(cells))
    print()
    print("## gap (got - want) per horizon")
    print(hdr)
    for req in reqs:
        want = float(req.expected["amount_safe_to_pay"])
        cells = [f"{R[n][req.request_id]['safe'] - want:+14.2f}" for n in names]
        print(f"{req.request_id:11s} {want:14.2f} " + " ".join(cells))
    print()

    print("## earliest_date_for_full_payment per horizon (want | got per N, * = match)")
    print(f"{'req':11s} {'want':>11s} " + " ".join(f"{n:>12s}" for n in names))
    for req in reqs:
        want = req.expected["earliest_date_for_full_payment"]
        cells = []
        for n in names:
            got = R[n][req.request_id]["row"]["earliest_date_for_full_payment"]
            cells.append(f"{(got or '-'):>11s}{'*' if got == want else ' '}")
        print(f"{req.request_id:11s} {(want or '-'):>11s} " + " ".join(cells))
    print()

    print("## column matches per horizon (s=status m=method p=plan e=earliest c=changes; '.'=match, X=mismatch)")
    print(f"{'req':11s} " + " ".join(f"{n:>7s}" for n in names))
    for req in reqs:
        cells = []
        for n in names:
            row = R[n][req.request_id]["row"]
            marks = "".join("." if row[c] == req.expected[c] else "X" for c in COLS[1:])
            cells.append(f"{marks:>7s}")
        print(f"{req.request_id:11s} " + " ".join(cells))
    print()

    print("## summary per horizon")
    print(f"{'variant':8s} " + " ".join(f"{c[:10]:>10s}" for c in COLS[1:]) + f" {'safe<=2%':>9s} {'exact/125':>9s} {'sum|gap|':>16s} {'sum|gap|/req':>13s}")
    for n in names:
        ex = {c: 0 for c in COLS}
        close = 0
        tot = 0.0
        totrel = 0.0
        for req in reqs:
            row = R[n][req.request_id]["row"]
            for c in COLS:
                if row[c] == req.expected[c]:
                    ex[c] += 1
            got = R[n][req.request_id]["safe"]
            want = float(req.expected["amount_safe_to_pay"])
            if abs(got - want) <= 0.02 * max(1.0, abs(want)):
                close += 1
            tot += abs(got - want)
            totrel += abs(got - want) / req.requested_amount
        print(f"{n:8s} " + " ".join(f"{ex[c]:>10d}" for c in COLS[1:]) + f" {close:>9d} {sum(ex[c] for c in COLS[1:]):>9d} {tot:16.2f} {100*totrel:12.2f}%")
    print()

    print("## samples whose output differs between h84 and h90")
    for req in reqs:
        a, b = R["h84"][req.request_id], R["h90"][req.request_id]
        if a["row"] == b["row"]:
            continue
        rid = req.request_id
        print(f"### {rid} ({req.user_id}) request_date={req.request_date} requested={req.requested_amount} min={a['st'].min_balance}")
        for c in COLS:
            if a["row"][c] != b["row"][c]:
                print(f"    {c:32s} h84={a['row'][c]!s:32s} h90={b['row'][c]!s:32s} want={req.expected[c]}")
        print(f"    trough h84={a['trough']:.2f} on {[d.isoformat() for d in a['trough_days']]}   trough h90={b['trough']:.2f} on {[d.isoformat() for d in b['trough_days']]}")
        st = b["st"]
        flows = [f for f in st.all_flows() if req.request_date + timedelta(days=84) <= f.date <= req.request_date + timedelta(days=90)]
        bal = dict(b["bal"])
        for k in range(84, 91):
            d = req.request_date + timedelta(days=k)
            items = ", ".join(f"{f.label}:{f.amount:+.2f}" for f in flows if f.date == d)
            print(f"    day {k:2d} {d} balance={bal[d]:14.2f} headroom={bal[d]-st.min_balance:+14.2f} {items}")
    print()

    print("## is the request-date balance ever the trough? (h90)")
    for req in reqs:
        b = R["h90"][req.request_id]
        rq_bal = b["bal"][0][1]
        flag = "YES" if abs(rq_bal - b["trough"]) < 1e-6 else "no"
        print(f"{req.request_id:11s} rq_balance={rq_bal:14.2f} trough={b['trough']:14.2f} trough_on={[d.isoformat() for d in b['trough_days']]} request_date_is_trough={flag}")


if __name__ == "__main__":
    main()
