# usage: litref.py flash.bin <pool_addr_hex>...  -- find Thumb LDR (literal) instructions that load from the given pool slots
import sys,struct
f=open(sys.argv[1],'rb').read(); B=0x10000000; T={int(t,16) for t in sys.argv[2:]}
for o in range(0,len(f)-4,2):
    a=B+o; h=struct.unpack_from('<H',f,o)[0]
    if h>>11==0b01001:
        t=((a+4)&~3)+(h&0xff)*4
        if t in T: print(f'{a:08x} ldr r{(h>>8)&7} <- {t:08x}')
    h2=struct.unpack_from('<H',f,o+2)[0]
    if h&0xff7f==0xf85f:
        imm=h2&0xfff; t=((a+4)&~3)+(imm if h&0x80 else -imm)
        if t in T: print(f'{a:08x} ldr.w r{h2>>12} <- {t:08x}')
