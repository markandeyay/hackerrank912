import sys, json
from pathlib import Path
from datetime import date, timedelta
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "code"))
from data import Dataset, parse_date
from pipeline import load_adjustments, load_image_amounts
from state import StateBuilder, add_months
ds = Dataset(); images = load_image_amounts(ds, True); adjs = load_adjustments(ds, True)
reqs = ds.load_requests("sample_requests.csv") + ds.load_requests("requests.csv")
B1 = StateBuilder(ds, images, adjs); B0 = StateBuilder(ds, images, {})
def sal(st): return [(f.date.isoformat(), round(f.amount,2), f.label) for f in sorted(st.flows, key=lambda f: f.date) if f.kind in ('salary','income','known_credit')]
def creds(st): return [(f.date.isoformat(), round(f.amount,2), f.kind, f.label) for f in sorted(st.flows, key=lambda f: f.date) if f.amount > 0]
which = sys.argv[1]
for r in reqs:
    for a in adjs.get(r.user_id, []):
        if not (a.get('template_id') or '').startswith(which): continue
        st1 = B1.build(r); st0 = B0.build(r)
        prof = ds.profiles[r.user_id]
        salh = [e for e in ds.events_by_user[r.user_id] if e.category=='salary' and e.direction=='credit']
        salh.sort(key=lambda e: e.settlement_date or e.event_date)
        print(f"--- {r.request_id} {r.user_id} rq={r.request_date} home={prof.home_currency} msg={a['message_id']} sent={a['sent_at']} amt={a.get('amount')} {a.get('currency')} eff={a.get('effective_date')} scope={a.get('scope')} reg={a.get('regular_salary_amount')} pct={a.get('percent')}")
        print("   hist:", "; ".join(f"{e.description[:22]}:{e.amount if e.amount is not None else images.get(e.event_id)}{e.currency}@{e.settlement_date}({e.status[:4]})" for e in salh[-6:]))
        print("   WITH credits:", creds(st1))
        print("   W/O  credits:", creds(st0))
        print("   notes:", st1.notes)
        if which in ('T19',):
            for s in st1.series:
                if s.category=='rent': print("   rent series WITH:", s.amount, s.dates)
            for s in st0.series:
                if s.category=='rent': print("   rent series W/O :", s.amount, s.dates)
            rent=[e for e in ds.events_by_user[r.user_id] if e.category=='rent']; rent.sort(key=lambda e:e.settlement_date)
            print("   rent hist:", [(e.settlement_date.isoformat(), e.amount, e.status) for e in rent[-4:]])
        if which in ('T24','T25','T23','T18','T27','T28','T03','T32','T07','T17'):
            for e in ds.events_by_user[r.user_id]:
                if e.status in ('pending','scheduled','failed') or (e.linked_event_id and (e.settlement_date or e.event_date) >= r.request_date - timedelta(days=60)):
                    print(f"   ev {e.event_id}: {e.event_type}/{e.description} {e.direction} {e.amount} {e.currency} ev={e.event_date} sd={e.settlement_date} {e.status} linked={e.linked_event_id}")
            print("   debits WITH:", [(f.date.isoformat(), round(f.amount,2), f.label) for f in sorted(st1.flows, key=lambda f: f.date) if f.amount<0])
