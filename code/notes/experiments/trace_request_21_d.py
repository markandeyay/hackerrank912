"""Part D: which per-series occurrence counts reproduce each sample's reserve?
For each uncapped sample whose H0 trough is before the first payday: take monthly/known items strictly before payday as
fixed, then brute-force counts 0..4 for each periodic series (at the series mean) and list combos within +-1.5 % of the
reference reserve. Also report the implied 'days covered' if periodic spend were a daily rate.
Run: .venv/Scripts/python code/notes/experiments/trace_request_21_d.py"""
import itertools
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))
from data import Dataset  # noqa: E402
from forecast import daily_balances  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from state import StateBuilder  # noqa: E402

ds = Dataset()
reqs = {r.request_id: r for r in ds.load_requests("sample_requests.csv")}
builder = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True))

for rid, req in sorted(reqs.items()):
    st = builder.build(req)
    prof = st.profile
    actual_safe = float(req.expected["amount_safe_to_pay"])
    actual_res = prof.current_available_balance - prof.minimum_balance_to_keep - actual_safe
    capped = abs(actual_safe - req.requested_amount) < 1e-6
    pays = [d for d in st.salary_dates if d >= st.request_date]
    if capped or not pays:
        continue
    pay = pays[0]
    bal = dict(daily_balances(st))
    tdate = min(bal, key=lambda d: bal[d])
    if tdate >= pay:
        print(f"{rid}: trough {tdate} not before payday {pay}; skipped")
        continue
    rq = st.request_date
    fixed = sum(-f.amount for f in st.flows if f.amount < 0 and rq <= f.date < pay)
    monthly = [s for s in st.series if s.cadence == "monthly"]
    periodic = [s for s in st.series if s.cadence == "periodic"]
    fixed += sum(s.amount for s in monthly for d in s.dates if rq <= d < pay)
    need = actual_res - fixed
    h0_counts = [sum(1 for d in s.dates if rq <= d < pay) for s in periodic]
    days = (pay - rq).days
    print(f"\n{rid} rq={rq} pay={pay} days_to_pay={days} reserve={actual_res:.2f} fixed_pre_payday={fixed:.2f} periodic_needed={need:.2f}")
    for s, c in zip(periodic, h0_counts):
        last = s.dates[0] - timedelta(days=s.step_days)
        occ = [d.isoformat()[5:] for d in s.dates[:4]]
        print(f"   {s.category:10s} gap={s.step_days:2d} last={last} mean={s.amount:12.2f} H0count={c} occ={occ} flex={s.flexibility}")
    combos = []
    for counts in itertools.product(range(0, 5), repeat=len(periodic)):
        tot = fixed + sum(c * s.amount for c, s in zip(counts, periodic))
        err = (tot - actual_res) / actual_res * 100
        if abs(err) <= 1.5:
            combos.append((abs(err), counts, err))
    combos.sort()
    print(f"   H0 counts={tuple(h0_counts)} -> err {(fixed + sum(c*s.amount for c,s in zip(h0_counts,periodic)) - actual_res)/actual_res*100:+.1f}%")
    for _, counts, err in combos[:5]:
        print(f"   fits: counts={counts} err={err:+.1f}%")
    rate = sum(s.amount / s.step_days for s in periodic)
    if rate:
        print(f"   daily-rate model: periodic needed / daily rate = {need / rate:.1f} days (days_to_pay={days})")
