"""List, for all 25 samples, every short-cycle occurrence that falls on a payday or the day after
(within the window), with its gap and whether it is the bring-forward occurrence; plus the sample's
current reserve error. Read-only against the engine."""
import sys
from datetime import timedelta
from pathlib import Path
CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR))
from data import Dataset
from forecast import daily_balances
from pipeline import load_adjustments, load_image_amounts
from state import StateBuilder

ds = Dataset()
reqs = ds.load_requests("sample_requests.csv")
b = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True))
b2 = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True), options={"periodic_at_least_once_before_payday": False})
for req in reqs:
    st = b.build(req)
    st0 = b2.build(req)
    prof = st.profile
    head = prof.current_available_balance - prof.minimum_balance_to_keep
    want = float(req.expected["amount_safe_to_pay"])
    bal = daily_balances(st)
    ours = max(0.0, min(req.requested_amount, min(x for _, x in bal) - st.min_balance))
    err = (head - ours) - (head - want)
    pays = sorted(set(d for d in st.salary_dates if d > st.request_date))
    hits = []
    for s, s0 in zip(st.series, st0.series):
        if s.cadence != "periodic":
            continue
        for d in s0.dates:  # raw last+gap dates (before bring-forward)
            for i, p in enumerate(pays):
                off = (d - p).days
                if 0 <= off <= 2:
                    bf = "BF" if (s.dates and s.dates[0] == p - timedelta(days=1) and s0.dates[0] == d) else "  "
                    hits.append(f"{s.category[:5]}/{s.step_days}d {d.isoformat()[5:]}=pay{i+1}+{off} {bf}")
    capped = "capped" if want >= req.requested_amount - 1e-6 else f"res_err {100*err/(head-want):+.2f}%"
    print(f"{req.request_id} rq={st.request_date} pays={[p.isoformat()[5:] for p in pays[:3]]} {capped:18s} | " + "; ".join(hits))
