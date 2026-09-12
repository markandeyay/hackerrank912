"""Reserve model via minimum_allowed_amount (subagent 1).

Run:  .venv/Scripts/python code/notes/improve/1_reserve_leak.py [grid|table|resid|kcheck]
Does not modify the engine: subclasses StateBuilder and overrides the per-series forecast amount.

hyp keys:
  leak: True  -> variable series with minimum_allowed_amount use nominal = k(category) * minimum_allowed_amount
                 (k = dataset median of amount/min rounded to the nearest 0.5: dining/entertainment 2.0, shopping 2.5)
  est:  mean | mid | imid   (estimator for the remaining variable series; imid = midpoint of the feasible interval
                 [max/(1+a), min/(1-a)] with the per-category half-band a)
  round_mult: m -> round the estimate to the nearest m x currency unit (IDR 100, INR 10, ZAR/EUR/USD 1)
  round_feasible: True -> snap to the nearest multiple inside the feasible interval (fallback: unrounded estimate)
  zar_unit: override the ZAR unit (1 or 10)
"""
from __future__ import annotations

import importlib.util
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR))

from data import Dataset  # noqa: E402
from explain import template_explanation  # noqa: E402
from forecast import daily_balances  # noqa: E402
from pipeline import decision_row, load_adjustments, load_image_amounts  # noqa: E402
from planner import decide  # noqa: E402
from state import NON_RECURRING_CATEGORIES, NON_RECURRING_TYPES, StateBuilder  # noqa: E402

spec = importlib.util.spec_from_file_location("evalmain", CODE_DIR / "evaluation" / "main.py")
evalmain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evalmain)

COLS = evalmain.COLS
UNIT = {"IDR": 100, "INR": 10, "ZAR": 1, "EUR": 1, "USD": 1}
NORM = {"IDR": 10000, "INR": 100, "ZAR": 10, "EUR": 1, "USD": 1}
BAND = {"dining": 0.28, "groceries": 0.28, "transport": 0.28, "entertainment": 0.12, "healthcare": 0.12, "shopping": 0.12, "utilities": 0.12}


def is_constant(xs):
    return max(xs) - min(xs) < 0.005 * max(1.0, statistics.mean(xs))


def leak_multipliers(ds):
    """k(category) = median(amount / minimum_allowed_amount) over all settled debits, rounded to 0.5."""
    r = defaultdict(list)
    for e in ds.events.values():
        if e.status == "settled" and e.direction == "debit" and e.amount and e.minimum_allowed_amount:
            r[e.category].append(e.amount / e.minimum_allowed_amount)
    return {c: round(statistics.median(v) * 2) / 2 for c, v in r.items()}


class LeakBuilder(StateBuilder):
    def __init__(self, *a, hyp=None, **k):
        super().__init__(*a, **k)
        self.hyp = dict(hyp or {})
        self.k = leak_multipliers(self.ds)

    def _groups(self, st, hist, linked_targets):
        groups = defaultdict(list)
        for e in hist:
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
                continue
            if e.linked_event_id or e.event_id in linked_targets:
                continue
            sd = e.settlement_date or e.event_date
            if self.opt.get("exclude_image_rows_from_mean") and e.amount_source != "csv":
                continue
            groups[e.category].append(self.to_home(self.amount_of(e), e.currency, st.home, sd))
        return groups

    def unit(self, home):
        if home == "ZAR" and self.hyp.get("zar_unit"):
            return self.hyp["zar_unit"]
        return UNIT[home]

    def estimate_fixed(self, cat, amts, home):
        h = self.hyp
        est = h.get("est", "mean")
        if h.get("est_cats") and cat not in h["est_cats"]:
            est = "mean"
        a = BAND.get(cat, 0.28) * h.get("band_scale", 1.0)
        lo, hi = max(amts) / (1 + a), min(amts) / (1 - a)
        if est == "mean":
            x = statistics.mean(amts)
        elif est == "mid":
            x = (max(amts) + min(amts)) / 2
        elif est == "imid":
            x = (lo + hi) / 2
        else:
            raise ValueError(est)
        m = h.get("round_mult")
        if m:
            unit = m * self.unit(home)
            r = round(x / unit) * unit
            if h.get("round_feasible") and not (lo - 1e-9 <= r <= hi + 1e-9):
                cands = [c for c in (math.floor(lo / unit) * unit, math.ceil(lo / unit) * unit, math.floor(hi / unit) * unit, math.ceil(hi / unit) * unit) if lo - 1e-9 <= c <= hi + 1e-9]
                r = min(cands, key=lambda c: abs(c - x)) if cands else x
            x = r
        return x

    def _build_debit_series(self, st, hist, linked_targets, adjs):
        super()._build_debit_series(st, hist, linked_targets, adjs)
        groups = self._groups(st, hist, linked_targets)
        st.hist_groups = groups
        st.leaked = set()
        for s in st.series:
            amts = groups.get(s.category)
            if not amts or is_constant(amts):
                continue
            if self.hyp.get("leak") and s.minimum_allowed_amount and s.category in self.k:
                s.amount = self.k[s.category] * s.minimum_allowed_amount
                st.leaked.add(s.category)
            elif self.hyp.get("est", "mean") != "mean" or self.hyp.get("round_mult"):
                s.amount = self.estimate_fixed(s.category, amts, st.home)


class Bench:
    def __init__(self):
        self.ds = Dataset()
        self.reqs = self.ds.load_requests("sample_requests.csv")
        self.images = load_image_amounts(self.ds, True)
        self.adjs = load_adjustments(self.ds, True)

    def results(self, hyp=None):
        b = LeakBuilder(self.ds, self.images, self.adjs, hyp=hyp)
        out = []
        for req in self.reqs:
            st = b.build(req)
            dec = decide(st, self.ds.options_by_request.get(req.request_id, []))
            out.append((dec, decision_row(dec, template_explanation(dec))))
        return out

    def evaluate(self, hyp=None):
        rows = []
        for dec, row in self.results(hyp):
            req, prof = dec.request, dec.state.profile
            exp = req.expected
            want, got = float(exp["amount_safe_to_pay"]), float(row["amount_safe_to_pay"])
            head = prof.current_available_balance - prof.minimum_balance_to_keep
            capped = want >= req.requested_amount - 1e-6
            ref_res, our_res = head - want, head - got
            rows.append(dict(id=req.request_id, cur=prof.home_currency, got=got, want=want, req=req.requested_amount, capped=capped, ref_res=ref_res, our_res=our_res,
                             rel=(our_res - ref_res) / ref_res if not capped else None, within2=evalmain._close(str(got), str(want), 0.02), within1=evalmain._close(str(got), str(want), 0.01),
                             cols=[row[c] == exp[c] for c in COLS[1:]], norm_abs=abs(got - want) / NORM[prof.home_currency], abs_gap=abs(got - want)))
        unc = [r for r in rows if not r["capped"]]
        summ = dict(within2=sum(r["within2"] for r in rows), within1=sum(r["within1"] for r in rows), mean_rel=statistics.mean(abs(r["rel"]) for r in unc),
                    med_rel=statistics.median(abs(r["rel"]) for r in unc), bias=statistics.mean(r["rel"] for r in unc), norm_abs=sum(r["norm_abs"] for r in rows),
                    total_abs=sum(r["abs_gap"] for r in rows), cols=sum(sum(r["cols"]) for r in rows))
        return summ, rows


def fmt(name, s):
    return (f"{name:40s} w1%={s['within1']:2d} w2%={s['within2']:2d}/25 meanRel={100*s['mean_rel']:5.2f}% medRel={100*s['med_rel']:5.2f}% "
            f"bias={100*s['bias']:+6.2f}% normAbs={s['norm_abs']:7.1f} tot|gap|={s['total_abs']:12,.0f} cols={s['cols']}/125")


GRID = {
    "BASELINE (engine: mean everywhere)": {},
    "leak (k*min) + mean": {"leak": True},
    "leak + mid": {"leak": True, "est": "mid"},
    "leak + imid": {"leak": True, "est": "imid"},
    "leak + mean round 1u": {"leak": True, "round_mult": 1},
    "leak + mid round 1u": {"leak": True, "est": "mid", "round_mult": 1},
    "leak + imid round 1u": {"leak": True, "est": "imid", "round_mult": 1},
    "leak + imid round 1u feasible": {"leak": True, "est": "imid", "round_mult": 1, "round_feasible": True},
    "leak + imid round 5u feasible": {"leak": True, "est": "imid", "round_mult": 5, "round_feasible": True},
    "leak + imid round 10u feasible": {"leak": True, "est": "imid", "round_mult": 10, "round_feasible": True},
    "leak + mean round 5u": {"leak": True, "round_mult": 5},
    "leak + mean round 10u": {"leak": True, "round_mult": 10},
    "leak + mid round 5u": {"leak": True, "est": "mid", "round_mult": 5},
    "leak + mid round 10u": {"leak": True, "est": "mid", "round_mult": 10},
    "leak + imid round 5u": {"leak": True, "est": "imid", "round_mult": 5},
    "leak + imid round 10u": {"leak": True, "est": "imid", "round_mult": 10},
    "leak + imid round 50u": {"leak": True, "est": "imid", "round_mult": 50},
    "leak + imid wide-band cats only": {"leak": True, "est": "imid", "est_cats": {"groceries", "transport", "dining"}},
    "leak + imid narrow-band cats only": {"leak": True, "est": "imid", "est_cats": {"utilities", "healthcare", "entertainment", "shopping"}},
    "leak + mid wide-band cats only": {"leak": True, "est": "mid", "est_cats": {"groceries", "transport", "dining"}},
    "leak + imid band x0.9": {"leak": True, "est": "imid", "band_scale": 0.9},
    "leak + imid band x1.1": {"leak": True, "est": "imid", "band_scale": 1.1},
    "no leak: mid": {"est": "mid"},
    "no leak: imid": {"est": "imid"},
    "no leak: imid round 1u": {"est": "imid", "round_mult": 1},
    "leak + imid zar_unit=10 round 1u": {"leak": True, "est": "imid", "round_mult": 1, "zar_unit": 10},
}


def table(bench, hyps):
    res = {n: bench.evaluate(h) for n, h in hyps.items()}
    names = list(res)
    print("reserve rel. error (ours-ref)/ref; w=within2%; cols=non-amount columns matched /5")
    print(f"{'req':11s}{'cur':4s}{'ref_res':>14s} " + " ".join(f"{n[:22]:>24s}" for n in names))
    for i, base in enumerate(res[names[0]][1]):
        cells = []
        for n in names:
            r = res[n][1][i]
            rel = "   (cap)" if r["rel"] is None else f"{100*r['rel']:+7.2f}%"
            cells.append(f"{rel} {'w' if r['within2'] else '.'} {sum(r['cols'])}/5".rjust(24))
        print(f"{base['id']:11s}{base['cur']:4s}{base['ref_res']:14.2f} " + " ".join(cells))
    for n in names:
        print(fmt(n, res[n][0]))


def resid(bench, hyp):
    """Task 3: residual target for the fixed variable series vs. mean / mid / imid totals (trough from hyp run)."""
    b = LeakBuilder(bench.ds, bench.images, bench.adjs, hyp=hyp)
    tot = defaultdict(float)
    print("target = ref_res - known debits before trough + credits - constant series - leaked series ; totals of the fixed variable series under each estimator")
    print(f"{'req':11s}{'cur':4s}{'trough':11s}{'target':>13s}{'mean':>13s}{'mid':>13s}{'imid':>13s}{'imid_r1':>13s}  err% mean/mid/imid/imid_r1   fixed-variable series (occ)")
    for req in bench.reqs:
        st = b.build(req)
        prof = st.profile
        want = float(req.expected["amount_safe_to_pay"])
        if want >= req.requested_amount - 1e-6:
            continue
        head = prof.current_available_balance - prof.minimum_balance_to_keep
        ref_res = head - want
        bal = daily_balances(st)
        tmin = min(bal, key=lambda x: x[1])[0]
        fixed = sum(-f.amount for f in st.flows if f.amount < 0 and st.request_date <= f.date <= tmin)
        credits = sum(f.amount for f in st.flows if f.amount > 0 and st.request_date <= f.date <= tmin)
        target = ref_res - fixed + credits
        sums = defaultdict(float)
        desc = []
        for s in st.series:
            occ = len([d for d in s.dates if d <= tmin])
            if not occ:
                continue
            amts = st.hist_groups[s.category]
            if is_constant(amts) or s.category in st.leaked:
                target -= occ * s.amount
                continue
            a = BAND.get(s.category, 0.28)
            lo, hi = max(amts) / (1 + a), min(amts) / (1 - a)
            ests = {"mean": statistics.mean(amts), "mid": (max(amts) + min(amts)) / 2, "imid": (lo + hi) / 2}
            ests["imid_r1"] = round(ests["imid"] / UNIT[st.home]) * UNIT[st.home]
            for k, v in ests.items():
                sums[k] += occ * v
            desc.append(f"{s.category}({occ})")
        errs = " ".join(f"{100*(sums[k]-target)/target:+6.2f}" for k in ("mean", "mid", "imid", "imid_r1")) if target else "n/a"
        rels = {k: (sums[k] - target) / target for k in ("mean", "mid", "imid", "imid_r1")}
        clean = min(abs(v) for v in rels.values()) < 0.025
        for k in ("mean", "mid", "imid", "imid_r1"):
            tot[k] += abs(sums[k] - target) / NORM[st.home]
            if clean:
                tot["clean_" + k] += abs(sums[k] - target) / NORM[st.home]
                tot["cleanrel_" + k] += abs(rels[k])
                tot["n_clean"] = tot.get("n_clean", 0) + 0.25
            tot["w1_" + k] += abs(rels[k]) <= 0.01
            tot["w2_" + k] += abs(rels[k]) <= 0.02
        print(f"{req.request_id:11s}{st.home:4s}{str(tmin):11s}{target:13.2f}{sums['mean']:13.2f}{sums['mid']:13.2f}{sums['imid']:13.2f}{sums['imid_r1']:13.2f}  {errs}   {' '.join(desc)}{'' if clean else '   [structural]'}")
    print("normalised total |error| of the fixed-variable block (all 21):", {k: round(tot[k], 1) for k in ("mean", "mid", "imid", "imid_r1")})
    n = int(tot["n_clean"])
    print(f"clean subset (n={n}, best estimator within 2.5%): normAbs", {k: round(tot['clean_' + k], 1) for k in ("mean", "mid", "imid", "imid_r1")},
          "mean |rel|", {k: f"{100*tot['cleanrel_' + k]/n:.2f}%" for k in ("mean", "mid", "imid", "imid_r1")})
    print("block within 1% / 2% (of 21):", {k: f"{int(tot['w1_' + k])}/{int(tot['w2_' + k])}" for k in ("mean", "mid", "imid", "imid_r1")})


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "grid"
    bench = Bench()
    if mode == "kcheck":
        print(leak_multipliers(bench.ds))
    elif mode == "grid":
        rs = []
        for n, h in GRID.items():
            s, _ = bench.evaluate(h)
            rs.append((n, s))
            print(fmt(n, s))
        print("\n# ranked by within2, cols, total normAbs")
        for n, s in sorted(rs, key=lambda r: (-r[1]["within2"], -r[1]["cols"], r[1]["norm_abs"])):
            print(fmt(n, s))
    elif mode == "table":
        keys = sys.argv[2:] or ["BASELINE (engine: mean everywhere)", "leak (k*min) + mean", "leak + imid", "leak + imid round 1u"]
        table(bench, {k: GRID[k] for k in keys})
    elif mode == "resid":
        resid(bench, {"leak": True})
