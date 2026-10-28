import sys,runpy,io,contextlib
ARGV=list(sys.argv); sys.argv=[ARGV[1],ARGV[2]]
with contextlib.redirect_stdout(io.StringIO()): g=runpy.run_path(ARGV[1],run_name='x')
H,seed,table,nm=g['H'],g['seed'],g['table'],g['nm']
WORDS=sorted(set("""VECTOR BURN VOID ORBIT DECAY THRUST LOSS ECHO CORE FLUX PULSE FIELD TRACE ASTRA SHIFT
ZENITH DRIFT LOCK DUST APOGEE PARALLAX ION WAKE NOVA PERIGEE PHASE PLASMA ARC RADIAL LAGRANGE DEEP
QUANTUM STAR OFFSET""".split()))
done={2,3,4,6,7,8,9,10,12,13,14,16,17,18,19,20,21,22,24,25,26,27,28,29,30,31}
dic=sorted({l.strip().upper() for l in open(ARGV[3]) if l.strip().isalpha() and l.strip().isascii()})
print(len(WORDS),'x',len(dic),flush=True)
hit=set(done)
for w in WORDS:
    for d in dic:
        for code in ('SC_%s_%s'%(w,d),'SC_%s_%s'%(d,w)):
            k=table.get(H(code.encode(),seed))
            if k and k not in hit: hit.add(k); print('FOUND bit',k,nm(k),'=',code,flush=True)
rem=[k for k in range(2,32) if k not in hit]
print('remaining:',rem,[nm(k) for k in rem],flush=True)
