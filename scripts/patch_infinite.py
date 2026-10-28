# usage: patch_infinite.py in_flash.bin out_flash.bin  -- infinite fuel + hull + no crew loss (on top of the minigame patch)
import sys,hashlib
B=0x10000000; NOP=b'\x00\xbf'
P=[  # addr, original bytes, replacement, what it disables
 (0x100027b4,b'\x01\x3b',NOP,'travel: fuel -= 1'),
 (0x10001cc2,b'\xa8\xbf',NOP,'event: fuel = min(fuel+delta,cap) -> fuel = cap'),
 (0x10001ce0,b'\xa8\xbf',NOP,'event: hull = min(hull+delta,cap) -> hull = cap'),
 (0x100033f0,b'\x02\x3b',NOP,'nebula fail: fuel -= 2'),
 (0x1000338a,b'\x02\x3b',NOP,'asteroid fail: hull -= 2'),
 # FUN_100018a4: crew effect < 0 -> bne 0x10001a28 (remove a random crew member);
 # retarget to 0x100019ee, the generic "Crew: -1" print path, so nobody is removed
 (0x10001940,b'\x72\xd1',b'\x55\xd1','event: crew -= n'),
]
f=bytearray(open(sys.argv[1],'rb').read())
for a,orig,new,why in P:
    o=a-B; cur=bytes(f[o:o+2])
    if cur==new: print(f'{a:#x} already patched  ({why})'); continue
    assert cur==orig,f'{a:#x}: expected {orig.hex()} got {cur.hex()}'
    f[o:o+2]=new; print(f'{a:#x} {orig.hex()} -> {new.hex()}  ({why})')
open(sys.argv[2],'wb').write(f); print('sha256',hashlib.sha256(f).hexdigest())
