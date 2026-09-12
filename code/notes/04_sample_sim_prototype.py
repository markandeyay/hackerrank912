import csv, sys, json, statistics
from collections import defaultdict
from datetime import date, timedelta
D='dataset/'
def rd(f): return list(csv.DictReader(open(D+f,encoding='utf-8')))
def d(s): return date.fromisoformat(s)
def addm(dt, n):
    y=dt.year+(dt.month-1+n)//12; m=(dt.month-1+n)%12+1
    import calendar
    return date(y,m,min(dt.day,calendar.monthrange(y,m)[1]))
samples=rd('sample_requests.csv'); prof={r['user_id']:r for r in rd('financial_profiles.csv')}
ev=defaultdict(list)
for r in rd('financial_events.csv'): ev[r['user_id']].append(r)
rates={(r['rate_date'],r['from_currency'],r['to_currency']):float(r['rate']) for r in rd('exchange_rates.csv')}
imgs=json.load(open('code/notes/02_images_manual.json'))
img_amt={v['event_id']:v['amount'] for v in imgs.values()}
EST=sys.argv[1] if len(sys.argv)>1 else 'mean'
import math
def rnd(x): return int(math.floor(x+0.5)) if '-halfup' in sys.argv else int(round(x))
STRICT='-strict' in sys.argv
NMON=int([a for a in sys.argv if a.startswith('-n')][0][2:]) if any(a.startswith('-n') for a in sys.argv) else 99
OUTL='-outl' in sys.argv
HOR=int([a for a in sys.argv if a.startswith('-h')][0][2:]) if any(a.startswith('-h') for a in sys.argv) else 90
MONTHLY_MODE=sys.argv[2] if len(sys.argv)>2 else 'dom'   # dom = same day of month; per = last+period
# manual message overrides for samples: user -> dict
OV={
 'user_02': {'salary_amount':42750000},
 'user_06': {'salary_amount':1037.52},
 'user_07': {'salary_date':'2024-09-23'},
 'user_08': {'salary_amount':1422.85},
 'user_11': {'salary_amount':38760000,'no_commission':True},
 'user_12': {'no_salary':True},
 'user_14': {'salary_amount':2717,'salary_date':'2025-08-15'},
 'user_15': {'salary_amount':1661,'salary_date':'2026-01-15'},
 'user_16': {'rent_mult':1.12},
 'user_05': {'no_salary':True},
 'user_10': {'no_salary':True},
}
def conv(amt,cur,home,dt):
    if cur==home: return amt
    k=(dt,cur,home)
    return amt*rates[k]
def est(amts):
    if EST=='mean': return statistics.mean(amts)
    if EST=='median': return statistics.median(amts)
    if EST=='last': return amts[-1]
    if EST=='max': return max(amts)
    if EST=='last3': return statistics.mean(amts[-3:])
    if EST=='rmean': return round(statistics.mean(amts))
    if EST=='max3': return max(amts[-3:])
    if EST=='p75':
        a=sorted(amts); import math; return a[min(len(a)-1,int(math.ceil(0.75*len(a))-1))]
    if EST=='meanstd': return statistics.mean(amts)+(statistics.pstdev(amts) if len(amts)>1 else 0)
    if EST=='mean1': return statistics.mean(amts)*1.05
    if EST=='mean2': return statistics.mean(amts)*1.10
def project(s, extra_payments=()):
    u=s['user_id']; p=prof[u]; rq=d(s['request_date']); home=p['home_currency']
    bal=float(p['current_available_balance']); mn=float(p['minimum_balance_to_keep'])
    ov=OV.get(u,{})
    H=HOR; end=rq+timedelta(days=H)
    flows=defaultdict(float)   # date -> net
    notes=[]; detail=defaultdict(list)
    # known future events
    hist=defaultdict(list)
    for e in ev[u]:
        st=e['status']; sd=e['settlement_date']
        amt=float(e['amount']) if e['amount'] else img_amt.get(e['event_id'])
        if amt is None: notes.append('NOAMT '+e['event_id']); continue
        if e['direction']=='non_cash' or st in ('failed','cancelled','unrealized'): continue
        if st=='settled' and d(sd)<rq:
            if e['event_type'] in ('refund',) or e['linked_event_id']: continue
            if e['category']=='salary' and ov.get('no_commission') and 'ommission' in e['description']: continue
            hist[(e['category'],e['direction'])].append((d(sd),conv(amt,e['currency'],home,sd),e))
            continue
        if st in ('pending','scheduled') or (st=='settled' and d(sd)>=rq):
            if e['direction']=='credit' and st!='settled' and e['category']!='salary': notes.append('skip pending credit '+e['event_id']); continue
            if e['direction']=='credit' and st=='pending': continue
            dt=d(sd)
            if dt<rq: dt=rq
            v=conv(amt,e['currency'],home,sd)
            flows[dt]+= v if e['direction']=='credit' else -v; detail[dt].append((e['category'],round(v if e['direction']=='credit' else -v,2)))
            notes.append(f"known {e['event_id']} {e['category']} {'+' if e['direction']=='credit' else '-'}{v:.2f} @{dt}")
            if e['category']=='salary' and st=='scheduled' and e['direction']=='credit':
                t=addm(dt,1)
                while t<=end: flows[t]+=v; detail[t].append(('salary',v)); t=addm(t,1)
                notes.append(f"  ..recurring monthly {v} from {dt}")
    has_sched_salary=any('salary' in n and 'known' in n and '+' in n for n in notes)
    for (cat,dr),g in hist.items():
        g.sort(key=lambda x:x[0])
        if len(g)<3 and not (cat=='salary' and ('salary_amount' in ov or 'salary_date' in ov)): continue
        dates=[x[0] for x in g]; amts=[x[1] for x in g]
        gaps=[(dates[i+1]-dates[i]).days for i in range(len(dates)-1)] or [30]
        per=statistics.median(gaps)
        if cat=='salary':
            if ov.get('no_salary') or has_sched_salary: continue
            # monthly salary on same DOM (use the primary regular series: most common day)
            amt=ov.get('salary_amount', amts[-1])
            if per>=20:
                from collections import Counter
                dom=Counter(x.day for x in dates).most_common(1)[0][0]
                base=[x for x in dates if x.day==dom][-1]
                amt=ov.get('salary_amount', [a for x,a in zip(dates,amts) if x.day==dom][-1])
                nxt=addm(base,1)
                if 'salary_date' in ov: nxt=d(ov['salary_date'])
                while nxt<rq: nxt=addm(nxt,1)
                t=nxt
                while t<=end: flows[t]+=amt; detail[t].append(('salary',amt)); t=addm(t,1)
                notes.append(f"salary {amt} monthly from {nxt}")
            else:
                step=int(round(per)); val=statistics.mean(amts); t=dates[-1]+timedelta(days=step)
                while t<rq: t+=timedelta(days=step)
                while t<=end: flows[t]+=val; detail[t].append(('income',round(val,2))); t+=timedelta(days=step)
                notes.append(f"irregular income {val:.2f} every {step}d from {t}")
            continue
        if OUTL:
            med=statistics.median(amts); amts2=[a for a in amts if a<=2*med] or amts
        else: amts2=amts
        val=est(amts2)
        if cat=='rent' and 'rent_mult' in ov: val*=ov['rent_mult']
        if per>=28:
            t=addm(dates[-1],1) if MONTHLY_MODE=='dom' else dates[-1]+timedelta(days=rnd(per))
            while t<rq or (STRICT and t<=rq and MONTHLY_MODE=='per'): t=addm(t,1) if MONTHLY_MODE=='dom' else t+timedelta(days=rnd(per))
            k=0
            while t<=end and k<NMON:
                flows[t]-=val; detail[t].append((cat,round(-val,2))); t=addm(t,1) if MONTHLY_MODE=='dom' else t+timedelta(days=rnd(per)); k+=1
        else:
            step=rnd(per); t=dates[-1]+timedelta(days=step)
            while t<rq or (STRICT and t<=rq): t+=timedelta(days=step)
            while t<=end: flows[t]-=val; detail[t].append((cat,round(-val,2))); t+=timedelta(days=step)
    for dt,a in extra_payments: flows[dt]-=a
    # daily balance
    series=[]; b=bal; t=rq
    while t<=end:
        b+=flows.get(t,0.0); series.append((t,b)); t+=timedelta(days=1)
    return series, mn, notes, detail
def r2(x): return round(x+1e-9,2)
out=[]; TOT=[]; REL=[]
for s in samples:
    series,mn,notes,detail=project(s)
    req=float(s['requested_amount']); rq=d(s['request_date'])
    trough=min(b for t,b in series)
    safe=max(0,min(req,trough-mn))
    # earliest date: first date D s.t. paying req at D keeps balance>=mn for all t>=D
    earliest=''
    for i,(t,b) in enumerate(series):
        if min(bb for tt,bb in series[i:])-req>=mn: earliest=t.isoformat(); break
    out.append((s['request_id'],r2(safe),float(s['amount_safe_to_pay']),earliest,s['earliest_date_for_full_payment']))
    diff=r2(safe-float(s['amount_safe_to_pay']))
    TOT.append((abs(diff)/req, earliest==s['earliest_date_for_full_payment'], s['request_id']))
    b0=float(prof[s['user_id']]['current_available_balance']); ares=b0-mn-float(s['amount_safe_to_pay']); mres=b0-min(bb for tt,bb in series)
    if float(s['amount_safe_to_pay'])<req and ares>0: REL.append(abs(ares-mres)/ares)
    print(f"{s['request_id']} safe={r2(safe):>14} actual={float(s['amount_safe_to_pay']):>14} diff={diff:>12} ({(diff/req*100):+.2f}% of req) | earliest={earliest} actual={s['earliest_date_for_full_payment']} {'OK' if earliest==s['earliest_date_for_full_payment'] else 'XX'}")
    if '-v' in sys.argv:
        for n in notes: print('     ',n)
    if '-g' in sys.argv:
        tmin=min(series,key=lambda x:x[1])[0]
        b=float(prof[s['user_id']]['current_available_balance'])
        actual_res=b-mn-float(s['amount_safe_to_pay']); my_res=b-tmin_bal if False else b-min(bb for tt,bb in series)
        print(f"    trough={tmin} my_reserve={my_res:.2f} actual_reserve={actual_res:.2f} delta(actual-mine)={actual_res-my_res:.2f}")
        for k in range(0,3):
            tt=tmin+timedelta(days=k)
            if detail.get(tt): print(f"        day+{k} {tt}: {detail[tt]}")
    if '-f' in sys.argv and s['request_id'] in sys.argv:
        tmin=min(series,key=lambda x:x[1])[0]
        b=float(prof[s['user_id']]['current_available_balance'])
        for t,bb in series:
            if detail.get(t): print(f"        {t} {bb:14.2f}  {detail[t]}")
        print('        TROUGH',tmin,'min',mn)

print('  rel_reserve_err=%.4f n=%d'%(sum(REL)/len(REL),len(REL)))
print('SUMMARY est=%s mode=%s strict=%s outl=%s hor=%d  mean|diff|/req=%.4f  earliest_ok=%d/25  worst=%s'%(EST,MONTHLY_MODE,STRICT,OUTL,HOR,sum(t[0] for t in TOT)/len(TOT),sum(t[1] for t in TOT),sorted(TOT,reverse=True)[:3]))
