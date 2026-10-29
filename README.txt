2026 SaintCon Badge Hack — project folder (updated 2026-10-28)

START HERE: SETUP.md  - set up Python (.venv from requirements.txt), serial access, run the bot.

SUBMISSION.md / 2026-SaintCon-Badge-Hack-Teardown.html   write-up for the badge talk (the .html opens in any browser)
FINDINGS.md                              every address, patch and result
AGENTS.md                                continuing the reverse engineering; backup/restore details
SECURITY_NOTES.md                        station-protocol notes for the organizers

backups/<name>/       firmware images (flash.bin) and EEPROM backups; current image: backups/patched-crew
scripts/badgectl.py   verify | backup | restore-eeprom DIR | restore-flash DIR | replay --handle NAME
scripts/cargobot.py   plays cargo runs on the badge (needs the patched firmware)
tools/                plumwriter (RAM-only EEPROM helper), btninject (console hook source)

Quick check with the badge plugged in (after SETUP.md step 1):
  .venv/bin/python -I scripts/badgectl.py verify
