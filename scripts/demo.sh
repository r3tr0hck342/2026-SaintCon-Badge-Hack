#!/usr/bin/env bash
# REABadge submission demo — recovers every static result from the firmware image.
# No hardware, no firmware execution. Safe to run anywhere Python 3 is installed.
#
#   bash scripts/demo.sh [path/to/flash.bin]
#
# Everything that reads the (untrusted) image runs under `python3 -I`.
set -euo pipefail

cd "$(dirname "$0")/.."
FW="${1:-fw_dump/flash.bin}"
PY="$([ -x .venv/bin/python ] && echo .venv/bin/python || echo python3)"

rule() { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }

rule "Firmware identity"
sha256sum "$FW"
expect=37ee8a7e3f256ff92f115e830acb147439ed3cca07f37f0b0e82160069b298fd
got=$(sha256sum "$FW" | cut -d' ' -f1)
if [ "$got" = "$expect" ]; then echo "matches the analyzed stock image"; else echo "NOTE: differs from the analyzed stock image"; fi

rule "Flags + all 30 unlock codes (static recovery)"
# Rebuilds RAM from the crt0 copy table, reimplements the custom hash + GOST/Magma,
# decodes the XOR/rotate flags, and self-verifies every code against the hash table.
$PY -I scripts/badge.py "$FW"

rule "Save-record checksum is reproducible"
# Proves the reversed hash is byte-exact: it regenerates the stored EEPROM save hash.
latest_eeprom=$(ls -t backups/*/eeprom.bin 2>/dev/null | head -1 || true)
if [ -n "$latest_eeprom" ]; then
  echo "using $latest_eeprom"
  $PY -I - "$FW" "$latest_eeprom" <<'PYEOF'
import sys, io, contextlib
# Load badge.py's namespace (H, q) without re-printing its recovery output.
ns = {}
src = open('scripts/badge.py').read().split('# --- FLAG 0/1/2')[0]  # stop before the flag prints
with contextlib.redirect_stdout(io.StringIO()):
    exec(compile(src, 'badge.py', 'exec'), ns)
H, q = ns['H'], ns['q']
e = open(sys.argv[2], 'rb').read()
calc = H(e[0x10:0x28], q(0x1000e180, 0x1000e184)).to_bytes(8, 'little')
stored = e[0x28:0x30]
print('stored save hash :', stored.hex())
print('recomputed hash  :', calc.hex())
print('MATCH' if calc == stored else 'MISMATCH')
PYEOF
else
  echo "(no EEPROM backup present — skipping; run badgectl.py backup with a badge attached)"
fi

rule "Minigame auto-win patch (static diff, no device)"
if [ -f backups/patched-minigames/flash.bin ]; then
  $PY -I - "$FW" backups/patched-minigames/flash.bin <<'PYEOF'
import sys
a = open(sys.argv[1], 'rb').read(); b = open(sys.argv[2], 'rb').read()
B = 0x10000000
diffs = [(i, a[i], b[i]) for i in range(min(len(a), len(b))) if a[i] != b[i]]
print(f'{len(diffs)} byte(s) differ from stock:')
for off, x, y in diffs:
    print(f'  0x{B+off:08x}: {x:02x} -> {y:02x}')
print('(patches neutralize the 3 minigame-loss branches; see SUBMISSION.md §5)')
PYEOF
else
  echo "(no patched image present — skipping)"
fi

rule "Done"
echo "Full write-up: SUBMISSION.md   |   Method: AGENTS.md   |   Raw findings: FINDINGS.md"
