import sys,runpy,io,contextlib,time
ARGV=list(sys.argv); sys.argv=[ARGV[1],ARGV[2]]
with contextlib.redirect_stdout(io.StringIO()): g=runpy.run_path(ARGV[1],run_name='x')
H,seed,table,nm=g['H'],g['seed'],g['table'],g['nm']
done={2,3,4,5,6,7,8,9,10,11,12,13,14,16,17,18,19,20,21,22,24,25,26,27,28,29,30,31}
dic=sorted({l.strip().upper() for l in open(ARGV[3]) if l.strip().isalpha() and l.strip().isascii() and 3<=len(l.strip())<=9})
print(len(dic),'dict (len3-9) squared =',len(dic)**2,flush=True)
hit=set(done); t=time.time()
for a in dic:
    sa='SC_'+a+'_'
    for b in dic:
        k=table.get(H((sa+b).encode(),seed))
        if k and k not in hit:
            hit.add(k); print('FOUND bit',k,nm(k),'= '+sa+b,flush=True)
    if len(hit)==30: break
print('DONE elapsed',int(time.time()-t),'s remaining:',[nm(k) for k in range(2,32) if k not in hit],flush=True)
