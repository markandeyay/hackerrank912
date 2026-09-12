import csv, statistics
from collections import defaultdict
rows = [r for r in csv.DictReader(open("dataset/financial_events.csv", encoding="utf-8")) if r["status"]=="settled" and r["direction"]=="debit" and r["amount"] and not r["linked_event_id"]]
ser = defaultdict(list)
for r in rows: ser[(r["user_id"], r["category"])].append(float(r["amount"]))
print("# lower bound on half-band a per category: max over series of (max-min)/(max+min); and its distribution")
by = defaultdict(list)
for (u,c),a in ser.items():
    if len(a)>=3 and max(a)-min(a) > 0.005*statistics.mean(a):
        by[c].append(((max(a)-min(a))/(max(a)+min(a)), len(a)))
for c,l in sorted(by.items()):
    v = sorted(x[0] for x in l)
    print(f"{c:14s} series={len(l):3d} a_min: max={v[-1]:.4f} p90={v[int(0.9*(len(v)-1))]:.4f} med={statistics.median(v):.4f}  median n={statistics.median(x[1] for x in l):.0f}")
