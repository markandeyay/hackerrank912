"""Occurrence-count study (improve3, task 2).

Part A (`counts`): for the eight samples that miss (04, 06, 10, 11, 13, 15, 17, 19), how many
occurrences of every variable series must the reference have counted before the binding day so
that the expected amount holds with the engine's current nominal amounts?  Integer problem per
sample: counts 0..4 per variable series, constant series at their calendar count, minimise the
residual.  For 11 and 17 the between-payday window that decides the earliest date is analysed too.

Part B (`rules`): candidate scheduling rules implemented as a post-processing of the series dates
(StateBuilder subclass, engine untouched), each scored with the full planner on all 25 samples.

Run (repo root):  .venv/Scripts/python code/notes/improve3/occurrence_counts.py [counts|rules|all]
"""
from __future__ import annotations

import itertools
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(CODE_DIR))

from data import Dataset  # noqa: E402
from explain import template_explanation  # noqa: E402
from forecast import daily_balances  # noqa: E402
from pipeline import decision_row, load_adjustments, load_image_amounts  # noqa: E402
from planner import decide  # noqa: E402
from state import NON_RECURRING_CATEGORIES, NON_RECURRING_TYPES, StateBuilder, add_months  # noqa: E402

COLS = ["amount_safe_to_pay", "affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed"]
STUDY = ["request_04", "request_06", "request_10", "request_11", "request_13", "request_15", "request_17", "request_19", "request_05", "request_25"]


# ----------------------------------------------------------------------------- helpers
def history_dates(builder: StateBuilder, st) -> dict[str, tuple[list[date], list[float]]]:
    """Per category: settled-debit history exactly as _build_debit_series groups it."""
    ds = builder.ds
    events = ds.events_by_user.get(st.request.user_id, [])
    linked_targets = {e.linked_event_id for e in events if e.linked_event_id}
    groups: dict[str, list[tuple[date, float]]] = defaultdict(list)
    for e in events:
        if e.status != "settled" or e.direction != "debit":
            continue
        if builder.amount_of(e) is None:
            continue
        sd = e.settlement_date or e.event_date
        if sd > st.request_date:
            continue
        if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
            continue
        if e.linked_event_id or e.event_id in linked_targets:
            continue
        if builder.opt.get("exclude_image_rows_from_mean") and e.amount_source != "csv":
            continue
        groups[e.category].append((sd, builder.to_home(builder.amount_of(e), e.currency, st.home, sd)))
    out = {}
    for cat, rows in groups.items():
        rows.sort()
        out[cat] = ([r[0] for r in rows], [r[1] for r in rows])
    return out


def is_constant(amts: list[float]) -> bool:
    return max(amts) - min(amts) < 0.005 * max(1.0, statistics.mean(amts))


def first_payday(st):
    pays = [d for d in st.salary_dates if d > st.request_date]
    return min(pays) if pays else None


# ----------------------------------------------------------------------------- part A
def implied_counts(ds, builder, req, st, window_end=None, window_start=None, target=None, label="binding day"):
    """Enumerate per-series counts in [window_start, window_end] so that the series total equals
    `target` (the reference's series total for that window).  Prints the table."""
    rq = st.request_date
    lo = window_start or rq
    hi = window_end
    hist = history_dates(builder, st)
    known_deb = sum(-f.amount for f in st.flows if f.amount < 0 and lo <= f.date <= hi)
    credits = sum(f.amount for f in st.flows if f.amount > 0 and lo <= f.date <= hi)
    rows = []
    for s in st.series:
        dts, amts = hist.get(s.category, ([], []))
        const = is_constant(amts) if amts else True
        occ = [d for d in s.dates if lo <= d <= hi]
        later = [d for d in s.dates if d > hi][:3]
        rows.append((s, const, occ, later))
    const_total = sum(len(occ) * s.amount for s, const, occ, _ in rows if const)
    var_rows = [(s, occ, later) for s, const, occ, later in rows if not const]
    need = target - known_deb + credits - const_total
    ours_var = sum(len(occ) * s.amount for s, occ, _ in var_rows)
    print(f"  window {lo}..{hi} ({label}): known debits {known_deb:,.2f} credits {credits:,.2f} constant-series {const_total:,.2f}")
    print(f"  variable series must sum to {need:,.2f}; ours = {ours_var:,.2f} (diff {ours_var - need:+,.2f}, {100*(ours_var-need)/target:+.2f}% of target)")
    print(f"  {'series':14s} {'gap':>4s} {'nominal':>14s} ours  dates in window            next after window")
    for s, occ, later in var_rows:
        print(f"  {s.category:14s} {s.step_days:4d} {s.amount:14,.2f} {len(occ):4d}  {' '.join(d.isoformat()[5:] for d in occ):26s} {' '.join(d.isoformat()[5:] for d in later)}")
    # integer problem: counts = ours + delta, delta in -2..+2 for short-cycle series, -1..+1 for monthly
    ranges = []
    for s, occ, _ in var_rows:
        n = len(occ)
        lo_d, hi_d = (-2, 2) if s.cadence == "periodic" else (-1, 1)
        ranges.append([n + d for d in range(lo_d, hi_d + 1) if 0 <= n + d])
    sols = []
    for counts in itertools.product(*ranges):
        tot = sum(c * s.amount for c, (s, _, _) in zip(counts, var_rows))
        monthly_moved = any(c != len(occ) for c, (s, occ, _) in zip(counts, var_rows) if s.cadence != "periodic")
        sols.append((abs(tot - need), monthly_moved, counts, tot - need))
    sols.sort()
    ours = tuple(len(occ) for _, occ, _ in var_rows)
    print(f"  ours   counts={ours} residual {ours_var - need:+,.2f} ({100*(ours_var-need)/target:+.2f}%)")
    shown = 0
    for _, mm, counts, res in sols:
        if abs(res) > 0.012 * abs(target) and shown >= 3:
            break
        desc = []
        for c, (s, occ, later) in zip(counts, var_rows):
            if c > len(occ):
                desc.append(f"{s.category}+{' +'.join(d.isoformat()[5:] for d in later[:c-len(occ)]) or '?'}")
            elif c < len(occ):
                desc.append(f"{s.category}-{' -'.join(d.isoformat()[5:] for d in occ[c:])}")
        tag = "monthly count changed" if mm else "short-cycle only"
        print(f"  fit #{shown+1} counts={counts} residual {res:+,.2f} ({100*res/target:+.2f}%) [{tag}]  {'; '.join(desc) or 'same as ours'}")
        shown += 1
        if shown >= 8:
            break
    return var_rows, sols


def part_a(ds, builder, reqs):
    for rid in STUDY:
        req = reqs[rid]
        st = builder.build(req)
        prof = st.profile
        want = float(req.expected["amount_safe_to_pay"])
        head = prof.current_available_balance - prof.minimum_balance_to_keep
        ref_res = head - want
        bal = daily_balances(st)
        tmin = min(bal, key=lambda x: x[1])[0]
        our_res = head - max(0.0, min(req.requested_amount, min(b for _, b in bal) - st.min_balance))
        pay = first_payday(st)
        print(f"\n=== {rid} ({prof.home_currency}) rq={st.request_date} first payday={pay} trough={tmin} horizon_end={st.horizon_end}")
        print(f"  reference reserve {ref_res:,.2f}; ours {our_res:,.2f} (diff ours-ref {our_res-ref_res:+,.2f}); days rq->payday = {(pay - st.request_date).days if pay else None}")
        implied_counts(ds, builder, req, st, window_end=tmin, target=ref_res, label="trough")
        if rid == "request_11":
            # June 15 payment must FAIL at Jul 14 in the reference: balance(07-14) - requested < min
            pays = [d for d in st.salary_dates if d > st.request_date]
            b = dict(bal)
            d2 = pays[2] - timedelta(days=1)
            margin = b[d2] - req.requested_amount - st.min_balance
            print(f"  earliest check: balance on {d2} = {b[d2]:,.2f}; margin after paying on {pays[1]} = {margin:+,.2f}")
            print(f"  -> the reference needs >= {margin:,.2f} more debits in [{st.request_date}, {d2}] than ours; of that {ref_res-our_res:,.2f} is already before the trough,")
            print(f"     so >= {margin-(ref_res-our_res):,.2f} extra must fall in ({tmin}, {d2}]")
            w0 = pays[0] + timedelta(days=1)
            ours_w = sum(-f.amount for f in st.flows if f.amount < 0 and w0 <= f.date <= d2) + sum(len([d for d in s.dates if w0 <= d <= d2]) * s.amount for s in st.series)
            implied_counts(ds, builder, req, st, window_start=w0, window_end=d2, target=ours_w + margin - (ref_res - our_res), label="between paydays, MINIMUM total needed")
        if rid == "request_17":
            pays = [d for d in st.salary_dates if d > st.request_date]
            b = dict(bal)
            d2 = pays[1] - timedelta(days=1)
            margin = b[d2] - req.requested_amount - st.min_balance
            print(f"  earliest check: balance on {d2} = {b[d2]:,.2f}; margin after paying on {pays[0]} = {margin:+,.2f} (must be >= 0 in the reference)")
            print(f"  -> the reference has <= {-margin + (our_res-ref_res):,.2f} less debits in ({tmin}, {d2}] than ours (its pre-trough reserve is {ref_res-our_res:+,.2f} vs ours)")
            w0 = pays[0] + timedelta(days=1)
            ours_w = sum(-f.amount for f in st.flows if f.amount < 0 and w0 <= f.date <= d2) + sum(len([d for d in s.dates if w0 <= d <= d2]) * s.amount for s in st.series)
            implied_counts(ds, builder, req, st, window_start=w0, window_end=d2, target=ours_w + margin - (ref_res - our_res), label="between paydays, MAXIMUM total allowed")


# ----------------------------------------------------------------------------- part B
class RuleBuilder(StateBuilder):
    def __init__(self, *a, rule=None, **k):
        super().__init__(*a, **k)
        self.rule = rule

    def build(self, req):
        st = super().build(req)
        if self.rule:
            self.rule(self, st)
        return st


def periodic(st):
    return [s for s in st.series if s.cadence == "periodic"]


def r_skip_rq_plus(n):
    def f(b, st):
        for s in periodic(st):
            s.dates = [d for d in s.dates if (d - st.request_date).days != n]
    return f


def r_skip_rq1_rephase(b, st):
    """occurrence on rq+1 skipped and the series re-anchored at rq+1 (next = rq+1+gap)."""
    for s in periodic(st):
        if s.dates and (s.dates[0] - st.request_date).days == 1:
            t = s.dates[0] + timedelta(days=s.step_days)
            new = []
            while t <= st.horizon_end:
                new.append(t)
                t += timedelta(days=s.step_days)
            s.dates = new


def set_count_before_payday(st, s, target):
    pay = first_payday(st)
    before = [d for d in s.dates if d < pay]
    after = [d for d in s.dates if d >= pay]
    if len(before) > target:
        before = before[:target]
    while len(before) < target:
        before.append(pay - timedelta(days=1))
    s.dates = sorted(before) + after


def r_days_rule(fn, offset=0, at_least_one=False, per_cycle=False):
    def f(b, st):
        pays = [d for d in st.salary_dates if d > st.request_date]
        if not pays:
            return
        for s in periodic(st):
            if not per_cycle:
                D = (pays[0] - st.request_date).days + offset
                target = int(fn(D / s.step_days))
                if at_least_one:
                    target = max(1, target)
                set_count_before_payday(st, s, target)
            else:
                bounds = [st.request_date] + sorted(set(pays)) + [st.horizon_end + timedelta(days=1)]
                new = []
                for i in range(len(bounds) - 1):
                    lo, hi = bounds[i], bounds[i + 1]
                    D = (hi - lo).days + offset
                    target = int(fn(D / s.step_days))
                    if at_least_one:
                        target = max(1, target)
                    seg = [d for d in s.dates if lo <= d < hi]
                    if len(seg) > target:
                        seg = seg[:target]
                    while len(seg) < target:
                        seg.append(min(hi - timedelta(days=1), st.horizon_end))
                    new.extend(seg)
                s.dates = sorted(new)
    return f


def r_monthly_once(b, st):
    """a monthly series is counted at most once before the first payday."""
    pay = first_payday(st)
    if not pay:
        return
    for s in st.series:
        if s.cadence != "monthly":
            continue
        before = [d for d in s.dates if d < pay]
        after = [d for d in s.dates if d >= pay]
        s.dates = before[:1] + after


def r_monthly_copy(skip_rq=True, bring_forward=True, months=3):
    """short-cycle series recur on the same days of month as their history (every historical
    occurrence shifted by 1, 2, 3 months) instead of last + gap."""
    def f(b, st):
        hist = history_dates(b, st)
        pay = first_payday(st)
        for s in periodic(st):
            dts, _ = hist[s.category]
            new = set()
            for d in dts:
                for k in range(1, months + 1):
                    t = add_months(d, k)
                    if (t > st.request_date if skip_rq else t >= st.request_date) and t <= st.horizon_end:
                        new.add(t)
            s.dates = sorted(new)
            if bring_forward and pay and pay > st.request_date and s.dates and s.dates[0] >= pay:
                s.dates[0] = pay - timedelta(days=1)
                s.dates.sort()
    return f


def r_last_month_copy(skip_rq=True, bring_forward=True):
    """only the last 30 days of history are copied forward month by month (calendar-month count)."""
    def f(b, st):
        hist = history_dates(b, st)
        pay = first_payday(st)
        for s in periodic(st):
            dts, _ = hist[s.category]
            last = dts[-1]
            recent = [d for d in dts if d > last - timedelta(days=30)]
            new = set()
            for d in recent:
                for k in range(1, 4):
                    t = add_months(d, k)
                    if (t > st.request_date if skip_rq else t >= st.request_date) and t <= st.horizon_end:
                        new.add(t)
            s.dates = sorted(new)
            if bring_forward and pay and pay > st.request_date and s.dates and s.dates[0] >= pay:
                s.dates[0] = pay - timedelta(days=1)
                s.dates.sort()
    return f


def r_through_desired(b, st):
    """periodic occurrences between the first payday and desired_completion_date are reserved before the payday."""
    pay = first_payday(st)
    if not pay:
        return
    dd = st.request.desired_completion_date
    if dd < pay:
        return
    for s in periodic(st):
        s.dates = sorted(pay - timedelta(days=1) if pay <= d <= dd else d for d in s.dates)


def r_ceil_horizon(b, st):
    """one extra occurrence of every periodic series at the horizon end (count = ceil over the window)."""
    for s in periodic(st):
        s.dates = sorted(s.dates + [st.horizon_end])


def r_ceil_horizon_if_no_payday(b, st):
    if [d for d in st.salary_dates if d > st.request_date]:
        return
    r_ceil_horizon(b, st)


def r_payday_window(win, periodic_only=True, min_gap=0, max_gap=99, first_payday_only=False):
    def f(b, st):
        pays = sorted(set(d for d in st.salary_dates if d > st.request_date))
        if first_payday_only:
            pays = pays[:1]
        for s in st.series:
            if periodic_only and s.cadence != "periodic":
                continue
            if s.cadence == "periodic" and not (min_gap <= s.step_days <= max_gap):
                continue
            new = []
            for d in s.dates:
                hit = [p for p in pays if p <= d < p + timedelta(days=win)]
                new.append(hit[0] - timedelta(days=1) if hit else d)
            s.dates = sorted(new)
    return f


def chain(*rules):
    def f(b, st):
        for r in rules:
            r(b, st)
    return f


def score(ds, images, adjs, reqs_list, rule=None, options=None):
    b = RuleBuilder(ds, images, adjs, rule=rule, options=options)
    out = {}
    for req in reqs_list:
        st = b.build(req)
        dec = decide(st, ds.options_by_request.get(req.request_id, []))
        row = decision_row(dec, template_explanation(dec))
        out[req.request_id] = row
    return out


def compare(base_rows, rows, reqs):
    exact = {c: 0 for c in COLS}
    w2 = 0
    cells = 0
    gained, lost, amt_moves = [], [], []
    for req in reqs:
        exp = req.expected
        row = rows[req.request_id]
        brow = base_rows[req.request_id]
        for c in COLS:
            ok = row[c] == exp[c]
            bok = brow[c] == exp[c]
            if ok:
                exact[c] += 1
                cells += 1
            if ok and not bok:
                gained.append(f"{req.request_id[-2:]}:{c[:5]}")
            if bok and not ok:
                lost.append(f"{req.request_id[-2:]}:{c[:5]}")
        got, want, bgot = float(row["amount_safe_to_pay"]), float(exp["amount_safe_to_pay"]), float(brow["amount_safe_to_pay"])
        if abs(got - want) <= 0.02 * max(1.0, abs(want)):
            w2 += 1
        if abs(got - bgot) > 0.005:
            amt_moves.append(f"{req.request_id[-2:]}:{100*(got-want)/max(1.0,want):+.1f}%")
    return exact, cells, w2, gained, lost, amt_moves


def part_b(ds, images, adjs, reqs_list):
    rules = [
        ("baseline", None, None),
        ("A1 skip rq+1 (drop that occurrence)", r_skip_rq_plus(1), None),
        ("A2 skip rq+1 and re-anchor at rq+1", r_skip_rq1_rephase, None),
        ("A3 skip rq+2", r_skip_rq_plus(2), None),
        ("B1 include occurrence on request_date", None, {"periodic_skip_request_date": False}),
        ("C1 count = ceil(days_to_payday/gap)", r_days_rule(math.ceil), None),
        ("C2 count = ceil((days+1)/gap)", r_days_rule(math.ceil, 1), None),
        ("C3 count = floor(days/gap)", r_days_rule(math.floor), None),
        ("C4 count = floor(days/gap), >=1", r_days_rule(math.floor, at_least_one=True), None),
        ("C5 count = floor((days+1)/gap), >=1", r_days_rule(math.floor, 1, at_least_one=True), None),
        ("C6 count = round(days/gap), >=1", r_days_rule(lambda x: math.floor(x + 0.5), at_least_one=True), None),
        ("C7 ceil per pay cycle (all cycles)", r_days_rule(math.ceil, per_cycle=True), None),
        ("C8 round per pay cycle, >=1", r_days_rule(lambda x: math.floor(x + 0.5), at_least_one=True, per_cycle=True), None),
        ("D1 at most 1 occurrence per cycle", None, {"periodic_max_per_cycle": 1}),
        ("D2 at most 2 per cycle", None, {"periodic_max_per_cycle": 2}),
        ("E1 payday occurrence before salary (win=1)", None, {"periodic_before_payday_days": 1}),
        ("E2 payday..payday+1 before salary (win=2)", None, {"periodic_before_payday_days": 2}),
        ("E3 win=2 for all series incl. monthly", r_payday_window(2, periodic_only=False), None),
        ("F1 monthly series counted once before payday", r_monthly_once, None),
        ("G1 calendar-month copy of all history (skip rq, bf)", r_monthly_copy(True, True), None),
        ("G2 calendar-month copy (skip rq, no bf)", r_monthly_copy(True, False), None),
        ("G3 calendar-month copy (incl rq, bf)", r_monthly_copy(False, True), None),
        ("G4 last-30-days copy (skip rq, bf)", r_last_month_copy(True, True), None),
        ("G5 last-30-days copy (skip rq, no bf)", r_last_month_copy(True, False), None),
        ("H1 through desired_completion_date", r_through_desired, None),
        ("I1 ceil at horizon end (all samples)", r_ceil_horizon, None),
        ("I2 ceil at horizon end (no-income samples only)", r_ceil_horizon_if_no_payday, None),
        ("E4 win=1, first payday only", r_payday_window(1, first_payday_only=True), None),
        ("E5 win=2, first payday only", r_payday_window(2, first_payday_only=True), None),
        ("E6 win=1, gap>=7 only", r_payday_window(1, min_gap=7), None),
        ("E7 win=2, gap>=7 only", r_payday_window(2, min_gap=7), None),
        ("E8 win=2, gap==7 only", r_payday_window(2, min_gap=7, max_gap=7), None),
        ("E9 win=2, gap==7, first payday only", r_payday_window(2, min_gap=7, max_gap=7, first_payday_only=True), None),
        ("E10 win=1, gap==7, first payday only", r_payday_window(1, min_gap=7, max_gap=7, first_payday_only=True), None),
        ("J0 A1 + E9", chain(r_skip_rq_plus(1), r_payday_window(2, min_gap=7, max_gap=7, first_payday_only=True)), None),
        ("J1 A1 + E2", chain(r_skip_rq_plus(1), r_payday_window(2)), None),
        ("J2 A1 + E1", chain(r_skip_rq_plus(1), r_payday_window(1)), None),
        ("J3 A1 + I2", chain(r_skip_rq_plus(1), r_ceil_horizon_if_no_payday), None),
        ("J4 A1 + H1", chain(r_skip_rq_plus(1), r_through_desired), None),
        ("J5 A1 + C7", chain(r_skip_rq_plus(1), r_days_rule(math.ceil, per_cycle=True)), None),
        ("J6 E2 + I2", chain(r_payday_window(2), r_ceil_horizon_if_no_payday), None),
        ("J7 A1 + E2 + I2", chain(r_skip_rq_plus(1), r_payday_window(2), r_ceil_horizon_if_no_payday), None),
    ]
    base = score(ds, images, adjs, reqs_list)
    print(f"\n{'rule':52s} {'amt st me pl ea ch':20s} {'overall':>8s} {'w2%':>4s}  gained | lost | amounts moved (err vs ref)")
    results = []
    for name, rule, opts in rules:
        rows = score(ds, images, adjs, reqs_list, rule, opts)
        exact, cells, w2, gained, lost, moves = compare(base, rows, reqs_list)
        cols = " ".join(f"{exact[c]:2d}" for c in COLS)
        print(f"{name:52s} {cols:20s} {cells:4d}/150 {w2:2d}/25  {' '.join(gained) or '-'} | {' '.join(lost) or '-'} | {' '.join(moves) or '-'}")
        results.append((name, cells, w2, gained, lost, rows))
    return results


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    ds = Dataset()
    reqs_list = ds.load_requests("sample_requests.csv")
    reqs = {r.request_id: r for r in reqs_list}
    images = load_image_amounts(ds, True)
    adjs = load_adjustments(ds, True)
    builder = StateBuilder(ds, images, adjs)
    if mode in ("counts", "all"):
        part_a(ds, builder, reqs)
    if mode in ("rules", "all"):
        part_b(ds, images, adjs, reqs_list)


if __name__ == "__main__":
    main()
