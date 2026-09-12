import csv, statistics
from collections import defaultdict
rows = [r for r in csv.DictReader(open("dataset/financial_events.csv", encoding="utf-8")) if r["status"]=="settled" and r["direction"]=="debit" and r["amount"]]
K = {"dining":2.0,"entertainment":2.0,"shopping":2.5,"gym":2.0,"streaming":2.0}
print("# noise = amount/(k*min) histogram for leaked categories (bins of 0.04)")
for cat,k in K.items():
    xs = [float(r["amount"])/(k*float(r["minimum_allowed_amount"])) for r in rows if r["category"]==cat and r["minimum_allowed_amount"]]
    if not xs: continue
    h = defaultdict(int)
    for x in xs: h[round((x-1)/0.04)]+=1
    print(f"{cat:14s} n={len(xs)} min={min(xs):.4f} max={max(xs):.4f} sd={statistics.pstdev(xs):.4f} (uniform±a => sd=a/1.732)")
    print("   ", " ".join(f"{b*0.04:+.2f}:{h[b]}" for b in sorted(h)))
    # are noise values on a grid? e.g. steps of 0.01?
    fr = [round(x*100,6)%1 for x in xs]
    print("    fraction of noise values that are exact 0.01 multiples:", sum(1 for f in fr if abs(f)<1e-6 or abs(f-1)<1e-6)/len(xs))
print("\n# fixed categories: per-series spread (max/mean-1, 1-min/mean, sd/mean) medians by category, n rows per series")
ser = defaultdict(list)
for r in rows:
    if r["category"] in ("salary",) : continue
    ser[(r["user_id"], r["category"])].append(float(r["amount"]))
bycat = defaultdict(list)
for (u,c),a in ser.items():
    if len(a)<3: continue
    m=statistics.mean(a)
    if max(a)-min(a) < 0.005*m: bycat[c].append(None); continue
    bycat[c].append((max(a)/m-1, 1-min(a)/m, statistics.pstdev(a)/m, len(a), (max(a)+min(a))/2/m))
for c,l in sorted(bycat.items()):
    v=[x for x in l if x]
    nc = len(l)-len(v)
    if not v: print(f"{c:18s} all {nc} series constant"); continue
    print(f"{c:18s} series={len(v)} const={nc} med n={statistics.median(x[3] for x in v):.0f} max/mean-1={statistics.median(x[0] for x in v):.3f} (max {max(x[0] for x in v):.3f}) 1-min/mean={statistics.median(x[1] for x in v):.3f} sd/mean={statistics.median(x[2] for x in v):.3f} mid/mean med={statistics.median(x[4] for x in v):.4f}")
