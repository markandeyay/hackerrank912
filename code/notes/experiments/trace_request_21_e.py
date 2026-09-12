"""Part E: score the 25 samples under four configurations (engine untouched; rule A applied as a post-build patch).
Rule A: every recurring short-cycle (periodic) debit series contributes at least one occurrence before the first
projected payday; when its next occurrence falls on/after that payday, one occurrence is pulled to payday-1.
Run: .venv/Scripts/python code/notes/experiments/trace_request_21_e.py"""
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
IMG, ADJ = load_image_amounts(ds, True), load_adjustments(ds, True)
COLS = ["amount_safe_to_pay", "affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed"]


def rule_a(st):
    pays = [d for d in st.salary_dates if d >= st.request_date]
    if not pays:
        return st
    pay = pays[0]
    s2 = copy.copy(st)
    s2.series = []
    for s in st.series:
        s3 = copy.copy(s)
        if s.cadence == "periodic" and s.dates and not any(st.request_date <= d < pay for d in s.dates):
            s3.dates = sorted([pay - timedelta(days=1)] + list(s.dates))
        s2.series.append(s3)
    return s2


def score(label, win, patch, verbose=True):
    builder = StateBuilder(ds, IMG, ADJ, options={"periodic_before_payday_days": win})
    hits = {c: 0 for c in COLS}
    within2 = 0
    rows = []
    for rid, req in sorted(reqs.items()):
        st = patch(builder.build(req))
        dec = decide(st, ds.options_by_request.get(rid, []))
        row = decision_row(dec, "")
        exp = req.expected
        ok = {c: str(row[c]) == str(exp[c]) for c in COLS}
        for c in COLS:
            hits[c] += ok[c]
        prof = st.profile
        head = prof.current_available_balance - prof.minimum_balance_to_keep
        a_res = head - float(exp["amount_safe_to_pay"])
        m_res = head - float(row["amount_safe_to_pay"])
        capped = abs(float(exp["amount_safe_to_pay"]) - req.requested_amount) < 1e-6
        if not capped and abs(m_res - a_res) / a_res <= 0.02:
            within2 += 1
        bad = [c for c in COLS[1:] if not ok[c]]
        rows.append((rid, row["amount_safe_to_pay"], exp["amount_safe_to_pay"], "cap" if capped else f"{(m_res - a_res) / a_res * 100:+.1f}%", bad))
    print(f"\n=== {label}: exact {sum(hits.values())}/150 {hits}  uncapped reserve within 2%: {within2}/21")
    if verbose:
        for r in rows:
            print(f"   {r[0]} safe={r[1]} exp={r[2]} reserve_err={r[3]} mismatches={r[4]}")


score("old baseline (win=0)", 0, lambda st: st)
score("new default (win=1: periodic on payday -> payday-1)", 1, lambda st: st)
score("rule A on win=0", 0, rule_a)
score("rule A on win=1", 1, rule_a)

print("\n=== request_21 under rule A (win=0)")
builder0 = StateBuilder(ds, IMG, ADJ, options={"periodic_before_payday_days": 0})
st = rule_a(builder0.build(reqs["request_21"]))
dec = decide(st, ds.options_by_request["request_21"])
print(f"   reserve={st.balance - trough(st):.2f} safe={dec.safe_amount} earliest={dec.earliest} -> {dec.plan.method}/{dec.plan.status} plan={dec.plan.plan_string()} changes={dec.plan.changes_string()}")
for s in st.series:
    if s.cadence == "periodic":
        print(f"   {s.category:10s} dates={[d.isoformat() for d in s.dates[:3]]}")
