"""Noise-band calibration (improve2 / subagent 1).

Run:  .venv/Scripts/python code/notes/improve2/1_noise_band.py [band|fixed|est|all]
Engine untouched: subclasses StateBuilder and re-estimates only the NON-leaked variable series.
Deterministic evidence path only (use_llm=False), as the caches are being rebuilt concurrently.

band  : task 1 - r = observed / (k x minimum) on every leaked series; bounds, symmetry, uniformity, per category x currency
fixed : task 3 - per-series (max-min)/(max+min) of fixed variable categories -> implied half-width a, vs the leaked categories
est   : task 2 - estimators for the fixed variable block, full scorer on the 25 samples (six-column exact count)
"""
from __future__ import annotations

import importlib.util
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR))

from data import Dataset  # noqa: E402
from explain import template_explanation  # noqa: E402
from pipeline import decision_row, load_adjustments, load_image_amounts  # noqa: E402
from planner import decide  # noqa: E402
from state import NON_RECURRING_CATEGORIES, NON_RECURRING_TYPES, StateBuilder  # noqa: E402

spec = importlib.util.spec_from_file_location("evalmain", CODE_DIR / "evaluation" / "main.py")
evalmain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evalmain)
COLS = evalmain.COLS

GRID = {"IDR": 100.0, "INR": 10.0, "ZAR": 0.2, "EUR": 1.0, "USD": 1.0}  # grid of the leaked nominals (verified in `band`)
NORM = {"IDR": 10000, "INR": 100, "ZAR": 10, "EUR": 1, "USD": 1}
# clean half-bands hypothesised by the previous pass
BAND = {"dining": 0.28, "groceries": 0.28, "transport": 0.28, "entertainment": 0.12, "healthcare": 0.12, "shopping": 0.12, "utilities": 0.12}


# ------------------------------------------------------------------ stats helpers (no scipy in the venv)
def ks_uniform(xs, lo, hi):
    """Two-sided KS statistic and asymptotic p-value of xs against U[lo, hi]."""
    n = len(xs)
    s = sorted(xs)
    d = 0.0
    for i, x in enumerate(s):
        f = min(1.0, max(0.0, (x - lo) / (hi - lo)))
        d = max(d, abs((i + 1) / n - f), abs(f - i / n))
    lam = d * (math.sqrt(n) + 0.12 + 0.11 / math.sqrt(n))
    p = 2 * sum((-1) ** (k - 1) * math.exp(-2 * k * k * lam * lam) for k in range(1, 200))
    return d, min(1.0, max(0.0, p))


def _gammainc_upper(a, x):
    """Regularised upper incomplete gamma Q(a, x) (Numerical Recipes gser/gcf)."""
    if x <= 0:
        return 1.0
    if x < a + 1:
        ap, s, d = a, 1.0 / a, 1.0 / a
        for _ in range(500):
            ap += 1
            d *= x / ap
            s += d
            if abs(d) < abs(s) * 1e-14:
                break
        return 1.0 - s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    b, c, d = x + 1 - a, 1e300, 1.0 / (x + 1 - a)
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1e-300 if abs(d) < 1e-300 else d
        c = b + an / c
        c = 1e-300 if abs(c) < 1e-300 else c
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1) < 1e-14:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def chi2_uniform(xs, lo, hi, bins=10):
    n = len(xs)
    cnt = [0] * bins
    for x in xs:
        i = min(bins - 1, max(0, int((x - lo) / (hi - lo) * bins)))
        cnt[i] += 1
    e = n / bins
    stat = sum((c - e) ** 2 / e for c in cnt)
    return stat, _gammainc_upper((bins - 1) / 2, stat / 2), cnt


def skewness(xs):
    m = statistics.mean(xs)
    sd = statistics.pstdev(xs)
    return sum((x - m) ** 3 for x in xs) / len(xs) / sd**3 if sd else 0.0


def nearest_clean(v):
    """Nearest 'clean' band edge (multiple of 0.01) and its distance."""
    c = round(v, 2)
    return c, v - c


def leak_multipliers(ds):
    r = defaultdict(list)
    for e in ds.events.values():
        if e.status == "settled" and e.direction == "debit" and e.amount and e.minimum_allowed_amount:
            r[e.category].append(e.amount / e.minimum_allowed_amount)
    return {c: round(statistics.median(v) * 2) / 2 for c, v in r.items() if len(v) >= 5}


def series_rows(ds):
    """(user, category) -> list of settled csv debit rows that the engine would put in a series (same filters as state.py)."""
    out = defaultdict(list)
    for uid, events in ds.events_by_user.items():
        linked_targets = {e.linked_event_id for e in events if e.linked_event_id}
        for e in events:
            if e.status != "settled" or e.direction != "debit" or e.amount is None:
                continue
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
                continue
            if e.linked_event_id or e.event_id in linked_targets or e.amount_source != "csv":
                continue
            out[(uid, e.category)].append(e)
    return out


def is_constant(xs):
    return max(xs) - min(xs) < 0.005 * max(1.0, statistics.mean(xs))


def on_grid(v, g):
    q = v / g
    return abs(q - round(q)) < 1e-6


# ------------------------------------------------------------------ task 1
def band(ds):
    k = leak_multipliers(ds)
    print("k per category (dataset median of amount/min rounded to 0.5):", k)
    rows = series_rows(ds)
    r_by = defaultdict(list)  # (category, currency) -> r values
    grid_hits = defaultdict(Counter)
    nominal_examples = defaultdict(list)
    cur_mismatch = 0
    for (uid, cat), evs in rows.items():
        mins = {e.minimum_allowed_amount for e in evs}
        if len(mins) != 1 or None in mins or cat not in k:
            continue
        m = mins.pop()
        cur = {e.currency for e in evs}
        home = ds.profiles[uid].home_currency
        if cur != {home}:
            cur_mismatch += 1
        nominal = k[cat] * m
        c = evs[0].currency
        grid_hits[c][on_grid(nominal, GRID[c])] += 1
        if len(nominal_examples[c]) < 6:
            nominal_examples[c].append(nominal)
        for e in evs:
            r_by[(cat, c)].append(e.amount / nominal)
    print(f"leaked series with event currency != home currency: {cur_mismatch}")
    print("nominal (k x min) on the currency grid?", {c: dict(v) for c, v in grid_hits.items()}, "examples:", {c: v for c, v in nominal_examples.items()})
    print()
    hdr = f"{'category':14s}{'cur':5s}{'n':>6s}{'min r':>9s}{'max r':>9s}{'clean lo/hi':>14s}{'mean r':>9s}{'skew':>8s}{'a_hat':>8s}{'KS D':>8s}{'KS p (clean)':>13s}{'KS p (fit)':>11s}{'chi2 p':>8s}"
    print(hdr)
    per_cat = defaultdict(list)
    table = []
    for (cat, c), xs in sorted(r_by.items()):
        per_cat[cat].extend(xs)
        table.append(((cat, c), xs))
    for cat, xs in per_cat.items():
        table.append(((cat, "ALL"), xs))
    for (cat, c), xs in table:
        lo, hi = min(xs), max(xs)
        clo, dlo = nearest_clean(lo)
        chi, dhi = nearest_clean(hi)
        n = len(xs)
        if hi - lo < 1e-6:  # constant categories (gym, streaming)
            print(f"{cat:14s}{c:5s}{n:6d}{lo:9.4f}{hi:9.4f}{'constant':>14s}{statistics.mean(xs):9.4f}")
            continue
        # unbiased half-width from the sample range: E[range] = 2a (n-1)/(n+1)
        a_hat = (hi - lo) / 2 * (n + 1) / (n - 1)
        d1, p1 = ks_uniform(xs, clo, chi)
        d2, p2 = ks_uniform(xs, lo, hi)
        cs, cp, cnt = chi2_uniform(xs, clo, chi)
        lab = f"{clo:.2f}/{chi:.2f}"
        print(f"{cat:14s}{c:5s}{n:6d}{lo:9.4f}{hi:9.4f}{lab:>14s}{statistics.mean(xs):9.4f}{skewness(xs):8.3f}{a_hat:8.4f}{d1:8.4f}{p1:13.3f}{p2:11.3f}{cp:8.3f}")
    print("\nhistograms of r (0.02-wide bins over the clean band), per category (all currencies):")
    for cat, xs in per_cat.items():
        if max(xs) - min(xs) < 1e-6:
            continue
        clo, _ = nearest_clean(min(xs))
        chi, _ = nearest_clean(max(xs))
        nb = int(round((chi - clo) / 0.02))
        _, _, cnt = chi2_uniform(xs, clo, chi, nb)
        print(f"  {cat:14s} [{clo:.2f},{chi:.2f}] {cnt}")
    print("\nexpected gap between sample extreme and true edge = width/(n+1):")
    for cat, xs in per_cat.items():
        if max(xs) - min(xs) < 1e-6:
            continue
        w = round(max(xs), 2) - round(min(xs), 2)
        print(f"  {cat:14s} n={len(xs):5d} expected {w/(len(xs)+1):.5f}  observed lo-gap {min(xs)-round(min(xs),2):+.5f}  hi-gap {round(max(xs),2)-max(xs):+.5f}")


# ------------------------------------------------------------------ task 3
def fixed(ds):
    k = leak_multipliers(ds)
    rows = series_rows(ds)
    stat = defaultdict(list)  # (category, leaked?) -> per-series (s, n, a_hat)
    for (uid, cat), evs in rows.items():
        amts = [e.amount for e in evs]
        if len(amts) < 3 or is_constant(amts):
            continue
        mins = {e.minimum_allowed_amount for e in evs}
        leaked = len(mins) == 1 and None not in mins and cat in k
        s = (max(amts) - min(amts)) / (max(amts) + min(amts))
        n = len(amts)
        stat[(cat, leaked)].append((s, n, s * (n + 1) / (n - 1)))
    print(f"{'category':14s}{'leaked':8s}{'series':>7s}{'n/series':>9s}{'max s':>8s}{'mean s':>8s}{'mean a_hat':>11s}{'median a_hat':>13s}{'implied a':>10s}")
    for (cat, leaked), v in sorted(stat.items()):
        ss = [x[0] for x in v]
        ah = [x[2] for x in v]
        ns = [x[1] for x in v]
        print(f"{cat:14s}{'yes' if leaked else 'no':8s}{len(v):7d}{statistics.mean(ns):9.1f}{max(ss):8.4f}{statistics.mean(ss):8.4f}{statistics.mean(ah):11.4f}{statistics.median(ah):13.4f}{round(statistics.mean(ah)*50)/50:10.2f}")
    print("(s = (max-min)/(max+min) per series; a_hat = s (n+1)/(n-1) is unbiased for the half-width under uniform noise; 'implied a' = mean a_hat rounded to 0.02)")


# ------------------------------------------------------------------ task 2
class EstBuilder(StateBuilder):
    """Re-estimates the non-leaked variable series after the engine has built them."""

    def __init__(self, *a, hyp=None, **kw):
        super().__init__(*a, **kw)
        self.hyp = dict(hyp or {})
        self.stats = Counter()

    def _build_debit_series(self, st, hist, linked_targets, adjs):
        super()._build_debit_series(st, hist, linked_targets, adjs)
        groups = defaultdict(list)
        for e in hist:
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
                continue
            if e.linked_event_id or e.event_id in linked_targets:
                continue
            if self.opt.get("exclude_image_rows_from_mean") and e.amount_source != "csv":
                continue
            sd = e.settlement_date or e.event_date
            groups[e.category].append((self.to_home(self.amount_of(e), e.currency, st.home, sd), e))
        for s in st.series:
            rows = groups.get(s.category)
            if not rows:
                continue
            amts = [r[0] for r in rows]
            if is_constant(amts):
                continue
            latest_min = rows[-1][1].minimum_allowed_amount
            if latest_min and s.category in self.min_factor and all(r[1].minimum_allowed_amount == latest_min for r in rows):
                continue  # leaked series: engine already uses k x min
            only = self.hyp.get("only_cats")
            if not only or s.category in only:
                s.amount = self.estimate(s.category, amts, st.home)

    def estimate(self, cat, amts, home):
        h = self.hyp
        est = h.get("est", "mean")
        a = h.get("band", BAND).get(cat, 0.28)
        L, U = max(amts) / (1 + a), min(amts) / (1 - a)
        n = len(amts)
        mean = statistics.mean(amts)
        if est == "mean":
            return mean
        if est == "mid":
            return (max(amts) + min(amts)) / 2
        if L > U:  # band too narrow for this series: fall back
            self.stats["infeasible"] += 1
            return mean
        if est == "imid":
            x = (L + U) / 2
        elif est == "mle":  # likelihood (2 a n)^-N is maximal at the lower feasible endpoint
            x = L
        elif est == "pmean":  # posterior mean under a flat prior on the feasible interval, density ~ n^-N
            if n == 1:
                x = (L + U) / 2
            elif n == 2:
                x = (U - L) / math.log(U / L)
            else:
                x = ((U ** (2 - n) - L ** (2 - n)) / (2 - n)) / ((U ** (1 - n) - L ** (1 - n)) / (1 - n))
        elif est in ("snap", "snap_mean"):
            g = GRID[home]
            base = (L + U) / 2 if est == "snap" else mean
            cands = []
            c = math.ceil(L / g - 1e-9) * g
            while c <= U + 1e-9:
                cands.append(c)
                c += g
            self.stats[f"grid_pts_{min(len(cands), 3)}"] += 1
            x = base if not cands else min(cands, key=lambda v: abs(v - base))
        else:
            raise ValueError(est)
        return x


class Bench:
    def __init__(self):
        self.ds = Dataset()
        self.reqs = self.ds.load_requests("sample_requests.csv")
        self.images = load_image_amounts(self.ds, False)
        self.adjs = load_adjustments(self.ds, False)

    def evaluate(self, hyp=None):
        b = EstBuilder(self.ds, self.images, self.adjs, hyp=hyp)
        rows = []
        for req in self.reqs:
            st = b.build(req)
            dec = decide(st, self.ds.options_by_request.get(req.request_id, []))
            row = decision_row(dec, template_explanation(dec))
            exp = req.expected
            want, got = float(exp["amount_safe_to_pay"]), float(row["amount_safe_to_pay"])
            prof = st.profile
            head = prof.current_available_balance - prof.minimum_balance_to_keep
            capped = want >= req.requested_amount - 1e-6
            rows.append(dict(id=req.request_id, cur=prof.home_currency, got=got, want=want, capped=capped, ref_res=head - want,
                             rel=None if capped else (want - got) / (head - want),
                             within2=evalmain._close(str(got), str(want), 0.02), within1=evalmain._close(str(got), str(want), 0.01),
                             cols={c: row[c] == exp[c] for c in COLS}, norm_abs=abs(got - want) / NORM[prof.home_currency], abs_gap=abs(got - want)))
        unc = [r for r in rows if not r["capped"]]
        summ = dict(within2=sum(r["within2"] for r in rows), within1=sum(r["within1"] for r in rows), mean_rel=statistics.mean(abs(r["rel"]) for r in unc),
                    med_rel=statistics.median(abs(r["rel"]) for r in unc), norm_abs=sum(r["norm_abs"] for r in rows), total_abs=sum(r["abs_gap"] for r in rows),
                    cols=sum(sum(r["cols"].values()) for r in rows), stats=dict(b.stats))
        return summ, rows


HYPS = {
    "mean (engine)": {},
    "midrange": {"est": "mid"},
    "imid a=.28/.12": {"est": "imid"},
    "mle (lower endpoint)": {"est": "mle"},
    "posterior mean": {"est": "pmean"},
    "snap imid->grid": {"est": "snap"},
    "snap mean->grid": {"est": "snap_mean"},
    "imid wide cats only": {"est": "imid", "only_cats": {"groceries", "transport", "dining"}},
    "imid narrow cats only": {"est": "imid", "only_cats": {"utilities", "healthcare", "entertainment", "shopping"}},
}


def fmt(name, s):
    return (f"{name:24s} w1%={s['within1']:2d} w2%={s['within2']:2d}/25 meanRel={100*s['mean_rel']:5.2f}% medRel={100*s['med_rel']:5.2f}% "
            f"normAbs={s['norm_abs']:7.1f} tot|gap|={s['total_abs']:12,.0f} cols={s['cols']}/150 {s['stats']}")


def est(bench, hyps=None):
    hyps = hyps or HYPS
    res = {n: bench.evaluate(h) for n, h in hyps.items()}
    names = list(res)
    base = res[names[0]][1]
    print("amount rel. error (want-got)/ref_reserve; w=within2%; k/6 columns exact")
    print(f"{'req':11s}{'cur':4s}" + "".join(f"{n[:20]:>22s}" for n in names))
    for i, b in enumerate(base):
        cells = []
        for n in names:
            r = res[n][1][i]
            rel = " (cap)" if r["rel"] is None else f"{100*r['rel']:+6.2f}%"
            cells.append(f"{rel} {'w' if r['within2'] else '.'} {sum(r['cols'].values())}/6".rjust(22))
        print(f"{b['id']:11s}{b['cur']:4s}" + "".join(cells))
    print()
    for n in names:
        print(fmt(n, res[n][0]))
    print("\ncolumns lost / gained vs", names[0])
    for n in names[1:]:
        lost, gained = [], []
        for b, r in zip(base, res[n][1]):
            for c in COLS:
                if b["cols"][c] and not r["cols"][c]:
                    lost.append(f"{b['id']}:{c}")
                if r["cols"][c] and not b["cols"][c]:
                    gained.append(f"{b['id']}:{c}")
        print(f"  {n:24s} lost={lost or '-'} gained={gained or '-'}")
    return res


VARIANTS = {
    "mean (engine)": {},
    "snap mean->grid": {"est": "snap_mean"},
    "round mean to grid (no interval)": {"est": "round_mean"},
    "clamp mean (no grid)": {"est": "clamp_mean"},
    "clamp mean + grid": {"est": "clamp_mean_grid"},
    "snap mean, 1-pt only else mean": {"est": "snap_mean_1"},
    "snap mean, <=2 pts else mean": {"est": "snap_mean_2"},
    "snap mean band x1.05": {"est": "snap_mean", "band_scale": 1.05},
    "snap mean band x0.95": {"est": "snap_mean", "band_scale": 0.95},
    "snap pmean->grid": {"est": "snap_pmean"},
    "snap mean wide cats only": {"est": "snap_mean", "only_cats": {"groceries", "transport", "dining"}},
    "snap mean narrow cats only": {"est": "snap_mean", "only_cats": {"utilities", "healthcare", "entertainment", "shopping"}},
    "snap mean, grid x5": {"est": "snap_mean", "grid_mult": 5},
    "snap mean, ZAR grid 1": {"est": "snap_mean", "zar_grid": 1.0},
}


def _grid(self, home):
    g = GRID[home] * self.hyp.get("grid_mult", 1)
    if home == "ZAR" and self.hyp.get("zar_grid"):
        g = self.hyp["zar_grid"]
    return g


def _estimate2(self, cat, amts, home):
    """Extra estimators for the variant grid; falls back to the original for the rest."""
    h = self.hyp
    est = h.get("est", "mean")
    a = h.get("band", BAND).get(cat, 0.28) * h.get("band_scale", 1.0)
    L, U = max(amts) / (1 + a), min(amts) / (1 - a)
    n = len(amts)
    mean = statistics.mean(amts)
    g = _grid(self, home)
    if est == "round_mean":
        return round(mean / g) * g
    if est in ("clamp_mean", "clamp_mean_grid"):
        if L > U:
            self.stats["infeasible"] += 1
            return mean
        x = min(max(mean, L), U)
        if x != mean:
            self.stats["mean_outside"] += 1
        if est == "clamp_mean_grid":
            r = round(x / g) * g
            if not (L - 1e-9 <= r <= U + 1e-9):  # nearest grid point inside the interval
                cands = [c for c in (math.ceil(L / g - 1e-9) * g, math.floor(U / g + 1e-9) * g) if L - 1e-9 <= c <= U + 1e-9]
                r = min(cands, key=lambda v: abs(v - x)) if cands else x
            x = r
        return x
    if est in ("snap_mean_1", "snap_mean_2", "snap_pmean"):
        if L > U:
            self.stats["infeasible"] += 1
            return mean
        cands = []
        c = math.ceil(L / g - 1e-9) * g
        while c <= U + 1e-9:
            cands.append(c)
            c += g
        self.stats[f"grid_pts_{min(len(cands), 3)}"] += 1
        if est == "snap_pmean":
            base = ((U ** (2 - n) - L ** (2 - n)) / (2 - n)) / ((U ** (1 - n) - L ** (1 - n)) / (1 - n)) if n > 2 else (L + U) / 2
            return base if not cands else min(cands, key=lambda v: abs(v - base))
        lim = 1 if est == "snap_mean_1" else 2
        if 1 <= len(cands) <= lim:
            return min(cands, key=lambda v: abs(v - mean))
        return mean
    if est in ("snap", "snap_mean") and (h.get("grid_mult") or h.get("zar_grid")):
        if L > U:
            self.stats["infeasible"] += 1
            return mean
        base = (L + U) / 2 if est == "snap" else mean
        cands = []
        c = math.ceil(L / g - 1e-9) * g
        while c <= U + 1e-9:
            cands.append(c)
            c += g
        self.stats[f"grid_pts_{min(len(cands), 3)}"] += 1
        return base if not cands else min(cands, key=lambda v: abs(v - base))
    return _estimate_orig(self, cat, amts, home)


_estimate_orig = EstBuilder.estimate
EstBuilder.estimate = _estimate2


def detail(bench, ids=("request_08", "request_18", "request_11", "request_20", "request_25", "request_21"), hyp=None):
    """Per fixed series: mean, feasible interval, grid points, snapped value."""
    b = EstBuilder(bench.ds, bench.images, bench.adjs, hyp=hyp or {"est": "snap_mean"})
    for req in bench.reqs:
        if req.request_id not in ids:
            continue
        st = b.build(req)
        print(f"--- {req.request_id} {st.home} want={req.expected['amount_safe_to_pay']}")
        hist = [e for e in bench.ds.events_by_user[req.user_id] if e.status == "settled" and e.direction == "debit" and e.amount_source == "csv"]
        groups = defaultdict(list)
        for e in hist:
            if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES or e.linked_event_id:
                continue
            groups[e.category].append(e.amount)
        for s in st.series:
            amts = groups.get(s.category)
            if not amts or is_constant(amts):
                continue
            a = BAND.get(s.category, 0.28)
            L, U = max(amts) / (1 + a), min(amts) / (1 - a)
            g = GRID[st.home]
            cands = []
            c = math.ceil(L / g - 1e-9) * g
            while c <= U + 1e-9:
                cands.append(round(c, 2))
                c += g
            leaked = "leaked" if s.minimum_allowed_amount else "fixed "
            print(f"  {leaked} {s.category:13s} n={len(amts):2d} occ={len(s.dates)} mean={statistics.mean(amts):12.2f} mid={(max(amts)+min(amts))/2:12.2f} "
                  f"feasible=[{L:.2f},{U:.2f}] width={U-L:.2f} grid_pts={len(cands)} {cands if len(cands) <= 6 else str(cands[:3]) + '..'} -> used {s.amount:.2f}")


def grid250(ds):
    """Well-determinedness over all evaluation requests: grid points in the feasible interval per fixed variable series."""
    reqs = ds.load_requests("requests.csv")
    k = leak_multipliers(ds)
    rows = series_rows(ds)
    cnt = defaultdict(Counter)
    width = defaultdict(list)
    users = {r.user_id for r in reqs}
    for (uid, cat), evs in rows.items():
        if uid not in users:
            continue
        amts = [e.amount for e in evs]
        if len(amts) < 3 or is_constant(amts):
            continue
        mins = {e.minimum_allowed_amount for e in evs}
        if len(mins) == 1 and None not in mins and cat in k:
            continue
        home = ds.profiles[uid].home_currency
        a = BAND.get(cat, 0.28)
        L, U = max(amts) / (1 + a), min(amts) / (1 - a)
        g = GRID[home]
        npts = 0 if L > U else int(math.floor(U / g + 1e-9) - math.ceil(L / g - 1e-9) + 1)
        cnt[home][min(npts, 3)] += 1
        width[home].append((U - L) / g if U > L else 0)
    print(f"{'cur':5s}{'series':>7s}{'0 pts':>7s}{'1 pt':>6s}{'2 pts':>7s}{'3+ pts':>8s}{'median width (grid units)':>27s}")
    for home, c in sorted(cnt.items()):
        tot = sum(c.values())
        print(f"{home:5s}{tot:7d}{c[0]:7d}{c[1]:6d}{c[2]:7d}{c[3]:8d}{statistics.median(width[home]):27.1f}")
    # how often is the historical mean outside the feasible interval, and by how much (all 250 evaluation users)
    out = defaultdict(list)
    tot = Counter()
    for (uid, cat), evs in rows.items():
        if uid not in users:
            continue
        amts = [e.amount for e in evs]
        if len(amts) < 3 or is_constant(amts):
            continue
        mins = {e.minimum_allowed_amount for e in evs}
        if len(mins) == 1 and None not in mins and cat in k:
            continue
        a = BAND.get(cat, 0.28)
        L, U = max(amts) / (1 + a), min(amts) / (1 - a)
        m = statistics.mean(amts)
        tot[cat] += 1
        if m < L:
            out[cat].append((L - m) / m)
        elif m > U:
            out[cat].append((m - U) / m)
    print("\nfixed series whose mean lies outside the feasible interval (needs a move), all evaluation users:")
    for cat in sorted(tot):
        v = out[cat]
        print(f"  {cat:14s} {len(v):4d}/{tot[cat]:4d} ({100*len(v)/tot[cat]:4.1f}%)  mean move {100*statistics.mean(v) if v else 0:.2f}%  max move {100*max(v) if v else 0:.2f}%")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    ds = Dataset()
    if mode == "detail":
        detail(Bench())
        sys.exit()
    if mode == "variants":
        est(Bench(), VARIANTS)
        sys.exit()
    if mode == "grid250":
        grid250(ds)
        sys.exit()
    if mode in ("band", "all"):
        print("=" * 30, "TASK 1: noise band of the leaked series")
        band(ds)
    if mode in ("fixed", "all"):
        print("\n" + "=" * 30, "TASK 3: implied half-width of the fixed variable categories")
        fixed(ds)
    if mode in ("est", "all"):
        print("\n" + "=" * 30, "TASK 2: estimators for the fixed block, full scorer")
        est(Bench())
