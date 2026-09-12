"""Edge-case sweep over the 250 hidden requests (read-only; engine untouched).

Run from the repo root:  .venv/Scripts/python code/notes/improve3/4_edge_cases.py
"""
import sys, csv
from collections import Counter
sys.path.insert(0, 'code')
from data import Dataset, parse_date
from pipeline import load_image_amounts, load_adjustments
from state import StateBuilder, REGULAR_SALARY, FREELANCE_INCOME, GIG_INCOME
import planner
from planner import decide

ds = Dataset()
reqs = ds.load_requests('requests.csv')
adjs = load_adjustments(ds, True)
images = load_image_amounts(ds, True)
builder = StateBuilder(ds, images, adjs)
out_rows = {r['request_id']: r for r in csv.DictReader(open('output.csv', encoding='utf-8'))}
decs = {}
for r in reqs:
    st = builder.build(r)
    decs[r.request_id] = decide(st, ds.options_by_request.get(r.request_id, []))
print('built', len(decs))


def row(rid):
    o = out_rows[rid]
    return f"safe={o['amount_safe_to_pay']} status={o['affordability_status']} method={o['recommended_payment_method']} plan={o['payment_plan']} earliest={o['earliest_date_for_full_payment']!r} changes={o['spending_changes_needed']}"


def sal_flows(st):
    return sorted([f for f in st.flows if f.kind in ('salary', 'income')], key=lambda f: f.date)


def tmpl(uid):
    return [(a['message_id'], (a.get('template_id') or 'none')[:3], a['adjustment_type'], a.get('effective_date'), a.get('amount'), a.get('currency')) for a in adjs.get(uid, [])]


# consistency check: engine (in-process) vs output.csv
mism = []
for r in reqs:
    d = decs[r.request_id]; o = out_rows[r.request_id]
    if d.plan.method != o['recommended_payment_method'] or d.plan.plan_string() != o['payment_plan'] or d.plan.status != o['affordability_status']:
        mism.append(r.request_id)
print('output.csv vs in-process mismatches:', mism)

print('\n===== CASE 1: income ended / final payroll =====')
for r in reqs:
    uid = r.user_id; st = decs[r.request_id].state
    ended_msg = [t for t in tmpl(uid) if t[1] in ('T08', 'T16')]
    evs = [e for e in ds.events_by_user[uid] if e.category == 'salary' and e.status == 'settled' and e.description in REGULAR_SALARY]
    evs.sort(key=lambda e: e.settlement_date)
    final = bool(evs) and evs[-1].description == 'Final employer payroll'
    if ended_msg or final:
        sf = sal_flows(st)
        fl = [e for e in ds.events_by_user[uid] if e.category == 'salary' and e.status == 'settled' and e.description in FREELANCE_INCOME | GIG_INCOME]
        sched = [e for e in ds.events_by_user[uid] if e.category == 'salary' and e.status == 'scheduled']
        print(f"{r.request_id} {uid} msgs={[t[:2] for t in ended_msg]} final_payroll={final} last_regular={evs[-1].settlement_date if evs else None} freelance/gig_hist={len(fl)} scheduled_salary={[e.event_id for e in sched]}")
        print(f"   projected income flows={[(f.date.isoformat(), round(f.amount,2), f.label) for f in sf]}  notes={[n for n in st.notes if 'salary' in n or 'income' in n or 'payout' in n]}")
        print('   ', row(r.request_id), '| requested', r.requested_amount, 'headroom', round(st.balance - st.min_balance, 2))

print('\n===== CASE 2: first-salary messages T10/T11/T12 =====')
for r in reqs:
    uid = r.user_id; st = decs[r.request_id].state
    fs = [t for t in tmpl(uid) if t[1] in ('T10', 'T11', 'T12')]
    if not fs:
        continue
    sf = sal_flows(st)
    sched = [e for e in ds.events_by_user[uid] if e.category == 'salary' and e.status == 'scheduled']
    hist = [e for e in ds.events_by_user[uid] if e.category == 'salary' and e.status == 'settled']
    eff = fs[0][3]
    first = sf[0].date.isoformat() if sf else None
    ok = (first == eff) if eff and parse_date(eff) >= r.request_date else 'eff<rq'
    print(f"{r.request_id} {uid} rq={r.request_date} msg={fs} sched={[(e.event_id, e.settlement_date.isoformat(), e.amount) for e in sched]} settled_salary_hist={len(hist)} first_proj={first} amounts={[round(f.amount,2) for f in sf[:3]]} dates={[f.date.isoformat() for f in sf]} first==msg_date:{ok}")
    print('   ', row(r.request_id))

print('\n===== CASE 3: foreign-currency salary =====')
for r in reqs:
    uid = r.user_id; st = decs[r.request_id].state; home = st.home
    fx_rows = [e for e in ds.events_by_user[uid] if e.category == 'salary' and e.status in ('settled', 'scheduled') and e.currency != home]
    fx_msg = [t for t in tmpl(uid) if t[1] in ('T13', 'T22')]
    if not fx_rows and not fx_msg:
        continue
    sf = sal_flows(st)
    missing = []
    curs = {e.currency for e in fx_rows} | {t[5] for t in fx_msg if t[5] and t[5] != home}
    for cur in curs:
        for f in sf:
            if (f.date, cur, home) not in ds.rates and (f.date, home, cur) not in ds.rates:
                missing.append((f.date.isoformat(), cur))
    print(f"{r.request_id} {uid} home={home} fx_rows={[(e.event_id, e.description, e.status, e.currency, e.amount, e.settlement_date.isoformat()) for e in fx_rows][-3:]} msgs={fx_msg}")
    print(f"   proj income={[(f.date.isoformat(), round(f.amount,2), f.label) for f in sf]} no-exact-rate-dates={missing}")
    print('   ', row(r.request_id))

print('\n===== CASE 4: two-option requests =====')
two = [r for r in reqs if len(ds.options_by_request.get(r.request_id, [])) == 2]
print('count', len(two), Counter(len(ds.options_by_request.get(r.request_id, [])) for r in reqs))
for r in two:
    d = decs[r.request_id]; prof = ds.profiles[r.user_id]
    opts = ds.options_by_request[r.request_id]
    print(f"{r.request_id} {r.user_id} methods={prof.methods} max_m={prof.max_installment_months} opts={[(o.payment_option_id, o.payment_method, o.number_of_payments, o.first_payment_date.isoformat(), o.payment_frequency_days, o.total_payable_amount) for o in opts]} elig={[o.payment_option_id for o in opts if planner.installment_eligible(o, prof)]}")
    print(f"   cands={[(c.method, c.completes_by_deadline, len(c.changes), c.option.payment_option_id if c.option else None) for c in d.candidates]} ->", row(r.request_id))

print('\n===== CASE 5: installment cap definition =====')
orig = planner.installment_eligible


def alt_eligible(opt, prof):
    if opt.payment_method != 'installments' or 'installments' not in prof.methods or prof.max_installment_months is None:
        return False
    span_months = opt.number_of_payments * (opt.payment_frequency_days or 30) / 30.0
    return span_months <= prof.max_installment_months + 1e-9


eq = []; three31 = []; changed = []
freqs = Counter()
for r in reqs:
    prof = ds.profiles[r.user_id]
    opts = [o for o in ds.options_by_request.get(r.request_id, []) if o.payment_method == 'installments']
    for o in opts:
        freqs[o.payment_frequency_days] += 1
        if prof.max_installment_months is not None and o.number_of_payments == prof.max_installment_months:
            eq.append((r.request_id, r.user_id, o.payment_option_id, o.number_of_payments, o.payment_frequency_days, 'installments' in prof.methods))
        if o.number_of_payments == 3 and o.payment_frequency_days == 31 and prof.max_installment_months == 3:
            three31.append((r.request_id, r.user_id, o.payment_option_id, 'installments' in prof.methods))
    a = {o.payment_option_id for o in opts if orig(o, prof)}
    b = {o.payment_option_id for o in opts if alt_eligible(o, prof)}
    if a != b:
        planner.installment_eligible = alt_eligible
        d2 = decide(decs[r.request_id].state, ds.options_by_request.get(r.request_id, []))
        planner.installment_eligible = orig
        d1 = decs[r.request_id]
        diff = (d1.plan.method, d1.plan.plan_string()) != (d2.plan.method, d2.plan.plan_string())
        changed.append((r.request_id, r.user_id, sorted(a), sorted(b), diff, d1.plan.method, d1.plan.plan_string(), d2.plan.method, d2.plan.plan_string()))
print('installment frequencies:', freqs)
print('options with n == max:', len(eq))
for x in eq:
    print('  ', x, row(x[0]))
print('3x31 vs cap 3:', three31)
print('eligibility set differs under n*freq/30 definition:', len(changed))
for x in changed:
    print('  ', x)

print('\n===== CASE 6: partial with earliest == desired =====')
for r in reqs:
    o = out_rows[r.request_id]
    if o['recommended_payment_method'] == 'partial_payment' and o['earliest_date_for_full_payment'] == r.desired_completion_date.isoformat():
        print(r.request_id, r.user_id, 'desired', r.desired_completion_date, row(r.request_id))
print('all partials:', [(r.request_id, out_rows[r.request_id]['earliest_date_for_full_payment'], r.desired_completion_date.isoformat()) for r in reqs if out_rows[r.request_id]['recommended_payment_method'] == 'partial_payment'])

print('\n===== CASE 7: wait past deadline =====')
for r in reqs:
    o = out_rows[r.request_id]
    if o['recommended_payment_method'] == 'wait':
        e = parse_date(o['earliest_date_for_full_payment'])
        late = e > r.desired_completion_date
        d = decs[r.request_id]
        names = e.isoformat() in o['decision_explanation'] and r.desired_completion_date.isoformat() in o['decision_explanation']
        print(f"{r.request_id} {r.user_id} earliest={e} desired={r.desired_completion_date} late={late} cands={[(c.method, c.completes_by_deadline, len(c.changes)) for c in d.candidates]} explanation_names_both={names}")
        if late:
            print('    ', row(r.request_id)); print('     expl:', o['decision_explanation'])

print('\n===== CASE 8: desired before first/last installment date =====')
for r in reqs:
    d = decs[r.request_id]; prof = ds.profiles[r.user_id]
    for o in ds.options_by_request.get(r.request_id, []):
        if o.payment_method != 'installments':
            continue
        sched = o.schedule()
        if r.desired_completion_date < sched[0][0] or r.desired_completion_date < sched[-1][0]:
            elig = orig(o, prof)
            cand = [c for c in d.candidates if c.option is o]
            chosen = d.plan.option is o
            print(f"{r.request_id} {r.user_id} {o.payment_option_id} n={o.number_of_payments} first={sched[0][0]} last={sched[-1][0]} desired={r.desired_completion_date} before_first={r.desired_completion_date < sched[0][0]} eligible={elig} candidate={[(c.completes_by_deadline, len(c.changes)) for c in cand]} chosen={chosen} -> {out_rows[r.request_id]['recommended_payment_method']}")

print('\n===== CASE 9: safe == requested but full_payment not accepted =====')
for r in reqs:
    d = decs[r.request_id]; prof = ds.profiles[r.user_id]
    if abs(d.safe_amount - r.requested_amount) < 0.005 and 'full_payment' not in prof.methods:
        print(f"{r.request_id} {r.user_id} methods={prof.methods} max_m={prof.max_installment_months} partial_allowed={r.allows_partial_payment} earliest={d.earliest} cands={[(c.method, c.completes_by_deadline, c.option.payment_option_id if c.option else None) for c in d.candidates]} opts={[(o.payment_option_id, o.number_of_payments) for o in ds.options_by_request[r.request_id] if o.payment_method == 'installments']}")
        print('   ', row(r.request_id))

print('\n===== CASE 10: safe == requested but status != affordable_now =====')
for r in reqs:
    d = decs[r.request_id]; o = out_rows[r.request_id]
    if abs(d.safe_amount - r.requested_amount) < 0.005 and o['affordability_status'] != 'affordable_now':
        print(r.request_id, r.user_id, ds.profiles[r.user_id].methods, row(r.request_id))

print('\n===== CASE 11: same-day salary / same-day known debit =====')
for r in reqs:
    st = decs[r.request_id].state; rq = r.request_date
    sf = sal_flows(st)
    same_sal = [f for f in sf if f.date == rq]
    evs = [e for e in ds.events_by_user[r.user_id] if e.status in ('pending', 'scheduled') and e.direction == 'debit' and (e.settlement_date or e.event_date) == rq]
    past_pending = [e for e in ds.events_by_user[r.user_id] if e.status in ('pending', 'scheduled') and e.direction == 'debit' and (e.settlement_date or e.event_date) < rq]
    if same_sal or evs or past_pending:
        kd = [(f.date.isoformat(), round(f.amount, 2), f.label) for f in st.flows if f.kind == 'known_debit' and f.date == rq]
        print(f"{r.request_id} {r.user_id} rq={rq} same_day_salary={[(round(f.amount,2), f.label) for f in same_sal]} same_day_debit_events={[(e.event_id, e.status, e.amount, e.description) for e in evs]} past_due_pending={[(e.event_id, e.status, (e.settlement_date or e.event_date).isoformat(), e.amount) for e in past_pending]} known_debit_flows_on_rq={kd}")
        print('   ', row(r.request_id))

print('\n===== CASE 12: two household streams without T15 =====')
for r in reqs:
    uid = r.user_id; st = decs[r.request_id].state
    evs = [e for e in ds.events_by_user[uid] if e.category == 'salary' and e.status == 'settled']
    descs = Counter(e.description for e in evs)
    if 'Primary household salary' in descs and 'Second household income' in descs:
        t15 = [t for t in tmpl(uid) if t[1] == 'T15']
        sf = sal_flows(st)
        prim = sorted([e for e in evs if e.description == 'Primary household salary'], key=lambda e: e.settlement_date)
        sec = sorted([e for e in evs if e.description == 'Second household income'], key=lambda e: e.settlement_date)
        sched = [e for e in ds.events_by_user[uid] if e.category == 'salary' and e.status == 'scheduled']
        print(f"{r.request_id} {uid} T15={t15} primary=({len(prim)} rows, last {prim[-1].settlement_date} {prim[-1].amount}) second=({len(sec)} rows, last {sec[-1].settlement_date} {sec[-1].amount}) sched={[(e.event_id, e.description, e.amount, e.settlement_date.isoformat()) for e in sched]}")
        print(f"   proj={[(f.date.isoformat(), round(f.amount,2)) for f in sf]} notes={[n for n in st.notes if 'salary' in n]}")
        print('   ', row(r.request_id))
