"""Boundary sensitivity of the 250 hidden-set decisions to the variable-spend block.

Runs the engine with state.OPTIONS["variable_scale"] at 1.0 (baseline, verified against
output.csv), 0.97 and 1.03, lists every request whose decision columns flip, finds the
flip threshold per request by a fine scan, and for each flipped request identifies the
driving series and the margin of the failing/passing check.

Run: .venv/Scripts/python code/notes/improve3/sensitivity_sweep.py
Writes: code/notes/improve3/sweep_results.json and debug_<request>_<scale>.txt
"""
from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))

from data import Dataset  # noqa: E402
from forecast import daily_balances, trough  # noqa: E402
from pipeline import load_adjustments, load_image_amounts, run  # noqa: E402
from planner import decide  # noqa: E402
from state import Flow, StateBuilder  # noqa: E402

OUT = Path(__file__).resolve().parent
COLS = ["affordability_status", "recommended_payment_method", "payment_plan", "earliest_date_for_full_payment", "spending_changes_needed"]
SIX = ["amount_safe_to_pay"] + COLS


def key6(row: dict, requested: float) -> tuple:
    safe = float(row["amount_safe_to_pay"])
    edge = "zero" if safe <= 0 else ("full" if abs(safe - requested) < 1e-6 else "mid")
    return tuple(row[c] for c in COLS) + (edge,)


def main():
    ds = Dataset()
    reqs = ds.load_requests("requests.csv")
    req_amt = {r.request_id: r.requested_amount for r in reqs}
    images = load_image_amounts(ds, True)
    adjs = load_adjustments(ds, True)

    def run_scale(s):
        return {d.request.request_id: (d, row) for d, row in run(reqs, ds, use_llm=True, options={"variable_scale": s})}

    base = run_scale(1.0)
    # 1. verify baseline == output.csv on the six decision columns
    with open(ROOT / "output.csv", encoding="utf-8", newline="") as f:
        shipped = {r["request_id"]: r for r in csv.DictReader(f)}
    bad = [rid for rid, r in shipped.items() if any(r[c] != base[rid][1][c] for c in SIX)]
    print(f"baseline vs output.csv: {len(shipped)} rows, {len(bad)} mismatches {bad[:5]}")

    lo, hi = run_scale(0.97), run_scale(1.03)
    flips = {}
    for rid in base:
        kb = key6(base[rid][1], req_amt[rid])
        d = {}
        for name, res in (("0.97", lo), ("1.03", hi)):
            if key6(res[rid][1], req_amt[rid]) != kb:
                d[name] = res[rid][1]
        if d:
            flips[rid] = d
    print(f"flips at 0.97: {sum('0.97' in v for v in flips.values())}, at 1.03: {sum('1.03' in v for v in flips.values())}, union {len(flips)}")

    # 2. fine scan for the flip threshold (smallest |s-1| that changes any decision column)
    scales = [round(1 + k * 0.0025, 4) for k in range(-40, 41) if k != 0]
    thresh = {rid: None for rid in base}
    for s in sorted(scales, key=lambda x: abs(x - 1)):
        res = run_scale(s)
        for rid in base:
            if thresh[rid] is None and key6(res[rid][1], req_amt[rid]) != key6(base[rid][1], req_amt[rid]):
                thresh[rid] = s
    n1 = sum(1 for v in thresh.values() if v is not None and abs(v - 1) <= 0.01 + 1e-9)
    n3 = sum(1 for v in thresh.values() if v is not None and abs(v - 1) <= 0.03 + 1e-9)
    n10 = sum(1 for v in thresh.values() if v is not None)
    print(f"flip threshold within 1%: {n1}, within 3%: {n3}, within 10%: {n10}")

    # 3. per-flip diagnostics
    def build(rid, s):
        b = StateBuilder(ds, images, adjs, options={"variable_scale": s})
        req = next(r for r in reqs if r.request_id == rid)
        st = b.build(req)
        return st, decide(st, ds.options_by_request.get(rid, []))

    def variable_block(st_base, st_hi):
        hi_amt = {x.latest_event_id: x.amount for x in st_hi.series}
        var = [x for x in st_base.series if abs(hi_amt.get(x.latest_event_id, x.amount) - x.amount) > 1e-9]
        return var, sum(x.amount * len(x.dates) for x in var)

    def check_margins(st, dec):
        """Margins (currency) of the checks that decide the columns."""
        req = st.request
        out = {}
        pay_full = [Flow(st.request_date, -req.requested_amount, "payment", "payment")]
        bal = daily_balances(st, pay_full)
        tmin = min(bal, key=lambda x: x[1])
        out["full_today_margin"] = tmin[1] - st.min_balance
        out["full_today_trough_date"] = tmin[0].isoformat()
        series = daily_balances(st)
        suf = [0.0] * len(series)
        m = float("inf")
        for i in range(len(series) - 1, -1, -1):
            m = min(m, series[i][1])
            suf[i] = m
        if dec.earliest is not None:
            i = [d for d, _ in series].index(dec.earliest)
            out["earliest"] = dec.earliest.isoformat()
            out["earliest_pass_margin"] = suf[i] - req.requested_amount - st.min_balance
            if i > 0:
                out["day_before_fail_margin"] = suf[i - 1] - req.requested_amount - st.min_balance
        else:
            out["earliest"] = None
            out["best_suffix_margin"] = max(suf) - req.requested_amount - st.min_balance
        p = dec.plan
        if p.payments:
            flows = [Flow(d, -a, "payment", "payment") for d, a in p.payments if d <= st.horizon_end]
            flows += [f for c in p.changes for f in c.flows()]
            b2 = daily_balances(st, flows)
            t2 = min(b2, key=lambda x: x[1])
            out["plan_margin"] = t2[1] - st.min_balance
            out["plan_trough_date"] = t2[0].isoformat()
            if p.changes:
                b3 = daily_balances(st, [Flow(d, -a, "payment", "payment") for d, a in p.payments if d <= st.horizon_end])
                out["plan_without_changes_margin"] = min(x for _, x in b3) - st.min_balance
        for c in dec.candidates:
            if c.method == "installments":
                flows = [Flow(d, -a, "payment", "payment") for d, a in c.payments if d <= st.horizon_end]
                flows += [f for x in c.changes for f in x.flows()]
                out[f"installments_opt{c.option.option_num}_margin"] = trough(st, flows) - st.min_balance
        return out

    def driving(st_base, st_hi, upto):
        var, _ = variable_block(st_base, st_hi)
        best = None
        for x in var:
            occ = [d for d in x.dates if d <= upto]
            if not occ:
                continue
            contrib = x.amount * len(occ)
            if best is None or contrib > best[0]:
                best = (contrib, x, occ)
        return best

    def dump(rid, s, st, dec, path):
        req = st.request
        lines = [f"{rid} {req.user_id} scale={s} date={req.request_date} amount={req.requested_amount} by={req.desired_completion_date} partial={req.allows_partial_payment}",
                 f"  balance={st.balance} min={st.min_balance} methods={st.profile.methods} max_m={st.profile.max_installment_months}",
                 "  series:"]
        for x in st.series:
            lines.append(f"    {x.category:18s} {x.cadence:8s} step={x.step_days:3d} n={x.n_hist:2d} amt={x.amount:12.2f} flex={x.flexibility:22s} min={x.minimum_allowed_amount} latest={x.latest_event_id} next={[d.isoformat() for d in x.dates[:4]]}")
        lines.append(f"  safe={dec.safe_amount} earliest={dec.earliest} -> {dec.plan.method}/{dec.plan.status} plan={dec.plan.plan_string()} changes={dec.plan.changes_string()}")
        for c in dec.candidates:
            lines.append(f"    cand {c.method:16s} deadline={c.completes_by_deadline} changes={len(c.changes)} total={c.total_paid:.2f} start={c.start} n={len(c.payments)}")
        lines.append("  daily projection (days with flows, no payment applied):")
        net = defaultdict(list)
        for f in st.all_flows():
            if st.request_date <= f.date <= st.horizon_end:
                net[f.date].append(f)
        for d, b in daily_balances(st):
            if d in net or d == st.request_date:
                items = ", ".join(f"{f.label}:{f.amount:+.2f}" for f in net.get(d, []))
                lines.append(f"    {d} {b:14.2f}  {items}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    diag = {}
    for rid, d in sorted(flips.items(), key=lambda kv: int(kv[0].split("_")[1])):
        st0, dec0 = build(rid, 1.0)
        st_hi, _ = build(rid, 1.03)
        var, block = variable_block(st0, st_hi)
        m0 = check_margins(st0, dec0)
        entry = {"requested": req_amt[rid], "min_balance": st0.min_balance, "balance": st0.balance,
                 "variable_block": block, "n_variable_series": len(var),
                 "baseline": {c: base[rid][1][c] for c in SIX}, "margins_base": m0, "threshold": thresh[rid], "scales": {}}
        dump(rid, 1.0, st0, dec0, OUT / f"debug_{rid}_1.00.txt")
        for s_name, row in d.items():
            s = float(s_name)
            st1, dec1 = build(rid, s)
            m1 = check_margins(st1, dec1)
            dump(rid, s, st1, dec1, OUT / f"debug_{rid}_{s:.2f}.txt")
            upto = None
            for k in ("full_today_trough_date", "plan_trough_date"):
                if k in m1:
                    dd = date.fromisoformat(m1[k])
                    upto = dd if upto is None else max(upto, dd)
            drv = driving(st0, st_hi, upto or st0.horizon_end)
            entry["scales"][s_name] = {
                "row": {c: row[c] for c in SIX}, "margins": m1,
                "driver": None if drv is None else {"category": drv[1].category, "amount_base": drv[1].amount, "amount_scaled": drv[1].amount * s,
                                                     "occurrences_upto": [x.isoformat() for x in drv[2]], "contrib_base": drv[0], "delta": drv[0] * (s - 1)},
            }
        diag[rid] = entry
        print(rid, "thr", thresh[rid], "base", [base[rid][1][c] for c in SIX], {k: [v["row"][c] for c in SIX] for k, v in entry["scales"].items()})

    near = {rid: thresh[rid] for rid in base if thresh[rid] is not None and abs(thresh[rid] - 1) <= 0.03 + 1e-9}
    json.dump({"baseline_mismatches": bad, "flips": diag, "thresholds": thresh, "near_boundary_3pct": near,
               "counts": {"within_1pct": n1, "within_3pct": n3, "within_10pct": n10}}, open(OUT / "sweep_results.json", "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
