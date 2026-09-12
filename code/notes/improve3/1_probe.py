"""Probes on top of 1_residual_backsolve.py: per-series estimator vs implied nominal range; structural samples; horizon test.

Run: .venv/Scripts/python code/notes/improve3/1_probe.py
"""
from __future__ import annotations

import itertools
import statistics
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import importlib

bs = importlib.import_module("1_residual_backsolve")
from data import Dataset  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402

BAND, GRID, fmt = bs.BAND, bs.GRID, bs.fmt


def per_series_estimators(rows):
    print("### per-series: implied nominal range (from the exact band+grid solutions) vs estimators")
    print("| req | series | n | occ | implied range | engine | mean | midrange | imid | median | last | first | in range: engine/mean/mid/imid/median/last |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    hits = {k: [0, 0] for k in ("engine", "mean", "mid", "imid", "median", "last")}
    for r in rows:
        if r["capped"] or not r["unknown"]:
            continue
        g = GRID[r["cur"]]
        n, bounds = bs.exact_solutions(r["unknown"], [u["occ"] for u in r["unknown"]], r["residual"], g)
        if not bounds:
            continue
        for u, b in zip(r["unknown"], bounds):
            if b[0] is None:
                continue
            amts = [a for _, a in u["hist"]]
            a = BAND.get(u["cat"], 0.28)
            lo, hi = max(amts) / (1 + a), min(amts) / (1 - a)
            ests = dict(engine=u["amount"], mean=statistics.mean(amts), mid=(max(amts) + min(amts)) / 2, imid=(lo + hi) / 2, median=statistics.median(amts), last=amts[-1])
            first = amts[0]
            width = (b[1] - b[0]) / u["amount"]
            informative = width <= 0.06  # implied range narrower than +/-3 %
            marks = []
            for k, v in ests.items():
                ok = b[0] - 0.5 * g - 1e-9 <= v <= b[1] + 0.5 * g + 1e-9  # within half a grid step of the range
                marks.append("Y" if ok else "n")
                if informative:
                    hits[k][0] += ok
                    hits[k][1] += 1
            c = r["cur"]
            print(f"| {r['id'][-2:]} | {u['cat']} | {u['n_hist']} | {u['occ']} | [{fmt(b[0], c)}, {fmt(b[1], c)}]{' *' if informative else ''} | {fmt(ests['engine'], c)} | {fmt(ests['mean'], c)} | {fmt(ests['mid'], c)} | {fmt(ests['imid'], c)} | {fmt(ests['median'], c)} | {fmt(ests['last'], c)} | {fmt(first, c)} | {'/'.join(marks)} |")
    print("\n(* = implied range narrower than 6 % of the amount; a 'Y' means the estimator is within half a grid step of the range)")
    print("hits on the informative series:", {k: f"{v[0]}/{v[1]}" for k, v in hits.items()})


def structural(rows, ids=("04", "05", "06", "10", "13", "15")):
    print("\n### structural samples: periodic occurrence dates up to the trough")
    for r in rows:
        if r["id"][-2:] not in ids:
            continue
        print(f"\n{r['id']} {r['cur']} request {r['request_date']} payday {r['first_payday']} T={r['T']} residual={fmt(r['residual'], r['cur'])} engine={fmt(r['eng_block'], r['cur'])}")
        for u in r["unknown"]:
            hist_d = [d for d, _ in u["hist"]]
            print(f"  {u['cat']:13s} {u['cadence']:8s} step={u['step']:2d} occ={u['occ']:2d} amt={fmt(u['amount'], r['cur'])} last hist {hist_d[-3:]} -> projected {u['dates']}")


def horizon_test(ids=("05", "10", "13", "12")):
    print("\n### horizon sensitivity for the samples whose trough is the horizon end (no income) or multi-cycle")
    ds = Dataset()
    reqs = [q for q in ds.load_requests("sample_requests.csv") if q.request_id[-2:] in ids]
    images = load_image_amounts(ds, True)
    adjs = load_adjustments(ds, True)
    for h in (84, 85, 86, 87, 88, 89, 90):
        builder = bs.CaptureBuilder(ds, images, adjs, horizon_days=h)
        rows = bs.backsolve(dict(ds=ds, reqs=reqs, builder=builder))
        cells = []
        for r in rows:
            if r["capped"]:
                cells.append(f"{r['id'][-2:]}: cap eng={fmt(r['got'], r['cur'])} vs {fmt(r['want'], r['cur'])}")
                continue
            g = GRID[r["cur"]]
            L = U = 0.0
            for u in r["unknown"]:
                amts = [a for _, a in u["hist"]]
                a = BAND.get(u["cat"], 0.28)
                L += u["occ"] * max(amts) / (1 + a)
                U += u["occ"] * min(amts) / (1 - a)
            n, _ = bs.exact_solutions(r["unknown"], [u["occ"] for u in r["unknown"]], r["residual"], g)
            counts = tuple(u["occ"] for u in r["unknown"])
            cells.append(f"{r['id'][-2:]}: T={r['T']} counts={counts} resid={fmt(r['residual'], r['cur'])} eng={fmt(r['eng_block'], r['cur'])} ({100*r['diff']/r['eng_block']:+.1f}%) band=[{fmt(L, r['cur'])},{fmt(U, r['cur'])}] {'IN' if L <= r['residual'] <= U else 'out'} exact={n}")
        print(f"h={h}: " + " | ".join(cells))


def wide_count_search(rows, ids=("10", "04", "05", "13")):
    print("\n### wider count search (periodic +/-3, monthly +/-1) for the unexplained samples")
    for r in rows:
        if r["id"][-2:] not in ids:
            continue
        g = GRID[r["cur"]]
        u = r["unknown"]
        ours = [x["occ"] for x in u]
        choices = [sorted({max(0, x["occ"] + d) for d in range(-3, 4)}) if x["cadence"] == "periodic" else sorted({max(0, x["occ"] + d) for d in (-1, 0, 1)}) for x in u]
        sols = []
        for cs in itertools.product(*choices):
            n, _ = bs.exact_solutions(u, list(cs), r["residual"], g)
            if n:
                sols.append((sum(abs(a - b) for a, b in zip(cs, ours)), cs, n))
        sols.sort()
        lab = " ".join(x["cat"][:5] for x in u)
        print(f"{r['id']} ours={tuple(ours)} [{lab}] -> {', '.join(f'{cs} L1={l1}' for l1, cs, n in sols[:8])}{' ...' if len(sols) > 8 else ''}")


if __name__ == "__main__":
    import json

    rows = json.load(open(Path(__file__).resolve().parent / "1_residual_backsolve.json", encoding="utf-8"))
    per_series_estimators(rows)
    structural(rows)
    wide_count_search(rows)
    horizon_test()
