import sys,runpy,io,contextlib
ARGV=list(sys.argv); sys.argv=[ARGV[1],ARGV[2]]
with contextlib.redirect_stdout(io.StringIO()): g=runpy.run_path(ARGV[1],run_name='x')
H,seed,table,nm=g['H'],g['seed'],g['table'],g['nm']
CODES=['SC_VECTOR_BURN','SC_VOID_VECTOR','SC_ORBIT_DECAY','SC_THRUST_LOSS','SC_ECHO_ORBIT',
'SC_DUST_FLUX','SC_CORE_FLUX','SC_PULSE_FIELD','SC_FIELD_ECHO','SC_FLUX_VECTOR','SC_ORBIT_TRACE',
'SC_ASTRA_SHIFT','SC_ZENITH_DRIFT','SC_ECHO_VECTOR','SC_DRIFT_LOCK','SC_APOGEE_DRIFT','SC_DEEP_PARALLAX',
'SC_ION_WAKE','SC_NOVA_TRACE','SC_PERIGEE_SHIFT','SC_PHASE_DRIFT','SC_PLASMA_ARC','SC_RADIAL_DRIFT','SC_LAGRANGE_LOCK']
done={2,3,4,6,7,9,10,12,13,14,16,17,18,19,21,22,24,25,26,27,28,29,30,31}
words=sorted({w for c in CODES for w in c[3:].split('_')})
dic=sorted({l.strip().upper() for l in open(ARGV[3]) if l.strip().isalpha() and l.strip().isascii()})
print(len(words),'known words x',len(dic),'dict',flush=True)
hit=set(done)
for w in words:
    for d in dic:
        for code in ('SC_%s_%s'%(w,d),'SC_%s_%s'%(d,w)):
            k=table.get(H(code.encode(),seed))
            if k and k not in hit: hit.add(k); print('FOUND bit',k,nm(k),'=',code,flush=True)
rem=[k for k in range(2,32) if k not in hit]
print('remaining:',rem,[nm(k) for k in rem],flush=True)
