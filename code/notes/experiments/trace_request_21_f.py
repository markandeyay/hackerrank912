"""Part F: rule A variants - 'add' one occurrence at payday-1 vs 'move' the next occurrence to payday-1.
Run: .venv/Scripts/python code/notes/experiments/trace_request_21_f.py"""
import copy
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))
from data import Dataset  # noqa: E402
from forecast import trough  # noqa: E402
from pipeline import decision_row, load_adjustments, load_image_amounts  # noqa: E402
from planner import decide  # noqa: E402
from state import StateBuilder  # noqa: E402

ds = Dataset()
reqs = {r.request_id: r for r in ds.load_requests("sample_requests.csv")}
builder = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True), options={"periodic_before_payday_days": 0})
COLS = ["amount_safe_to_pay", "affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed"]


def rule_a(st, mode):
    pays = [d for d in st.salary_dates if d >= st.request_date]
    if not pays:
        return st
    pay = pays[0]
    s2 = copy.copy(st)
    s2.series = []
    for s in st.series:
        s3 = copy.copy(s)
        if s.cadence == "periodic" and s.dates and not any(st.request_date <= d < pay for d in s.dates):
            s3.dates = sorted([pay - timedelta(days=1)] + (list(s.dates) if mode == "add" else list(s.dates[1:])))
        s2.series.append(s3)
    return s2


for mode in ("add", "move"):
    hits = {c: 0 for c in COLS}
    bad_rows = []
    for rid, req in sorted(reqs.items()):
        st = rule_a(builder.build(req), mode)
        dec = decide(st, ds.options_by_request.get(rid, []))
        row = decision_row(dec, "")
        ok = {c: str(row[c]) == str(req.expected[c]) for c in COLS}
        for c in COLS:
            hits[c] += ok[c]
        bad = [c for c in COLS[1:] if not ok[c]]
        if bad:
            bad_rows.append((rid, row["amount_safe_to_pay"], req.expected["amount_safe_to_pay"], dec.earliest, bad))
    print(f"rule A '{mode}': exact {sum(hits.values())}/150 {hits}")
    for b in bad_rows:
        print("   ", b)
# request_16 detail
req = reqs["request_16"]
for mode in ("add", "move"):
    st = rule_a(builder.build(req), mode)
    print(f"request_16 {mode}: reserve={st.balance - trough(st):.2f} (reference bound <= {st.balance - st.min_balance - req.requested_amount:.2f}); periodic next dates:",
          {s.category: [d.isoformat() for d in s.dates[:2]] for s in st.series if s.cadence == "periodic"}, "payday", st.salary_dates[:1])
