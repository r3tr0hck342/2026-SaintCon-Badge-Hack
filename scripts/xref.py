# usage: xref.py flash.bin <target_hex>...  -- find Thumb BL/B.W call sites to targets
import sys,struct
f=open(sys.argv[1],'rb').read(); B=0x10000000; T={int(t,16) for t in sys.argv[2:]}
for o in range(0,len(f)-4,2):
    h1,h2=struct.unpack_from('<HH',f,o)
    if h1>>11==0b11110 and (h2>>14)==0b11 and (h2>>12)&1:
        S=(h1>>10)&1; J1=(h2>>13)&1; J2=(h2>>11)&1
        imm=(S<<24)|((1-(J1^S))<<23)|((1-(J2^S))<<22)|((h1&0x3ff)<<12)|((h2&0x7ff)<<1)
        if S: imm-=1<<25
        t=B+o+4+imm
        if t in T: print(f'{B+o:08x} -> {t:08x}')
