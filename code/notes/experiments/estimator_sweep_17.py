"""Cross-sample check for the request_17 finding: does a lower per-occurrence
estimator (median / midrange) help or hurt the other samples? Engine untouched;
midrange is injected by shimming state.statistics.mean."""
import sys, statistics, types
from pathlib import Path
sys.path.insert(0, str(Path("code").resolve()))
import state
from data import Dataset
from pipeline import run
import importlib.util as _iu; _sp=_iu.spec_from_file_location("evalmain", Path("code/evaluation/main.py").resolve()); evalmain=_iu.module_from_spec(_sp); _sp.loader.exec_module(evalmain); score=evalmain.score
ds = Dataset(); reqs = ds.load_requests("sample_requests.csv")
real_stats = state.statistics
def midrange(xs): xs=list(xs); return (min(xs)+max(xs))/2
def trimmed(xs): xs=sorted(xs); k=max(1,len(xs)//5); return statistics.mean(xs[k:-k]) if len(xs)>2*k+1 else statistics.mean(xs)
shims = {"mean": real_stats, "midrange": types.SimpleNamespace(mean=midrange, median=real_stats.median),
         "trimmed20": types.SimpleNamespace(mean=trimmed, median=real_stats.median)}
rows = {}
for name in ("mean","median","midrange","trimmed20"):
    state.statistics = shims.get(name, real_stats)
    opts = {"estimator": "median"} if name=="median" else {"estimator":"mean"}
    res = run(reqs, ds, use_llm=True, options=opts)
    state.statistics = real_stats
    summ = score(res)
    print(f"== {name}: " + ", ".join(f"{k}={v}" for k,v in summ.items()))
    for dec,row in res:
        exp=dec.request.expected
        if not exp: continue
        prof=ds.profiles[dec.request.user_id]; head=prof.current_available_balance-prof.minimum_balance_to_keep
        want=float(exp["amount_safe_to_pay"]); got=float(row["amount_safe_to_pay"]); want_res=head-want
        capped = want >= dec.request.requested_amount-1e-6
        rows.setdefault(dec.request.request_id, {})[name] = (got-want, want_res, capped, row["earliest_date_for_full_payment"]==exp["earliest_date_for_full_payment"], exp["earliest_date_for_full_payment"], row["earliest_date_for_full_payment"])
print(f"\n{'req':11s} " + " ".join(f"{n:>22s}" for n in ("mean","median","midrange","trimmed20")) + "   (gap%res of reserve, earliest ok?)")
for rid, d in rows.items():
    cells=[]
    for n in ("mean","median","midrange","trimmed20"):
        gap,res,capped,eok,ew,eg = d[n]
        cells.append(f"{'cap' if capped else f'{100*gap/res:+6.1f}%':>10s} {'E-ok' if eok else 'E-'+eg:>11s}")
    print(f"{rid:11s} " + " ".join(cells))
