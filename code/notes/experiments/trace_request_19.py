"""Scratch: decompose the reference reserve of request_19 and test single-rule hypotheses
across all 25 samples.  Does not modify the engine.
Run: .venv/Scripts/python code/notes/experiments/trace_request_19.py
"""
import statistics, sys
from pathlib import Path
from datetime import timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import state as S
from data import Dataset
from pipeline import load_adjustments, load_image_amounts, run
from state import StateBuilder
from planner import decide

ds = Dataset()
imgs = load_image_amounts(ds, True); adjs = load_adjustments(ds, True)
samples = ds.load_requests("sample_requests.csv")
req19 = [r for r in samples if r.request_id == "request_19"][0]
prof = ds.profiles["user_19"]
REF_RES = prof.current_available_balance - prof.minimum_balance_to_keep - 28820  # 77925

# ---------- part A: per-category estimators for user_19 ----------
hist = {}
for e in ds.events_by_user["user_19"]:
    if e.status == "settled" and e.direction == "debit":
        hist.setdefault(e.category, []).append((e.settlement_date, e.amount if e.amount is not None else imgs.get(e.event_id), e.amount_source))
for c in hist: hist[c].sort()
VAR = ["utilities", "healthcare", "shopping", "groceries", "transport"]
FIXED = 36100 + 11850 + 395
def ests(a):
    m = statistics.mean(a); sd = statistics.pstdev(a); ssd = statistics.stdev(a)
    return {"mean": m, "median": statistics.median(a), "last": a[-1], "max": max(a), "last3": statistics.mean(a[-3:]),
            "midrange": (max(a)+min(a))/2, "mean+.5psd": m+.5*sd, "mean+psd": m+sd, "mean+.5ssd": m+.5*ssd,
            "p75": sorted(a)[min(len(a)-1, int(round(0.75*(len(a)-1))))], "max3": max(a[-3:]), "mean*1.04": m*1.04}
tab = {}
for c in VAR:
    a_csv = [x[1] for x in hist[c] if x[2] == "csv"]; a_all = [x[1] for x in hist[c]]
    tab[c] = ests(a_csv)
    if c == "groceries":
        tab["groceries_incl_image"] = ests(a_all)
        tab["groceries_last12"] = ests(a_csv[-12:]); tab["groceries_last8"] = ests(a_csv[-8:]); tab["groceries_last4"] = ests(a_csv[-4:])
    if c == "transport":
        tab["transport_last6"] = ests(a_csv[-6:])
keys = list(next(iter(tab.values())).keys())
print(f"target reserve {REF_RES:.2f}; fixed items (rent 36100 + debt 11850 + cloud 395) = {FIXED}; variable target = {REF_RES-FIXED:.2f}\n")
print(f"{'category':22s}" + "".join(f"{k:>11s}" for k in keys))
for c, row in tab.items():
    print(f"{c:22s}" + "".join(f"{row[k]:11.2f}" for k in keys))
print(f"{'SUM (5 base cats)':22s}" + "".join(f"{sum(tab[c][k] for c in VAR):11.2f}" for k in keys))
print(f"{'reserve = fixed+sum':22s}" + "".join(f"{FIXED+sum(tab[c][k] for c in VAR):11.2f}" for k in keys))
print(f"{'err % vs 77925':22s}" + "".join(f"{100*(FIXED+sum(tab[c][k] for c in VAR)-REF_RES)/REF_RES:11.2f}" for k in keys))

base = FIXED + sum(tab[c]["mean"] for c in VAR)
print(f"\nengine baseline (means) = {base:.2f}, gap = {REF_RES-base:.2f} ({100*(REF_RES-base)/REF_RES:.2f}%)")
print("single-item swaps from the mean baseline:")
hyp = {
  "+1 grocery occurrence (09-04 not skipped)": base + tab["groceries"]["mean"],
  "+ family_support 12650 on payday": base + 12650,
  "grocery mean incl. image row 2854": base - tab["groceries"]["mean"] + tab["groceries_incl_image"]["mean"],
  "grocery last12 mean": base - tab["groceries"]["mean"] + tab["groceries_last12"]["mean"],
  "grocery last8 mean": base - tab["groceries"]["mean"] + tab["groceries_last8"]["mean"],
  "grocery max": base - tab["groceries"]["mean"] + tab["groceries"]["max"],
  "healthcare max": base - tab["healthcare"]["mean"] + tab["healthcare"]["max"],
  "transport max": base - tab["transport"]["mean"] + tab["transport"]["max"],
  "utilities max": base - tab["utilities"]["mean"] + tab["utilities"]["max"],
  "shopping max": base - tab["shopping"]["mean"] + tab["shopping"]["max"],
  "+ image grocery 2854 as a known debit": base + 2854,
  "+ transport 2nd occurrence": base + tab["transport"]["mean"],
  "- rent (request-date rent not counted) + family": base - 36100 + 12650,
  "monthly vars = max, groc/transport = mean": FIXED + sum(tab[c]["max"] for c in ["utilities","healthcare","shopping"]) + tab["groceries"]["mean"] + tab["transport"]["mean"],
  "all vars mean+0.5 pstdev": FIXED + sum(tab[c]["mean+.5psd"] for c in VAR),
  "all vars mean+0.5 sample stdev": FIXED + sum(tab[c]["mean+.5ssd"] for c in VAR),
}
for k, v in hyp.items():
    print(f"  {k:48s} {v:12.2f}  err {100*(v-REF_RES)/REF_RES:+6.2f}%")

# ---------- part B: which rounded nominals could sum to 29580? ----------
print("\nround-hundred nominal search (each nominal within ±8% of its mean, sum == 29580):")
import itertools
cands = {c: [n for n in range(int(tab[c]["mean"]*0.92)//100*100, int(tab[c]["mean"]*1.08)//100*100+100, 100)] for c in VAR}
sols = [combo for combo in itertools.product(*[cands[c] for c in VAR]) if sum(combo) == 29580]
print(f"  {len(sols)} combos of round hundreds sum to 29580 (means: {[round(tab[c]['mean']) for c in VAR]}); e.g. {sols[:5]}")
cands50 = {c: [n for n in range(int(tab[c]["mean"]*0.95)//50*50, int(tab[c]["mean"]*1.05)//50*50+50, 50)] for c in VAR}
sols50 = [combo for combo in itertools.product(*[cands50[c] for c in VAR]) if sum(combo) == 29580]
print(f"  {len(sols50)} combos of multiples of 50 within ±5% sum to 29580")

# ---------- part C: cross-sample consistency of candidate rules ----------
def reserve_table(label, options=None, est_fn=None):
    real_mean = statistics.mean
    if est_fn is not None:
        S.statistics = type("Shim", (), {"mean": staticmethod(lambda a: est_fn(a) if isinstance(a, list) else statistics.mean(a)), "median": staticmethod(statistics.median), "pstdev": staticmethod(statistics.pstdev)})
    try:
        res = run(samples, ds, True, options=options)
    finally:
        S.statistics = statistics
    errs = []
    line = []
    for dec, row in res:
        exp = dec.request.expected; p = ds.profiles[dec.request.user_id]
        head = p.current_available_balance - p.minimum_balance_to_keep
        want = float(exp["amount_safe_to_pay"]); got = float(row["amount_safe_to_pay"])
        if want >= dec.request.requested_amount - 1e-9:
            continue  # capped, uninformative
        wr, gr = head - want, head - got
        e = 100 * (gr - wr) / wr
        errs.append(abs(e)); line.append(f"{dec.request.request_id[-2:]}:{e:+.1f}")
    print(f"{label:34s} mean|err| {statistics.mean(errs):5.2f}%  within2% {sum(1 for e in errs if e <= 2)}/{len(errs)}  within1% {sum(1 for e in errs if e <= 1)}/{len(errs)}")
    print("   " + " ".join(line))

print("\n=== cross-sample reserve error (got-want)/want, uncapped samples ===")
if "--skip" not in sys.argv: reserve_table("mean (engine)")
if "--skip" not in sys.argv: reserve_table("median", {"estimator": "median"})
if "--skip" not in sys.argv: reserve_table("last", {"estimator": "last"})
if "--skip" not in sys.argv: reserve_table("max", est_fn=lambda a: max(a))
reserve_table("mean+0.5*pstdev", est_fn=lambda a: statistics.mean(a) + 0.5*statistics.pstdev(a))
reserve_table("mean+0.5*stdev", est_fn=lambda a: statistics.mean(a) + 0.5*statistics.stdev(a) if len(a) > 1 else statistics.mean(a))
reserve_table("mean*1.04", est_fn=lambda a: statistics.mean(a) * 1.04)
reserve_table("mean of last 3", est_fn=lambda a: statistics.mean(a[-3:]))
reserve_table("midrange", est_fn=lambda a: (max(a)+min(a))/2)
reserve_table("periodic: request-date not skipped", {"periodic_skip_request_date": False})
reserve_table("image rows in mean", {"exclude_image_rows_from_mean": False})
reserve_table("debit_first on payday", {"debit_first": True})
