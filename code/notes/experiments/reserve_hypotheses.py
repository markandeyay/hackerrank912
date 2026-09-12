"""Scratch harness: test reserve hypotheses for amount_safe_to_pay on the 25 samples.

Run:  .venv/Scripts/python code/notes/experiments/reserve_hypotheses.py [dump|grid|top|split]
Does not modify the engine; subclasses StateBuilder and re-implements
_build_debit_series with pluggable estimator / rounding / scheduling hooks.
"""
from __future__ import annotations

import math
import statistics
import sys
from collections import defaultdict
from datetime import timedelta
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR))

from data import Dataset  # noqa: E402
from forecast import amount_safe_to_pay, daily_balances  # noqa: E402
from pipeline import load_adjustments, load_image_amounts, decision_row  # noqa: E402
from planner import decide  # noqa: E402
from explain import template_explanation  # noqa: E402
from state import NON_RECURRING_CATEGORIES, NON_RECURRING_TYPES, Series, StateBuilder, add_months  # noqa: E402
COLS = ["amount_safe_to_pay", "affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed"]


def _close(a, b, tol):
    try:
        x, y = float(a), float(b)
    except ValueError:
        return a == b
    return abs(x - y) <= tol * max(1.0, abs(y))


# ---------------------------------------------------------------- estimators
def p75(xs):
    s = sorted(xs)
    k = 0.75 * (len(s) - 1)
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


ESTIMATORS = {
    "mean": statistics.mean,
    "median": statistics.median,
    "max": max,
    "min": min,
    "last": lambda xs: xs[-1],
    "first": lambda xs: xs[0],
    "last3": lambda xs: statistics.mean(xs[-3:]),
    "p75": p75,
    "mode": lambda xs: statistics.multimode([round(x, 2) for x in xs])[0],
    "mean_std": lambda xs: statistics.mean(xs) + (statistics.pstdev(xs) if len(xs) > 1 else 0),
    "trim_mean": lambda xs: statistics.mean(sorted(xs)[1:-1]) if len(xs) > 3 else statistics.mean(xs),
    "mid": lambda xs: (max(xs) + min(xs)) / 2,
}


def is_constant(xs):
    return max(xs) - min(xs) < 0.005 * max(1.0, statistics.mean(xs))


# ---------------------------------------------------------------- rounding
def round_to(x, unit, mode):
    if not unit:
        return x
    if mode == "nearest":
        return round(x / unit) * unit
    if mode == "up":
        return math.ceil(x / unit - 1e-9) * unit
    if mode == "down":
        return math.floor(x / unit + 1e-9) * unit
    raise ValueError(mode)


def sig_round(x, nsig, mode):
    if x <= 0:
        return x
    mag = 10 ** (math.floor(math.log10(x)) - (nsig - 1))
    return round_to(x, mag, mode)


CUR_SCALE = {"IDR": 10000, "INR": 100, "ZAR": 10, "EUR": 1, "USD": 1}


# ---------------------------------------------------------------- builder
class HypBuilder(StateBuilder):
    """StateBuilder with hooks. hyp keys:
    est: estimator name (all series) | est_var / est_const: split by variability
    round_unit: absolute unit | round_sig: n significant figures | round_scaled: unit multiplier of CUR_SCALE
    round_mode: nearest|up|down ; round_only_var: only round variable (non-constant) series
    scale: multiply variable estimates by this factor
    schedule: cadence (default) | monthly30 (every 30 days from last) | monthly_dom (monthly on DOM for all)
    last_month_sum: use total of last complete calendar month as monthly amount on DOM
    """

    def __init__(self, *a, hyp=None, **k):
        super().__init__(*a, **k)
        self.hyp = dict(hyp or {})

    def estimate(self, cat, amts, dates, rq, home):
        h = self.hyp
        const = is_constant(amts)
        name = h.get("est_const" if const else "est_var") or h.get("est") or self.opt.get("estimator", "mean")
        if h.get("last_month_sum") and not const:
            first_of_this = rq.replace(day=1)
            last_month_end = first_of_this - timedelta(days=1)
            lm_start = last_month_end.replace(day=1)
            tot = sum(a for a, d in zip(amts, dates) if lm_start <= d <= last_month_end)
            amount = tot if tot > 0 else ESTIMATORS[name](amts)
        else:
            amount = ESTIMATORS[name](amts)
        if not const and h.get("scale"):
            amount *= h["scale"]
        if h.get("round_only_var") and const:
            return amount
        mode = h.get("round_mode", "nearest")
        if h.get("round_sig"):
            amount = sig_round(amount, h["round_sig"], mode)
        elif h.get("round_scaled"):
            amount = round_to(amount, h["round_scaled"] * CUR_SCALE[home], mode)
        elif h.get("round_unit"):
            amount = round_to(amount, h["round_unit"], mode)
        return amount

    def build(self, req):
        st = super().build(req)
        h = self.hyp
        shift = int(h.get("salary_shift") or 0)
        if shift:
            for f in st.flows:
                if f.kind in ("salary", "income"):
                    f.date = f.date + timedelta(days=shift)
            st.salary_dates = sorted(d + timedelta(days=shift) for d in st.salary_dates)
        win = h.get("payday_var_before")  # int: variable-series occurrences on payday..payday+win-1 are applied before the salary
        if win and st.salary_dates:
            for s in st.series:
                if h.get("payday_all") or not is_constant(st.hist_groups[s.category][1]):
                    if h.get("payday_periodic_only") and s.cadence != "periodic":
                        continue
                    new = []
                    for d in s.dates:
                        hit = [p for p in st.salary_dates if p <= d < p + timedelta(days=win)]
                        new.append(hit[0] - timedelta(days=1) if hit else d)
                    s.dates = new
        return st

    def _build_debit_series(self, st, hist, linked_targets, adjs):
        rq, end, home = st.request_date, st.horizon_end, st.home
        h = self.hyp
        groups = defaultdict(list)
        for e in hist:
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
                continue
            if e.linked_event_id or e.event_id in linked_targets:
                continue
            sd = e.settlement_date or e.event_date
            if self.opt.get("exclude_image_rows_from_mean") and e.amount_source != "csv":
                continue
            groups[e.category].append((sd, self.to_home(self.amount_of(e), e.currency, home, sd), e))
        rent_pct = 0.0
        for a in adjs:
            if a["adjustment_type"] == "expense_increase_percent" and a.get("percent"):
                rent_pct = max(rent_pct, float(a["percent"]))
        st.hist_groups = {}
        for cat, rows in groups.items():
            rows.sort(key=lambda r: r[0])
            if len(rows) < 3:
                continue
            dates = [r[0] for r in rows]
            amts = [r[1] for r in rows]
            gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            per = statistics.median(gaps)
            if per > 45:
                continue
            st.hist_groups[cat] = (dates, amts)
            amount = self.estimate(cat, amts, dates, rq, home)
            if cat == "rent" and rent_pct:
                amount *= 1 + rent_pct / 100.0
            latest = rows[-1][2]
            proj = []
            sched = h.get("schedule", "cadence")
            monthly_like = per >= 28 or sched in ("monthly30", "monthly_dom") or (h.get("last_month_sum") and not is_constant(amts))
            if monthly_like:
                if (sched == "monthly30" and per < 28) or (sched == "monthly_last30" and per >= 28):
                    cadence, step = "periodic", 30
                    t = dates[-1] + timedelta(days=30)
                    while t <= rq:
                        t += timedelta(days=30)
                    while t <= end:
                        proj.append(t)
                        t += timedelta(days=30)
                else:
                    cadence, step = "monthly", 30
                    t = add_months(dates[-1], 1)
                    while t < rq:
                        t = add_months(t, 1)
                    while t <= end:
                        proj.append(t)
                        t = add_months(t, 1)
            else:
                cadence, step = "periodic", max(1, int(round(per)))
                t = dates[-1] + timedelta(days=step)
                if self.opt.get("periodic_skip_request_date", True):
                    while t <= rq:
                        t += timedelta(days=step)
                else:
                    while t < rq:
                        t += timedelta(days=step)
                while t <= end:
                    proj.append(t)
                    t += timedelta(days=step)
                cap = int(self.opt.get("periodic_max_per_cycle") or 0)
                if cap and st.salary_dates:
                    bounds = sorted(set(st.salary_dates))
                    kept = []
                    lo = rq - timedelta(days=1)
                    for hi in bounds + [end + timedelta(days=1)]:
                        seg = [d for d in proj if lo < d <= hi]
                        kept.extend(seg[:cap])
                        lo = hi
                    proj = sorted(set(kept))
            st.series.append(Series(cat, latest.description, amount, cadence, step, proj, latest.flexibility, latest.event_id, latest.minimum_allowed_amount, len(rows)))


# ---------------------------------------------------------------- evaluation
class Bench:
    def __init__(self):
        self.ds = Dataset()
        self.reqs = self.ds.load_requests("sample_requests.csv")
        self.images = load_image_amounts(self.ds, True)
        self.adjs = load_adjustments(self.ds, True)

    def states(self, hyp=None, options=None, horizon=84):
        b = HypBuilder(self.ds, self.images, self.adjs, horizon_days=horizon, options=options, hyp=hyp)
        return [(r, b.build(r)) for r in self.reqs]

    def evaluate(self, hyp=None, options=None, full=False):
        rows = []
        for req, st in self.states(hyp, options):
            prof = st.profile
            exp = req.expected
            want = float(exp["amount_safe_to_pay"])
            head = prof.current_available_balance - prof.minimum_balance_to_keep
            if full:
                dec = decide(st, self.ds.options_by_request.get(req.request_id, []))
                row = decision_row(dec, template_explanation(dec))
                safe = float(row["amount_safe_to_pay"])
                nmatch = sum(1 for c in COLS[1:] if row[c] == exp[c])
            else:
                safe = amount_safe_to_pay(st, req.requested_amount)
                nmatch = None
            capped = want >= req.requested_amount - 1e-6
            ref_res = head - want
            our_res = head - safe
            rows.append(dict(id=req.request_id, cur=prof.home_currency, got=safe, want=want, req=req.requested_amount, capped=capped, ref_res=ref_res, our_res=our_res,
                             rel=(our_res - ref_res) / ref_res if not capped else None, within2=_close(str(safe), str(want), 0.02), nmatch=nmatch,
                             norm_abs=abs(safe - want) / CUR_SCALE[prof.home_currency]))
        unc = [r for r in rows if not r["capped"]]
        summ = dict(within2=sum(r["within2"] for r in rows), mean_rel=statistics.mean(abs(r["rel"]) for r in unc), med_rel=statistics.median(abs(r["rel"]) for r in unc),
                    bias=statistics.mean(r["rel"] for r in unc), norm_abs=sum(r["norm_abs"] for r in rows), gap_req=sum(abs(r["got"] - r["want"]) / r["req"] for r in rows) / len(rows),
                    nmatch=(sum(r["nmatch"] for r in rows) if full else None))
        return summ, rows


def fmt_summ(name, s):
    nm = f" cols={s["nmatch"]}/125" if s.get("nmatch") is not None else ""
    return f"{name:52s} w2%={s['within2']:2d}/25 meanRel={100*s['mean_rel']:5.2f}% medRel={100*s['med_rel']:5.2f}% bias={100*s['bias']:+6.2f}% normAbs={s['norm_abs']:8.1f} gap/req={100*s['gap_req']:5.2f}%{nm}"


def dump(bench):
    """Per-sample: fixed known items before the trough vs. series; residual split."""
    for req, st in bench.states():
        prof = st.profile
        exp = req.expected
        want = float(exp["amount_safe_to_pay"])
        head = prof.current_available_balance - prof.minimum_balance_to_keep
        ref_res = head - want
        bal = daily_balances(st)
        tmin = min(bal, key=lambda x: x[1])[0]
        fixed = sum(-f.amount for f in st.flows if f.amount < 0 and st.request_date <= f.date <= tmin)
        credits = sum(f.amount for f in st.flows if f.amount > 0 and st.request_date <= f.date <= tmin)
        capped = want >= req.requested_amount - 1e-6
        print(f"== {req.request_id} {prof.home_currency} rq={st.request_date} trough={tmin} salary={st.salary_dates[:2]} head={head:.2f} ref_res={ref_res:.2f} ours={head-amount_safe_to_pay(st, req.requested_amount):.2f} fixed_before_trough={fixed:.2f} credits={credits:.2f} {'CAPPED' if capped else ''}")
        resid = ref_res - fixed + credits
        var_total = 0.0
        for s in st.series:
            occ = [d for d in s.dates if d <= tmin]
            dts, amts = st.hist_groups[s.category]
            c = "C" if is_constant(amts) else "V"
            if not occ:
                print(f"   ({s.category:12s} {c} next={s.dates[0] if s.dates else None} not before trough)")
                continue
            print(f"   {s.category:14s} {c} n={len(amts):2d} step={s.step_days:2d} occ={len(occ)} {[str(d) for d in occ]} mean={statistics.mean(amts):12.2f} med={statistics.median(amts):12.2f} max={max(amts):12.2f} last={amts[-1]:12.2f} first={amts[0]:12.2f} hist={[round(a,2) for a in amts]}")
            if c == "C":
                resid -= len(occ) * s.amount
            else:
                var_total += len(occ) * s.amount
        print(f"   residual for variable series = {resid:.2f} ; our variable total (mean) = {var_total:.2f} ; ratio = {resid/var_total if var_total else float('nan'):.4f}")


def grid(bench):
    results = []

    def run(name, hyp=None, options=None):
        s, rows = bench.evaluate(hyp, options)
        results.append((name, s, hyp, options))
        print(fmt_summ(name, s))

    run("BASELINE mean/cadence/salary-first")
    print("\n# 2. estimators")
    for e in ESTIMATORS:
        run(f"est={e}", {"est": e})
    for ev in ESTIMATORS:
        if ev != "mean":
            run(f"est_var={ev} est_const=mean", {"est_var": ev, "est_const": "mean"})
    for sc in (0.95, 1.05, 1.10, 1.15, 1.20):
        run(f"mean*{sc} (variable only)", {"scale": sc})

    print("\n# 1. rounding (mean)")
    for unit in (10, 50, 100, 500, 1000):
        for mode in ("nearest", "up"):
            run(f"round_unit={unit} {mode}", {"round_unit": unit, "round_mode": mode})
    for k in (1, 5, 10, 50):
        for mode in ("nearest", "up", "down"):
            run(f"round_scaled={k}xCUR {mode}", {"round_scaled": k, "round_mode": mode})
            run(f"round_scaled={k}xCUR {mode} var-only", {"round_scaled": k, "round_mode": mode, "round_only_var": True})
    for n in (1, 2, 3):
        for mode in ("nearest", "up", "down"):
            run(f"round_sig={n} {mode}", {"round_sig": n, "round_mode": mode})
            run(f"round_sig={n} {mode} var-only", {"round_sig": n, "round_mode": mode, "round_only_var": True})

    print("\n# 3. last-full-month sum")
    run("last_month_sum (monthly on DOM)", {"last_month_sum": True})

    print("\n# 4. scheduling")
    run("schedule=monthly30 (all every 30d from last)", {"schedule": "monthly30"})
    run("schedule=monthly_dom (all monthly on DOM)", {"schedule": "monthly_dom"})
    run("periodic_max_per_cycle=1", None, {"periodic_max_per_cycle": 1})
    run("periodic_max_per_cycle=2", None, {"periodic_max_per_cycle": 2})
    run("periodic_skip_request_date=False", None, {"periodic_skip_request_date": False})
    run("include image rows in mean", None, {"exclude_image_rows_from_mean": False})

    print("\n# 5. salary-day ordering")
    run("debit_first=True", None, {"debit_first": True})

    print("\n# combos")
    for ev in ("median", "p75", "max", "last3", "mid"):
        run(f"est_var={ev} + debit_first", {"est_var": ev, "est_const": "mean"}, {"debit_first": True})
        run(f"est_var={ev} + skip_rq=False", {"est_var": ev, "est_const": "mean"}, {"periodic_skip_request_date": False})
    for mode in ("up", "nearest"):
        for n in (2, 3):
            run(f"round_sig={n} {mode} + debit_first", {"round_sig": n, "round_mode": mode}, {"debit_first": True})
            run(f"round_sig={n} {mode} + skip_rq=False", {"round_sig": n, "round_mode": mode}, {"periodic_skip_request_date": False})
    run("est_var=p75 round_sig=2 up", {"est_var": "p75", "est_const": "mean", "round_sig": 2, "round_mode": "up"})
    run("est_var=median round_sig=2 nearest", {"est_var": "median", "est_const": "mean", "round_sig": 2})
    run("mean*1.10 + skip_rq=False", {"scale": 1.10}, {"periodic_skip_request_date": False})
    run("mean*1.10 + debit_first", {"scale": 1.10}, {"debit_first": True})
    run("max_per_cycle=1 + debit_first", None, {"periodic_max_per_cycle": 1, "debit_first": True})
    print("\n# 6. structural (payday handling)")
    run("salary_shift=+1 (salary lands a day late)", {"salary_shift": 1})
    run("salary_shift=+2", {"salary_shift": 2})
    run("payday_var_before=1 (variable items on payday before salary)", {"payday_var_before": 1})
    run("payday_var_before=2 (payday and next day)", {"payday_var_before": 2})
    run("payday_var_before=1 periodic only", {"payday_var_before": 1, "payday_periodic_only": True})
    run("payday_var_before=2 periodic only", {"payday_var_before": 2, "payday_periodic_only": True})
    run("payday_all_before=1 (== debit_first)", {"payday_var_before": 1, "payday_all": True})
    run("schedule=monthly_last30 (monthly = last+30d)", {"schedule": "monthly_last30"})
    run("monthly_last30 + payday_var_before=1", {"schedule": "monthly_last30", "payday_var_before": 1})
    results.sort(key=lambda r: (-r[1]["within2"], r[1]["mean_rel"]))
    print("\n# ranked (top 20 by within2%, then mean rel)")
    for name, s, hyp, opt in results[:20]:
        print(fmt_summ(name, s))
    return results


def show_rows(bench, name, hyp=None, options=None):
    s, rows = bench.evaluate(hyp, options, full=True)
    print("\n### " + name)
    print(fmt_summ(name, s))
    print(f"{'req':11s} {'cur':3s} {'got':>14s} {'want':>14s} {'ref_res':>13s} {'our_res':>13s} {'relRes':>8s} w2 cols")
    for r in rows:
        rel = f"{100*r['rel']:+7.2f}%" if r["rel"] is not None else "  (cap) "
        print(f"{r['id']:11s} {r['cur']:3s} {r['got']:14.2f} {r['want']:14.2f} {r['ref_res']:13.2f} {r['our_res']:13.2f} {rel} {'Y' if r['within2'] else '.'}  {r['nmatch']}/4")
    return s, rows


TOP = {
    "baseline mean/cadence/salary-first": (None, None),
    "round_scaled=5xCUR nearest": ({"round_scaled": 5, "round_mode": "nearest"}, None),
    "est_var=mid + debit_first": ({"est_var": "mid", "est_const": "mean"}, {"debit_first": True}),
    "payday_var_before=1": ({"payday_var_before": 1}, None),
    "payday_var_before=2": ({"payday_var_before": 2}, None),
    "payday_var_before=1 periodic only": ({"payday_var_before": 1, "payday_periodic_only": True}, None),
    "payday_var_before=2 periodic only": ({"payday_var_before": 2, "payday_periodic_only": True}, None),
    "mean*1.05 (variable only)": ({"scale": 1.05}, None),
    "debit_first=True": (None, {"debit_first": True}),
}

if __name__ == "__main__":
    bench = Bench()
    mode = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if mode == "dump":
        dump(bench)
    elif mode == "grid":
        grid(bench)
    elif mode == "top":
        for name, (hyp, opt) in TOP.items():
            show_rows(bench, name, hyp, opt)
