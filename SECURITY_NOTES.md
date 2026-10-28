# REABadge — Station Protocol Trust Model: Findings for Organizers

**Audience:** the badge/CTF organizers and infrastructure maintainers.
**Purpose:** document the trust assumptions in the badge ↔ station link so the scoring
infrastructure can be hardened. This is a defensive write-up: it describes *what a badge could
assert* and *how to tell*, not a tool for doing it. No forged traffic was produced, and the
only changes made to any badge were confined to that badge's own local play.

**Scope of evidence:** static analysis of `fw_dump/flash.bin`
(SHA-256 `37ee8a7e…069b298fd`), cross-checked against one physical badge. Addresses and function
names refer to [FINDINGS.md](FINDINGS.md).

---

## Summary

The station link treats the badge as a **trusted, authoritative source** of its own achievements,
votes, crew, and flight-log scores. The badge's only integrity mechanism — a 4-character tag on each
flight-log record — is keyed on a value the badge itself broadcasts in the clear, so it authenticates
nothing against a party who can read one `$ID` line. If station-side scoring or a leaderboard consumes
these records as-is, it is trusting client-supplied data.

This is a reasonable posture for a *badge* (it's meant to be hacked). It is worth hardening on the
*station/infrastructure* side if any shared ranking depends on it.

---

## How the link works (recap)

- Physical link: **UART0, 9600 8N1, GP0/GP1** — a wired dock, no pairing or session key.
- On dock the badge sends, in cleartext:
  - `$ID <team><badgeID><handle><achievement-mask>` — its identity and full achievement bitmask.
  - every stored `$GAME` flight-log record (score, crew, run ID, + a 4-char tag).
- The station can send `$UNLOCK`, `$VOTE`, `$CREW`, `$OPTIONS`, `$EOL`; the badge awards itself the
  corresponding achievement bits locally.

Full command table and record format: [FINDINGS.md](FINDINGS.md).

---

## Findings

### F1 — The flight-log "MAC" is keyed on a public value
**What.** Each `$GAME` record ends with a 4-char tag = `base64(hash(record, key = badgeID))[:4]`
(`FUN_1000dd84`). The hash (`FUN_10010a9c`) is the firmware's custom 64-bit mix; its constants are in
the image and have been reproduced exactly. The **key is the 6-byte badge ID** — which the badge sends
in cleartext in every `$ID` line.
**Impact.** The tag detects accidental corruption, not forgery. Anyone who observes one `$ID` line has
the key and can compute a valid tag for any record attributed to that badge. It is a checksum, not an
authenticator.
**Also.** 4 base64 chars ≈ 24 bits, so even treating it as opaque, a blind guess collides ~1 in 16M —
weak if records are ever accepted without rate limiting.

### F2 — Identity (`$ID`) is self-asserted
**What.** Team, badge ID, handle, and the 32-bit achievement mask are whatever the badge chooses to
send; there is no challenge, signature, or enrollment secret.
**Impact.** A device on the UART can present any badge ID and any achievement mask. Station-side state
keyed on badge ID can be written under another badge's identity.

### F3 — Achievements are client-authoritative
**What.** The mask is set on the badge (UNLOCK codes, `$EOL`/`$VOTE`/`$CREW` awards, or a direct EEPROM
edit — the save checksum is the same reversible hash, see FINDINGS §3). The badge then reports the
whole mask in `$ID`.
**Impact.** "Achievements earned" as seen by a station reflects the badge's local state, which the
holder fully controls. It is not evidence that the tasks were performed.

### F4 — Scores are client-computed
**What.** `$GAME` score is computed on the badge from local run state (`FUN_10000754`), tagged per F1,
and uploaded on dock.
**Impact.** A leaderboard built directly from uploaded `$GAME` records is ranking self-reported numbers.

### F5 — Firmware is unverified at boot
**What.** The RP2350 image is flagged "ARM Secure" but carries **no hash or signature block**, and the
OTP secure-boot/flash-lock fuses are unprogrammed (an arbitrary image flashes and runs). See FINDINGS.
**Impact.** Expected and probably intended for a hackable badge; noted so it's a conscious choice. It
means nothing about a badge's on-wire behavior can be assumed from "it's our firmware.




### F6 — Runs can be played by software (demonstrated, disclosed, approved)
**What.** With a 6-byte hook plus code in unused flash (possible because of F5), the USB console can
inject button presses, read RAM and name the current screen. `scripts/cargobot.py` uses that to play full
cargo runs unattended: 31 of 36 delivered, 22.1/24 cargo on average. Further patches remove fuel, hull and
crew loss. The resulting `$GAME` records are ordinary records (F4); nothing in them shows the run was
automated or the firmware patched. See SUBMISSION §6–§9.
**Status.** Disclosed to the organizers on 2026-10-28, who approved it and plan to present it at the badge
talk.
**Impact.** It shows F4 and F5 in practice: a leaderboard can't tell bot-played runs from hand-played ones.

### F7 — OFFLINE MODE strap (GP29)
**What.** At boot the firmware latches `!GP29` into `0x20044a7b`. When GP29 is low, the title shows
"OFFLINE MODE", every run gets a random 5-person crew, and flight logs are **not saved**
(`FUN_10000754` returns early). See FINDINGS "Hidden OFFLINE MODE".
**Impact.** Offline runs never reach a station, so they don't affect scoring. Worth knowing when a badge
reports no flight logs: it may simply be booting offline.
