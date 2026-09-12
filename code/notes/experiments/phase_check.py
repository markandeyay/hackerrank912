"""Scratch: for each sample, print periodic series phase: last history date, request date, first projected date,
and the count of occurrences before the first payday. Read-only."""
import sys
from pathlib import Path
CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE))
from data import Dataset
from pipeline import load_adjustments, load_image_amounts
from state import StateBuilder
ds = Dataset()
b = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True))
for r in ds.load_requests("sample_requests.csv"):
    st = b.build(r)
    pay = min([d for d in st.salary_dates if d > st.request_date], default=None)
    prof = ds.profiles[r.user_id]
    want_res = prof.current_available_balance - prof.minimum_balance_to_keep - float(r.expected["amount_safe_to_pay"])
    print(f"{r.request_id} rq={st.request_date} payday={pay} want_reserve={want_res:.2f}")
    hist = {}
    for e in ds.events_by_user[r.user_id]:
        if e.status == "settled" and e.direction == "debit":
            hist.setdefault(e.category, []).append(e.settlement_date)
    for s in st.series:
        if s.cadence != "periodic":
            continue
        last = max(hist[s.category])
        n_before = len([d for d in s.dates if pay is None or d < pay])
        print(f"   {s.category:12s} step={s.step_days:2d} amt={s.amount:10.2f} last={last} last+step={last.toordinal()-st.request_date.toordinal()+s.step_days:+3d}d first_proj={s.dates[0] if s.dates else None} n_before_payday={n_before} n_hist={s.n_hist}")
