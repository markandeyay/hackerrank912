"""Task 1: gap statistics of every recurring debit series the engine builds.

Run:  .venv/Scripts/python code/notes/improve2/gap_stats.py
Read-only against the engine. Groups settled debits exactly like
StateBuilder._build_debit_series (per category, same exclusions) for every
user that appears in requests.csv or sample_requests.csv, then also groups
per description inside each category.
"""
from __future__ import annotations

import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR))

from data import Dataset  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from state import NON_RECURRING_CATEGORIES, NON_RECURRING_TYPES, StateBuilder  # noqa: E402


def history_groups(builder: StateBuilder, req):
    """Replicates build()+_build_debit_series grouping: (category -> rows) and
    (category, description) -> rows, rows = (settlement_date, amount, event)."""
    ds = builder.ds
    prof = ds.profiles[req.user_id]
    rq = req.request_date
    events = ds.events_by_user.get(req.user_id, [])
    linked_targets = {e.linked_event_id for e in events if e.linked_event_id}
    by_cat = defaultdict(list)
    by_desc = defaultdict(list)
    for e in events:
        amt = builder.amount_of(e)
        if e.direction != "debit" or e.status != "settled" or amt is None:
            continue
        sd = e.settlement_date or e.event_date
        if sd > rq:
            continue
        if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
            continue
        if e.linked_event_id or e.event_id in linked_targets:
            continue
        if e.amount_source != "csv":
            continue
        row = (sd, amt, e)
        by_cat[e.category].append(row)
        by_desc[(e.category, e.description)].append(row)
    return by_cat, by_desc


def gaps_of(rows):
    ds = sorted(r[0] for r in rows)
    return [(ds[i + 1] - ds[i]).days for i in range(len(ds) - 1)]


def main():
    ds = Dataset()
    reqs = ds.load_requests("requests.csv") + ds.load_requests("sample_requests.csv")
    builder = StateBuilder(ds, load_image_amounts(ds, False), load_adjustments(ds, False))
    seen = set()
    cat_stats = []  # per engine series
    desc_stats = []
    for req in reqs:
        if req.user_id in seen:
            continue
        seen.add(req.user_id)
        by_cat, by_desc = history_groups(builder, req)
        for cat, rows in by_cat.items():
            if len(rows) < 3:
                continue
            g = gaps_of(rows)
            per = statistics.median(g)
            if per > 45:
                continue
            ndesc = len({r[2].description for r in rows})
            dates = sorted(r[0] for r in rows)
            cat_stats.append(dict(user=req.user_id, cat=cat, n=len(rows), gaps=g, per=per, ndesc=ndesc, doms=[d.day for d in dates]))
        for (cat, desc), rows in by_desc.items():
            if len(rows) < 3:
                continue
            g = gaps_of(rows)
            per = statistics.median(g)
            if per > 45:
                continue
            dates = sorted(r[0] for r in rows)
            desc_stats.append(dict(user=req.user_id, cat=cat, desc=desc, n=len(rows), gaps=g, per=per, doms=[d.day for d in dates]))

    print(f"users: {len(seen)}  engine (per-category) series: {len(cat_stats)}  per-description series: {len(desc_stats)}")

    def report(name, stats):
        const = [s for s in stats if len(set(s["gaps"])) == 1]
        print(f"\n== {name}: {len(stats)} series, constant gap: {len(const)} ({100*len(const)/len(stats):.1f}%)")
        monthly = [s for s in stats if s["per"] >= 28]
        short = [s for s in stats if s["per"] < 28]
        print(f"   monthly (median gap >= 28): {len(monthly)}, short-cycle: {len(short)}")
        sc_const = [s for s in short if len(set(s["gaps"])) == 1]
        print(f"   short-cycle with constant gap: {len(sc_const)}/{len(short)}")
        print("   short-cycle median-gap distribution:", sorted(Counter(int(s["per"]) for s in short).items()))
        print("   short-cycle: all individual gap values:", sorted(Counter(g for s in short for g in s["gaps"]).items()))
        # monthly: same DOM?
        same_dom = [s for s in monthly if len(set(s["doms"])) == 1]
        const30 = [s for s in monthly if len(set(s["gaps"])) == 1]
        print(f"   monthly: same day-of-month every time: {len(same_dom)}/{len(monthly)}; constant day gap: {len(const30)}/{len(monthly)}")
        print("   monthly: individual gap values:", sorted(Counter(g for s in monthly for g in s["gaps"]).items()))
        # DOM clamp cases (day 29-31)?
        near_end = [s for s in monthly if max(s["doms"]) >= 29]
        print(f"   monthly series with DOM >= 29: {len(near_end)}; of which same DOM: {len([s for s in near_end if len(set(s['doms'])) == 1])}")
        irregular = [s for s in stats if len(set(s["gaps"])) > 1]
        if irregular:
            print(f"   irregular series ({len(irregular)}):")
            for s in irregular[:40]:
                extra = f" desc={s['desc']}" if "desc" in s else f" ndesc={s.get('ndesc')}"
                print(f"     {s['user']:8s} {s['cat']:16s} n={s['n']:2d} med={s['per']:5.1f} gaps={Counter(s['gaps']).most_common()}{extra}")
            if len(irregular) > 40:
                print(f"     ... {len(irregular) - 40} more")
        return const, irregular

    report("engine per-category series", cat_stats)
    pooled = [s for s in cat_stats if s["ndesc"] > 1]
    print(f"\n   per-category series pooling >1 description: {len(pooled)}; of which constant gap: {len([s for s in pooled if len(set(s['gaps'])) == 1])}")
    print("   pooled categories:", sorted(Counter(s["cat"] for s in pooled).items()))
    report("per-description series", desc_stats)

    # for the samples: short-cycle series and their last gap vs median
    print("\n== sample users, short-cycle series: n, gaps")
    sample_users = {r.user_id for r in ds.load_requests("sample_requests.csv")}
    for s in cat_stats:
        if s["user"] in sample_users and s["per"] < 28:
            print(f"   {s['user']:8s} {s['cat']:14s} n={s['n']:2d} ndesc={s['ndesc']} gaps={Counter(s['gaps']).most_common()}")


if __name__ == "__main__":
    main()
