import sys,runpy,io,contextlib
ARGV=list(sys.argv); sys.argv=[ARGV[1],ARGV[2]]
with contextlib.redirect_stdout(io.StringIO()): g=runpy.run_path(ARGV[1],run_name='x')
H,seed,table,nm=g['H'],g['seed'],g['table'],g['nm']
KNOWN={2,3,4,6,7,9,10,12,13,14,16,17,18,19,21,22,24,25,26,27,28,29,30,31}
pool=[w.strip() for w in open(ARGV[3]) if w.strip()]
hit=set(KNOWN)
for a in pool:
    for b in pool:
        if a!=b:
            k=table.get(H(('SC_%s_%s'%(a,b)).encode(),seed))
            if k and k not in hit: hit.add(k); print('FOUND bit',k,nm(k),'= SC_%s_%s'%(a,b),flush=True)
rem=[k for k in range(2,32) if k not in hit]
print('remaining:',rem,[nm(k) for k in rem],flush=True)
