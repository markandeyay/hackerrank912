"""Cross-sample check of candidate rules (post-hoc State mutations, engine untouched)."""
from __future__ import annotations
import sys, copy, statistics
from datetime import date, timedelta
from pathlib import Path
CODE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE))
from data import Dataset
from pipeline import load_adjustments, load_image_amounts
from planner import decide
from forecast import daily_balances, earliest_full_payment_date, amount_safe_to_pay
from state import StateBuilder, Flow, HORIZON_DAYS, add_months

ds = Dataset()
reqs = ds.load_requests("sample_requests.csv")
IM = load_image_amounts(ds, True); AD = load_adjustments(ds, True)
B = StateBuilder(ds, IM, AD, horizon_days=HORIZON_DAYS)

def hdays(st): return (st.horizon_end - st.request_date).days

# ---- rules -------------------------------------------------------------
def r_base(st): return st
def r_accrual(st, incl_rq=False):
    for s in st.series:
        if s.cadence == "periodic":
            s.amount = s.amount / s.step_days
            k0 = 0 if incl_rq else 1
            s.dates = [st.request_date + timedelta(days=k) for k in range(k0, hdays(st) + 1)]
    return st
def r_accrual_all(st):
    for s in st.series:
        step = s.step_days if s.cadence == "periodic" else 30
        s.amount = s.amount / step
        s.dates = [st.request_date + timedelta(days=k) for k in range(1, hdays(st) + 1)]
    return st
def r_lump(st):
    # periodic series -> monthly lump amount*30/step on the DOM of its next occurrence
    for s in st.series:
        if s.cadence == "periodic" and s.dates:
            s.amount = s.amount * 30 / s.step_days
            first = s.dates[0]; t = first; out = []
            while t <= st.horizon_end:
                out.append(t); t = add_months(first, len(out))
            s.dates = out
    return st
def r_monthly_gap(st):
    # monthly series at last + median gap (in days) instead of same DOM
    hist = {}
    for e in ds.events_by_user[st.request.user_id]:
        if e.status == "settled" and e.direction == "debit": hist.setdefault(e.category, []).append(e.settlement_date or e.event_date)
    for s in st.series:
        if s.cadence == "monthly":
            ds_ = sorted(hist[s.category]); gaps = [(ds_[i+1]-ds_[i]).days for i in range(len(ds_)-1)]
            step = int(round(statistics.median(gaps))); t = ds_[-1] + timedelta(days=step)
            while t < st.request_date: t += timedelta(days=step)
            out = []
            while t <= st.horizon_end: out.append(t); t += timedelta(days=step)
            s.dates = out
    return st
def r_median(st):
    hist = {}
    for e in ds.events_by_user[st.request.user_id]:
        if e.status == "settled" and e.direction == "debit" and e.amount is not None:
            hist.setdefault(e.category, []).append(ds.convert(e.amount, e.currency, st.home, e.settlement_date or e.event_date))
    for s in st.series: s.amount = statistics.median(hist[s.category])
    return st
def r_min_per_cycle(st):
    # every periodic series gets at least round(30/step) occurrences per salary cycle (adds one at cycle end if short)
    if not st.salary_dates: return st
    bounds = sorted(set(st.salary_dates)) + [st.horizon_end + timedelta(days=1)]
    for s in st.series:
        if s.cadence != "periodic": continue
        need = int(round(30 / s.step_days)); lo = st.request_date - timedelta(days=1); extra = []
        for hi in bounds:
            seg = [d for d in s.dates if lo < d <= hi]
            if len(seg) < need and hi - timedelta(days=1) > lo:
                extra.append(hi - timedelta(days=1))
            lo = hi
        s.dates = sorted(s.dates + extra)
    return st

RULES = {"base": r_base, "accrual": r_accrual, "accrual_inclrq": lambda st: r_accrual(st, True), "accrual_all": r_accrual_all,
         "lump30": r_lump, "monthly_gap": r_monthly_gap, "median": r_median, "min_per_cycle": r_min_per_cycle}

def run(rule):
    rows = []
    for req in reqs:
        st = rule(B.build(req))
        dec = decide(st, ds.options_by_request.get(req.request_id, []))
        exp = req.expected
        prof = st.profile
        want_res = prof.current_available_balance - prof.minimum_balance_to_keep - float(exp["amount_safe_to_pay"])
        got_res = prof.current_available_balance - prof.minimum_balance_to_keep - dec.safe_amount
        earl = dec.earliest.isoformat() if dec.earliest else ""
        if dec.plan.status == "affordable_now": earl = req.request_date.isoformat()
        capped = float(exp["amount_safe_to_pay"]) >= req.requested_amount - 1e-6
        rows.append(dict(id=req.request_id, earl_ok=earl == exp["earliest_date_for_full_payment"], earl=earl, want_earl=exp["earliest_date_for_full_payment"],
                         meth_ok=dec.plan.method == exp["recommended_payment_method"], chg_ok=dec.plan.changes_string() == exp["spending_changes_needed"],
                         res_err=(None if capped else (got_res - want_res) / want_res if want_res else 0.0), got_res=got_res, want_res=want_res))
    return rows

if __name__ == "__main__":
    names = sys.argv[1:] or list(RULES)
    for name in names:
        rows = run(RULES[name])
        e = sum(r["earl_ok"] for r in rows); m = sum(r["meth_ok"] for r in rows); c = sum(r["chg_ok"] for r in rows)
        errs = [abs(r["res_err"]) for r in rows if r["res_err"] is not None]
        print(f"== {name}: earliest {e}/25 method {m}/25 changes {c}/25 mean|res err| {100*sum(errs)/len(errs):.1f}% within2% {sum(x<=0.02 for x in errs)}/{len(errs)}")
        for r in rows:
            flag = "" if r["earl_ok"] and r["meth_ok"] and r["chg_ok"] else "  <-- " + ("" if r["earl_ok"] else f"earl {r['earl']}!={r['want_earl']} ") + ("" if r["meth_ok"] else "meth ") + ("" if r["chg_ok"] else "chg")
            re = "cap" if r["res_err"] is None else f"{100*r['res_err']:+.1f}%"
            print(f"   {r['id']:11s} res {re:>7s}{flag}")
