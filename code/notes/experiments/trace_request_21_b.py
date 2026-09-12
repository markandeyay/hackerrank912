"""Part B: what lands on payday / payday+1 in every sample, and does the reference reserve it?
Run: .venv/Scripts/python code/notes/experiments/trace_request_21_b.py"""
import copy
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))
from data import Dataset  # noqa: E402
from forecast import amount_safe_to_pay, daily_balances, earliest_full_payment_date, trough  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from planner import decide, greedy_changes, spending_change_candidates  # noqa: E402
from state import Flow, StateBuilder  # noqa: E402

ds = Dataset()
reqs = {r.request_id: r for r in ds.load_requests("sample_requests.csv")}
builder = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True))

print("=== per-sample: residual (actual - H0 reserve) vs debits on payday (P), payday+1 (P1), payday+2 (P2)")
for rid, req in sorted(reqs.items()):
    st = builder.build(req)
    prof = st.profile
    actual_safe = float(req.expected["amount_safe_to_pay"])
    actual_res = prof.current_available_balance - prof.minimum_balance_to_keep - actual_safe
    capped = abs(actual_safe - req.requested_amount) < 1e-6
    r0 = st.balance - trough(st)
    pay = min((d for d in st.salary_dates if d >= st.request_date), default=None)
    src = "scheduled" if any("anchored on scheduled" in n for n in st.notes) else ("message" if any("salary_amount_change" in n or "commission" in n for n in st.notes) else "history/other")
    bal = dict(daily_balances(st))
    tdate = min(bal, key=lambda d: bal[d])
    def items_on(d):
        return [f"{f.label.split(':')[0]}:{-f.amount:.0f}" for f in st.all_flows() if f.date == d and f.amount < 0]
    if pay is None:
        print(f"{rid} no payday; residual {actual_res - r0:+.2f} {'cap' if capped else ''}")
        continue
    p0, p1, p2 = items_on(pay), items_on(pay + timedelta(days=1)), items_on(pay + timedelta(days=2))
    print(f"{rid} pay={pay} ({src:13s}) trough={tdate} resid={actual_res - r0:+12.2f} ({(actual_res - r0)/actual_res*100:+5.1f}%){' cap' if capped else ''}\n      P={p0}\n      P1={p1}\n      P2={p2}")

print("\n=== request_21 change selection with the reference trough emulated (salary credited 2026-04-17, i.e. after the 04-16 debits)")
req = reqs["request_21"]
st = builder.build(req)
st3 = copy.copy(st)
st3.flows = [Flow(f.date + timedelta(days=2), f.amount, f.label, f.kind) if f.kind == "salary" else f for f in st.flows]
st3.salary_dates = [d + timedelta(days=2) for d in st.salary_dates]
safe3 = amount_safe_to_pay(st3, req.requested_amount)
print(f"  emulated safe = {safe3} (reference 1543.35; engine reserve now {st.balance - trough(st3):.2f} vs reference 568)")
print(f"  shortfall after paying 1574.40 today = {req.requested_amount - safe3:.2f}")
for c in spending_change_candidates(st3):
    print(f"    cand {c.as_string():30s} series_amt={c.series.amount:7.2f} saving/occ={c.saving_per_occurrence:6.2f} first={c.series.dates[0]}")
ch = greedy_changes(st3, [(st.request_date, req.requested_amount)])
print("  greedy result:", "|".join(c.as_string() for c in ch) if ch else ch)
dec = decide(st3, ds.options_by_request["request_21"])
print(f"  decision: safe={dec.safe_amount} earliest={earliest_full_payment_date(st3, req.requested_amount)} -> {dec.plan.method}/{dec.plan.status} plan={dec.plan.plan_string()} changes={dec.plan.changes_string()}")
for c in dec.candidates:
    print(f"    cand {c.method:14s} deadline={c.completes_by_deadline} changes={c.changes_string()} total={c.total_paid:.2f} start={c.start}")

# Same emulation but with the exact reference numbers: shortfall 31.05
print("\n  alternative orderings with need=31.05 (only candidates whose first occurrence precedes the trough day 2026-04-16 count):")
need = 31.05
cands = spending_change_candidates(st3)
def greedy(order, need=need, single_first=False):
    cs = sorted(cands, key=order)
    cs = [c for c in cs if c.series.dates[0] <= st.request_date + timedelta(days=13)]
    if single_first:
        for c in cs:
            if c.saving_per_occurrence >= need:
                return c.as_string()
    out, acc = [], 0.0
    for c in cs:
        out.append(c.as_string()); acc += c.saving_per_occurrence
        if acc >= need - 1e-9:
            return "|".join(out)
    return None
print("   amount asc      :", greedy(lambda c: c.series.amount))
print("   saving asc      :", greedy(lambda c: c.saving_per_occurrence))
print("   event_id asc    :", greedy(lambda c: c.series.latest_event_id))
print("   amount desc     :", greedy(lambda c: -c.series.amount))
print("   saving desc     :", greedy(lambda c: -c.saving_per_occurrence))
print("   single-sufficient-first (amount asc):", greedy(lambda c: c.series.amount, single_first=True))
print("   single-sufficient-first (saving asc):", greedy(lambda c: c.saving_per_occurrence, single_first=True))
