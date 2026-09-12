"""Distribution and outlier review of output.csv (subagent 4).

Run:  .venv/Scripts/python code/notes/improve/4_outliers.py [--out DIR]
Writes a text dump per flag to DIR (default: scratch) and prints the tables.
Read-only with respect to the engine.
"""
from __future__ import annotations

import argparse
import csv
import itertools
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))

from data import Dataset  # noqa: E402
from forecast import daily_balances, is_safe, trough  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from planner import decide, spending_change_candidates  # noqa: E402
from state import Flow, StateBuilder  # noqa: E402


def pct(n, d):
    return f"{n} ({100.0 * n / d:.0f}%)" if d else "0"


def table(title, rows, cols):
    print(f"\n### {title}\n")
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join(str(x) for x in r) + " |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    ds = Dataset()
    out_rows = {r["request_id"]: r for r in csv.DictReader(open(ROOT / "output.csv", encoding="utf-8"))}
    sample = {r["request_id"]: r for r in csv.DictReader(open(ROOT / "dataset/sample_requests.csv", encoding="utf-8"))}
    reqs = {r.request_id: r for r in ds.load_requests("requests.csv")}
    assert set(reqs) == set(out_rows), "output/request mismatch"

    # ---------------- distribution ----------------
    print("## 1. Distribution\n")
    for col in ("affordability_status", "recommended_payment_method"):
        c_out = Counter(r[col] for r in out_rows.values())
        c_s = Counter(r[col] for r in sample.values())
        keys = sorted(set(c_out) | set(c_s))
        table(col, [(k, pct(c_out[k], 250), pct(c_s[k], 25)) for k in keys], ["value", "output (250)", "samples (25)"])
    combo = Counter((r["affordability_status"], r["recommended_payment_method"]) for r in out_rows.values())
    table("status x method (output)", [(s, m, n) for (s, m), n in sorted(combo.items())], ["status", "method", "n"])

    def breakdown(name, keyf):
        groups = defaultdict(list)
        for rid, r in out_rows.items():
            groups[keyf(rid)].append(r["recommended_payment_method"])
        rows = []
        for k in sorted(groups, key=lambda x: str(x)):
            c = Counter(groups[k])
            rows.append((k, len(groups[k]), c["full_payment"], c["partial_payment"], c["installments"], c["wait"], c["not_recommended"]))
        table(f"by {name}", rows, [name, "n", "full", "partial", "instal", "wait", "not_rec"])

    breakdown("request_type", lambda rid: reqs[rid].request_type)
    breakdown("currency", lambda rid: ds.profiles[reqs[rid].user_id].home_currency)
    breakdown("methods accepted", lambda rid: "|".join(ds.profiles[reqs[rid].user_id].methods))
    breakdown("allows_partial_payment", lambda rid: reqs[rid].allows_partial_payment)

    def days_bucket(rid):
        d = (reqs[rid].desired_completion_date - reqs[rid].request_date).days
        for lo, hi in ((0, 30), (31, 60), (61, 90), (91, 180), (181, 10**6)):
            if lo <= d <= hi:
                return f"{lo:03d}-{hi if hi < 10**6 else 'inf'}"
        return "?"

    breakdown("days to desired_completion_date", days_bucket)

    # ---------------- engine states ----------------
    builder = StateBuilder(ds, load_image_amounts(ds, True), load_adjustments(ds, True))
    flagged: dict[str, list[str]] = defaultdict(list)
    detail: dict[str, list[str]] = defaultdict(list)
    counts = Counter()
    later_past_deadline = []
    outdir = Path(args.out) if args.out else None
    if outdir:
        outdir.mkdir(parents=True, exist_ok=True)

    def flag(rid, code, msg):
        flagged[rid].append(code)
        detail[rid].append(f"[{code}] {msg}")
        counts[code] += 1

    for rid in sorted(reqs, key=lambda x: int(x.split("_")[1])):
        req = reqs[rid]
        prof = ds.profiles[req.user_id]
        st = builder.build(req)
        opts = ds.options_by_request.get(rid, [])
        dec = decide(st, opts)
        o = out_rows[rid]
        # sanity: output.csv == engine
        if (o["recommended_payment_method"] != dec.plan.method or o["payment_plan"] != dec.plan.plan_string()
                or o["spending_changes_needed"] != dec.plan.changes_string()):
            flag(rid, "MISMATCH", f"output.csv {o['recommended_payment_method']}/{o['payment_plan']}/{o['spending_changes_needed']} vs engine {dec.plan.method}/{dec.plan.plan_string()}/{dec.plan.changes_string()}")
        headroom = prof.current_available_balance - prof.minimum_balance_to_keep
        requested = req.requested_amount
        safe = dec.safe_amount
        earliest = dec.earliest
        status, method = o["affordability_status"], o["recommended_payment_method"]
        bal = daily_balances(st)
        flows_by_day = defaultdict(list)
        for f in st.all_flows():
            if st.request_date <= f.date <= st.horizon_end:
                flows_by_day[f.date].append(f)
        income_days = {d for d, fs in flows_by_day.items() if any(f.amount > 0 and f.kind in ("salary", "income", "known_credit") for f in fs)}
        tr = trough(st)

        def flows_str(d):
            return "; ".join(f"{f.label}:{f.amount:+.2f}" for f in flows_by_day.get(d, [])) or "(no flows)"

        # a. not_affordable with big headroom
        if status == "not_affordable" and headroom > 2 * requested:
            flag(rid, "A_notaff_headroom", f"headroom={headroom:.2f} requested={requested} safe={safe} earliest={earliest} methods={prof.methods} trough={tr:.2f} min={st.min_balance} cands={[(c.method, c.completes_by_deadline, len(c.changes)) for c in dec.candidates]}")
        # b. affordable_now tight
        if status == "affordable_now":
            tr_pay = trough(st, [Flow(st.request_date, -requested, "payment", "payment")])
            if tr_pay - st.min_balance < 0.01 * st.min_balance:
                flag(rid, "B_now_tight", f"post-payment trough={tr_pay:.2f} min={st.min_balance} margin={tr_pay - st.min_balance:.2f}")
            if headroom < requested:
                flag(rid, "B_now_headroom_lt_req", f"headroom={headroom:.2f} < requested={requested}; income days before trough: {sorted(d.isoformat() for d in income_days)[:3]}")
        # c. wait/affordable_later: earliest on an income day?
        if method == "wait":
            if earliest not in income_days:
                flag(rid, "C_wait_not_income_day", f"earliest={earliest} flows that day: {flows_str(earliest)}; income days={sorted(d.isoformat() for d in income_days)}")
        # d. installments while full safe & accepted; full chosen while cheaper safe plan exists
        full_safe_today = is_safe(st, [(st.request_date, requested)])
        if method == "installments" and full_safe_today and "full_payment" in prof.methods:
            flag(rid, "D_instal_over_full", f"full safe today; cands={[(c.method, c.total_paid) for c in dec.candidates]}")
        if method == "full_payment":
            cheaper = [c for c in dec.candidates if c.total_paid < dec.plan.total_paid - 1e-6]
            if cheaper:
                flag(rid, "D_full_not_cheapest", f"cheaper cands={[(c.method, c.total_paid, c.completes_by_deadline, len(c.changes)) for c in cheaper]}")
        # e. earliest neither request_date nor income day
        if earliest is not None and earliest != st.request_date and earliest not in income_days:
            flag(rid, "E_earliest_not_income", f"earliest={earliest}: {flows_str(earliest)}; prev day bal={[b for d, b in bal if d == earliest]}")
        # f. safe == 0
        if safe == 0:
            nxt_inc = min((d for d in income_days if d >= st.request_date), default=None)
            debits = [(d.isoformat(), f.label, round(f.amount, 2)) for d, fs in sorted(flows_by_day.items()) for f in fs if f.amount < 0 and (nxt_inc is None or d < nxt_inc)]
            flag(rid, "F_safe_zero", f"headroom={headroom:.2f} trough={tr:.2f} min={st.min_balance} next income={nxt_inc} debits before it ({len(debits)}): {debits[:12]}")
        # g. partial second payment
        if method == "partial_payment":
            d2 = dec.plan.payments[1][0]
            if d2 not in income_days or d2 > req.desired_completion_date:
                flag(rid, "G_partial_date", f"second={d2} income_day={d2 in income_days} desired={req.desired_completion_date}: {flows_str(d2)}")
            else:
                detail[rid].append(f"[g-ok] partial second {d2} income day, desired {req.desired_completion_date}")
        # h. spending changes
        if dec.plan.changes:
            ch = dec.plan.changes
            cands = spending_change_candidates(st)
            pays = dec.plan.payments if dec.plan.method != "installments" else [(d, a) for d, a in dec.plan.payments if d <= st.horizon_end]
            pay_flows = [Flow(d, -a, "payment", "payment") for d, a in pays]
            # cheapest sufficient set: enumerate subsets up to len(ch) by total monthly saving
            best = None
            for k in range(1, len(ch) + 1):
                for sub in itertools.combinations(cands, k):
                    fl = pay_flows + [f for c in sub for f in c.flows()]
                    if trough(st, fl) + 1e-6 >= st.min_balance:
                        cost = sum(c.saving_per_occurrence * len(c.series.dates) for c in sub)
                        if best is None or (k, cost) < (best[0], best[1]):
                            best = (k, cost, [c.as_string() for c in sub])
                if best:
                    break
            chosen_cost = sum(c.saving_per_occurrence * len(c.series.dates) for c in ch)
            # latest event check
            latest_bad = []
            for c in ch:
                cat_rows = [e for e in ds.events_by_user[req.user_id] if e.status == "settled" and e.direction == "debit" and e.category == c.series.category and e.description == c.series.description]
                cat_rows.sort(key=lambda e: (e.settlement_date, e.event_id))
                if cat_rows and cat_rows[-1].event_id != c.series.latest_event_id:
                    latest_bad.append((c.series.latest_event_id, cat_rows[-1].event_id))
            msg = f"chosen={[c.as_string() for c in ch]} saving={chosen_cost:.2f}; cheapest-sufficient={best}; latest_id_mismatch={latest_bad}"
            if latest_bad or (best and (best[0] < len(ch) or best[1] < chosen_cost - 1e-6)):
                flag(rid, "H_changes", msg)
            else:
                detail[rid].append("[h-ok] " + msg)
        # i. affordable_later past deadline
        if status == "affordable_later" and earliest and earliest > req.desired_completion_date:
            later_past_deadline.append((rid, earliest.isoformat(), req.desired_completion_date.isoformat()))
            flag(rid, "I_later_past_deadline", f"earliest={earliest} > desired={req.desired_completion_date}")
        # j. salary zero with regular payroll history
        regular_hist = [e for e in ds.events_by_user[req.user_id] if e.status == "settled" and e.category == "salary" and e.direction == "credit"]
        sal_flows = [f for f in st.flows if f.kind in ("salary", "income") and f.amount > 0]
        if regular_hist and not sal_flows:
            flag(rid, "J_no_salary", f"{len(regular_hist)} settled salary rows (last {max(e.settlement_date for e in regular_hist)}) but no projected income; notes={[n for n in st.notes if 'salary' in n or 'income' in n or 'projected' in n]}")
        # k. foreign currency
        home = prof.home_currency
        foreign = [e for e in ds.events_by_user[req.user_id] if e.currency != home and e.status in ("settled", "pending", "scheduled")]
        if foreign:
            fut = [e for e in foreign if (e.settlement_date or e.event_date) >= st.request_date and e.status in ("pending", "scheduled")]
            sal_foreign = [e for e in foreign if e.category == "salary" and e.status == "settled"]
            info = []
            for e in fut:
                amt = builder.amount_of(e)
                conv = builder.to_home(amt, e.currency, home, e.settlement_date) if amt is not None else None
                rate = ds.rates.get((e.settlement_date, e.currency, home)) or ds.rates.get((e.settlement_date, home, e.currency))
                info.append((e.event_id, e.description, amt, e.currency, e.settlement_date.isoformat(), round(conv, 2) if conv else None, rate))
            if sal_foreign:
                info.append(("salary_hist", len(sal_foreign), sal_foreign[-1].currency, st.salary_amount))
            flag(rid, "K_foreign", f"foreign rows={len(foreign)} future={info}")

        if outdir and rid in flagged:
            with open(outdir / f"{rid}.txt", "w", encoding="utf-8") as fh:
                fh.write(f"{rid} {req.user_id} {req.request_type} date={req.request_date} amount={requested} by={req.desired_completion_date} partial={req.allows_partial_payment}\n")
                fh.write(f"balance={prof.current_available_balance} min={prof.minimum_balance_to_keep} headroom={headroom:.2f} methods={prof.methods} max_m={prof.max_installment_months} protect={prof.protect} reduce={prof.reduce} stop={prof.stop}\n")
                fh.write(f"OUTPUT: {dict((k, v) for k, v in o.items() if k != 'decision_explanation')}\n")
                fh.write("flags:\n" + "\n".join("  " + d for d in detail[rid]) + "\n")
                fh.write("notes:\n" + "\n".join("  " + n for n in st.notes) + "\n")
                fh.write("flows:\n" + "\n".join(f"  {f.date} {f.amount:14.2f} {f.kind:12s} {f.label}" for f in sorted(st.flows, key=lambda f: f.date)) + "\n")
                fh.write("series:\n" + "\n".join(f"  {s.category:18s} {s.cadence:8s} step={s.step_days:3d} n={s.n_hist:2d} amt={s.amount:12.2f} flex={s.flexibility:22s} min={s.minimum_allowed_amount} latest={s.latest_event_id} next={[d.isoformat() for d in s.dates[:4]]}" for s in st.series) + "\n")
                fh.write(f"safe={safe} earliest={earliest} -> {dec.plan.method}/{dec.plan.status} plan={dec.plan.plan_string()} changes={dec.plan.changes_string()}\n")
                for c in dec.candidates:
                    fh.write(f"  cand {c.method:16s} deadline={c.completes_by_deadline} changes={len(c.changes)} total={c.total_paid:.2f} start={c.start} n={len(c.payments)}\n")
                fh.write("projection (days with flows):\n")
                for d, b in bal:
                    if d in flows_by_day or d == st.request_date:
                        fh.write(f"  {d} {b:14.2f}  {flows_str(d)}{' <-- below min' if b < st.min_balance else ''}\n")

    print("\n## 2. Flags\n")
    table("flag counts", sorted(counts.items()), ["flag", "n"])
    print(f"\nrows flagged: {len(flagged)} / 250")
    for rid in sorted(flagged, key=lambda x: int(x.split('_')[1])):
        print(f"\n{rid}: " + " ".join(flagged[rid]))
        for d in detail[rid]:
            print("   " + d)
    print(f"\naffordable_later past deadline: {len(later_past_deadline)} {later_past_deadline}")


if __name__ == "__main__":
    main()
