# usage: dis.py flash.bin <start_hex> [count]  -- Thumb-2 disassembly with literal-pool resolution
import sys,struct,capstone
f=open(sys.argv[1],'rb').read(); B=0x10000000
md=capstone.Cs(capstone.CS_ARCH_ARM,capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS); md.detail=True
a=int(sys.argv[2],16); n=int(sys.argv[3]) if len(sys.argv)>3 else 60
for i,ins in enumerate(md.disasm(f[a-B:a-B+n*4],a)):
    if i>=n: break
    x=''
    if ins.mnemonic.startswith('ldr') and '[pc' in ins.op_str:
        lit=((ins.address+4)&~3)+ins.operands[1].mem.disp; v=struct.unpack_from('<I',f,lit-B)[0]; x=f'  ; ={v:#x}'
        if B<=v<B+len(f):
            s=f[v-B:v-B+40].split(b'\0')[0]
            if len(s)>2 and all(32<=c<127 for c in s): x+=f' {s!r}'
    print(f'{ins.address:08x}  {ins.mnemonic:8} {ins.op_str}{x}')
