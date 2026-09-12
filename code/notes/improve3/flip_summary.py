"""Compact per-flip summary for the sensitivity report (reads sweep_results.json, recomputes states)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))
from data import Dataset  # noqa: E402
from forecast import daily_balances  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from planner import decide  # noqa: E402
from state import Flow, StateBuilder  # noqa: E402

OUT = Path(__file__).resolve().parent
ds = Dataset()
reqs = {r.request_id: r for r in ds.load_requests("requests.csv")}
images, adjs = load_image_amounts(ds, True), load_adjustments(ds, True)
sw = json.load(open(OUT / "sweep_results.json"))
thr_real = json.load(open(OUT / "thresholds_real.json"))


def build(rid, s):
    st = StateBuilder(ds, images, adjs, options={"variable_scale": s}).build(reqs[rid])
    return st, decide(st, ds.options_by_request.get(rid, []))


def margins(st, dec):
    req = st.request
    R, M = req.requested_amount, st.min_balance
    out = {}
    out["full_today"] = min(b for _, b in daily_balances(st, [Flow(st.request_date, -R, "p", "p")])) - M
    ser = daily_balances(st)
    suf, m = [0.0] * len(ser), float("inf")
    for i in range(len(ser) - 1, -1, -1):
        m = min(m, ser[i][1])
        suf[i] = m
    if dec.earliest is not None:
        i = [d for d, _ in ser].index(dec.earliest)
        out["earliest_pass"] = suf[i] - R - M
        if i > 0:
            out["closest_earlier_miss"] = max(suf[:i]) - R - M
    else:
        out["best_suffix"] = max(suf) - R - M
    p = dec.plan
    if p.payments:
        pays = [Flow(d, -a, "p", "p") for d, a in p.payments if d <= st.horizon_end]
        chg = [f for c in p.changes for f in c.flows()]
        b2 = daily_balances(st, pays + chg)
        t2 = min(b2, key=lambda x: x[1])
        out["plan"] = t2[1] - M
        out["plan_trough"] = t2[0]
        if p.changes:
            out["plan_no_changes"] = min(b for _, b in daily_balances(st, pays)) - M
    for c in dec.candidates:
        if c.method == "installments" and c is not p:
            pays = [Flow(d, -a, "p", "p") for d, a in c.payments if d <= st.horizon_end]
            out[f"inst{c.option.option_num}"] = min(b for _, b in daily_balances(st, pays + [f for x in c.changes for f in x.flows()])) - M
    return out


def outcome(row):
    return f"{row['affordability_status']}/{row['recommended_payment_method']}; earliest={row['earliest_date_for_full_payment'] or '-'}; changes={row['spending_changes_needed']}; safe={row['amount_safe_to_pay']}"


lines = []
for rid, e in sw["flips"].items():
    b = e["baseline"]
    if b["recommended_payment_method"] == "partial_payment" and all(v["row"]["earliest_date_for_full_payment"] == b["earliest_date_for_full_payment"] for v in e["scales"].values()):
        continue
    st0, dec0 = build(rid, 1.0)
    st_hi, _ = build(rid, 1.03)
    hi_amt = {x.latest_event_id: x.amount for x in st_hi.series}
    var = [x for x in st0.series if abs(hi_amt.get(x.latest_event_id, x.amount) - x.amount) > 1e-9]
    block = sum(x.amount * len(x.dates) for x in var)
    m0 = margins(st0, dec0)
    # binding check: smallest |margin| among the decision checks at baseline
    cand = {k: v for k, v in m0.items() if isinstance(v, float)}
    bind = min(cand, key=lambda k: abs(cand[k]))
    trough_d = m0.get("plan_trough", st0.horizon_end)
    drv = max(var, key=lambda x: x.amount * len([d for d in x.dates if d <= trough_d]), default=None)
    n_occ = len([d for d in drv.dates if d <= trough_d]) if drv else 0
    s97 = e["scales"].get("0.97", {}).get("row")
    s103 = e["scales"].get("1.03", {}).get("row")
    m97 = margins(*build(rid, 0.97)) if s97 else {}
    m103 = margins(*build(rid, 1.03)) if s103 else {}
    lines.append({
        "rid": rid, "thr": thr_real[rid], "cur": st0.home, "req": st0.request.requested_amount, "min": st0.min_balance, "block": block,
        "base": outcome(b), "s97": outcome(s97) if s97 else "(same)", "s103": outcome(s103) if s103 else "(same)",
        "bind": bind, "bind_margin": cand[bind], "bind_pct": 100 * cand[bind] / block if block else None,
        "m0": {k: (round(v, 2) if isinstance(v, float) else str(v)) for k, v in m0.items()},
        "m97": {k: (round(v, 2) if isinstance(v, float) else str(v)) for k, v in m97.items()},
        "m103": {k: (round(v, 2) if isinstance(v, float) else str(v)) for k, v in m103.items()},
        "driver": f"{drv.category} {drv.amount:.2f} x{n_occ} (first {drv.dates[0]}, step {drv.step_days}d, {drv.flexibility})" if drv else "-",
        "driver_delta3": 0.03 * drv.amount * n_occ if drv else 0.0,
    })
json.dump(lines, open(OUT / "flip_summary.json", "w"), indent=1, default=str)
for L in lines:
    print(f"{L['rid']} thr={L['thr']} {L['cur']} req={L['req']} min={L['min']} block={L['block']:.2f} bind={L['bind']} margin={L['bind_margin']:.2f} ({L['bind_pct']:.2f}% of block) driver={L['driver']} d3%={L['driver_delta3']:.2f}")
    print(f"   base: {L['base']}\n   0.97: {L['s97']}\n   1.03: {L['s103']}")
    print(f"   m0={L['m0']}")
    if L['m97']: print(f"   m97={L['m97']}")
    if L['m103']: print(f"   m103={L['m103']}")
