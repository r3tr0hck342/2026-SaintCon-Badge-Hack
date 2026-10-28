import struct,sys,re
f=open(sys.argv[1],'rb').read(); B=0x10000000; M=(1<<64)-1
u32=lambda a: struct.unpack_from('<I',f,a-B)[0]
# --- rebuild RAM from crt0 data_cpy_table (src,dst,end triples) ---
ram=bytearray(0x82000); best=None
for off in range(0,0x40000,4):
    trip=[];o=off
    while True:
        s,d,e=struct.unpack_from('<III',f,o)
        if not(B<=s<B+len(f) and 0x20000000<=d<=e<0x20082000): break
        trip.append((s,d,e)); o+=12
    if len(trip)>=2 and struct.unpack_from('<I',f,o)[0]==0:
        best=(off,trip); break
print('data_cpy_table @',hex(B+best[0]), [(hex(s),hex(d),hex(e)) for s,d,e in best[1]])
for s,d,e in best[1]: ram[d-0x20000000:e-0x20000000]=f[s-B:s-B+e-d]
def rd(a,n): return bytes(ram[a-0x20000000:a-0x20000000+n]) if a>=0x20000000 else f[a-B:a-B+n]
def q(lo,hi): return (u32(hi)<<32)|u32(lo)
# --- hash (FUN_10010a9c) ---
K1=q(0x10010bf0,0x10010bfc); C1=q(0x10010bf4,0x10010bf8)
K2=q(0x10010c08,0x10010c00); C2=q(0x10010c04,0x10010c0c); X=q(0x10010c10,0x10010bec)
def H(data,seed):
    h=seed^X; n=len(data); i=0
    while i+8<=n: h=(((h^int.from_bytes(data[i:i+8],'little'))*K1)+C1)&M; i+=8
    if i<n: h^=int.from_bytes(data[i:],'little')
    h=(h*K1+C1)&M; h^=n
    h=(h*K2+C2)&M; h^=h>>33
    h=(h*K1+C1)&M; h^=h>>29
    h=(h*K2+C2)&M; h^=h>>32
    return h
seed=q(0x1000e180,0x1000e184); tbl=u32(0x1000e188); names=u32(0x1000e190)
table={int.from_bytes(rd(tbl+8*(k-1),8),'little'):k for k in range(2,32)}
print('seed',hex(seed),'table@',hex(tbl),'names@',hex(names))
def nm(k):
    p=int.from_bytes(rd(names+4*k,4),'little'); return rd(p,48).split(b'\0')[0].decode('latin1')
cands=set(re.findall(rb'[\x20-\x7e]{3,40}',f)); cands|={b'SC_DUST_FLUX'}
# full recovered set (bits 2..31); dict brute results from huntdd.c, kept here so the table self-verifies
cands|={b'SC_'+w.encode() for w in '''VECTOR_BURN NOVA_TRACE ION_WAKE SOLAR_SHEAR PLASMA_ARC VOID_VECTOR STAR_OFFSET
 ORBIT_DECAY THRUST_LOSS SIGNAL_GHOST ECHO_ORBIT DUST_FLUX PHASE_DRIFT GRAV_SHIFT CORE_FLUX LAGRANGE_LOCK
 PULSE_FIELD FIELD_ECHO QUANTUM_WAKE DEEP_PARALLAX RADIAL_DRIFT COSMIC_BIAS FLUX_VECTOR ORBIT_TRACE
 ASTRA_SHIFT ZENITH_DRIFT ECHO_VECTOR DRIFT_LOCK APOGEE_DRIFT PERIGEE_SHIFT'''.split()}
found={}
for c in cands:
    for v in {c, c.upper(), c.strip(), c.upper().strip()}:
        for w in [v]+v.split(b' '):
            if w and H(w,seed) in table: found[table[H(w,seed)]]=w
for k in range(2,32): print(f'bit {k:2}: {nm(k)!r:40} code={found.get(k)}')
print(f'{len(found)}/30 codes verified against hash table')
# --- FLAG 0/1/2 (dispatcher FUN_1000ff2c) ---
print('FLAG  :',rd(u32(0x100103c4),17))
print('FLAG 1:',bytes(b^0xcc for b in rd(u32(0x100101c8),21)))
def f2(i,c): b=((c^i^0xa5)+3*i)&255; return ((b>>5)|(b<<3))&255
print('FLAG 2:',bytes(f2(i,c) for i,c in enumerate(rd(u32(0x100103d8),21))))
print('HELP  :',bytes(b^0x55 for b in rd(u32(0x100103ac),13)),'(XOR 0x55, printed after HELP text)')
# --- GOST/Magma for FLAG 3 ---
key=rd(u32(0x100103cc),32); K=[int.from_bytes(key[i:i+4],'little') for i in range(0,32,4)]
sbox=rd(u32(0x100109c4),128); sched=[int.from_bytes(rd(u32(0x10010a98)+4*i,4),'little') for i in range(32)]
print('key',key.hex(),'sched',sched)
def G(x):
    y=0
    for j in range(8): y|=sbox[16*j+((x>>(4*j))&15)]<<(4*j)
    return ((y<<11)|(y>>21))&0xffffffff
def blk(b):
    n1,n2=struct.unpack('<II',b)
    for r in range(32): n1,n2=G((K[sched[r]]+n1)&0xffffffff)^n2,n1
    return struct.pack('<II',n2,n1)
ct=rd(u32(0x100103c8),24); print('FLAG 3 (device prints *** instead):',b''.join(blk(ct[i:i+8]) for i in range(0,24,8)))
