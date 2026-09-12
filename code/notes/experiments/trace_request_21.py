"""Scratch experiment: why is the reference reserve for request_21 568 while the engine reserves 438.22?
Run: .venv/Scripts/python code/notes/experiments/trace_request_21.py
Does not modify the engine; only reads state/forecast/planner."""
import copy
import itertools
import statistics
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))
from data import Dataset  # noqa: E402
from forecast import amount_safe_to_pay, trough  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from planner import REDUCIBLE, STOPPABLE, decide, greedy_changes, spending_change_candidates  # noqa: E402
from state import Flow, StateBuilder  # noqa: E402

ds = Dataset()
reqs = {r.request_id: r for r in ds.load_requests("sample_requests.csv")}
builder = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True))


def reserve_of(st, extra=None):
    return st.balance - trough(st, extra)


def shifted(st, days, kinds=("salary", "income", "known_credit")):
    s2 = copy.copy(st)
    s2.flows = [Flow(f.date + timedelta(days=days), f.amount, f.label, f.kind) if f.kind in kinds else f for f in st.flows]
    return s2


print("=== Hypothesis sweep over all samples (reserve = balance - trough). actual = balance - min - actual_safe (upper bound when capped)")
print(f"{'req':10s} {'actual':>14s} {'H0 base':>14s} {'H1 credit+1d':>14s} {'H2 debit1st':>14s} {'H0 err%':>8s} {'H1 err%':>8s} cap")
tot0 = tot1 = n = 0
for rid, req in sorted(reqs.items()):
    st = builder.build(req)
    prof = st.profile
    actual_safe = float(req.expected["amount_safe_to_pay"])
    actual_res = prof.current_available_balance - prof.minimum_balance_to_keep - actual_safe
    capped = abs(actual_safe - req.requested_amount) < 1e-6
    r0 = reserve_of(st)
    r1 = reserve_of(shifted(st, 1))
    st2 = copy.copy(st)
    st2.debit_first = True
    r2 = reserve_of(st2)
    e0 = (r0 - actual_res) / actual_res * 100 if actual_res else 0
    e1 = (r1 - actual_res) / actual_res * 100 if actual_res else 0
    if not capped:
        tot0 += abs(e0)
        tot1 += abs(e1)
        n += 1
    print(f"{rid:10s} {actual_res:14.2f} {r0:14.2f} {r1:14.2f} {r2:14.2f} {e0:8.1f} {e1:8.1f} {'cap' if capped else ''}")
print(f"mean |err| over uncapped: H0 {tot0/n:.2f}%  H1 {tot1/n:.2f}%")

print("\n=== request_21 decomposition search")
req = reqs["request_21"]
st = builder.build(req)
items = []  # (date, amount, label) debits in the first 20 days
for f in st.all_flows():
    if st.request_date <= f.date <= st.request_date + timedelta(days=20) and f.amount < 0:
        items.append((f.date, -f.amount, f.label))
items.sort()
for d, a, lab in items:
    print(f"  {d} {a:8.2f} {lab}")
target = st.profile.current_available_balance - st.profile.minimum_balance_to_keep - float(req.expected["amount_safe_to_pay"])
print(f"  target reserve = {target:.2f}")
pre = [x for x in items if x[0] < st.salary_dates[0]]
post = [x for x in items if x[0] >= st.salary_dates[0]]
base = sum(a for _, a, _ in pre)
print(f"  pre-payday sum (engine trough) = {base:.2f}; gap = {target-base:.2f}")
print("  subsets of post-payday items closest to the gap:")
res = []
for k in range(0, len(post) + 1):
    for combo in itertools.combinations(post, k):
        s = sum(a for _, a, _ in combo)
        res.append((abs(base + s - target), base + s, [f"{d}:{lab.split(':')[0]}:{a:.2f}" for d, a, lab in combo]))
res.sort()
for dlt, tot, combo in res[:6]:
    print(f"    total {tot:8.2f}  delta {tot-target:+7.2f}  {combo}")

print("\n=== nominal-rounding analysis (fixed exact: fuel 53, streaming 47, cloud 11)")
hist = {}
for e in ds.events_by_user["user_21"]:
    if e.status == "settled" and e.direction == "debit" and e.category in ("utilities", "shopping", "groceries", "transport", "dining"):
        hist.setdefault(e.category, []).append(e.amount)
for cat, v in hist.items():
    m = statistics.mean(v)
    print(f"  {cat:10s} n={len(v):2d} mean={m:7.2f} median={statistics.median(v):7.2f} min={min(v):7.2f} max={max(v):7.2f} std={statistics.pstdev(v):5.2f} round5={5*round(m/5)} ceil5={5*-(-m//5):.0f} round={round(m)}")
need = target - (53 + 47 + 11)
print(f"  variable total needed = {need:.2f}")
print("  integer nominal sets U + S + 2G + T = need (04-16 set), with each nominal within [min,max] of its history and |nominal-mean| <= 5:")
sols = []
for U in range(116, 127):
    for S in range(117, 128):
        for G in range(79, 89):
            for T in range(37, 47):
                if U + S + 2 * G + T == round(need):
                    sols.append((U, S, G, T))
print(f"    {len(sols)} integer solutions; those with all four multiples of 5: {[s for s in sols if all(x % 5 == 0 for x in s)]}")
print(f"    those with U,S multiples of 5: {[s for s in sols if U % 5 == 0 and s[1] % 5 == 0][:12]}")
print("  04-17 alternative U + S + G + T + D = need, multiples of 5:")
print("   ", [(U, S, G, T, D) for U in range(115, 130, 5) for S in range(115, 135, 5) for G in range(75, 95, 5) for T in range(35, 50, 5) for D in range(75, 95, 5) if U + S + G + T + D == round(need)])

print("\n=== spending-change selection under the reference's numbers")
# Force the trough to the reference's value by adding a synthetic debit of the gap on 2026-04-16 (the day the extra items land)
gap_flow = [Flow(st.request_date + timedelta(days=13), -(target - base), "synthetic gap", "known_debit")]
st3 = copy.copy(st)
st3.flows = st.flows + gap_flow
safe3 = amount_safe_to_pay(st3, req.requested_amount)
print(f"  synthetic safe = {safe3} (expected 1543.35); shortfall after full payment = {req.requested_amount - safe3:.2f}")
cands = spending_change_candidates(st3)
print("  engine candidate order (series amount asc, reduce preferred):")
for c in cands:
    nxt = c.series.dates[0] if c.series.dates else None
    print(f"    {c.as_string():32s} series_amt={c.series.amount:7.2f} saving={c.saving_per_occurrence:6.2f} next={nxt}")
ch = greedy_changes(st3, [(st.request_date, req.requested_amount)])
print("  greedy result:", "|".join(c.as_string() for c in ch) if ch else ch)
dec = decide(st3, ds.options_by_request["request_21"])
print(f"  decision: safe={dec.safe_amount} earliest={dec.earliest} {dec.plan.method}/{dec.plan.status} plan={dec.plan.plan_string()} changes={dec.plan.changes_string()}")


def run_order(order_key, prefer_stop=False, single_first=False):
    prof = st3.profile
    cs = []
    for s in st3.series:
        if not s.dates or s.category in prof.protect:
            continue
        can_reduce = s.flexibility in REDUCIBLE and s.category in prof.reduce and s.minimum_allowed_amount is not None
        can_stop = s.flexibility in STOPPABLE and s.category in prof.stop
        if prefer_stop and can_stop:
            cs.append(("stop", s, s.amount))
        elif can_reduce:
            cs.append(("reduce_to", s, s.amount - s.minimum_allowed_amount))
        elif can_stop:
            cs.append(("stop", s, s.amount))
    cs.sort(key=order_key)
    need = req.requested_amount - safe3
    trough_day = st.request_date + timedelta(days=13)
    if single_first:
        for a, s, sv in cs:
            if sv >= need and s.dates[0] <= trough_day:
                return [(a, s.latest_event_id, round(sv, 2))]
    out, acc = [], 0.0
    for a, s, sv in cs:
        if s.dates[0] > trough_day:
            continue  # after trough: no help
        out.append((a, s.latest_event_id, round(sv, 2)))
        acc += sv
        if acc >= need - 1e-9:
            return out
    return None


for name, key, ps, sf in [
    ("amount asc, reduce pref", lambda c: c[1].amount, False, False),
    ("saving asc, reduce pref", lambda c: c[2], False, False),
    ("event_id asc, reduce pref", lambda c: c[1].latest_event_id, False, False),
    ("amount asc, STOP pref", lambda c: c[1].amount, True, False),
    ("amount desc, reduce pref", lambda c: -c[1].amount, False, False),
    ("saving desc, reduce pref", lambda c: -c[2], False, False),
    ("single sufficient change first (amount asc)", lambda c: c[1].amount, False, True),
]:
    r = run_order(key, ps, sf)
    print(f"  {name:45s} -> {r}")
