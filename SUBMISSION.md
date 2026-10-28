# REABadge — Reverse-Engineering a Conference CTF Badge with an AI Agent

**Target:** conference CTF badge firmware, Raspberry Pi RP2350 / Pico 2
(Cortex-M33, ARMv7E-M, 4 MB flash), C/C++ on the pico-sdk.
**Image:** `fw_dump/flash.bin`, SHA-256 `37ee8a7e3f256ff92f115e830acb147439ed3cca07f37f0b0e82160069b298fd`.
**Method:** static reverse engineering with Claude Code driving Ghidra 12.1.4 through
the REA MCP server, cross-checked against a live badge over USB serial. Then verified
firmware patches and a bot that plays the game on the badge from a laptop.
**Running on the badge now:** `backups/patched-crew/flash.bin`, SHA-256
`aaf337c06c9b4b0ebe95423fb1b9e12806f8871af6124677958344d307dac1c3`.

Everything below was recovered from decompiled pseudocode and verified either by a
self-contained Python reimplementation (no hardware) or against the physical badge.
Each claim is tied to a function or address so a judge can re-derive it.

---

## TL;DR — what was achieved

| Result | Evidence |
|---|---|
| **3 real flags decoded**, 1 decoy identified | `scripts/badge.py` prints all three; matches device |
| **All 30 unlock codes recovered** from one-way hashes | hash table self-verifies in `badge.py` |
| **Custom 64-bit hash reversed** (seed `"ProfPlum"`) | `FUN_10010a9c`, reimplemented |
| **GOST/Magma cipher reconstructed** for the hidden flag | key + S-box + schedule from RAM |
| **EEPROM save format + checksum cracked** | edit saves the badge accepts as valid |
| **Station UART protocol fully mapped** | `FUN_10003a94`, 9600 8N1 on GP0/GP1 |
| **Game economy understood** | starting credits formula, shop gate |
| **8-byte minigame patch**, flashed + verified | 3 branches neutralized, readback-matched |
| **Infinite fuel and hull** patch | 5 two-byte `nop`s; fuel stayed full through every bot run |
| **Remote-control console hook**: `BTN` `PEEK` `PAN` `WHERE` | 948 B in unused flash, emulator-tested, flashed + verified |
| **Game engine mapped**: screens, hex map, scoring, 66 events | decompiled, then confirmed screen by screen on the badge |
| **Autonomous cargo bot** playing on the badge | 31 of 36 runs delivered (86%), 22.1 / 24 cargo on average |
| **Hidden OFFLINE MODE** found | GP29 strap at boot: random 5-person crew, runs not saved |
| **Crew fix**: `CREW` command + no-crew-loss patch | flashed; 5 of 5 runs delivered, 0 crew lost |

The analysis needs **no hardware** to reproduce: `bash scripts/demo.sh` rebuilds the
RAM image, reimplements the crypto, and recovers everything from the image alone.

---

## 1. The console and the hidden `FLAG` command

The badge exposes a serial console (dispatcher `FUN_1000ff2c` @ `0x1000ff2c`). It reads
a line, uppercases the verb, and dispatches. `HELP` advertises only `HANDLE`, `UNLOCK`,
`IDENT`, `CLEAR` — but the dispatcher also handles a hidden **`FLAG <arg>`**.

### The four flags

| Flag | Value | Storage | Note |
|---|---|---|---|
| decoy | `{Rusty_C0d3_1s_4w3s0m3}` | plaintext @ `0x10028070` | **Never printed** — every branch overwrites the buffer. `strings` finds it first; it's bait. |
| FLAG 1 | `{At0m1c_Ut0p1a_1955}` | XOR 0xCC @ `0x10028088` | prints on device |
| FLAG 2 | `{R4ygun_G0th13_Ph4s3}` | `rol8((c^i^0xA5)+3i, 3)` @ `0x100280bc` | **gated**: EEPROM bytes 0..3 must equal `"PLUM"` |
| FLAG 3 | `{Fly1ng_C4r_Pr0m1s3}` | GOST/Magma @ `0x100280a0` | **device prints `*****`** — buffer is starred before output; recoverable only statically |

Two deliberate traps, both defeated:
- The **decoy** is the only plaintext flag, so a `strings` dump surfaces it first. Reading the
  dispatcher shows it's dead data.
- **FLAG 3** is correctly decrypted in RAM, then overwritten with `*` before the print call,
  so the hardware never reveals it. We recovered it by reimplementing the cipher instead.

### FLAG 3: the GOST/Magma reconstruction

The hidden flag uses GOST 28147-89 (Magma): a 256-bit key (8 × 32-bit words @ `0x100103cc`),
an 8×16 S-box @ `0x100109c4`, and a 32-round key schedule @ `0x10010a98`. The round function
is substitution then an 11-bit left rotate (`FUN_100109c8`). All three tables live in RAM, so
they only exist after the crt0 copy table runs — see §10. `badge.py` rebuilds that RAM image and
decrypts the three 8-byte blocks.

---

## 2. UNLOCK — 30 one-way hashes, all 30 codes recovered

Unlock codes are **not stored**. The firmware keeps only 64-bit hashes (30-entry table,
`FUN_1000e0d0`). `UNLOCK <code>` hashes the input (`FUN_10010a9c`) and sets the matching
achievement bit (bits 2..31) if a hash matches.

The hash is a custom xxHash/SipHash-style mix (constants `0x10010bec`–`0x10010c10`,
**seed = ASCII `"ProfPlum"` = `0x50726f66506c756d`**). Reversing it from the decompiled
mixing function let us hash candidates offline:

- 28 codes fell to a **wordlist pass**: codes follow `SC_<WORD>_<WORD>`, and the words come
  from the firmware's own string table + themed pools (`scripts/pool*.txt`).
- The last 2 (bit 15 `SC_GRAV_SHIFT`, bit 23 `SC_COSMIC_BIAS`) needed a **dict × dict brute
  force** — an OpenMP C port of the hash (`scripts/huntdd.c`) over the dwyl `words_alpha`
  list (~370k words). `scripts/consts.py` dumps the hash constants + target table as a C header.

All 30 are listed in [FINDINGS.md](FINDINGS.md#recovered-codes-30-of-30); the table in
`badge.py` **self-verifies** — each printed code is confirmed by re-hashing it at runtime.

---

## 3. The save file: editing what the badge trusts

Persistent state lives in an external EEPROM (I2C0, SDA=GP4, SCL=GP5, 400 kHz, 24C08 @ `0x50`,
1 KB). The save record is integrity-protected:

```
0x10  handle (15 B) + team letter @0x1f
0x20  achievement bitmask (u32)
0x26  vote counter
0x28  hash of bytes 0x10..0x27  (FUN_10010a9c over 0x18 bytes — same hash as UNLOCK)
0x40..0x3ff  station $-records (flight logs)
```

Because the checksum is the **same hash we already reversed**, we can change the saved
achievement mask and recompute a hash the badge accepts. This is how all 30 achievement bits
were set without playing: flip the mask to `0xFFFFFFFF`, rewrite the hash at `0x28`. `badge.py`
reproduces the stored hash exactly (`save hash valid: True`), proving the reimplementation is
byte-accurate.

> **FLAG 2 gate.** The flag checks EEPROM bytes 0..3 == `"PLUM"`. Those bytes normally hold the
> start of the `SC_SIGNAL_GHOST` unlock code. Writing `"PLUM"` there (`tools/plumwriter`, an
> SRAM-only helper loaded with `picotool load -x`, flash untouched) makes the device print FLAG 2.

---

## 4. Station UART protocol (fully mapped)

The badge docks with physical "stations" over a **second** serial link — **UART0, 9600 8N1,
GP0=TX / GP1=RX** (init @ `0x100103dc`), separate from the USB console. Incoming lines are
queued by interrupt into an 8 × 512-byte ring (`FUN_1001048c`); replies go out via
`FUN_1001044c`. The whole protocol lives in `FUN_10003a94`:

| Station → badge | Badge action |
|---|---|
| `$STATION n\|Tm\|name\|text` | Dock. Badge replies `$ID <team><badgeid5><handle14><mask%08X>`, dumps every flight-log `$`-record, then `$EOL`. |
| `$GAME <badgeid><runid>` | Upload ack — erase the matching flight-log record, freeing a slot. |
| `$OPTIONS` + up to 4 `%02d%03d%32[^\|]\|` | Load vote options; badge answers `$VOTE <badgeid> <n>`. 3rd vote → bit 9 (Civic Duty). |
| `$EOL a b c` | End session. `c` 1–9 → bit 7; `c` ≥ 10 → bit 8; `a` ≥ 9000 → bit 2 (Frequent Flyer). |
| `$CREW <20-byte entries>` | Up to 5 crew `[role A-E][id4][14 B]`. 5 crew → bit 5; 5 distinct roles → bit 6. |
| `$UNLOCK <code>` | Same as the USB `UNLOCK`. |
| anything else | `Bad uart command: %s` |

Station ranks shown: Cadet, Deckhand, Spacer, Veteran, Legend. This is the map of how the badge
reports progress to the organizers' infrastructure, and how stations award the event-side bits.

---

## 5. Game economy and the minigames

- **Starting credits = `1000 + 150 × popcount(achievement mask)`** (`0x10001076`, popcount
  `FUN_1000e070`). More achievements → richer runs. At 32 bits set that's $5800.
- **The outfit shop** (FUEL TANK, HULL ARMOR) only opens if **achievement bit 1** is set
  (`0x100032aa`). Bit 1 isn't an UNLOCK code — it's set after a completed run whose flight log
  saves (`0x100033e4`). Setting it in the save (§3) unlocks the shop permanently.
- **Minigames** "Clear the asteroid field" (fail: −2 hull) and "Escape the nebula" (fail: −2 fuel)
  run natively; inputs are the physical buttons (`FUN_1000dca4/dcb0`). On success they pay credits
  (nebula = +$300).

### The 8-byte auto-win patch

Three branches decide a minigame loss. Replacing each with a `nop` makes both games always reach
their success branch:

| Address | Original | Patched | Effect |
|---|---|---|---|
| `0x10005128` | `bne.w 0x10005bd8` | `nop.w` | asteroid: ignore collision → fail |
| `0x10005b68` | `cbnz r6, 0x10005bd8` | `nop` | asteroid: final hit check |
| `0x100067ee` | `bmi 0x10006838` | `nop` | nebula: "lost" check |

The patched image (`backups/patched-minigames/flash.bin`) differs from stock by exactly 8 bytes.
It was flashed with `picotool load -v` (write + verify), the flash was read back and matched, the
EEPROM was left untouched, and the post-flash self-check passed. Stock firmware is backed up and a
one-command restore is documented.

---

## 6. Infinite fuel and hull

The ship lives at `0x20002438`, with hull at `+0xb4` and fuel at `+0xb8`. A sweep of every store
instruction that touches those two fields found five places that make them go down. Each became a
two-byte `nop` (`00 bf`):

| Address | Was | What it stops |
|---|---|---|
| `0x100027b4` | `subs r3,#1` | each hex jump costs 1 fuel |
| `0x10001cc2` | `it ge` | fuel events: the cap clamp becomes unconditional, so any fuel event refills the tank |
| `0x10001ce0` | `it ge` | hull events: same trick, hull goes to full armour |
| `0x100033f0` | `subs r3,#2` | nebula failure, −2 fuel |
| `0x1000338a` | `subs r3,#2` | asteroid failure, −2 hull |

The writes that remain only refill or upgrade: run start (`0x1000106e`), return to the station
(`0x1000334e`), the outfit shop (`0x10002ff2`, `0x10003028`) and refuelling (`0x10002c08`).
`scripts/patch_infinite.py` checks the original bytes before patching. The image was flashed, read
back and matched. Across 14 bot runs of 20 to 46 hops each, fuel never moved off its starting value.

---

## 7. A remote control in 948 bytes

The game reads only the physical buttons, and the USB console has no game commands. So we added
some. The dispatcher's "Unknown command" branch at `0x100102e8` (6 bytes) now calls a small C
function (`tools/btninject/hook.c`) placed in empty flash at `0x10180000`. Anything the hook
doesn't recognise still prints the original message, so the stock commands behave exactly as before.

| Command | What it does |
|---|---|
| `BTN A` · `BTN up down` · `BTN 40` | Queues button presses. It sets the same event bits as the button interrupt (`0x20002e1c`), so the game can't tell the difference. |
| `PEEK addr [n]` | Reads up to 64 words of RAM or flash. Read-only, and it refuses other address ranges. |
| `PAN x y` | Sets the map view (`0x20044534/38`). The map pans with the raw pin levels (`FUN_1000dcc8`), which `BTN` can't reach, and the hex in the centre of the view is the travel target. |
| `WHERE` | Names the current screen. Every wait loop polls the console from its own call site, and the hook reads that return address off the dispatcher's stack frame. |

The button map came from the firmware's own Konami-code matcher at `0x1000db9c`
(↑ ↑ ↓ ↓ ← → ← → B A), which spells out which GPIO is which button:

```
UP=01 (GP23)  DOWN=02 (GP21)  LEFT=04 (GP22)  RIGHT=08 (GP19)
SEL=10 (GP20) B=20 (GP16)     A=40 (GP17)          // GPIO table @ 0x1016d25c
```

**Tested before flashing.** The hook ran in a Unicorn emulator against the real patched image, with
every command and error path checked. Only then did it go to the badge, with a readback check and a
one-command restore.

---

## 8. Mapping the game engine

A bot needs to know where it is and what each screen wants. `WHERE` gives the screen. Everything else
was decompiled from the game loop `FUN_10003258` and then confirmed on the badge one screen at a time.

| `WHERE` | Screen | Bot's move |
|---|---|---|
| `10003A9C` | Title (mode byte `0x20044a76` = 0) | A starts a run |
| `10002FA2` | Outfit shop | B leaves, since fuel and hull are already infinite |
| `100025FC` | Star map | `PAN` to the next hex, then A moves one hex |
| `10001B98` | Encounter choice | DOWN to the best option, then A |
| `10002B6E` | Trading post | A buys one unit, B leaves |
| `10003216` | Score screen | A |

- **The map is an axial hex grid** (flat-top, size 36). The centre hex is
  `trunc((180−px)·⅔/36)`, `trunc(((180−py)·0.577 − (180−px)/3)/36)`, so the bot computes the exact
  pan for any target hex. The path to it is at `0x20002248` (length `0x20044478`).
- **Each hex has a type** (`FUN_100005f4`). Home is (0,0) and ends the run. There are 9 trading posts
  with live prices, a 3-hex nebula and 6 asteroid fields, both of which launch minigames. Any other hex
  has a 1-in-3 chance of an encounter. The layout is re-randomised every run.
- **Score = 300 × cargo + 10 × crew + two bonus counters** (ship `+0xc4`, `+0xc8`). Credits don't count,
  so the goal is a full hold. Cargo is ship `+0xc0`; the cap is 24 units.
- **Encounters are data in flash** at `0x1005f78c` (66 events × 0x200 B). Each has up to 4 options, some
  gated on a crew role or a resource, and each option has weighted outcomes. Effects can change hull,
  fuel, credits, crew, cargo or the bonus counters, or award an achievement.
- **A run ends at zero crew** (`0x20003990`), as well as at zero hull or fuel. That matters because
  some encounter options remove a random crew member.

> **Hidden OFFLINE MODE.** At boot (`0x1000051e`) the firmware reads GPIO 29 and stores the inverted
> level at `0x20044a7b`. If GP29 is low, the title screen shows **"OFFLINE MODE"** (string @ `0x1002722c`),
> every run starts with a **random crew of five** (`FUN_10000850`), and the flight-log save
> (`FUN_10000754`) returns immediately, so **offline runs are never saved**. It reads like a strap for
> playing away from the stations. Our badge boots with GP29 high. We haven't traced what drives the pin
> on the badge PCB.

---

## 9. The cargo bot

`scripts/cargobot.py` plays on the badge from a laptop over USB. The badge runs the game and draws
every frame. The laptop reads state with `PEEK` and `WHERE`, decides the move, and sends presses.
Each run is a state machine, and every transition is appended to a JSONL log (`cargoruns.jsonl`):

```
STARTING → PLANNING_ROUTE → IN_TRANSIT ⇄ PROCESSING_ENCOUNTER → LOADING → IN_TRANSIT → DELIVERING → COMPLETED
```

- **Routing:** breadth-first search over the hex grid. It avoids the nebula and asteroid fields,
  because the minigames stop polling the console, and it avoids posts it isn't heading for.
- **Buying:** it picks the post with the best price-plus-distance and buys until the hold is full or
  credits run out. If it's still short, it tries the next post, then flies home.
- **Encounters:** it reads the event's outcome table from flash, drops options the crew can't take, and
  picks the best expected value. Cargo is worth 300 per unit, credits 1 each, and losing the last crew
  member counts as −1,000,000.

| Result | Value |
|---|---|
| Runs delivered | **31 of 36** (86%) with the encounter policy |
| Average cargo | **22.1 / 24**; 18 runs came home with a full hold |
| Encounters handled | **288**; 11 cost a crew member, 5 of those ended a run |
| Time per run | **29–70 s**, title screen to score screen, hands off |

> **What the first run taught.** The first version always took option 0. Three hexes in, an
> encounter's first option removed the only crew member, and the run ended. Reading the outcome tables
> from flash and scoring every option fixed most of it.

### When good choices aren't enough: the crew

The first 14 runs all delivered; then failures appeared. Every one was the same: a crew of one, and an
encounter where **every option** can remove a crew member. Scanning all 66 event tables showed 9 such
events, and two ("Mysterious Illness", "Dysentery Outbreak") always do. That is about a 6% chance of
losing the run per encounter, or roughly 57% survival over 9 encounters. No choice policy can fix that,
so the fix went into the firmware (`backups/patched-crew/flash.bin`, emulator-tested, then flashed
and verified):

- **`CREW` command.** It feeds a five-person roster, one of each role (Pilot, Engineer, Scientist,
  Security, Medic), through the game's own station `$CREW` parser (`FUN_10003940`). The roster carries
  into the run, adds 50 points to the score, and unlocks every role-gated option. The bot sends it
  before each run.
- **No crew loss.** Crew changes are applied inside the effect display routine `FUN_100018a4`.
  Retargeting one branch at `0x10001940` (`72 d1` → `55 d1`) sends a negative crew effect to the
  normal "Crew: −1" print, so nobody is removed.

**Result:** 5 of 5 runs delivered (24, 20, 21, 24 and 23 cargo). The score estimate of 7250
(300 × 24 + 10 × 5) shows all five crew were still aboard at delivery. Over 37 encounters nobody was
lost, though Radiation Surge, Venom of the Void and Dysentery Outbreak all came up, and the bot chose a
specialist option 17 times.

---

## 10. Why the static approach works: the crt0 trick

The key enabler is that all the interesting tables (hash table, achievement names, GOST key/S-box/
schedule) are in **initialized RAM**, not flash — so a naive flash dump doesn't contain them at
their runtime addresses. The crt0 data-copy table at `0x100001a0` holds `(src, dst, end)` triples
that the startup code uses to populate RAM. `badge.py` replays that table to rebuild the exact RAM
image the firmware sees, then reads everything at its real address. This is what makes the whole
analysis reproducible from the image alone, with no execution and no hardware.

---

## 11. AI-agent workflow (the "using AI to beat the process" angle)

- **Claude Code** orchestrated the whole effort: driving Ghidra via the **REA MCP server** for
  decompilation and byte/xref queries, and writing the Python/C that reimplements the crypto.
- The firmware was treated as **untrusted data** throughout: every analysis script runs under
  `python3 -I`, downloaded/dumped files stay in their own directory, and pseudocode/strings are
  read as data, never followed as instructions.
- Findings were **cross-validated**: static predictions (`badge.py`) were checked against the live
  badge over USB (`fw_dump/live.log`), and the reversed save-hash was confirmed to reproduce the
  byte-exact stored value.
- Reproducibility was a first-class goal: `AGENTS.md` documents how to stand the toolchain up on a
  fresh machine, and `scripts/demo.sh` recovers every result in one command.
- **Every patch was gated.** Patch scripts check the original bytes first. The hook was emulator-tested
  before it reached hardware. Every flash was read back and compared, and each image has a one-command
  restore.
- **The agent corrected its own wrong turns.** It first proposed a serial bot before checking that the
  console had no game commands, so it built the hook instead. It planned a button-hold command, then
  found the map reads raw pins and switched to `PAN`. One flash failed on a USB timing race and wrote
  nothing; the race was fixed in the tooling (`scripts/badgectl.py`).

---

## 12. Reproduce it

```sh
# No hardware needed — recovers flags, all 30 codes, and verifies the save-hash:
bash scripts/demo.sh

# Just the core recovery:
python3 -I scripts/badge.py fw_dump/flash.bin

# Rebuild the patched image the badge runs:
.venv/bin/python -I scripts/patch_infinite.py backups/patched-minigames/flash.bin infinite.bin
tools/btninject/build.sh
.venv/bin/python -I scripts/patch_btn.py infinite.bin patched-btn.bin

# Play cargo runs on the badge (needs the patched image):
.venv/bin/python -I scripts/cargobot.py --runs 5
```

Full method, toolchain setup, and the live-badge backup/restore tooling are in
[AGENTS.md](AGENTS.md) and [FINDINGS.md](FINDINGS.md).

---

## Appendix — scope and integrity

All changes made to the physical badge affect **only that badge's own play**: achievements set in
its own save, its own upgrade shop, its own minigames. The firmware differs from stock only by the
documented patches: 8 bytes for the minigames, 10 bytes for fuel and hull, and the 6-byte hook call
plus 948 bytes in unused flash, then 2 more bytes for crew with the hook grown to 1124 bytes
(`patched-crew`, the image the badge runs now). Every change has a verified backup and restore path, and the full
stock image is retained. The station protocol is **documented, not abused**.

> **Disclosed and approved.** Bot runs save ordinary `$GAME` flight logs to the badge's EEPROM, just
> like runs played by hand, and a station uploads them at the next dock. The organizers were told the
> runs were bot-played on patched firmware and approved the automation, which is the kind of creative
> engineering the badge was built to invite. (The pre-bot EEPROM is still kept at
> `backups/20261028-104653` if a clean save is ever wanted.)
