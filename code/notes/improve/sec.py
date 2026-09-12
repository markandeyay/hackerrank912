import sys,re
txt=open('3_evidence_audit_dump.txt',encoding='cp1252',errors='replace').read()
secs=txt.split('='*100)
want=set(sys.argv[1:])
for s in secs:
    m=re.match(r'\n(request_\d+) ',s)
    if m and m.group(1) in want: print('='*60+s)
