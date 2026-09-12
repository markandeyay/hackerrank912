"""Task 1: ratio = amount / minimum_allowed_amount over all flexible events."""
import csv, statistics
from collections import defaultdict
rows = list(csv.DictReader(open("dataset/financial_events.csv", encoding="utf-8")))
flex = [r for r in rows if r["minimum_allowed_amount"] not in ("", None) and r["amount"] not in ("",) and r["status"]=="settled" and r["direction"]=="debit"]
print("rows with min_allowed:", sum(1 for r in rows if r["minimum_allowed_amount"]), "settled debit with amount:", len(flex))
print("flexibility values among them:", set(r["flexibility"] for r in flex))
by_cat = defaultdict(list); by_series = defaultdict(list)
for r in flex:
    a = float(r["amount"]); m = float(r["minimum_allowed_amount"])
    by_cat[r["category"]].append(a/m)
    by_series[(r["user_id"], r["category"])].append((r["settlement_date"], a, m, r["flexibility"], r["event_id"]))
print("\n# ratio amount/min by category")
print(f"{'category':18s} n   min    p10   median  mean   p90   max")
for c, xs in sorted(by_cat.items()):
    s = sorted(xs); n = len(s)
    print(f"{c:18s} {n:3d} {s[0]:.3f} {s[int(0.1*(n-1))]:.3f} {statistics.median(s):.3f} {statistics.mean(s):.3f} {s[int(0.9*(n-1))]:.3f} {s[-1]:.3f}")
print("\n# per (user, category) series: is min constant? mean/(2*min)? midrange/(2*min)?")
print(f"{'user':8s}{'category':18s} n  nmin  min_allowed   mean      mean/2min  mid/2min  min_ratio max_ratio flex")
agg = defaultdict(list)
for (u, c), lst in sorted(by_series.items()):
    lst.sort()
    mins = sorted(set(x[2] for x in lst)); amts = [x[1] for x in lst]
    m = lst[-1][2]
    mean = statistics.mean(amts); mid = (max(amts)+min(amts))/2
    rat = [x[1]/x[2] for x in lst]
    const = max(amts)-min(amts) < 0.005*mean
    agg[c].append((mean/(2*m), mid/(2*m), const))
    print(f"{u:8s}{c:18s} {len(lst):2d} {len(mins):3d}  {m:12.2f} {mean:12.2f} {mean/(2*m):8.4f} {mid/(2*m):8.4f} {min(rat):8.3f} {max(rat):8.3f} {lst[-1][3]}{' CONST' if const else ''}")
print("\n# per category: mean/(2*min) across series (variable series only)")
for c, lst in sorted(agg.items()):
    v = [x[0] for x in lst if not x[2]]; md = [x[1] for x in lst if not x[2]]
    if v:
        print(f"{c:18s} n={len(v):2d} mean/2min: min={min(v):.4f} med={statistics.median(v):.4f} max={max(v):.4f} | mid/2min: min={min(md):.4f} med={statistics.median(md):.4f} max={max(md):.4f}")
    cst = [x[0] for x in lst if x[2]]
    if cst: print(f"{c:18s} constant series: amount/(2min) = {sorted(set(round(x,4) for x in cst))}")
