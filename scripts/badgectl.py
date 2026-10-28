#!/usr/bin/env python3
"""Back up, verify and restore the REABadge (RP2350 badge, EEPROM on I2C0 @ 0x50).

Run with the project venv:  .venv/bin/python -I scripts/badgectl.py <command>

  backup                 flash (4 MB) + EEPROM (1 KB) + handle -> backups/<timestamp>/ ; read-only
  verify                 all 30 codes report ALREADY UNLOCKED, FLAG 1/2 print ; sends only UNLOCK/FLAG/IDENT
  restore-eeprom DIR     write DIR/eeprom.bin back byte-for-byte (verified by readback)
  restore-flash DIR      write DIR/flash.bin back to the badge's flash (only if the firmware is damaged)
  replay [--handle NAME] fallback without an image: send all 30 UNLOCK codes, set HANDLE, write PLUM

Every write command asks for confirmation unless --yes is given.
The EEPROM helper (tools/plumwriter) runs from SRAM only; the badge boots its own firmware afterwards.
"""
import argparse, datetime, glob, hashlib, json, os, re, subprocess, sys, time

import serial

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PICOTOOL = os.path.expanduser('~/.local/bin/picotool')
HELPER = os.path.join(ROOT, 'tools/plumwriter/build/plumwriter.uf2')
FLASH_SIZE = 4 * 1024 * 1024
CODES = '''VECTOR_BURN NOVA_TRACE ION_WAKE SOLAR_SHEAR PLASMA_ARC VOID_VECTOR STAR_OFFSET ORBIT_DECAY THRUST_LOSS
SIGNAL_GHOST ECHO_ORBIT DUST_FLUX PHASE_DRIFT GRAV_SHIFT CORE_FLUX LAGRANGE_LOCK PULSE_FIELD FIELD_ECHO QUANTUM_WAKE
DEEP_PARALLAX RADIAL_DRIFT COSMIC_BIAS FLUX_VECTOR ORBIT_TRACE ASTRA_SHIFT ZENITH_DRIFT ECHO_VECTOR DRIFT_LOCK
APOGEE_DRIFT PERIGEE_SHIFT'''.split()  # bits 2..31 in order
FLAGS = {'1': '{At0m1c_Ut0p1a_1955}', '2': '{R4ygun_G0th13_Ph4s3}'}


def sha256(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def confirm(args, what):
    if args.yes:
        return
    if input(f'{what}\nType YES to continue: ').strip() != 'YES':
        sys.exit('aborted, nothing written')


def picotool(*a):
    r = subprocess.run([PICOTOOL, *a], capture_output=True, text=True)
    if r.returncode:
        sys.exit(f'picotool {" ".join(a)} failed:\n{r.stdout}{r.stderr}')
    return r.stdout


def wait_usb(pid, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if f'2e8a:{pid}' in subprocess.run(['lsusb'], capture_output=True, text=True).stdout:
            return
        time.sleep(0.5)
    sys.exit(f'badge did not appear as 2e8a:{pid} (BOOTSEL=000f, app=0009); replug it and retry')


def open_port(timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        for p in sorted(glob.glob('/dev/ttyACM*')):
            try:
                s = serial.Serial(p, 115200, timeout=1)
                time.sleep(0.5)
                s.reset_input_buffer()
                return s
            except serial.SerialException:
                pass
        time.sleep(0.5)
    sys.exit('no usable /dev/ttyACM* (check the udev rule / replug)')


def to_bootsel():
    picotool('reboot', '-u', '-f')
    wait_usb('000f')
    time.sleep(2)  # 000f enumerates before the bootrom accepts commands ("returned an error: rebooting")


def to_app():
    picotool('reboot', '-f')
    wait_usb('0009')
    time.sleep(2)


def start_helper():
    to_bootsel()
    picotool('load', '-x', HELPER)
    wait_usb('0009')
    return open_port()


def helper_cmd(s, cmd, until, timeout=20):
    """Send a one-letter helper command and collect lines until one starts with any of `until`."""
    s.write(cmd)
    lines, end = [], time.time() + timeout
    while time.time() < end:
        ln = s.readline().decode('latin1').strip()
        if not ln or ln.startswith('plumwriter ready'):
            continue
        lines.append(ln)
        if ln.startswith(until):
            return lines
    sys.exit(f'helper timed out on {cmd!r}; got: {lines[-3:]}')


def console(s, line, wait=0.5):
    s.reset_input_buffer()
    s.write((line + '\r\n').encode())
    time.sleep(wait)
    return s.read(2000).decode('latin1').replace('\r', '')


def read_eeprom(s):
    img = bytearray()
    for ln in helper_cmd(s, b'D', ('DUMP END',)):
        m = re.match(r'([0-9a-f]{3}):((?: [0-9a-f]{2}){16})$', ln)
        if m:
            assert int(m.group(1), 16) == len(img), f'out-of-order dump line {ln}'
            img += bytes.fromhex(m.group(2))
        elif 'FAILED' in ln:
            sys.exit(f'EEPROM read error: {ln}')
    if len(img) != 1024:
        sys.exit(f'EEPROM dump incomplete ({len(img)} bytes)')
    return bytes(img)


def cmd_backup(args):
    out = os.path.join(ROOT, 'backups', datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    os.makedirs(out)
    s = open_port()
    handle = re.search(r'IDENT "([^"]*)"', console(s, 'IDENT'))
    s.close()
    to_bootsel()
    print('reading 4 MB flash ...')
    picotool('save', '-r', '0x10000000', hex(0x10000000 + FLASH_SIZE), os.path.join(out, 'flash.bin'))
    picotool('load', '-x', HELPER)
    wait_usb('0009')
    s = open_port()
    img = read_eeprom(s)
    s.close()
    open(os.path.join(out, 'eeprom.bin'), 'wb').write(img)
    to_app()
    ref = os.path.join(ROOT, 'fw_dump/flash.bin')
    man = {
        'created': datetime.datetime.now().isoformat(timespec='seconds'),
        'handle': handle.group(1) if handle else None,
        'flash_sha256': sha256(os.path.join(out, 'flash.bin')),
        'eeprom_sha256': hashlib.sha256(img).hexdigest(),
        'eeprom_0_15': img[:16].decode('latin1'),
        'flash_matches_fw_dump': sha256(os.path.join(out, 'flash.bin')) == sha256(ref) if os.path.exists(ref) else None,
        'codes': [f'SC_{c}' for c in CODES],
    }
    json.dump(man, open(os.path.join(out, 'manifest.json'), 'w'), indent=2)
    print(json.dumps({k: v for k, v in man.items() if k != 'codes'}, indent=2))
    print(f'backup written to {out}')


def cmd_verify(args):
    s = open_port()
    res = {}
    for bit, c in enumerate(CODES, 2):
        m = re.search(r'UNLOCK: ([A-Z ]+)', console(s, f'UNLOCK SC_{c}', 0.35))
        res[bit] = m.group(1).strip() if m else '?'
    flags = {n: re.search(r'Flag: (.*)', console(s, f'FLAG {n}', 0.6)) for n in FLAGS}
    ident = re.search(r'IDENT "([^"]*)"', console(s, 'IDENT'))
    s.close()
    bad = {b: r for b, r in res.items() if r != 'ALREADY UNLOCKED'}
    print(f'handle: {ident.group(1) if ident else "?"}')
    print(f'achievements: {30 - len(bad)}/30 already unlocked' + (f'; newly set/other: {bad}' if bad else ''))
    ok = not bad
    for n, want in FLAGS.items():
        got = flags[n].group(1).strip() if flags[n] else '?'
        print(f'FLAG {n}: {got}' + ('' if got == want else f'   (expected {want})'))
        ok &= got == want
    print('ALL GOOD' if ok else 'NOT COMPLETE')
    return ok


def cmd_restore_eeprom(args):
    img = open(os.path.join(args.dir, 'eeprom.bin'), 'rb').read()
    if len(img) != 1024:
        sys.exit('eeprom.bin must be exactly 1024 bytes')
    confirm(args, f'Overwrite all 1 KB of badge EEPROM with {args.dir}/eeprom.bin '
                  f'(sha256 {hashlib.sha256(img).hexdigest()[:16]}…, bytes 0..15 {img[:16]!r})?')
    s = start_helper()
    helper_cmd(s, b'L', ('LOAD READY',))
    s.write(img)
    res = helper_cmd(s, b'', ('LOAD OK', 'LOAD FAILED', 'LOAD VERIFY', 'LOAD ABORTED'))[-1]
    back = read_eeprom(s) if res == 'LOAD OK' else None
    s.close()
    to_app()
    if res != 'LOAD OK' or back != img:
        sys.exit(f'restore failed: {res}')
    print('EEPROM restored and verified byte-for-byte; running verify ...')
    cmd_verify(args)


def cmd_restore_flash(args):
    img = os.path.join(args.dir, 'flash.bin')
    if os.path.getsize(img) != FLASH_SIZE:
        sys.exit(f'{img} must be exactly {FLASH_SIZE} bytes')
    confirm(args, f'Rewrite the badge FIRMWARE (4 MB flash) from {img} (sha256 {sha256(img)[:16]}…)? '
                  'Only needed if the firmware is damaged. EEPROM is not touched.')
    to_bootsel()
    print('writing + verifying 4 MB flash (takes a minute) ...')
    picotool('load', '-v', img, '-t', 'bin', '-o', '0x10000000')
    to_app()
    print('flash restored; running verify ...')
    cmd_verify(args)


def cmd_replay(args):
    confirm(args, 'Send all 30 UNLOCK codes' + (f', set HANDLE {args.handle}' if args.handle else '') +
                  ', and write PLUM to EEPROM bytes 0..3?')
    s = open_port()
    for c in CODES:
        console(s, f'UNLOCK SC_{c}', 0.35)
    if args.handle:
        print(console(s, f'HANDLE {args.handle}').strip())
    s.close()
    s = start_helper()
    print(helper_cmd(s, b'W', ('WRITE OK', 'WRITE FAILED', 'WRITE TIMEOUT'))[0])
    s.close()
    to_app()
    cmd_verify(args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--yes', action='store_true', help='skip confirmation prompts')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('backup')
    sub.add_parser('verify')
    for name in ('restore-eeprom', 'restore-flash'):
        sub.add_parser(name).add_argument('dir', help='a backups/<timestamp> directory')
    sub.add_parser('replay').add_argument('--handle', help='handle to set (3-14 chars)')
    args = ap.parse_args()
    ok = {'backup': cmd_backup, 'verify': cmd_verify, 'restore-eeprom': cmd_restore_eeprom,
          'restore-flash': cmd_restore_flash, 'replay': cmd_replay}[args.cmd](args)
    sys.exit(0 if ok is not False else 1)


if __name__ == '__main__':
    main()
