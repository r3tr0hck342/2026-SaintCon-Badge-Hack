#!/usr/bin/env python3
"""Unlock all 30 achievements on the REABadge conference badge.

Plug the badge in over USB, then run:

    pip install pyserial
    python unlock_all.py            # finds the badge automatically
    python unlock_all.py --port COM5    (Windows)  or  --port /dev/ttyACM0  (Linux)  or  --port /dev/cu.usbmodem1101  (macOS)
    python unlock_all.py --list     # just print the codes, don't touch the badge

What it does: types `UNLOCK <code>` into the badge's own serial console, once per
achievement, exactly as you could by hand. UNLOCK can only ADD achievements, so it is
safe to run more than once; codes you already have report "ALREADY UNLOCKED".
It never writes the badge's firmware or memory directly.
"""
import argparse
import re
import sys
import time

CODES = [  # (bit, achievement, code)
    (2, 'Frequent Flyer', 'SC_VECTOR_BURN'),
    (3, 'Relics of the First Builders', 'SC_NOVA_TRACE'),
    (4, 'The Obsidian Monolith', 'SC_ION_WAKE'),
    (5, 'Full Complement', 'SC_SOLAR_SHEAR'),
    (6, 'A Crew of Specialists', 'SC_PLASMA_ARC'),
    (7, 'Signed On', 'SC_VOID_VECTOR'),
    (8, 'Works Well With Others', 'SC_STAR_OFFSET'),
    (9, 'Civic Duty', 'SC_ORBIT_DECAY'),
    (10, 'Deep Storage', 'SC_THRUST_LOSS'),
    (11, 'Long-Term Memory', 'SC_SIGNAL_GHOST'),
    (12, 'Manual Override', 'SC_ECHO_ORBIT'),
    (13, 'Service Port', 'SC_DUST_FLUX'),
    (14, "Dockmaster's Channel", 'SC_PHASE_DRIFT'),
    (15, 'Misaligned Home Row', 'SC_GRAV_SHIFT'),
    (16, 'Diagnostics Complete', 'SC_CORE_FLUX'),
    (17, 'Circles Within Circles', 'SC_LAGRANGE_LOCK'),
    (18, 'Connect the Dots', 'SC_PULSE_FIELD'),
    (19, 'Know a Guy', 'SC_FIELD_ECHO'),
    (20, 'Synthetic Minds', 'SC_QUANTUM_WAKE'),
    (21, 'Attack Surface Survey', 'SC_DEEP_PARALLAX'),
    (22, 'Fabric of Reality', 'SC_RADIAL_DRIFT'),
    (23, 'Blue Skies Ahead', 'SC_COSMIC_BIAS'),
    (24, 'Bare Metal', 'SC_FLUX_VECTOR'),
    (25, 'Sick Bay', 'SC_ORBIT_TRACE'),
    (26, 'Domestic Infrastructure', 'SC_ASTRA_SHIFT'),
    (27, 'Identity Crisis', 'SC_ZENITH_DRIFT'),
    (28, 'Open Access', 'SC_ECHO_VECTOR'),
    (29, 'Off the Record', 'SC_DRIFT_LOCK'),
    (30, 'Seal Broken', 'SC_APOGEE_DRIFT'),
    (31, 'The Watchtower', 'SC_PERIGEE_SHIFT'),
]

RASPBERRY_PI_VID = 0x2E8A


def find_port(serial_tools):
    ports = [p for p in serial_tools.list_ports.comports() if p.vid == RASPBERRY_PI_VID]
    if not ports:
        sys.exit('No badge found. Plug it in over USB (a data cable, not charge-only) or pass --port.')
    if len(ports) > 1:
        names = ', '.join(p.device for p in ports)
        sys.exit(f'More than one Raspberry Pi device found ({names}); pick one with --port.')
    return ports[0].device


def send(ser, line, wait):
    ser.reset_input_buffer()
    ser.write((line + '\r\n').encode())
    time.sleep(wait)
    return ser.read(2000).decode('latin1', 'replace')


def main():
    ap = argparse.ArgumentParser(description='Unlock all 30 REABadge achievements over USB serial.')
    ap.add_argument('--port', help='serial port (default: auto-detect the badge)')
    ap.add_argument('--list', action='store_true', help='print the codes and exit')
    ap.add_argument('--delay', type=float, default=0.4, help='seconds to wait for each reply (default 0.4)')
    args = ap.parse_args()

    if args.list:
        for bit, name, code in CODES:
            print(f'{bit:2}  {name:30}  {code}')
        return

    try:
        import serial
        import serial.tools.list_ports
    except ImportError:
        sys.exit('This script needs pyserial:  pip install pyserial')

    port = args.port or find_port(serial.tools)
    try:
        ser = serial.Serial(port, 115200, timeout=0.5)
    except serial.SerialException as e:
        hint = ''
        if sys.platform.startswith('linux'):
            hint = ('\nOn Linux you may need serial-port access: '
                    'sudo usermod -aG uucp $USER (Arch) or dialout (Debian/Ubuntu), then log out and back in.')
        sys.exit(f'Could not open {port}: {e}{hint}')

    print(f'Badge on {port}')
    time.sleep(0.5)
    ident = re.search(r'IDENT "([^"]*)"', send(ser, 'IDENT', 0.5))
    if ident:
        print(f'Handle: {ident.group(1)}')

    counts = {'new': 0, 'had': 0, 'failed': 0}
    for bit, name, code in CODES:
        reply = send(ser, f'UNLOCK {code}', args.delay)
        m = re.search(r'UNLOCK: ([A-Z ]+)', reply)
        result = m.group(1).strip() if m else 'NO REPLY'
        if result == 'OK':
            counts['new'] += 1
        elif result == 'ALREADY UNLOCKED':
            counts['had'] += 1
        else:
            counts['failed'] += 1
        print(f'  bit {bit:2}  {name:30}  {result}')
    ser.close()

    total = counts['new'] + counts['had']
    print(f'\n{total}/30 unlocked ({counts["new"]} new, {counts["had"]} already had)')
    if counts['failed']:
        print(f'{counts["failed"]} got no clear reply; run again, or add --delay 1 on a slow connection.')
        sys.exit(1)


if __name__ == '__main__':
    main()
