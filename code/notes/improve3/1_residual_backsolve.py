"""Residual back-solve of the reference reserve (improve3 / subagent 1).

Run:  .venv/Scripts/python code/notes/improve3/1_residual_backsolve.py [table|hyp|detail|all]

Engine untouched: subclasses StateBuilder only to capture the per-category history rows.

Formula (per sample, home currency):
  head     = current_available_balance - minimum_balance_to_keep
  ref_res  = head - expected amount_safe_to_pay                      (reference reserve; only meaningful when uncapped)
  T        = engine trough day = argmin of daily_balances(st) (first day at the minimum)
  credits  = sum of projected credits (salary / income / known credits) with request_date <= date <= T
  R        = ref_res + credits          = total debits the reference must have counted in [request_date, T]
  certain  = known debits (pending / scheduled / retry / image rows) in [rq, T]
           + constant-amount series x occurrences in [rq, T]
           + leaked series (k x minimum_allowed_amount) x occurrences in [rq, T]
  residual = R - certain                = reference's sum of the unknown fixed-category nominals x their occurrence counts
  engine block = sum of the engine's (clamped, snapped) amounts x the same occurrence counts
The alternative binding day T' = first payday - 1 is reported next to T.
"""
from __future__ import annotations

import itertools
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR))

from data import Dataset  # noqa: E402
from forecast import daily_balances  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from state import NON_RECURRING_CATEGORIES, NON_RECURRING_TYPES, REGULAR_SALARY, StateBuilder, add_months  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent
GRID = {"IDR": 100.0, "INR": 10.0, "ZAR": 0.2, "EUR": 1.0, "USD": 1.0}
BAND = {"dining": 0.28, "groceries": 0.28, "transport": 0.28, "entertainment": 0.12, "healthcare": 0.12, "shopping": 0.12, "utilities": 0.12}


def is_constant(xs):
    return max(xs) - min(xs) < 0.005 * max(1.0, statistics.mean(xs))


def round_sig(x, n):
    if x == 0:
        return 0.0
    return round(x, -int(math.floor(math.log10(abs(x)))) + (n - 1))


class CaptureBuilder(StateBuilder):
    """Same forecast as the engine; additionally records the history rows behind each series."""

    def _build_debit_series(self, st, hist, linked_targets, adjs):
        super()._build_debit_series(st, hist, linked_targets, adjs)
        groups = defaultdict(list)
        for e in hist:
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
                continue
            if e.linked_event_id or e.event_id in linked_targets:
                continue
            sd = e.settlement_date or e.event_date
            if self.opt.get("exclude_image_rows_from_mean") and e.amount_source != "csv":
                continue
            groups[e.category].append((sd, self.to_home(self.amount_of(e), e.currency, st.home, sd), e))
        for cat in groups:
            groups[cat].sort(key=lambda r: r[0])
        st.hist_groups = groups


def series_kind(builder, st, s):
    rows = st.hist_groups.get(s.category, [])
    amts = [r[1] for r in rows]
    if not amts:
        return "unknown"
    if is_constant(amts):
        return "constant"
    latest_min = rows[-1][2].minimum_allowed_amount
    if latest_min and s.category in builder.min_factor and all(r[2].minimum_allowed_amount == latest_min for r in rows):
        nominal = builder.to_home(latest_min * builder.min_factor[s.category], rows[-1][2].currency, st.home, rows[-1][0])
        if abs(nominal - s.amount) < 1e-6:
            return "leaked"
    return "fixed"


def occ_before(s, T, rq):
    return len([d for d in s.dates if rq <= d <= T])


def backsolve(bench, verbose=False):
    ds, builder = bench["ds"], bench["builder"]
    out = []
    for req in bench["reqs"]:
        st = builder.build(req)
        prof = st.profile
        rq = st.request_date
        want = float(req.expected["amount_safe_to_pay"])
        head = prof.current_available_balance - prof.minimum_balance_to_keep
        capped = want >= req.requested_amount - 1e-6
        bal = daily_balances(st)
        tmin = min(bal, key=lambda x: x[1])
        T = tmin[0]
        got = max(0.0, min(req.requested_amount, tmin[1] - st.min_balance))
        paydays = sorted(d for d in st.salary_dates if d > rq)
        first_payday = paydays[0] if paydays else None
        T_alt = first_payday - timedelta(days=1) if first_payday else None
        salary_amt = st.salary_amount

        def block(Tb):
            known = sum(-f.amount for f in st.flows if f.amount < 0 and rq <= f.date <= Tb)
            credits = sum(f.amount for f in st.flows if f.amount > 0 and rq <= f.date <= Tb)
            certain = known
            unknown = []
            for s in st.series:
                occ = occ_before(s, Tb, rq)
                if not occ:
                    continue
                kind = series_kind(builder, st, s)
                if kind in ("constant", "leaked"):
                    certain += occ * s.amount
                else:
                    unknown.append((s, occ, kind))
            return known, credits, certain, unknown

        known, credits, certain, unknown = block(T)
        R = head - want + credits
        residual = R - certain
        eng_block = sum(occ * s.amount for s, occ, _ in unknown)
        rec = dict(
            id=req.request_id, user=req.user_id, cur=st.home, balance=prof.current_available_balance, minimum=prof.minimum_balance_to_keep,
            salary=salary_amt, first_payday=str(first_payday) if first_payday else None, request_date=str(rq), T=str(T), T_alt=str(T_alt) if T_alt else None,
            want=want, got=round(got, 2), requested=req.requested_amount, capped=capped, ref_res=head - want, eng_res=head - got,
            known=known, credits=credits, certain=certain, R=R, residual=residual, eng_block=eng_block, diff=residual - eng_block,
            unknown=[dict(cat=s.category, occ=occ, amount=s.amount, step=s.step_days, cadence=s.cadence, n_hist=s.n_hist, dates=[str(d) for d in s.dates if rq <= d <= T],
                          hist=[(str(r[0]), r[1]) for r in st.hist_groups[s.category]]) for s, occ, _ in unknown],
            certain_items=[dict(cat=s.category, occ=occ_before(s, T, rq), amount=s.amount, kind=series_kind(builder, st, s)) for s in st.series if occ_before(s, T, rq) and series_kind(builder, st, s) in ("constant", "leaked")]
            + [dict(cat=f.label, occ=1, amount=-f.amount, kind=f.kind) for f in st.flows if f.amount < 0 and rq <= f.date <= T],
        )
        if T_alt and T_alt != T:
            k2, c2, cert2, unk2 = block(T_alt)
            rec["alt"] = dict(T=str(T_alt), residual=head - want + c2 - cert2, eng_block=sum(occ * s.amount for s, occ, _ in unk2),
                              unknown=[(s.category, occ) for s, occ, _ in unk2])
        out.append(rec)
    return out


def fmt(x, cur):
    if x is None:
        return "-"
    return f"{x:,.2f}" if cur in ("EUR", "USD", "ZAR") else f"{x:,.0f}"


def table(rows):
    print("| req | cur | balance | minimum | salary / first payday | expected | engine | ref reserve | certain | residual | engine block | resid-eng | rel | T (trough) | T'=payday-1 | unknown series (occ) |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        c = r["cur"]
        rel = "" if r["capped"] or not r["eng_block"] else f"{100*r['diff']/r['eng_block']:+.2f}%"
        unk = " ".join(f"{u['cat']}({u['occ']})" for u in r["unknown"])
        alt = ""
        if r.get("alt"):
            alt = f"{r['alt']['T']} resid {fmt(r['alt']['residual'], c)} vs eng {fmt(r['alt']['eng_block'], c)}"
        elif r["T_alt"]:
            alt = "same"
        cap = " (cap)" if r["capped"] else ""
        print(f"| {r['id'][-2:]} | {c} | {fmt(r['balance'], c)} | {fmt(r['minimum'], c)} | {fmt(r['salary'], c)} / {r['first_payday'] or '-'} | {fmt(r['want'], c)}{cap} | {fmt(r['got'], c)} | {fmt(r['ref_res'], c)} | {fmt(r['certain'], c)} | {fmt(r['residual'], c)} | {fmt(r['eng_block'], c)} | {fmt(r['diff'], c)} | {rel} | {r['T']} | {alt} | {unk} |")


# ------------------------------------------------------------------ hypotheses
def within(a, b, tol=0.01):
    return abs(a - b) <= tol * abs(b) if b else abs(a) < 1e-9


def hist_window(hist, lo, hi):
    return [a for d, a in hist if lo <= date.fromisoformat(d) <= hi]


def estimators(u, cur, rq, T):
    """Per-series candidate nominals under different hypotheses -> dict name -> per-occurrence amount (or None)."""
    hist = u["hist"]
    amts = [a for _, a in hist]
    dts = [date.fromisoformat(d) for d, _ in hist]
    n = len(amts)
    a = BAND.get(u["cat"], 0.28)
    lo, hi = max(amts) / (1 + a), min(amts) / (1 - a)
    g = GRID[cur]
    mean = statistics.mean(amts)
    est = {
        "engine (clamp+snap mean)": u["amount"],
        "mean": mean,
        "median": statistics.median(amts),
        "first observed (oldest)": amts[0],
        "last observed": amts[-1],
        "max": max(amts),
        "min": min(amts),
        "midrange": (max(amts) + min(amts)) / 2,
        "imid": (lo + hi) / 2,
        "imid snapped": round((lo + hi) / 2 / g) * g,
        "mean 2 sig figs": round_sig(mean, 2),
        "mean 3 sig figs": round_sig(mean, 3),
        "mean to grid": round(mean / g) * g,
        "mean to 10x grid": round(mean / (10 * g)) * 10 * g,
        "mean ceil 10x grid": math.ceil(mean / (10 * g)) * 10 * g,
        "last 3 mean": statistics.mean(amts[-3:]),
        "mean + 0.5 sd": mean + 0.5 * (statistics.pstdev(amts) if n > 1 else 0),
        "max/(1+a) (L)": lo,
        "min/(1-a) (U)": hi,
    }
    # row nearest to 3 months before request
    target = add_months(rq, -3)
    est["row ~3 months before request"] = amts[min(range(n), key=lambda i: abs((dts[i] - target).days))]
    # row nearest to 1 month before request
    target1 = add_months(rq, -1)
    est["row ~1 month before request"] = amts[min(range(n), key=lambda i: abs((dts[i] - target1).days))]
    # same window one month earlier: rows in [rq-1m, T-1m] (total, not per occurrence)
    est["_window_1m_total"] = sum(hist_window(hist, add_months(rq, -1), add_months(T, -1)))
    est["_last30_total"] = sum(hist_window(hist, rq - timedelta(days=30), rq - timedelta(days=1)))
    est["_last_calendar_month_total"] = sum(hist_window(hist, date(add_months(rq, -1).year, add_months(rq, -1).month, 1), date(rq.year, rq.month, 1) - timedelta(days=1)))
    return est


def hypotheses(rows, tol=0.01):
    unc = [r for r in rows if not r["capped"]]
    names = None
    score = Counter()
    per = defaultdict(dict)
    for r in unc:
        cur, rq, T = r["cur"], date.fromisoformat(r["request_date"]), date.fromisoformat(r["T"])
        if not r["unknown"]:
            continue
        ests = [estimators(u, cur, rq, T) for u in r["unknown"]]
        names = [k for k in ests[0] if not k.startswith("_")]
        for k in names:
            tot = sum(u["occ"] * e[k] for u, e in zip(r["unknown"], ests))
            per[r["id"]][k] = tot
            score[k] += within(tot, r["residual"], tol)
        for k in ("_window_1m_total", "_last30_total", "_last_calendar_month_total"):
            tot = sum(e[k] for e in ests)
            per[r["id"]][k] = tot
            score[k] += within(tot, r["residual"], tol)
        # monthly-rate charging: each periodic series once at nominal x 30/step, monthly once
        tot = sum((e["engine (clamp+snap mean)"] * (30 / u["step"] if u["cadence"] == "periodic" else 1)) for u, e in zip(r["unknown"], ests))
        per[r["id"]]["_monthly_rate_once"] = tot
        score["_monthly_rate_once"] += within(tot, r["residual"], tol)
    n = len([r for r in unc if r["unknown"]])
    print(f"\n### (c)(d)(f) estimator hypotheses on the residual block — samples explained within {100*tol:.0f}% (of {n} uncapped with an unknown block)")
    print("| hypothesis | within 1% | within 2% | mean |rel err| |")
    print("|---|---|---|---|")
    keys = names + ["_window_1m_total", "_last30_total", "_last_calendar_month_total", "_monthly_rate_once"]
    stats = []
    for k in keys:
        w1 = sum(within(per[r["id"]][k], r["residual"], 0.01) for r in unc if r["unknown"])
        w2 = sum(within(per[r["id"]][k], r["residual"], 0.02) for r in unc if r["unknown"])
        mrel = statistics.mean(abs(per[r["id"]][k] - r["residual"]) / abs(r["residual"]) for r in unc if r["unknown"] and r["residual"])
        stats.append((k, w1, w2, mrel))
    for k, w1, w2, mrel in sorted(stats, key=lambda x: (-x[1], -x[2], x[3])):
        print(f"| {k.strip('_')} | {w1} | {w2} | {100*mrel:.2f}% |")
    return per


def coarse_grid(rows):
    print("\n### (a) residual on a coarse round-number grid")
    print("| req | cur | residual | on item grid? | nearest 100u | 500u | 1000u | rel dist 100u / 500u / 1000u |")
    print("|---|---|---|---|---|---|---|---|")
    cnt = Counter()
    for r in rows:
        if r["capped"]:
            continue
        g = GRID[r["cur"]]
        x = r["residual"]
        on = abs(x / g - round(x / g)) < 1e-6
        cells = []
        rels = []
        for m in (100, 500, 1000):
            u = m * g
            near = round(x / u) * u
            rel = abs(x - near) / abs(x) if x else 0
            rels.append(rel)
            cells.append(fmt(near, r["cur"]))
            cnt[(m, "exact")] += abs(x - near) < 1e-6
            cnt[(m, "w1")] += rel <= 0.01
        cnt["item_grid"] += on
        print(f"| {r['id'][-2:]} | {r['cur']} | {fmt(x, r['cur'])} | {'yes' if on else 'NO'} | {cells[0]} | {cells[1]} | {cells[2]} | {100*rels[0]:.2f}% / {100*rels[1]:.2f}% / {100*rels[2]:.2f}% |")
    print(f"\nresidual exactly on the item grid: {cnt['item_grid']}/21; exactly a multiple of 100u / 500u / 1000u: {cnt[(100,'exact')]} / {cnt[(500,'exact')]} / {cnt[(1000,'exact')]}; within 1% of one: {cnt[(100,'w1')]} / {cnt[(500,'w1')]} / {cnt[(1000,'w1')]}")


def salary_ratio(bench, rows):
    """(b) nominal / monthly salary for the leaked series, all users; then implied ratios of the fixed block."""
    ds, builder = bench["ds"], bench["builder"]
    print("\n### (b) leaked nominal / monthly salary, all users with a regular payroll")
    ratios = defaultdict(list)
    per_user_salary = {}
    for uid, events in ds.events_by_user.items():
        prof = ds.profiles[uid]
        reg = [e for e in events if e.status == "settled" and e.category == "salary" and e.description in REGULAR_SALARY and e.amount]
        if len(reg) < 2:
            continue
        sal = Counter(round(ds.convert(e.amount, e.currency, prof.home_currency, e.settlement_date), 2) for e in reg).most_common(1)[0][0]
        per_user_salary[uid] = sal
        linked_targets = {e.linked_event_id for e in events if e.linked_event_id}
        by_cat = defaultdict(list)
        for e in events:
            if e.status != "settled" or e.direction != "debit" or not e.amount or e.amount_source != "csv":
                continue
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES or e.linked_event_id or e.event_id in linked_targets:
                continue
            by_cat[e.category].append(e)
        for cat, evs in by_cat.items():
            mins = {e.minimum_allowed_amount for e in evs}
            if len(mins) == 1 and None not in mins and cat in builder.min_factor and len(evs) >= 3:
                nominal = ds.convert(mins.pop() * builder.min_factor[cat], evs[-1].currency, prof.home_currency, evs[-1].settlement_date)
                gaps = sorted((evs[i + 1].settlement_date - evs[i].settlement_date).days for i in range(len(evs) - 1))
                step = gaps[len(gaps) // 2]
                monthly = nominal * (30 / step if step < 28 else 1)
                ratios[cat].append((nominal / sal, monthly / sal, uid))
    print("| category | series | nominal/salary min | median | max | CV | monthly-rate/salary min | median | max |")
    print("|---|---|---|---|---|---|---|---|---|")
    for cat, v in sorted(ratios.items()):
        a = [x[0] for x in v]
        b = [x[1] for x in v]
        cv = statistics.pstdev(a) / statistics.mean(a)
        print(f"| {cat} | {len(v)} | {min(a):.4f} | {statistics.median(a):.4f} | {max(a):.4f} | {cv:.2f} | {min(b):.4f} | {statistics.median(b):.4f} | {max(b):.4f} |")
    # implied ratio per sample of the fixed block
    print("\nimplied residual / salary and per-occurrence engine amounts / salary for the fixed block (uncapped samples with a salary):")
    print("| req | residual/salary | unknown series: engine amount/salary (occ) |")
    print("|---|---|---|")
    for r in rows:
        if r["capped"] or not r["salary"]:
            continue
        parts = " ".join(f"{u['cat']} {u['amount']/r['salary']:.4f}({u['occ']})" for u in r["unknown"])
        print(f"| {r['id'][-2:]} | {r['residual']/r['salary']:.4f} | {parts} |")


def occurrence_solve(rows, tol=0.01, maxc=3):
    print("\n### (e) integer occurrence counts (0..3 per unknown series, engine nominals) that best explain the residual")
    print("| req | our counts | best counts | best rel err | #count vectors within 1% | ours within 1%? | nearest within-1% vector (L1 from ours) |")
    print("|---|---|---|---|---|---|---|")
    explained = 0
    ours_ok = 0
    nontrivial = 0
    for r in rows:
        if r["capped"] or not r["unknown"]:
            continue
        u = r["unknown"]
        ours = tuple(x["occ"] for x in u)
        best, bestrel, feas = None, None, []
        for cs in itertools.product(range(maxc + 1), repeat=len(u)):
            tot = sum(c * x["amount"] for c, x in zip(cs, u))
            rel = abs(tot - r["residual"]) / abs(r["residual"]) if r["residual"] else abs(tot)
            if bestrel is None or rel < bestrel:
                best, bestrel = cs, rel
            if rel <= tol:
                feas.append(cs)
        ours_rel = abs(sum(c * x["amount"] for c, x in zip(ours, u)) - r["residual"]) / abs(r["residual"])
        o_ok = ours_rel <= tol
        ours_ok += o_ok
        explained += bool(feas)
        near = min(feas, key=lambda cs: sum(abs(a - b) for a, b in zip(cs, ours))) if feas else None
        l1 = sum(abs(a - b) for a, b in zip(near, ours)) if near else None
        nontrivial += bool(feas) and not o_ok
        lab = " ".join(f"{x['cat'][:5]}" for x in u)
        print(f"| {r['id'][-2:]} | {ours} | {best} | {100*bestrel:.2f}% | {len(feas)} | {'yes' if o_ok else 'no'} ({100*ours_rel:+.2f}%) | {near} L1={l1} [{lab}] |")
    print(f"\nsamples with SOME count vector within 1%: {explained}; ours already within 1%: {ours_ok}; explained only by a different vector: {nontrivial}")


def one_off(rows):
    """(f) block explained by the engine block plus/minus exactly one occurrence of one series."""
    print("\n### (f) residual = engine block +/- one occurrence of one unknown series?")
    print("| req | resid-eng | closest single +/-1 occurrence | rel err after | note |")
    print("|---|---|---|---|---|")
    n = 0
    for r in rows:
        if r["capped"] or not r["unknown"]:
            continue
        best = None
        for u in r["unknown"]:
            for sgn in (+1, -1):
                tot = r["eng_block"] + sgn * u["amount"]
                rel = abs(tot - r["residual"]) / abs(r["residual"])
                if best is None or rel < best[0]:
                    best = (rel, sgn, u["cat"])
        base = abs(r["diff"]) / abs(r["residual"])
        ok = best[0] <= 0.01
        n += ok
        print(f"| {r['id'][-2:]} | {fmt(r['diff'], r['cur'])} ({100*r['diff']/r['residual']:+.2f}%) | {'+' if best[1]>0 else '-'}1 {best[2]} | {100*best[0]:.2f}% | {'within 1%' if ok else ''}{' (already within 1%)' if base <= 0.01 else ''} |")
    print(f"\nexplained within 1% by +/- one occurrence: {n}")


def detail(rows):
    for r in rows:
        if r["capped"]:
            continue
        print(f"\n#### {r['id']} {r['cur']} T={r['T']} residual={fmt(r['residual'], r['cur'])} engine={fmt(r['eng_block'], r['cur'])}")
        for u in r["unknown"]:
            amts = [a for _, a in u["hist"]]
            a = BAND.get(u["cat"], 0.28)
            print(f"  {u['cat']:13s} occ={u['occ']} step={u['step']} n={u['n_hist']} engine={u['amount']:.2f} mean={statistics.mean(amts):.2f} [L,U]=[{max(amts)/(1+a):.2f},{min(amts)/(1-a):.2f}] first={amts[0]:.2f} last={amts[-1]:.2f} dates={u['dates']}")
        for c in r["certain_items"]:
            print(f"  certain: {c['kind']:12s} {c['cat'][:30]:30s} occ={c['occ']} amt={c['amount']:.2f}")


def per_series_identification(rows):
    """Samples whose unknown block has one series: the nominal is identified exactly."""
    print("\n### single-series blocks (nominal identified exactly)")
    for r in rows:
        if r["capped"] or len(r["unknown"]) != 1:
            continue
        u = r["unknown"][0]
        amts = [a for _, a in u["hist"]]
        nominal = r["residual"] / u["occ"]
        a = BAND.get(u["cat"], 0.28)
        print(f"{r['id']} {r['cur']} {u['cat']} occ={u['occ']} implied nominal={nominal:.2f} engine={u['amount']:.2f} mean={statistics.mean(amts):.2f} [L,U]=[{max(amts)/(1+a):.2f},{min(amts)/(1-a):.2f}] hist={[round(x,2) for x in amts]}")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    ds = Dataset()
    reqs = ds.load_requests("sample_requests.csv")
    images = load_image_amounts(ds, True)
    adjs = load_adjustments(ds, True)
    builder = CaptureBuilder(ds, images, adjs)
    bench = dict(ds=ds, reqs=reqs, builder=builder)
    rows = backsolve(bench)
    with open(OUT_DIR / "1_residual_backsolve.json", "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=1, default=str)
    if mode in ("table", "all"):
        table(rows)
    if mode in ("hyp", "all"):
        coarse_grid(rows)
        salary_ratio(bench, rows)
        hypotheses(rows)
        occurrence_solve(rows)
        one_off(rows)
        per_series_identification(rows)
    if mode in ("exact", "all"):
        exact_mode(rows)
        more_estimators(bench, rows)
    if mode in ("detail", "all"):
        detail(rows)


# ------------------------------------------------------------------ exact grid back-solve under the noise band
def _range_conv(counts, lo, hi, occ, top):
    """Convolve a solution-count vector with the indicator of {occ * k : lo <= k <= hi} (integers, grid units)."""
    import numpy as np

    out = np.zeros(top + 1, dtype=np.float64)
    for k in range(lo, hi + 1):
        s = occ * k
        if s > top:
            break
        out[s:] += counts[: top + 1 - s]
    return out


def exact_solutions(unknown, counts_vec, residual, g):
    """Number of exact grid solutions and per-series implied bounds for a count vector.  Returns (n_solutions, bounds)."""
    import numpy as np

    R = int(round(residual / g))
    if abs(residual / g - R) > 1e-6 or R < 0:
        return 0, None
    ranges = []
    for u, c in zip(unknown, counts_vec):
        amts = [a for _, a in u["hist"]]
        a = BAND.get(u["cat"], 0.28)
        lo, hi = max(amts) / (1 + a), min(amts) / (1 - a)
        klo, khi = math.ceil(lo / g - 1e-9), math.floor(hi / g + 1e-9)
        if klo > khi:
            return 0, None
        ranges.append((klo, khi, c))
    fwd = [np.zeros(R + 1)]
    fwd[0][0] = 1.0
    for klo, khi, c in ranges:
        fwd.append(_range_conv(fwd[-1], klo, khi, c, R) if c else fwd[-1].copy())
    n_sol = fwd[-1][R]
    if n_sol == 0:
        return 0, None
    bwd = [None] * (len(ranges) + 1)
    bwd[len(ranges)] = np.zeros(R + 1)
    bwd[len(ranges)][R] = 1.0
    for i in range(len(ranges) - 1, -1, -1):
        klo, khi, c = ranges[i]
        nxt = bwd[i + 1]
        cur = np.zeros(R + 1)
        if c:
            for k in range(klo, khi + 1):
                s = c * k
                if s > R:
                    break
                cur[: R + 1 - s] += nxt[s:]
        else:
            cur = nxt.copy()
        bwd[i] = cur
    bounds = []
    for i, (klo, khi, c) in enumerate(ranges):
        if not c:
            bounds.append((None, None))
            continue
        feas = []
        for k in range(klo, khi + 1):
            s = c * k
            if s > R:
                break
            w = float(np.dot(fwd[i][: R + 1 - s], bwd[i + 1][s:]))
            if w > 0:
                feas.append(k)
        bounds.append((min(feas) * g, max(feas) * g) if feas else (None, None))
    return int(n_sol), bounds


def exact_mode(rows):
    print("\n### band feasibility and exact grid solutions under the engine's occurrence counts")
    print("| req | cur | residual | [sum occ*L, sum occ*U] | residual inside? | #exact grid solutions (our counts) | per-series implied nominal range vs engine |")
    print("|---|---|---|---|---|---|---|")
    feasible = 0
    for r in rows:
        if r["capped"] or not r["unknown"]:
            continue
        g = GRID[r["cur"]]
        L = U = 0.0
        for u in r["unknown"]:
            amts = [a for _, a in u["hist"]]
            a = BAND.get(u["cat"], 0.28)
            L += u["occ"] * max(amts) / (1 + a)
            U += u["occ"] * min(amts) / (1 - a)
        inside = L - 1e-6 <= r["residual"] <= U + 1e-6
        feasible += inside
        n, bounds = exact_solutions(r["unknown"], [u["occ"] for u in r["unknown"]], r["residual"], g)
        desc = ""
        if bounds:
            desc = "; ".join(f"{u['cat'][:5]} [{fmt(b[0], r['cur'])},{fmt(b[1], r['cur'])}] eng {fmt(u['amount'], r['cur'])}" for u, b in zip(r["unknown"], bounds) if b[0] is not None)
        pos = 100 * (r["residual"] - L) / (U - L) if U > L else 0
        print(f"| {r['id'][-2:]} | {r['cur']} | {fmt(r['residual'], r['cur'])} | [{fmt(L, r['cur'])}, {fmt(U, r['cur'])}] | {'yes' if inside else 'NO'} ({pos:.0f}% of the way) | {n} | {desc} |")
    print(f"\nresidual inside the band-feasible interval under our counts: {feasible}/21")

    print("\n### count vectors (ours +/-1 per periodic series, 0..3; monthly series fixed at ours) that admit an exact band+grid solution")
    print("| req | our counts | exact under ours? | vectors with exact solutions (L1 from ours, n = number of grid solutions) |")
    print("|---|---|---|---|")
    tot_ok = 0
    for r in rows:
        if r["capped"] or not r["unknown"]:
            continue
        g = GRID[r["cur"]]
        u = r["unknown"]
        ours = [x["occ"] for x in u]
        choices = []
        for x in u:
            if x["cadence"] == "periodic":
                choices.append(sorted({max(0, x["occ"] - 1), x["occ"], x["occ"] + 1}))
            else:
                choices.append([x["occ"]])
        sols = []
        for cs in itertools.product(*choices):
            n, _ = exact_solutions(u, list(cs), r["residual"], g)
            if n:
                sols.append((sum(abs(a - b) for a, b in zip(cs, ours)), cs, n))
        sols.sort()
        ours_ok = any(list(cs) == ours for _, cs, _ in sols)
        tot_ok += ours_ok
        lab = " ".join(x["cat"][:5] for x in u)
        print(f"| {r['id'][-2:]} | {tuple(ours)} [{lab}] | {'yes' if ours_ok else 'NO'} | {', '.join(f'{cs} L1={l1} n={n}' for l1, cs, n in sols[:6])}{' ...' if len(sols) > 6 else ''} |")
    print(f"\nsamples whose residual has an exact band+grid solution under our counts: {tot_ok}/21")


def more_estimators(bench, rows):
    """Extra amount hypotheses that need the raw events: mean over the last 90/60 days, mean incl. image / linked rows."""
    ds = bench["ds"]
    print("\n### extra estimators (need raw rows): within 1% / 2% of 21")
    res = Counter()
    for r in rows:
        if r["capped"] or not r["unknown"]:
            continue
        rq = date.fromisoformat(r["request_date"])
        events = ds.events_by_user[r["user"]]
        prof = ds.profiles[r["user"]]
        tots = Counter()
        for u in r["unknown"]:
            cat = u["cat"]
            rows_all = [e for e in events if e.status == "settled" and e.direction == "debit" and e.category == cat and (e.settlement_date or e.event_date) <= rq]

            def hv(e):
                amt = e.amount if e.amount is not None else bench["builder"].image_amounts.get(e.event_id)
                return ds.convert(amt, e.currency, prof.home_currency, e.settlement_date or e.event_date) if amt is not None else None

            csv_rows = [e for e in rows_all if e.amount_source == "csv" and not e.linked_event_id]
            last90 = [hv(e) for e in csv_rows if (rq - (e.settlement_date or e.event_date)).days <= 90]
            last60 = [hv(e) for e in csv_rows if (rq - (e.settlement_date or e.event_date)).days <= 60]
            allv = [v for v in (hv(e) for e in rows_all) if v is not None]
            hist = [a for _, a in u["hist"]]
            tots["mean last 90 days"] += u["occ"] * (statistics.mean(last90) if last90 else u["amount"])
            tots["mean last 60 days"] += u["occ"] * (statistics.mean(last60) if last60 else u["amount"])
            tots["mean incl. image+linked rows"] += u["occ"] * statistics.mean(allv)
            tots["midrange snapped to grid"] += u["occ"] * round((max(hist) + min(hist)) / 2 / GRID[r["cur"]]) * GRID[r["cur"]]
            tots["engine x 1.01"] += u["occ"] * u["amount"] * 1.01
            tots["engine x 1.02"] += u["occ"] * u["amount"] * 1.02
            tots["mean x (1+a/n)"] += u["occ"] * statistics.mean(hist) * (1 + BAND.get(cat, 0.28) / len(hist))
        for k, v in tots.items():
            res[(k, 1)] += within(v, r["residual"], 0.01)
            res[(k, 2)] += within(v, r["residual"], 0.02)
    for k in sorted({k for k, _ in res}):
        print(f"* {k}: {res[(k, 1)]} / {res[(k, 2)]}")


if __name__ == "__main__":
    main()
