"""Print the reconstructed state and daily projection for one request.

Run:  python code/debug_request.py request_21 [--llm] [--horizon N] [--sample]
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import Dataset  # noqa: E402
from forecast import daily_balances  # noqa: E402
from pipeline import load_adjustments, load_image_amounts  # noqa: E402
from planner import decide  # noqa: E402
from state import HORIZON_DAYS, StateBuilder  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("request_id")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--horizon", type=int, default=HORIZON_DAYS)
    ap.add_argument("--days", type=int, default=45, help="how many projected days to print")
    args = ap.parse_args()
    ds = Dataset()
    reqs = {r.request_id: r for r in ds.load_requests("sample_requests.csv")}
    reqs.update({r.request_id: r for r in ds.load_requests("requests.csv")})
    req = reqs[args.request_id]
    prof = ds.profiles[req.user_id]
    print(f"{req.request_id} {req.user_id} date={req.request_date} amount={req.requested_amount} by={req.desired_completion_date} partial={req.allows_partial_payment}")
    print(f"  balance={prof.current_available_balance} min={prof.minimum_balance_to_keep} headroom={prof.current_available_balance - prof.minimum_balance_to_keep:.2f} methods={prof.methods} max_m={prof.max_installment_months}")
    print(f"  protect={prof.protect} reduce={prof.reduce} stop={prof.stop}")
    if req.expected:
        print("  EXPECTED:", {k: v for k, v in req.expected.items() if k != "decision_explanation"})
    for m in ds.messages_by_user.get(req.user_id, []):
        print(f"  message {m.message_id} [{m.source_type}] {m.sent_at.date()} ev={m.related_event_id}: {m.message_text[:160]}")
    builder = StateBuilder(ds, load_image_amounts(ds, args.llm), load_adjustments(ds, args.llm), horizon_days=args.horizon)
    for a in builder.adjustments.get(req.user_id, []):
        print(f"  adjustment: {a['adjustment_type']} scope={a.get('scope')} amount={a.get('amount')} {a.get('currency')} date={a.get('effective_date')} pct={a.get('percent')} reg={a.get('regular_salary_amount')} tmpl={a.get('template_id')}")
    st = builder.build(req)
    for n in st.notes:
        print("  note:", n)
    print("  known flows:")
    for f in sorted(st.flows, key=lambda f: f.date):
        print(f"    {f.date} {f.amount:14.2f} {f.kind:12s} {f.label}")
    print("  series:")
    for s in st.series:
        print(f"    {s.category:18s} {s.cadence:8s} step={s.step_days:3d} n={s.n_hist:2d} amt={s.amount:12.2f} flex={s.flexibility:22s} min={s.minimum_allowed_amount} latest={s.latest_event_id} next={[d.isoformat() for d in s.dates[:4]]}")
    print("  history by category (settled debits, last 6 rows each):")
    hist = defaultdict(list)
    for e in ds.events_by_user[req.user_id]:
        if e.status == "settled" and e.direction == "debit":
            hist[e.category].append(e)
    for cat, evs in sorted(hist.items()):
        evs.sort(key=lambda e: e.settlement_date)
        print(f"    {cat:18s} " + ", ".join(f"{e.settlement_date.isoformat()[5:]}:{(e.amount if e.amount is not None else builder.image_amounts.get(e.event_id))}" for e in evs[-8:]))
    dec = decide(st, ds.options_by_request.get(req.request_id, []))
    print(f"  safe={dec.safe_amount} earliest={dec.earliest} -> {dec.plan.method}/{dec.plan.status} plan={dec.plan.plan_string()} changes={dec.plan.changes_string()}")
    for c in dec.candidates:
        print(f"    cand {c.method:16s} deadline={c.completes_by_deadline} changes={len(c.changes)} total={c.total_paid:.2f} start={c.start} n={len(c.payments)}")
    print("  daily projection (days with flows):")
    net = defaultdict(list)
    for f in st.all_flows():
        if st.request_date <= f.date <= st.horizon_end:
            net[f.date].append(f)
    for d, b in daily_balances(st)[: args.days]:
        if d in net or d == st.request_date:
            items = ", ".join(f"{f.label}:{f.amount:+.2f}" for f in net.get(d, []))
            flag = " <-- below min" if b < st.min_balance else ""
            print(f"    {d} {b:14.2f}  {items}{flag}")


if __name__ == "__main__":
    main()
