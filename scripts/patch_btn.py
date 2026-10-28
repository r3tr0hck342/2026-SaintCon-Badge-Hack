# usage: patch_btn.py in_flash.bin out_flash.bin  -- add BTN/PEEK console commands (tools/btninject)
# Needs tools/btninject/build.sh run first (hook.bin + hook.elf).
import sys,struct,hashlib,subprocess,os
B=0x10000000; CAVE=0x10180000; SITE=0x100102e8
D=os.path.join(os.path.dirname(os.path.abspath(__file__)),'../tools/btninject')
code=open(os.path.join(D,'hook.bin'),'rb').read()
nm=subprocess.run(['arm-none-eabi-nm',os.path.join(D,'hook.elf')],capture_output=True,text=True).stdout
hook=int(next(l for l in nm.splitlines() if l.endswith(' T hook')).split()[0],16)

def bl(src,dst):
    off=dst-(src+4); assert -(1<<24)<=off<(1<<24) and not off&1
    S=(off>>24)&1; I1=(off>>23)&1; I2=(off>>22)&1; J1=(1-I1)^S; J2=(1-I2)^S
    return struct.pack('<HH',0xf000|(S<<10)|((off>>12)&0x3ff),0xd000|(J1<<13)|(J2<<11)|((off>>1)&0x7ff))

f=bytearray(open(sys.argv[1],'rb').read())
o=SITE-B; orig=bytes.fromhex('3548')+bl(SITE+2,0x1000aa28)   # ldr r0,=UNKNOWN ; bl puts
new=b'\x0e\xa8'+bl(SITE+2,hook)                               # add r0,sp,#0x38 ; bl hook
c=CAVE-B
if bytes(f[o:o+6])==new and bytes(f[c:c+len(code)])==code: print('already patched')
else:
    assert bytes(f[o:o+6])==orig,f'site: got {bytes(f[o:o+6]).hex()} want {orig.hex()}'
    assert f[c:c+0x2000]==b'\xff'*0x2000,'cave not empty'
    f[o:o+6]=new; f[c:c+len(code)]=code
    print(f'{SITE:#x} {orig.hex()} -> {new.hex()}  (bl hook @ {hook:#x}); {len(code)} B at {CAVE:#x}')
open(sys.argv[2],'wb').write(f); print('sha256',hashlib.sha256(f).hexdigest())
