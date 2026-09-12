"""Audit of salary and fixed-date (monthly) projections in code/state.py.

Run:  .venv/Scripts/python code/notes/improve2/audit_fixed_dates.py
Deterministic evidence path only (no model caches).
"""
from __future__ import annotations

import calendar
import random
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))

from data import Dataset  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from state import (  # noqa: E402
    FREELANCE_INCOME,
    GIG_INCOME,
    NON_RECURRING_CATEGORIES,
    NON_RECURRING_TYPES,
    REGULAR_SALARY,
    SECONDARY_STREAM,
    StateBuilder,
    add_months,
)

ds = Dataset()
images = load_image_amounts(ds, False)
adjs = load_adjustments(ds, False)
sb = StateBuilder(ds, images, adjs)

samples = ds.load_requests("sample_requests.csv")
hidden = ds.load_requests("requests.csv")
rng = random.Random(7)
picked = rng.sample(hidden, 30) if not __import__("os").environ.get("ALL") else hidden
reqs = samples + picked

viol: list[str] = []
info: list[str] = []
counts = Counter()


def V(msg):
    viol.append(msg)


def I(msg):
    info.append(msg)


def eom(d: date) -> int:
    return calendar.monthrange(d.year, d.month)[1]


def same_dom(hist_dom: int, d: date) -> bool:
    return d.day == min(hist_dom, eom(d))


for req in reqs:
    st = sb.build(req)
    uid, rid, rq, end = req.user_id, req.request_id, req.request_date, st.horizon_end
    tag = f"{uid}/{rid}"
    events = ds.events_by_user.get(uid, [])
    home = st.home
    user_adjs = adjs.get(uid, [])
    sal_adjs = [a for a in user_adjs if a.get("target") == "salary" or a["adjustment_type"] in ("income_ended", "salary_date_change", "salary_amount_change", "one_time_confirmed_income")]

    # ---------------- salary -----------------
    sal_flows = sorted([f for f in st.flows if f.kind == "salary"], key=lambda f: f.date)
    sched = [e for e in events if e.status == "scheduled" and e.direction == "credit" and e.category == "salary"]
    regular = sorted([e for e in events if e.status == "settled" and e.direction == "credit" and e.category == "salary" and e.description in REGULAR_SALARY], key=lambda e: e.settlement_date)
    counts["requests"] += 1
    if sched:
        counts["scheduled_salary"] += 1
        s = sched[0]
        sd = s.settlement_date or s.event_date
        amt = sb.amount_of(s)
        exp_amt = ds.convert(amt, s.currency, home, sd)
        if len(sched) > 1:
            V(f"{tag} salary: {len(sched)} scheduled salary rows")
        if sd < rq:
            V(f"{tag} salary: scheduled salary {s.event_id} settles {sd} before request_date {rq}")
        if not sal_flows:
            V(f"{tag} salary: scheduled {s.event_id} on {sd} but no salary flow projected (notes={st.notes})")
        else:
            f0 = sal_flows[0]
            moved = [a for a in sal_adjs if a["adjustment_type"] in ("salary_date_change", "salary_amount_change") and a["adjustment_type"] != "no_effect"]
            if f0.date != sd and not moved:
                V(f"{tag} salary: first projected {f0.date} != scheduled {sd}")
            if abs(f0.amount - exp_amt) > 0.01 and not moved:
                V(f"{tag} salary: first projected amount {f0.amount:.2f} != scheduled {exp_amt:.2f} ({amt} {s.currency})")
            if moved:
                I(f"{tag} salary MOVED/RESIZED by message: adjs={[(a['adjustment_type'], a.get('scope'), a.get('amount'), a.get('currency'), a.get('effective_date'), a.get('template_id')) for a in moved]} scheduled={sd} {amt} {s.currency} -> flows={[(f.date.isoformat(), round(f.amount, 2)) for f in sal_flows]}")
            # later ones monthly on same DOM as first
            for k, f in enumerate(sal_flows[1:], 1):
                if f.date != add_months(sal_flows[0].date, k):
                    V(f"{tag} salary: flow {k} on {f.date} != add_months(first,{k})={add_months(sal_flows[0].date, k)}")
            # no duplicate: history-projected salary in the same month as the scheduled row
            months = Counter((f.date.year, f.date.month) for f in sal_flows)
            for ym, n in months.items():
                if n > 1:
                    V(f"{tag} salary: {n} salary flows in month {ym} (duplicate?) {[(f.date.isoformat(), round(f.amount,2)) for f in sal_flows]}")
            # check settled payroll in same month as scheduled row (would be double if both counted; the settled one is in balance already)
            if regular and (regular[-1].settlement_date.year, regular[-1].settlement_date.month) == (sd.year, sd.month):
                I(f"{tag} salary: last settled payroll {regular[-1].event_id} {regular[-1].settlement_date} is in the same month as scheduled {s.event_id} {sd} (both real rows; ok)")
            # scheduled DOM vs history DOM
            if regular:
                dom_hist = Counter(e.settlement_date.day for e in regular).most_common(1)[0][0]
                if not same_dom(dom_hist, sd):
                    I(f"{tag} salary: scheduled DOM {sd.day} differs from history modal DOM {dom_hist} (history {[e.settlement_date.isoformat() for e in regular[-3:]]})")
    elif regular:
        counts["history_salary"] += 1
        primary = [e for e in regular if e.description not in SECONDARY_STREAM] or regular
        dom_event = Counter(e.event_date.day for e in primary).most_common(1)[0][0]
        dom_settle = Counter(e.settlement_date.day for e in primary).most_common(1)[0][0]
        base = primary[-1]
        same_desc = [sb.amount_of(e) for e in primary if e.description == base.description and e.currency == base.currency]
        mode_amt, mode_n = Counter(same_desc).most_common(1)[0]
        exp_native = mode_amt if mode_n >= 3 else sb.amount_of(base)
        stale = (rq - base.settlement_date).days > 45
        income_ended = any(a["adjustment_type"] == "income_ended" for a in user_adjs)
        ending = base.description == "Final employer payroll"
        moved = [a for a in sal_adjs if a["adjustment_type"] in ("salary_date_change", "salary_amount_change", "one_time_confirmed_income")]
        if dom_event != dom_settle:
            V(f"{tag} salary: modal event-date DOM {dom_event} != modal settlement DOM {dom_settle} (engine uses event_date) rows={[(e.event_date.isoformat(), e.settlement_date.isoformat()) for e in primary[-4:]]}")
        if not sal_flows:
            if stale or income_ended or ending:
                I(f"{tag} salary: none projected (stale={stale} ended={income_ended} final={ending} last={base.settlement_date})")
            elif moved:
                I(f"{tag} salary: none projected but message adjs={[(a['adjustment_type'], a.get('scope'), a.get('amount'), a.get('effective_date'), a.get('template_id')) for a in moved]}")
            else:
                V(f"{tag} salary: history exists (last {base.event_id} {base.settlement_date}) but no salary projected; notes={st.notes}")
        else:
            f0 = sal_flows[0]
            # expected first: first DOM date strictly after last payroll that is >= rq
            t = add_months(base.event_date, 1)
            t = date(t.year, t.month, min(dom_settle, eom(t)))
            while t < rq:
                t = add_months(t, 1)
            exp_first = t
            # alternative: first DOM date after last settlement date
            t2 = base.settlement_date + timedelta(days=1)
            while not same_dom(dom_settle, t2):
                t2 += timedelta(days=1)
            while t2 < rq:
                t2 = add_months(t2, 1)
                t2 = date(t2.year, t2.month, min(dom_settle, eom(t2)))
            if moved:
                I(f"{tag} salary MOVED/RESIZED by message (history-based): adjs={[(a['adjustment_type'], a.get('scope'), a.get('amount'), a.get('currency'), a.get('effective_date'), a.get('template_id')) for a in moved]} last={base.settlement_date} {sb.amount_of(base)} {base.currency} modal={mode_amt}x{mode_n} dom={dom_settle} -> flows={[(f.date.isoformat(), round(f.amount, 2)) for f in sal_flows]}")
            else:
                if f0.date != exp_first:
                    V(f"{tag} salary: first projected {f0.date} != expected {exp_first} (dom={dom_settle}, last payroll {base.settlement_date})")
                if f0.date != t2:
                    V(f"{tag} salary: first projected {f0.date} != first DOM after last settlement {t2} (dom={dom_settle}, last payroll {base.settlement_date})")
                exp_amt = ds.convert(exp_native, base.currency, home, f0.date)
                if abs(f0.amount - exp_amt) > 0.01:
                    V(f"{tag} salary: amount {f0.amount:.2f} != expected {exp_amt:.2f} (modal {mode_amt} x{mode_n}, last {sb.amount_of(base)})")
                if f0.date < rq:
                    V(f"{tag} salary: first projected {f0.date} < request_date {rq}")
                if f0.date <= base.settlement_date:
                    V(f"{tag} salary: first projected {f0.date} <= last settled payroll {base.settlement_date}")
                for k, f in enumerate(sal_flows[1:], 1):
                    if not same_dom(dom_settle, f.date):
                        V(f"{tag} salary: flow {k} {f.date} not on DOM {dom_settle}")
            if dom_settle >= 29:
                I(f"{tag} salary DOM {dom_settle} (month-end): flows={[f.date.isoformat() for f in sal_flows]}")
            months = Counter((f.date.year, f.date.month) for f in sal_flows)
            for ym, n in months.items():
                if n > 1:
                    V(f"{tag} salary: {n} salary flows in month {ym}")
        # history day constancy
        days = Counter(e.settlement_date.day for e in primary)
        if len(days) > 1:
            I(f"{tag} salary history DOMs not constant: {dict(days)} rows={[(e.description[:20], e.settlement_date.isoformat()) for e in primary]}")
    else:
        counts["no_regular_salary"] += 1
        I(f"{tag} salary: no regular payroll history and no scheduled row; income flows={[(f.date.isoformat(), round(f.amount,2), f.label) for f in st.flows if f.kind=='income'][:4]}")

    # freelance / gig
    for label, names in (("freelance income", FREELANCE_INCOME), ("gig payout", GIG_INCOME)):
        rows = sorted([e for e in events if e.status == "settled" and e.direction == "credit" and e.category == "salary" and e.description in names], key=lambda e: e.settlement_date)
        fl = sorted([f for f in st.flows if f.kind == "income" and f.label == label], key=lambda f: f.date)
        if len(rows) >= 3:
            counts[label] += 1
            gaps = [(rows[i + 1].settlement_date - rows[i].settlement_date).days for i in range(len(rows) - 1)]
            step = max(1, int(round(statistics.median(gaps))))
            if fl:
                t = rows[-1].settlement_date + timedelta(days=step)
                while t <= rq:
                    t += timedelta(days=step)
                if fl[0].date != t:
                    V(f"{tag} {label}: first {fl[0].date} != expected {t} (step {step}, last {rows[-1].settlement_date})")
                for a, b in zip(fl, fl[1:]):
                    if (b.date - a.date).days != step:
                        V(f"{tag} {label}: gap {a.date}->{b.date} != step {step}")
                mean_amt = statistics.mean(ds.convert(sb.amount_of(e), e.currency, home, e.settlement_date) for e in rows)
                if abs(fl[0].amount - mean_amt) > 0.01:
                    V(f"{tag} {label}: amount {fl[0].amount:.2f} != mean {mean_amt:.2f}")
                I(f"{tag} {label}: step={step} gaps={gaps} n={len(rows)} first={fl[0].date} amt={fl[0].amount:.2f}")
            else:
                I(f"{tag} {label}: {len(rows)} rows but not projected; notes={[n for n in st.notes if 'not projected' in n]}")

    # ---------------- monthly debit series -----------------
    linked_targets = {e.linked_event_id for e in events if e.linked_event_id}
    hist_by_cat: dict[str, list] = defaultdict(list)
    for e in events:
        if e.status != "settled" or e.direction != "debit":
            continue
        if e.event_type in NON_RECURRING_TYPES or e.category in NON_RECURRING_CATEGORIES:
            continue
        if e.linked_event_id or e.event_id in linked_targets:
            continue
        if e.amount_source != "csv":
            continue
        hist_by_cat[e.category].append(e)
    # known (pending/scheduled) debit rows by category
    known_rows = [e for e in events if e.status in ("pending", "scheduled") and e.direction == "debit"]
    known_flow_labels = {f.label for f in st.flows if f.kind == "known_debit"}
    series_by_cat = {s.category: s for s in st.series}

    for cat, rows in hist_by_cat.items():
        rows.sort(key=lambda e: e.settlement_date)
        if len(rows) < 3:
            continue
        dates = [e.settlement_date for e in rows]
        gaps = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
        per = statistics.median(gaps)
        s = series_by_cat.get(cat)
        if per > 45:
            if s:
                V(f"{tag} {cat}: median gap {per} > 45 but series exists")
            else:
                I(f"{tag} {cat}: median gap {per} > 45 -> no series (n={len(rows)} dates={[d.isoformat() for d in dates]})")
            continue
        if s is None:
            V(f"{tag} {cat}: {len(rows)} history rows, median gap {per}, but no series built")
            continue
        if per < 28:
            continue  # periodic series are out of scope for this audit
        counts["monthly_series"] += 1
        # history DOM constancy (allow month-end clamp)
        doms = Counter(d.day for d in dates)
        modal = doms.most_common(1)[0][0]
        eom_ok = all(d.day == modal or (d.day == eom(d) and modal > eom(d)) for d in dates)
        if not eom_ok:
            V(f"{tag} {cat}: MIXED history DOMs {dict(doms)} dates={[d.isoformat() for d in dates]} -> projected {[d.isoformat() for d in s.dates]}")
            counts["mixed_dom_series"] += 1
        else:
            # projections on the same DOM
            for d in s.dates:
                if not same_dom(modal, d):
                    V(f"{tag} {cat}: projected {d} not on history DOM {modal}")
        if s.dates:
            if s.dates[0] < rq:
                V(f"{tag} {cat}: first projected {s.dates[0]} < request_date {rq}")
            # first projected should be the first modal-DOM date >= rq that is after the last history row
            t = add_months(dates[-1], 1)
            while t < rq:
                t = add_months(t, 1)
            if s.dates[0] != t:
                V(f"{tag} {cat}: first projected {s.dates[0]} != expected {t} (last hist {dates[-1]})")
            if s.dates[0] <= dates[-1]:
                V(f"{tag} {cat}: first projected {s.dates[0]} <= last history {dates[-1]}")
            # gap between last history row and first projection: if > 45 days the series may have lapsed / month missed
            gap0 = (s.dates[0] - dates[-1]).days
            if gap0 > 40:
                I(f"{tag} {cat}: {gap0} days between last history {dates[-1]} and first projection {s.dates[0]} (rq={rq}); a month between them was skipped")
            # occurrence of the series ON request_date?
            if s.dates[0] == rq:
                I(f"{tag} {cat}: projected occurrence on request_date {rq} (counted)")
        else:
            V(f"{tag} {cat}: series built but no projected dates")
        # month-end rolling
        if modal >= 29:
            counts["eom_series"] += 1
            I(f"{tag} {cat}: history DOM {modal} (month-end) -> projected {[d.isoformat() for d in s.dates]}")
        # amount check
        amts = [ds.convert(sb.amount_of(e), e.currency, home, e.settlement_date) for e in rows]
        constant = max(amts) - min(amts) < 0.005
        mean_amt = statistics.mean(amts)
        if constant:
            rent_pct = 0.0
            for a in user_adjs:
                if a["adjustment_type"] == "expense_increase_percent" and a.get("percent") and (a.get("target") == "rent" or str(a.get("template_id") or "").startswith("T19")):
                    rent_pct = max(rent_pct, float(a["percent"]))
            exp = amts[0] * (1 + rent_pct / 100.0) if cat == "rent" else amts[0]
            if abs(s.amount - exp) > 0.01:
                V(f"{tag} {cat}: constant history {amts[0]:.2f} but series amount {s.amount:.2f} (rent_pct={rent_pct})")
        else:
            if abs(s.amount - mean_amt) > 0.01:
                # nominal-from-minimum path?
                I(f"{tag} {cat}: variable history mean {mean_amt:.2f} (min {min(amts):.2f} max {max(amts):.2f}) -> series amount {s.amount:.2f} (nominal-from-minimum? min_allowed={s.minimum_allowed_amount})")
            else:
                I(f"{tag} {cat}: variable monthly history mean {mean_amt:.2f} (min {min(amts):.2f} max {max(amts):.2f}) used")
        # duplicates against pending/scheduled rows in the same category
        for k in known_rows:
            if k.category != cat:
                continue
            ksd = max(k.settlement_date or k.event_date, rq)
            kamt = sb.amount_of(k)
            near = [d for d in s.dates if abs((d - ksd).days) <= 20]
            same_month = [d for d in s.dates if (d.year, d.month) == (ksd.year, ksd.month)]
            counts["known_row_same_cat_as_series"] += 1
            V(f"{tag} {cat}: POSSIBLE DOUBLE COUNT: {k.status} row {k.event_id} '{k.description}' {kamt} {k.currency} on {ksd} (in flows={k.description in known_flow_labels}) + series '{s.description}' {s.amount:.2f} projected {[d.isoformat() for d in s.dates]}; same-month={[d.isoformat() for d in same_month]} within20d={[d.isoformat() for d in near]}; history={[(d.isoformat(), round(a,2)) for d,a in zip(dates[-4:], amts[-4:])]}")
    # known rows in categories without a series (informational)
    for k in known_rows:
        if k.category not in series_by_cat:
            hist = hist_by_cat.get(k.category, [])
            I(f"{tag} known {k.status} row {k.event_id} '{k.description}' {sb.amount_of(k)} {k.currency} cat={k.category} on {k.settlement_date}; no series in that category (history n={len(hist)})")

print("=== COUNTS ===")
for k, v in sorted(counts.items()):
    print(f"{k}: {v}")
print(f"\n=== VIOLATIONS ({len(viol)}) ===")
for v in viol:
    print("*", v)
print(f"\n=== INFO ({len(info)}) ===")
for v in info:
    print("-", v)
