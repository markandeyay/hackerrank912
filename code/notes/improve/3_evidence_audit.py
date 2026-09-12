"""Evidence application audit: build each request's state WITH and WITHOUT the
user's message adjustments and dump the diff plus template-specific checks.
Run: .venv/Scripts/python code/notes/improve/3_evidence_audit.py > code/notes/improve/3_evidence_audit_dump.txt
"""
from __future__ import annotations
import sys, json, copy
from pathlib import Path
from datetime import date, timedelta
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))
from data import Dataset, parse_date
from pipeline import load_adjustments, load_image_amounts
from state import StateBuilder, add_months
from forecast import daily_balances
from planner import decide

ds = Dataset()
images = load_image_amounts(ds, True)
adjs = load_adjustments(ds, True)
reqs = ds.load_requests("sample_requests.csv") + ds.load_requests("requests.csv")
by_user_req = {}
for r in reqs:
    by_user_req.setdefault(r.user_id, []).append(r)

msg_users = {m.user_id for m in ds.messages}
img_users = {im.user_id for im in ds.images}

def flows_key(st):
    return sorted((f.date.isoformat(), round(f.amount, 2), f.kind, f.label) for f in st.flows)

def series_key(st):
    return sorted((s.category, s.description, round(s.amount, 2), s.cadence, [d.isoformat() for d in s.dates]) for s in st.series)

def show(st):
    out = []
    for f in sorted(st.flows, key=lambda f: (f.date, f.label)):
        out.append(f"      {f.date} {f.amount:14.2f} {f.kind:12s} {f.label}")
    for s in st.series:
        out.append(f"      SERIES {s.category:16s} {s.cadence:8s} amt={s.amount:12.2f} n={s.n_hist} latest={s.latest_event_id} dates={[d.isoformat() for d in s.dates]}")
    return "\n".join(out)

records = []
for r in reqs:
    if r.user_id not in msg_users and r.user_id not in img_users:
        continue
    b_with = StateBuilder(ds, images, adjs)
    b_without = StateBuilder(ds, images, {})
    st1 = b_with.build(r)
    st0 = b_without.build(r)
    d1 = decide(st1, ds.options_by_request.get(r.request_id, []))
    d0 = decide(st0, ds.options_by_request.get(r.request_id, []))
    msgs = ds.messages_by_user.get(r.user_id, [])
    ims = ds.images_by_user.get(r.user_id, [])
    print("=" * 100)
    print(f"{r.request_id} {r.user_id} request_date={r.request_date} amount={r.requested_amount} by={r.desired_completion_date} home={st1.home} bal={st1.balance} min={st1.min_balance}")
    if r.expected:
        print("   EXPECTED:", {k: v for k, v in r.expected.items() if k != 'decision_explanation'})
    for m in msgs:
        print(f"   MSG {m.message_id} req={m.request_id} ev={m.related_event_id} sent={m.sent_at.date()} [{m.source_type}]: {m.message_text[:200]}")
        if m.related_event_id:
            e = ds.events[m.related_event_id]
            print(f"      linked event {e.event_id}: {e.event_type}/{e.description} {e.direction} {e.amount} {e.currency} ev={e.event_date} sd={e.settlement_date} {e.status} linked={e.linked_event_id}")
    for im in ims:
        e = ds.events.get(im.related_event_id)
        print(f"   IMG {im.image_id} req={im.request_id} ev={im.related_event_id} -> {e.description if e else None} {e.direction if e else ''} csv_amount={e.amount if e else None} {e.currency if e else ''} sd={e.settlement_date if e else None} {e.status if e else ''} image_amount={images.get(im.related_event_id)}")
    for a in adjs.get(r.user_id, []):
        print(f"   ADJ {a['message_id']} type={a['adjustment_type']} model_type={a.get('model_adjustment_type')} src={a.get('source')} tmpl={a.get('template_id')} scope={a.get('scope')} target={a.get('target')} amount={a.get('amount')} {a.get('currency')} date={a.get('effective_date')} pct={a.get('percent')} reg={a.get('regular_salary_amount')} sent={a.get('sent_at')}")
    # salary history
    sal = [e for e in ds.events_by_user[r.user_id] if e.category == 'salary' and e.direction == 'credit']
    sal.sort(key=lambda e: (e.settlement_date or e.event_date))
    print("   salary history:", "; ".join(f"{e.event_id}:{e.description}:{e.amount if e.amount is not None else images.get(e.event_id)}{e.currency}@{e.settlement_date}({e.status})" for e in sal[-8:]))
    rent = [e for e in ds.events_by_user[r.user_id] if e.category == 'rent']
    rent.sort(key=lambda e: (e.settlement_date or e.event_date))
    if rent:
        print("   rent history:", "; ".join(f"{e.event_id}:{e.amount}@{e.settlement_date}({e.status})" for e in rent[-6:]))
    pend = [e for e in ds.events_by_user[r.user_id] if e.status in ('pending', 'scheduled', 'failed')]
    for e in pend:
        print(f"   open event {e.event_id}: {e.event_type}/{e.description} {e.direction} {e.amount if e.amount is not None else images.get(e.event_id)} {e.currency} ev={e.event_date} sd={e.settlement_date} {e.status} linked={e.linked_event_id}")
    changed = flows_key(st1) != flows_key(st0) or series_key(st1) != series_key(st0)
    print(f"   CHANGED={changed}  decision with={d1.safe_amount}/{d1.plan.method}/{d1.plan.status}/{d1.earliest}  without={d0.safe_amount}/{d0.plan.method}/{d0.plan.status}/{d0.earliest}")
    print("   notes WITH:", st1.notes)
    print("   notes WITHOUT:", st0.notes)
    print("   state WITH:")
    print(show(st1))
    if changed:
        print("   state WITHOUT:")
        print(show(st0))
    records.append({
        "request_id": r.request_id, "user_id": r.user_id, "request_date": r.request_date.isoformat(),
        "messages": [m.message_id for m in msgs], "images": [im.image_id for im in ims],
        "adjs": [{k: v for k, v in a.items() if k != 'summary'} for a in adjs.get(r.user_id, [])],
        "changed": changed,
        "with": {"safe": d1.safe_amount, "method": d1.plan.method, "status": d1.plan.status, "earliest": str(d1.earliest), "notes": st1.notes,
                 "flows": flows_key(st1), "series": series_key(st1)},
        "without": {"safe": d0.safe_amount, "method": d0.plan.method, "status": d0.plan.status, "earliest": str(d0.earliest), "notes": st0.notes,
                    "flows": flows_key(st0), "series": series_key(st0)},
    })
json.dump(records, open(ROOT / "code/notes/improve/3_evidence_audit_records.json", "w"), indent=1, default=str)
print("N records", len(records))
