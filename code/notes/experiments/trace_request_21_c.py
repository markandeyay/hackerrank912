"""Part C: sweep two mechanisms that reserve short-cycle (periodic) items on payday / payday+1
V1: periodic occurrences shifted one day earlier (drop those <= request_date, i.e. the skip rule kept)
V2: periodic occurrences dated payday or payday+1 count before the salary (salary applied after them)
V3: V1 without the request-date skip (occurrence == request_date kept)
Run: .venv/Scripts/python code/notes/experiments/trace_request_21_c.py"""
import copy
import sys
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))
from data import Dataset  # noqa: E402
from forecast import earliest_full_payment_date, trough  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from state import Flow, StateBuilder  # noqa: E402

ds = Dataset()
reqs = {r.request_id: r for r in ds.load_requests("sample_requests.csv")}
builder = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True))
builder_noskip = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True), options={"periodic_skip_request_date": False})


def variant(st, mode):
    s2 = copy.copy(st)
    s2.series = []
    s2.flows = list(st.flows)
    for s in st.series:
        s3 = copy.copy(s)
        if s.cadence == "periodic":
            if mode in ("V1", "V3"):
                s3.dates = [d - timedelta(days=1) for d in s.dates if d - timedelta(days=1) > st.request_date or (mode == "V3" and d - timedelta(days=1) >= st.request_date)]
            elif mode == "V2":
                pays = set(st.salary_dates)
                # move an occurrence on payday / payday+1 to payday-1 so it precedes the salary credit
                s3.dates = [min(p for p in pays if p <= d) - timedelta(days=1) if any(d - timedelta(days=k) in pays for k in (0, 1)) else d for d in s.dates]
        s2.series.append(s3)
    return s2


rows = []
print(f"{'req':10s} {'actual':>13s} {'H0':>13s} {'V1 -1d':>13s} {'V2 pay+1':>13s} {'V3 -1d noskip':>13s} | err% H0 V1 V2 V3 | earliest act/H0/V1/V2/V3")
acc = {"H0": [], "V1": [], "V2": [], "V3": []}
for rid, req in sorted(reqs.items()):
    st = builder.build(req)
    st_ns = builder_noskip.build(req)
    prof = st.profile
    actual_safe = float(req.expected["amount_safe_to_pay"])
    actual_res = prof.current_available_balance - prof.minimum_balance_to_keep - actual_safe
    capped = abs(actual_safe - req.requested_amount) < 1e-6
    variants = {"H0": st, "V1": variant(st, "V1"), "V2": variant(st, "V2"), "V3": variant(st_ns, "V3")}
    res = {k: v.balance - trough(v) for k, v in variants.items()}
    errs = {k: (res[k] - actual_res) / actual_res * 100 for k in res}
    ear = {k: (earliest_full_payment_date(v, req.requested_amount) or "") for k, v in variants.items()}
    act_e = req.expected["earliest_date_for_full_payment"]
    if not capped:
        for k in acc:
            acc[k].append(abs(errs[k]))
    flag = " cap" if capped else ""
    print(f"{rid:10s} {actual_res:13.2f} {res['H0']:13.2f} {res['V1']:13.2f} {res['V2']:13.2f} {res['V3']:13.2f} | {errs['H0']:+6.1f} {errs['V1']:+6.1f} {errs['V2']:+6.1f} {errs['V3']:+6.1f} | {act_e} {'ok' if str(ear['H0'])==act_e else str(ear['H0'])} {'ok' if str(ear['V1'])==act_e else str(ear['V1'])} {'ok' if str(ear['V2'])==act_e else str(ear['V2'])} {'ok' if str(ear['V3'])==act_e else str(ear['V3'])}{flag}")
for k, v in acc.items():
    print(f"{k}: mean |err| {sum(v)/len(v):.2f}%  within 2%: {sum(1 for x in v if x <= 2)}  within 5%: {sum(1 for x in v if x <= 5)}")
