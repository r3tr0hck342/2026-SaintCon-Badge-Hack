import sys,runpy,io,contextlib
ARGV=list(sys.argv); bpy,fw=ARGV[1],ARGV[2]; sys.argv=[bpy,fw]
with contextlib.redirect_stdout(io.StringIO()): g=runpy.run_path(bpy,run_name='x')
H,seed,table,nm=g['H'],g['seed'],g['table'],g['nm']
KNOWN={2:'SC_VECTOR_BURN',7:'SC_VOID_VECTOR',9:'SC_ORBIT_DECAY',10:'SC_THRUST_LOSS',
12:'SC_ECHO_ORBIT',13:'SC_DUST_FLUX',16:'SC_CORE_FLUX',18:'SC_PULSE_FIELD',19:'SC_FIELD_ECHO',
24:'SC_FLUX_VECTOR',25:'SC_ORBIT_TRACE',26:'SC_ASTRA_SHIFT',27:'SC_ZENITH_DRIFT',
28:'SC_ECHO_VECTOR',29:'SC_DRIFT_LOCK'}
pool=[w.strip() for w in open(S+'/pool_words.txt') if w.strip()] if False else [w.strip() for w in open(ARGV[3])]
hit=dict(KNOWN)
def test(code):
    k=table.get(H(code.encode(),seed))
    if k and k not in hit: hit[k]=code; print('FOUND bit',k,nm(k),'=',code,flush=True)
# pass 1: pool x pool
for a in pool:
    for b in pool:
        if a!=b: test('SC_%s_%s'%(a,b))
print('after pool^2:',len(hit),'/ 30',flush=True)
# pass 2: known words x full dict (both positions)
kw=set()
for c in KNOWN.values(): kw.update(c[3:].split('_'))
dic=[l.strip().upper() for l in open(ARGV[4]) if l.strip().isascii() and l.strip().isalpha()]
dic=sorted(set(dic))
for w in kw:
    for d in dic:
        test('SC_%s_%s'%(w,d)); test('SC_%s_%s'%(d,w))
print('after known x dict:',len(hit),'/ 30',flush=True)
rem=[k for k in range(2,32) if k not in hit]
print('remaining bits:',rem,[nm(k) for k in rem],flush=True)
