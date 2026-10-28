# REABadge: unlock all achievements

Unlocks all 30 achievements on the badge by typing the `UNLOCK` codes into its USB console for you.

**Spoiler warning:** this gives away every unlock code. Only use it once you're done playing, or if you just want the badge complete.

## How to use

1. Plug the badge into your computer with a USB **data** cable.
2. Install Python 3 and pyserial: `pip install pyserial`
3. Run: `python unlock_all.py`

The script finds the badge on its own. If it can't, name the port:

| System | Example |
| --- | --- |
| Windows | `python unlock_all.py --port COM5` (check Device Manager → Ports) |
| macOS | `python3 unlock_all.py --port /dev/cu.usbmodem1101` |
| Linux | `python3 unlock_all.py --port /dev/ttyACM0` |

To see the codes without touching the badge: `python unlock_all.py --list`

## Is it safe?

Yes. The script only sends `UNLOCK` commands, exactly as you'd type them by hand. They can only add achievements, so running it twice does no harm; codes you already have show `ALREADY UNLOCKED`. It never changes the badge's firmware or writes to its memory directly.

One thing to avoid in general: on the badge's boot self-test screen, **don't hold A**. That's the badge's own "reset EEPROM" option, and it wipes all achievements and your handle.

## Troubleshooting

- **"No badge found":** try another cable (many are charge-only) or another USB port.
- **Linux "Permission denied":** add yourself to the serial group (`sudo usermod -aG dialout $USER` on Debian/Ubuntu, `uucp` on Arch), then log out and back in.
- **"NO REPLY" on some codes:** run it again with `--delay 1`.
