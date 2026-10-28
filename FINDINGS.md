# REABadge firmware analysis

**Target:** `fw_dump/flash.bin` (RP2350 / Cortex-M33, raw ARMv7-M image, base `0x10000000`)
SHA-256 `37ee8a7e3f256ff92f115e830acb147439ed3cca07f37f0b0e82160069b298fd`
**Tooling:** REA + Ghidra 12.1.4. All results below are from decompiled pseudocode, not strings alone.

## Serial console commands (dispatcher `FUN_1000ff2c` @ 0x1000ff2c)

Line is read, verb uppercased, then dispatched. A `$`-prefixed variant set mirrors these.

| Command | Behavior |
|---|---|
| `UNLOCK <code>` | Hash code, match against 30-entry achievement table |
| `HANDLE <name>` | Set handle (3–14 chars, restricted charset) |
| `IDENT` | Print current handle |
| `HELP` | Lists `HANDLE, UNLOCK, IDENT` |
| `CLEAR` | ANSI clear screen |
| `FLAG <arg>` | **Hidden** — prints a flag selected by the argument |

## FLAG — four hidden flags (each stored obfuscated, decoded at runtime)

- `{Rusty_C0d3_1s_4w3s0m3}` (plaintext @ 0x10028070): **false flag / decoy.** It's the only flag stored in plain text, so `strings` finds it first, but it's copied into the output buffer and **every branch overwrites it**, so the device never prints it. Don't submit it. `FLAG` alone → `Flag: requires argument`; `FLAG <other>` → `INVALID ARGUMENT`; `FLAG 2` with the flash gate unset → `INVALID`.
- `FLAG 1...` → `{At0m1c_Ut0p1a_1955}`  (21 bytes XOR 0xCC, data @ 0x10028088)
- `FLAG 2...` → `{R4ygun_G0th13_Ph4s3}`  (per byte i: `b=(c^i^0xA5)+3i; out=rol8(b,3)`; gated on stored check value 0x4d554c50 = "PLUM"; data @ 0x100280bc)
- `FLAG 3...` → `{Fly1ng_C4r_Pr0m1s3}`  (GOST/Magma block cipher; 32-bit-word key @ 0x100103cc, S-box @ 0x100109c4, 32-round schedule @ 0x10010a98; ciphertext @ 0x100280a0). **The firmware overwrites the decrypted buffer with `*` before printing**, so the device shows asterisks; this flag is only recoverable statically.

`HELP` also prints a 13-byte string XOR 0x55 (@ `*0x100103ac`) that decodes to `SC_DUST_FLUX`, the bit-13 unlock code.

**Live check 2026-10-27** (`/dev/ttyACM0`, logged in `fw_dump/live.log`): `FLAG 1` → `{At0m1c_Ut0p1a_1955}`;
`FLAG 2` → `INVALID` (this badge's stored check value isn't "PLUM"); `FLAG 3` → `***********************`.
All three match the static predictions.

**EEPROM (I2C0, SDA=GP4, SCL=GP5, 400 kHz, 24C08-style @ 0x50, 1 KB).** Bytes 0..15 shipped as
`SC_SIGNAL_GHOST\0`, the bit-11 ("Long-Term Memory") code. Written by the **EEPROM reset** in `FUN_10000300`
(self-test screen, "HOLD A TO RESET EEPROM DATA", ~3 s hold on A): zeroes all 1 KB, writes a new random handle +
hashed save record at 0x10, then 16 bytes XOR 0x55 (@ `*0x1000e01c`) = `SC_SIGNAL_GHOST\0` at offset 0.
**That reset wipes all achievements and `PLUM`.** No UART/station command reaches it (only caller is a boot path, 0x10000564).
Bytes 0x10..0x2f = save record (hash-checked); 0x40..0x3ff = 64-byte `$`-records from the station UART.
The FLAG 2 gate reads bytes 0..3 as a LE word and wants `PLUM`. On 2026-10-27 we wrote `PLUM` there with
`tools/plumwriter` (a no_flash program loaded into SRAM via `picotool load -x`; badge flash untouched) and the badge printed
`Flag: {R4ygun_G0th13_Ph4s3}`. Bytes 0..15 are now `PLUMIGNAL_GHOST`. The `S` command in plumwriter restores `SC_S`.
**Kept as `PLUM` by choice.** Re-verified after reboot: all 30 codes → `ALREADY UNLOCKED`, `FLAG 2` prints on device.

**Station UART protocol** (`FUN_10003a94`, "Bad uart command: %s"): `$STATION`, `$GAM…E` (erase record),
`$OPTIONS`, `$EOL` (awards bits 2/7/8 by score), `$CRE…W`. Not fully mapped.

*(Earlier notes had the FLAG 2/3 plaintexts swapped. Corrected 2026-10-27 from the decompiled dispatcher.)*

## UNLOCK — hash scheme (hash `FUN_10010a9c`, check `FUN_1000e0d0`)

Codes are NOT stored; only 64-bit hashes are. Custom SipHash/xxHash-style mix,
constants near 0x10010bec–0x10010c10, **seed = "ProfPlum" (0x50726f66506c756d)**.
Match sets the achievement bit (bits 2..31). Codes follow the pattern `SC_WORD_WORD`.

### Recovered codes (30 of 30)

| Bit | Achievement | Code |
|---|---|---|
| 2 | Frequent Flyer | `SC_VECTOR_BURN` |
| 3 | Relics of the First Builders | `SC_NOVA_TRACE` |
| 4 | The Obsidian Monolith | `SC_ION_WAKE` |
| 5 | Full Complement | `SC_SOLAR_SHEAR` |
| 6 | A Crew of Specialists | `SC_PLASMA_ARC` |
| 7 | Signed On | `SC_VOID_VECTOR` |
| 8 | Works Well With Others | `SC_STAR_OFFSET` |
| 9 | Civic Duty | `SC_ORBIT_DECAY` |
| 10 | Deep Storage | `SC_THRUST_LOSS` |
| 11 | Long-Term Memory | `SC_SIGNAL_GHOST` |
| 12 | Manual Override | `SC_ECHO_ORBIT` |
| 13 | Service Port | `SC_DUST_FLUX` |
| 14 | Dockmaster's Channel | `SC_PHASE_DRIFT` |
| 15 | Misaligned Home Row | `SC_GRAV_SHIFT` |
| 16 | Diagnostics Complete | `SC_CORE_FLUX` |
| 17 | Circles Within Circles | `SC_LAGRANGE_LOCK` |
| 18 | Connect the Dots | `SC_PULSE_FIELD` |
| 19 | Know a Guy | `SC_FIELD_ECHO` |
| 20 | Synthetic Minds | `SC_QUANTUM_WAKE` |
| 21 | Attack Surface Survey | `SC_DEEP_PARALLAX` |
| 22 | Fabric of Reality | `SC_RADIAL_DRIFT` |
| 23 | Blue Skies Ahead | `SC_COSMIC_BIAS` |
| 24 | Bare Metal | `SC_FLUX_VECTOR` |
| 25 | Sick Bay | `SC_ORBIT_TRACE` |
| 26 | Domestic Infrastructure | `SC_ASTRA_SHIFT` |
| 27 | Identity Crisis | `SC_ZENITH_DRIFT` |
| 28 | Open Access | `SC_ECHO_VECTOR` |
| 29 | Off the Record | `SC_DRIFT_LOCK` |
| 30 | Seal Broken | `SC_APOGEE_DRIFT` |
| 31 | The Watchtower | `SC_PERIGEE_SHIFT` |

All 30 recovered. The last two (bits 15, 23) fell to a dict×dict brute
(`scripts/huntdd.c`, OpenMP C) over dwyl `words_alpha` (370k words).

## Reproduction

`scripts/badge.py` rebuilds RAM from the crt0 data-copy table (@0x100001a0),
reimplements the hash + GOST, and recovers flags + codes.

## Ship upgrades & credits (2026-10-27)

- Upgrade state is RAM-only, per run: `0x200015a4` = fuel-tank level (start 5, max 15, cost $25×(lvl+1)),
  `+4` = hull-armor level (start 3, max 8, cost $30×(lvl+1)), `+0xc` = starting credits. Ship struct
  `0x20002438`: credits `+0xbc`, fuel `+0xb8`, hull `+0xb4`.
- Starting credits = **1000 + 150 × popcount(achievement mask)** (`0x10001076`, popcount `FUN_1000e070`).
- The outfit shop (`FUN_10002f84`) only opens if **achievement bit 1** is set (`0x100032aa`). Bit 1 is set on a
  completed run whose `$GAME` log saves (`0x100033e4`); bit 0 when a counter hits 10 (`0x1000dd3e`). Neither has an UNLOCK code.
- Applied: EEPROM mask `fffffffc` → `ffffffff`, hash @0x28 recomputed (`backups/mod-all-bits/eeprom.bin`), so the
  shop is open and runs start with $5800. Firmware untouched. Undo: `badgectl.py restore-eeprom backups/20261027-130203`.

## Station visit 2026-10-27 13:28 (diff `backups/20261027-131153` → `backups/20261027-132843`)

- EEPROM 0x26 (save+0x16) 0 → 1: **vote counter**. Station voting sends `$VOTE <badgeid> <n>` and calls `FUN_1000e238`,
  which increments it and rehashes; on the 3rd vote it sets bit 9 (Civic Duty). Save hash still valid.
- Slot 0 @0x40: `$GAME 2up2Ag63lo  1330  4 p7v8Eub4zB bhHA`, written by `FUN_10000754` when a run ends:
  `%5.5s` badge ID (`2up2A`, @0x20044444) + `%5.5s` encoded run ID + `%5d` score + `%2d` ship+0xc0, then crew NPC IDs.
- Achievement mask still `ffffffff`; firmware unchanged.

## Station UART protocol (`FUN_10003a94`, mapped 2026-10-27)

Link: **UART0, 9600 8N1, GP0 = TX, GP1 = RX** (init @0x100103dc). Lines are queued by IRQ into an 8×512 B ring
(`FUN_1001048c`); replies go out via `FUN_1001044c`. Separate from the USB console (which is also polled in the same loop).

| Station → badge | Badge action |
|---|---|
| `$STATION n\|Tm\|name\|text` | Dock (state 2). n=1 HORIZON, 2 MERIDIAN, 3 NEXUS, else FRONTIER STATION. Badge replies `$ID <team><badgeid5><handle14><mask%08X> `, then every non-empty `$`-record in EEPROM 0x40..0x3ff (the `$GAME` flight logs), then `$EOL \r\n`. |
| `$GAME <badgeid><runid>` | Erase every EEPROM record whose first 16 bytes match: the station's upload ack, which frees the slot. |
| `$OPTIONS` + up to 4 × `%02d%03d%32[^\|]\|` | Load vote options (number, current votes, label). The badge answers with `$VOTE <badgeid> <n>`, which bumps the EEPROM vote counter; the 3rd vote sets bit 9. |
| `$EOL a b c` | End of station session (state 1). c 1..9 sets bit 7, c ≥ 10 sets bit 8, a ≥ 9000 sets bit 2. |
| `$CREW <20-char entries…>` (only while docked) | Up to 5 crew: `[role A-E][id4][..14 bytes]`. 5 crew sets bit 5; 5 distinct roles sets bit 6. No valid entries means a crew of one (yourself). |
| `$UNLOCK <code>` | Same as USB `UNLOCK`. |
| anything else | `Bad uart command: %s` |

Rank titles shown at stations: Cadet, Deckhand, Spacer, Veteran, Legend.

## Minigames

"Clear the asteroid field" (fail: -2 hull) and "Escape the nebula" (fail: -2 fuel) run natively on the badge.
On success they pay credits. Input is only the physical buttons (SIO GPIO_IN read in `FUN_1000dca4/dcb0`).
No serial command injects button presses.

## Minigame auto-win patch (flashed 2026-10-27)

`backups/patched-minigames/flash.bin` (sha256 `33c53551…02e9c3`) = stock + 8 bytes:
`0x10005128` bne.w→nop.w and `0x10005b68` cbnz r6→nop (asteroid collision → fail), `0x100067ee` bmi→nop (nebula
"lost" check). Both games now run to their timer and always take the success/credits branch (nebula = +$300).
Readback after flashing matched; EEPROM untouched; `verify` ALL GOOD.
**Restore stock:** `.venv/bin/python -I scripts/badgectl.py restore-flash backups/20261027-132843`
(fixed restore-flash picotool arg order on the same day: filename must come before `-t/-o`).

## Infinite fuel + hull patch (flashed 2026-10-28)

`backups/patched-infinite/flash.bin` (sha256 `ade3ebf5…88da0b1`) = minigame patch + 5 × 2-byte `nop` (`00 bf`),
built by `scripts/patch_infinite.py` (asserts original bytes first):

| Addr | Was | Effect removed |
|---|---|---|
| `0x100027b4` | `subs r3,#1` | travel: fuel −1 per jump |
| `0x10001cc2` | `it ge` | event fuel delta: `movge r3,r2` becomes unconditional, so any fuel event sets fuel = tank cap |
| `0x10001ce0` | `it ge` | event hull delta: same, hull = armor cap |
| `0x100033f0` | `subs r3,#2` | nebula fail −2 fuel (already unreachable via minigame patch) |
| `0x1000338a` | `subs r3,#2` | asteroid fail −2 hull (already unreachable via minigame patch) |

Found by sweeping every `str` to ship+`0xb4`/`0xb8` (ship @`0x20002438`). Remaining writes are refills/upgrades:
run start `0x1000106e`, station return `0x1000334e` (reset to caps from `0x200015a4`), shop `0x10002ff2`/`0x10003028`,
refuel `0x10002c08`. Readback after flashing matched; `verify` ALL GOOD; EEPROM untouched. Flash: `.venv/bin/python -I scripts/badgectl.py restore-flash backups/patched-infinite`.

## Console hook: BTN / PEEK / PAN / WHERE (flashed 2026-10-28)

`backups/patched-btn/flash.bin` (sha256 `71b98d5d…b198bf5`) = infinite fuel/hull image + `tools/btninject/hook.c`
(948 B at `0x10180000`, unused flash) + 6 bytes at `0x100102e8` ("Unknown command" print → `add r0,sp,#0x38; bl hook`).
Build: `tools/btninject/build.sh && .venv/bin/python -I scripts/patch_btn.py backups/patched-infinite/flash.bin OUT`.

| Command | Effect |
|---|---|
| `BTN A` / `BTN up down` / `BTN 40` | OR mask into the latched press word `0x20002e1c` (what the GPIO IRQ `0x1000db78` sets; read+cleared by `FUN_1000dcb0`) |
| `PEEK addr [n]` | up to 64 words, RAM/flash only, read-only |
| `PAN x y` | write the nav-map pan ints `0x20044534/38` (the map centre hex is the travel target) |
| `WHERE` | call site of the console poll in the current wait loop = current screen (dispatcher saved lr = line buf + 0x8c) |

Button masks (GPIO table `0x1016d25c`, confirmed by the Konami-code matcher at `0x1000db9c`):
UP=1 (GP23), DOWN=2 (GP21), LEFT=4 (GP22), RIGHT=8 (GP19), SEL=16 (GP20), B=32 (GP16), A=64 (GP17).
The map pans with the *raw* pin read `FUN_1000dcc8`, which BTN does not reach, hence `PAN`.

## Game model (for `scripts/cargobot.py`)

- Title = top-level mode byte `0x20044a76` == 0 (`FUN_10004870`); A starts a run (`FUN_10003258`, in-run flag `0x20043efc`).
- Run: outfit shop `FUN_10002f84` (B leaves) → loop { map `FUN_100025c8` → location type `FUN_100005f4` }.
  Each A on the map moves **one hex** toward the centre hex (path array `0x20002248`, length `0x20044478`).
- Hex grid: axial, flat-top, size 36; centre hex = `trunc((180-px)·⅔/36)`, `trunc(((180-py)·0.57735 − (180-px)/3)/36)`.
- Location types: 3 = home (0,0) — cargo ≥ 1 ends the run, score = 300·cargo + ship[0xc4] + ship[0xc8] + 10·crew;
  4 = trading post (9 at ship+0x28.., prices ship+4..; menu buy/sell/refuel/leave, B leaves); 1 = nebula
  (ship+0x70, 3 hexes), 2 = asteroid field (ship+0x78.., 6, cleared → (100,100)); else 1/3 chance of an event.
  Minigames don't poll the console. Layout is re-randomised every run.
- Ship+0xc0 is the **cargo** count (cap `0x200015ac`, 24). Crew count `0x20003990` (roster `0x2000390c`, 5×0x1a);
  crew 0, hull 0 or fuel 0 ends the run.
- Events (`FUN_10001b38`): defs in flash at `0x1005f78c + idx·0x200`, current idx = `table@0x200022a0[(ctr@0x200049f8 − 1) % n@0x1005f788]`.
  Up to 4 options @+0x10 (stride 0x7c): flags +4 (bits 0..4 crew role A–E, 0x20 cargo, 0x40 credits, 0x80 fuel ≥ need@+6),
  outcomes @+0xc (stride 0x1c, weight +8, effect count +9, effects +10: type byte + s16). Effect types: 0 hull, 1 fuel,
  2 credits, 3 crew (negative = random crew member removed), 4 cargo, 5/6 score bonus, 7 achievement.

## Cargo bot (2026-10-28)

`.venv/bin/python -I scripts/cargobot.py --runs N` — state machine STARTING → PLANNING_ROUTE → IN_TRANSIT →
PROCESSING_ENCOUNTER → LOADING → … → DELIVERING → COMPLETED/FAILED, JSONL log `cargoruns.jsonl`. BFS route avoiding
hazards and other posts; buys at the cheapest reachable post until the hold is full; encounters pick the option with the
best expected value (losing the last crew member = −1e6). Before each run it sends `CREW` (no-op on older firmware).

Results on `patched-btn` (crew of one), from `cargoruns.jsonl`: **31 delivered, 5 failed (86%)**, 22.1/24 cargo on
average, 18 full holds, 29–70 s per run, 288 encounters. Every failure was crew loss. (The very first run, "always
option 0", also died that way; it is mislabelled COMPLETED in the log because FAILED detection came later.)

## Crew: why runs failed, and the fix (2026-10-28)

- A run starts with a **crew of one** (you) unless a station `$CREW` filled the roster. 9 of the 66 events can remove
  a crew member **whatever option is chosen**; "Mysterious Illness" (#31) and "Dysentery Outbreak" (#8) always do.
  Averaged over all events that is ~6% death per encounter → ~57% survival for a 9-encounter run.
- Crew effects are applied inside the effect *display* routine `FUN_100018a4`, not in the effect switch of
  `FUN_10001b38`. Negative crew → `bne 0x10001a28` (remove a random member, count−1).
- Roles: A Pilot, B Engineer, C Scientist, D Security, E Medic (from the role tags on gated option labels).
  `$CREW` parser `FUN_10003940`: 5 × 20 chars `[role][id5][name14]`, level fixed at 1, count `0x20003990`; awards
  bits 5/6 via `FUN_1000e198` (returns early if the bit is already set, so no EEPROM write on this badge).
- The roster **persists into a run**: `FUN_10000850` only builds a crew of one when the count is 0.

**`backups/patched-crew/flash.bin`** (sha256 `aaf337c06c9b4b0ebe95423fb1b9e12806f8871af6124677958344d307dac1c3`)
— **flashed 2026-10-28**, readback-verified, `verify` ALL GOOD (EEPROM untouched) = everything in `patched-btn` plus:
- `0x10001940` `72 d1` → `55 d1`: the crew-loss branch now goes to the generic "Crew: −1" print (`0x100019ee`), so
  nobody is removed (added to `scripts/patch_infinite.py`).
- `CREW` console command (hook is now 1124 B): feeds a fixed 5-role roster (Pilot Vega, Eng. Torque, Sci. Halley,
  Sec. Kestrel, Medic Okafor) through the real `$CREW` parser. Unicorn test: roster written byte-exact, count 5.

Live: `CREW` → `CREW: OK 5`, roster read back via PEEK byte-exact. First 5 bot runs: **5/5 delivered** (24/20/21/24/23
cargo, est. score up to 7250 = 300·24 + 10·5, so the full crew was aboard at delivery), 37 encounters, **0 crew lost**
(Radiation Surge, Venom of the Void and Dysentery Outbreak all came up), and the specialist option (index 3) was the
bot's pick 17 times.

Rebuild: `scripts/patch_infinite.py backups/patched-minigames/flash.bin X` → `tools/btninject/build.sh` →
`scripts/patch_btn.py X OUT`.

## Hidden OFFLINE MODE (2026-10-28)

Boot (`0x1000051e`) reads SIO GPIO_IN bit 29 and stores `!GP29` in the byte `0x20044a7b`. When **GP29 is low at boot**:
- the title screen (`FUN_10004870`, `0x100046c4`) draws **"OFFLINE MODE"** (string @ `0x1002722c`);
- every run starts with a **random crew of 5** (`FUN_10000850` @ `0x100010de`: random role A–E, generated name/ID);
- the flight-log save `FUN_10000754` returns at once (`0x1000075a`), so **offline runs are never saved** and use no slots.
It also changes the boot path at `0x10000548`. Our badge boots with GP29 high (normal mode). What drives GP29 on the
badge PCB isn't known (on a stock Pico 2 it is the VSYS/3 sense pin). Forcing the mode in firmware would be a 2-byte
patch at `0x1000052a` (`eors r3,r6` → `movs r3,#1`); not built.

## `$GAME` flight-log record — full field decode (`FUN_10000754`, 2026-10-27)

Record built with `snprintf(dst, 0x20, "$GAME %5.5s%5.5s %5d %2d ", id, run, score, hold)`,
then crew IDs, then a MAC, into a 64-byte EEPROM slot:

| Field | Width | Source | Meaning |
|---|---|---|---|
| badge ID | `%5.5s` | `FUN_1000e22c` → `*0x20044444` | 5-char badge token, set at boot, also sent in `$ID` |
| run ID | `%5.5s` | `base64(rng32)[:5]` | `FUN_1000d570`=RNG (`FUN_1000d3e8`→TRNG `FUN_10007a50`), base64 `FUN_1000da14` |
| score | `%5d` | `300·deliveries + ship[0xc4] + ship[0xc8] + 10·*0x20003990` (caller `0x100033ae`) | final mission score |
| hold | `%2d` | `ship[0xc0]` | cargo/hold count at end of run |
| crew | — | up to N crew NPC IDs (`DAT_10000840` count, stride 0x1a) + `DAT_10000848` | crew roster |
| **MAC** | 4 chars | `base64(hash(record, key=badgeID))[:4]` (`FUN_1000dd84`) | integrity tag |

**The MAC is the custom 64-bit hash (`FUN_10010a9c`) keyed on the 6-byte badge ID**, base64'd,
truncated to 4 chars. base64 alphabet is standard (`ABC…xyz0-9+/`, table @ `0x1016d218`).
This is the same hash reversed for UNLOCK/EEPROM — so the MAC is **not a secret-keyed MAC**: the
key is the badge ID, which the badge broadcasts in cleartext in its `$ID` line. See SECURITY_NOTES.md.

## Boot image / RP2350 secure-boot posture

picotool reports the image as **"ARM Secure"**, but that is only the Arm *security state* the image
runs in, not a cryptographic guarantee. The RP2350 IMAGE_DEF block @ `0x10000138` (marker
`0xffffded3` … `0xab123579`) contains a **single IMAGE_TYPE item** (`0x1021` = EXE / RP2350 / ARM /
Secure) and a LAST item — **no HASH_DEF block and no SIGNATURE block**. Combined with the fact that an
arbitrary re-flashed image boots (our 8-byte patch ran), the chip's OTP **`SECURE_BOOT_ENABLE` /
flash-lock fuses are unprogrammed**. So any image loads over BOOTSEL/`picotool`; nothing verifies it.
This is expected for a hackable conference badge, and it is *why* the static+patch workflow works.

The **EEPROM-reset** path ("HOLD A TO RESET EEPROM DATA", `FUN_10000300`, caller `0x10000564`) is
reachable only from the boot self-test, never from USB or the station UART — the one destructive path,
and it is physically gated behind holding A at power-on.
