import re,sys,runpy,io,contextlib
with contextlib.redirect_stdout(io.StringIO()):
    p=sys.argv[1]; sys.argv=[p,sys.argv[2]]; g=runpy.run_path(p,run_name='x')
H,seed,table,nm,f=g['H'],g['seed'],g['table'],g['nm'],g['f']
words=sorted({w.upper() for w in re.findall(rb'[A-Za-z]{3,12}',f)})
print(len(words),'words',flush=True)
hit={}
for a in words:
    for c in [b'SC_'+a]+[b'SC_'+a+b'_'+b for b in words]:
        k=table.get(H(c,seed))
        if k and k not in hit: hit[k]=c; print(k,nm(k),c,flush=True)
