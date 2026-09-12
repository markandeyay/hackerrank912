"""Scratch experiments for request_11 (no engine changes)."""
from __future__ import annotations
import sys, copy, statistics
from datetime import date, timedelta
from pathlib import Path
CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE))
from data import Dataset
from pipeline import load_adjustments, load_image_amounts
from planner import decide, greedy_changes
from forecast import daily_balances, trough, earliest_full_payment_date, amount_safe_to_pay, is_safe
from state import StateBuilder, Flow, HORIZON_DAYS

ds = Dataset()
reqs = {r.request_id: r for r in ds.load_requests("sample_requests.csv")}
IM = load_image_amounts(ds, True); AD = load_adjustments(ds, True)

def build(rid, horizon=HORIZON_DAYS, options=None):
    b = StateBuilder(ds, IM, AD, horizon_days=horizon, options=options)
    return b.build(reqs[rid])

def report(st, tag, req_amt=None):
    req = st.request; ra = req_amt or req.requested_amount
    db = daily_balances(st); tmin = min(db, key=lambda x: x[1])
    safe = amount_safe_to_pay(st, ra); earl = earliest_full_payment_date(st, ra)
    reserve = st.balance - st.min_balance - safe
    bal = dict(db)
    j14 = bal.get(date(2025,7,14)); j14_margin = (j14 - ra - st.min_balance) if j14 else None
    ch = greedy_changes(st, [(req.request_date, ra)])
    print(f"[{tag}] trough {tmin[0]} {tmin[1]:,.2f} reserve {reserve:,.2f} safe {safe:,.2f} earliest {earl} Jul14 margin after Jun15 pay {j14_margin:,.2f}"
          f" changes {[c.as_string() for c in ch] if ch else ch}")
    return reserve, earl, ch

def main():
    st = build("request_11")
    report(st, "baseline 84d")
    st90 = build("request_11", horizon=90); report(st90, "horizon 90")
    bal = dict(daily_balances(st))
    for d in (date(2025,5,14), date(2025,5,15), date(2025,6,14), date(2025,6,15), date(2025,7,14), date(2025,7,15), date(2025,7,26)):
        print("   ", d, f"{bal[d]:,.2f}")
    # (a) salary threshold for June to fail: need bal(Jul14) - 13.11M < min
    need = bal[date(2025,7,14)] - 13110000 - st.min_balance
    print(f"June passes by {need:,.2f}; two salaries in window -> salary must be <= {23256000 - need/2:,.2f} for June to fail (May 15 stays safe? check)")
    for S in (23256000, 23000000, 22998000, 22900000, 22000000, 20000000):
        s2 = copy.deepcopy(st)
        for f in s2.flows:
            if f.kind == "salary": f.amount = S
        report(s2, f"salary={S:,}")
    # (b) extra expense per cycle (monthly, on the 20th) threshold
    for E in (300000, 353000, 360000, 500000, 653000, 660000, 1000000):
        s2 = copy.deepcopy(st)
        for m in (5,6,7):
            s2.flows.append(Flow(date(2025,m,20), -E, "extra", "known_debit"))
        report(s2, f"extra monthly {E:,} on 20th")
    # (c) estimators
    for est in ("median", "last"):
        report(build("request_11", options={"estimator": est}), f"estimator={est}")
    # max estimator by hand
    s2 = build("request_11")
    hist = {}
    for e in ds.events_by_user["user_11"]:
        if e.status == "settled" and e.direction == "debit": hist.setdefault(e.category, []).append(e.amount)
    for s in s2.series: s.amount = max(hist[s.category])
    report(s2, "estimator=max")
    # (e) cloud shifted to last+31 (May 15, Jun 15, Jul 16)
    s2 = build("request_11")
    for s in s2.series:
        if s.category == "cloud_storage": s.dates = [date(2025,5,15), date(2025,6,15), date(2025,7,16)]
    report(s2, "cloud at last+31")
    # all monthly at last+31
    s2 = build("request_11")
    for s in s2.series:
        if s.cadence == "monthly":
            last = date(2025,4,s.dates[0].day); s.dates = [last + timedelta(days=31*k) for k in (1,2,3) if last + timedelta(days=31*k) <= s2.horizon_end]
    report(s2, "all monthly at last+31")
    # (f) periodic accrual: daily rate instead of discrete
    s2 = build("request_11")
    for s in s2.series:
        if s.cadence == "periodic":
            rate = s.amount / s.step_days
            s.amount = rate; s.dates = [s2.request_date + timedelta(days=k) for k in range(1, s2.horizon_days+1)]
    report(s2, "periodic accrual daily")
    # (g) periodic items: occurrences per month = 30/step applied as one monthly lump on last DOM
    s2 = build("request_11")
    for s in s2.series:
        if s.cadence == "periodic":
            s.amount = s.amount * 30 / s.step_days; last = s.dates[0]
            s.dates = [d for d in [date(2025,5,last.day), date(2025,6,last.day), date(2025,7,last.day)] if d <= s2.horizon_end]
    report(s2, "periodic as monthly lump (amt*30/step)")
    # (h) periodic series continue from request_date rather than last date (request_date+step)
    s2 = build("request_11")
    for s in s2.series:
        if s.cadence == "periodic":
            t = s2.request_date; ds_ = []
            while t <= s2.horizon_end:
                ds_.append(t); t += timedelta(days=s.step_days)
            s.dates = ds_
    report(s2, "periodic from request_date inclusive")
    s2 = build("request_11")
    for s in s2.series:
        if s.cadence == "periodic":
            t = s2.request_date + timedelta(days=s.step_days); ds_ = []
            while t <= s2.horizon_end:
                ds_.append(t); t += timedelta(days=s.step_days)
            s.dates = ds_
    report(s2, "periodic from request_date+step")
    # (i) extra occurrence: dining every 21 -> what if dining were monthly on the 23rd
    s2 = build("request_11")
    for s in s2.series:
        if s.category == "dining": s.dates = [date(2025,5,23), date(2025,6,23), date(2025,7,23)]
    report(s2, "dining monthly on 23rd")
    # (j) message salary 38.76M
    s2 = copy.deepcopy(st)
    for f in s2.flows:
        if f.kind == "salary": f.amount = 38760000
    report(s2, "salary 38.76M")
    # (k) no May salary (skip next payroll), rest normal
    s2 = copy.deepcopy(st); s2.flows = [f for f in s2.flows if not (f.kind=="salary" and f.date==date(2025,5,15))]
    report(s2, "skip May 15 salary")
    # (l) 38.76M once on May 15 then nothing
    s2 = copy.deepcopy(st); s2.flows = [f for f in s2.flows if f.kind!="salary"] + [Flow(date(2025,5,15), 38760000, "salary", "salary")]
    report(s2, "38.76M once, no later salary"); 
    s2 = copy.deepcopy(s2); s2.horizon_end = s2.request_date + timedelta(days=90); s2.horizon_days=90
    report(s2, "38.76M once, no later salary, 90d")

main()
