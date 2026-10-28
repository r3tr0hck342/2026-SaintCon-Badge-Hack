# REABadge setup on a new computer

How to get the scripts and the cargo bot running from a copy of this folder (for example from the USB drive).
The `.venv` folder does not copy between machines, so you build a fresh one.

## 1. Install Python packages (`.venv`)

Run these in the `REABadge` folder. Python 3.10 or newer works; this project was built with 3.12.

**Linux / macOS**
```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Windows**
```bat
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

`requirements.txt` pins the four packages:

| Package | Version | Used for |
|---|---|---|
| pyserial | 3.5 | talking to the badge over USB (`badgectl.py`, `cargobot.py`) |
| capstone | 5.0.9 | disassembly (`dis.py`, patch-site sweeps) |
| unicorn | 2.1.4 | emulating the console hook before flashing |
| keystone-engine | 0.9.2 | optional assembler; nothing in `scripts/` needs it |

If an old `.venv` folder came along with the copy, delete it first. Its links point at another
machine's Python and it won't run.

## 2. Install tools outside Python (only if you need them)

| Tool | Needed for |
|---|---|
| `picotool` | flashing firmware, EEPROM backup/restore (`badgectl.py backup`, `restore-*`) |
| `arm-none-eabi-gcc` | rebuilding the console hook (`tools/btninject/build.sh`) |

Playing with the bot and running `verify` need neither.

## 3. Allow access to the badge's serial port (Linux)

Pick one:
- add yourself to the serial group and log out and back in: `sudo usermod -aG dialout $USER`
  (`uucp` instead of `dialout` on Arch);
- or install the udev rule this project used, as `/etc/udev/rules.d/60-picotool.rules`, then replug the badge:
  ```
  SUBSYSTEM=="usb", ATTRS{idVendor}=="2e8a", TAG+="uaccess"
  SUBSYSTEM=="tty", ATTRS{idVendor}=="2e8a", TAG+="uaccess"
  ```

On Windows the badge shows up as a COM port; on macOS as `/dev/cu.usbmodem…`.

## 4. Check the badge

Plug the badge in with a USB **data** cable and wait a few seconds, then:
```sh
.venv/bin/python -I scripts/badgectl.py verify        # Windows: .venv\Scripts\python -I scripts\badgectl.py verify
```
It should end with `ALL GOOD` (30/30 achievements, FLAG 1 and 2 print).

## 5. Run the cargo bot

```sh
.venv/bin/python -I scripts/cargobot.py --runs 5
```
- The badge should be on its title screen. If the bot says `not_at_title`, press **B** on the badge and rerun.
- If a run was interrupted, the same command picks it up from the map.
- Every run is logged to `cargoruns.jsonl`.
- The bot needs the patched firmware the badge runs now (`backups/patched-crew/flash.bin`). On stock
  firmware the `BTN`/`PEEK`/`PAN`/`WHERE`/`CREW` commands don't exist.

## 6. Firmware images (flashing needs `picotool`)

| Image | What it is |
|---|---|
| `backups/patched-crew` | **current**: minigame auto-win, infinite fuel/hull, no crew loss, console hook with `CREW` |
| `backups/patched-btn` | same without the crew fix |
| `backups/patched-infinite` | minigames + fuel/hull, no console hook |
| `backups/20261027-134527` | minigame patch only |
| `backups/20261027-132843` | stock firmware |

Flash one with `.venv/bin/python -I scripts/badgectl.py restore-flash backups/<name>`. It asks for confirmation,
writes and verifies the 4 MB flash, then runs `verify`. The EEPROM (achievements, handle) is not touched.

## Where everything else is

- `SUBMISSION.md` and `REABadge-Teardown.html`: the write-up for the talk.
- `FINDINGS.md`: every address, patch and result.
- `AGENTS.md`: how to continue the reverse engineering (Ghidra/REA setup, backup/restore details).
- `SECURITY_NOTES.md`: notes for the organizers on the station protocol.
