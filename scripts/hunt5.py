import sys,runpy,io,contextlib,time
ARGV=list(sys.argv); sys.argv=[ARGV[1],ARGV[2]]
with contextlib.redirect_stdout(io.StringIO()): g=runpy.run_path(ARGV[1],run_name='x')
H,seed,table,nm=g['H'],g['seed'],g['table'],g['nm']
done={2,3,4,6,7,8,9,10,12,13,14,16,17,18,19,20,21,22,24,25,26,27,28,29,30,31}
pool=sorted({l.strip() for l in open(ARGV[3]) if l.strip()})
dic=sorted({l.strip().upper() for l in open(ARGV[4]) if l.strip().isalpha() and l.strip().isascii()})
print(len(pool),'pool x',len(dic),'dict both ways',flush=True)
hit=set(done); t=time.time()
for w in pool:
    for d in dic:
        for code in ('SC_%s_%s'%(w,d),'SC_%s_%s'%(d,w)):
            k=table.get(H(code.encode(),seed))
            if k and k not in hit: hit.add(k); print('FOUND bit',k,nm(k),'=',code,flush=True)
    if len(hit)==30: break
rem=[k for k in range(2,32) if k not in hit]
print('elapsed',int(time.time()-t),'s  remaining:',rem,[nm(k) for k in rem],flush=True)
