import sys,runpy,io,contextlib
sys.argv=[sys.argv[1],sys.argv[2]]
with contextlib.redirect_stdout(io.StringIO()): g=runpy.run_path(sys.argv[0],run_name='x')
for n in 'K1 C1 K2 C2 X seed'.split(): print(f'#define {n} 0x{g[n]:016x}ULL')
for h,k in g['table'].items(): print(f'// bit {k} 0x{h:016x}')
