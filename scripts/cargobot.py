#!/usr/bin/env python3
"""Cargo-run bot for the badge (needs the patched firmware: BTN / PEEK / PAN / WHERE, and CREW if present).

usage: .venv/bin/python -I scripts/cargobot.py [--runs N] [--log runs.jsonl] [--dry]

One run: title -> outfit shop -> plan a route to the cheapest reachable trading post -> step hex by hex
(resolving encounters) -> buy cargo until the hold is full or credits run out -> step home to (0,0) ->
the game scores 300 x cargo and saves the $GAME flight log -> back to the title screen.

The screen is identified by WHERE (the wait loop that is polling the console). Hazard hexes (nebula,
asteroid fields) are avoided because the minigames run without polling the console. Every state
transition and encounter is appended to the JSONL log.
"""
import argparse, json, math, os, re, sys, time
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import badgectl  # noqa: E402  (open_port: udev-permitted /dev/ttyACM*)

SHIP = 0x20002438          # ship struct; offsets below are from FINDINGS.md / FUN_10003258
CAPS = 0x200015a4          # [fuel cap, hull cap, cargo cap, start credits]
CREW = 0x20003990
INRUN = 0x20043efc
MODE = 0x20044a74          # byte 2 = top-level mode (0 = title)
PATH_N = 0x20044478
PATH = 0x20002248
PAN_MIN, PAN_MAX = (-400, -440), (750, 820)   # clamp in FUN_100025c8

# WHERE values (call site of the dispatcher in each wait loop)
TITLE, OUTFIT, MAP, ABANDON = 0x10003A9C, 0x10002FA2, 0x100025FC, 0x10002676
EVENT, EVENT_RESULT, POST = 0x10001B98, 0x10001C88, 0x10002B6E
GAME_OVER, SCORE, NO_CARGO, LOG_FULL, LOG_FULL_START = 0x100030B0, 0x10003216, 0x100034B4, 0x100035B2, 0x10003298
TRANSIENT = {0x1000330C, 0x10002C18}  # once-per-loop polls, not waits
ACK_ANY = {EVENT_RESULT, GAME_OVER, SCORE, NO_CARGO, LOG_FULL, LOG_FULL_START, 0x1000379A, 0x100037B2, 0x100030B0}

EV_COUNTER, EV_TABLE, EV_DEFS, EV_N = 0x200049f8, 0x200022a0, 0x1005f78c, 0x1005f788   # FUN_10003258 default case
ROSTER = 0x2000390c        # 5 x 0x1a crew entries: [role 'A'..'E'][level]...
EFFECT_NAMES = {0: 'hull', 1: 'fuel', 2: 'credits', 3: 'crew', 4: 'cargo', 5: 'bonus5', 6: 'bonus6', 7: 'achievement'}

NEIGHBOURS = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, -1), (-1, 1)]   # FUN_10001dd0


def s32(v):
    return v - (1 << 32) if v >> 31 else v


def hexdist(a, b):
    dq, dr = a[0] - b[0], a[1] - b[1]
    return (abs(dq) + abs(dr) + abs(dq + dr)) // 2


def hex_of(px, py):
    """Centre-of-view hex for a pan, same double math as FUN_10001dd0 (truncating)."""
    x, y = float(180 - px), float(180 - py)
    q = x * 0.6666666666666666 / 36.0
    r = (y * 0.57735026919 + x * -0.3333333333333333) / 36.0
    return q, r


def pan_for(h):
    """Pan that puts hex h in the centre with the widest margin, or None if outside the pan clamp."""
    q, r = h
    cx, cy = 180 - round(q * 54), 180 - round((q / 2 + r) * math.sqrt(3) * 36)
    best = None
    for dx in range(-25, 26):
        for dy in range(-25, 26):
            px, py = cx + dx, cy + dy
            if not (PAN_MIN[0] <= px <= PAN_MAX[0] and PAN_MIN[1] <= py <= PAN_MAX[1]):
                continue
            fq, fr = hex_of(px, py)
            if math.trunc(fq) != q or math.trunc(fr) != r:
                continue
            m = min(1 - abs(fq - q) if q == 0 else min(abs(fq) - abs(q), 1 - (abs(fq) - abs(q))),
                    1 - abs(fr - r) if r == 0 else min(abs(fr) - abs(r), 1 - (abs(fr) - abs(r))))
            if best is None or m > best[0]:
                best = (m, px, py)
    return best and best[1:]


class Badge:
    def __init__(self):
        self.s = badgectl.open_port()

    def cmd(self, line, timeout=2.0):
        self.s.reset_input_buffer()
        self.s.write((line + '\r\n').encode())
        buf, end = b'', time.time() + timeout
        while time.time() < end:
            buf += self.s.read(self.s.in_waiting or 1)
            if buf.endswith(b'> '):
                return buf.decode('latin1')
        return None  # console not polled (minigame running, or busy animating)

    def peek(self, addr, n=1):
        r = self.cmd(f'PEEK {addr:08X} {n:X}')
        m = r and re.search(r'PEEK [0-9A-F]{8}((?: [0-9A-F]{8})+)', r)
        return [int(x, 16) for x in m.group(1).split()] if m else None

    def where(self):
        r = self.cmd('WHERE', 1.0)
        m = r and re.search(r'WHERE ([0-9A-F]{8})', r)
        return int(m.group(1), 16) if m else None

    def press(self, btn):
        r = self.cmd(f'BTN {btn}')
        if not r or 'BTN: OK' not in r:
            raise RuntimeError(f'BTN {btn} failed: {r!r}')

    def pan(self, px, py):
        r = self.cmd(f'PAN {px} {py}')
        if not r or 'PAN: OK' not in r:
            raise RuntimeError(f'PAN failed: {r!r}')

    def read(self, addr, n):
        """n bytes from RAM/flash via PEEK (word-granular)."""
        base, out = addr & ~3, b''
        while len(out) < (addr - base) + n:
            words = self.peek(base + len(out), min(64, ((addr - base) + n - len(out) + 3) // 4))
            out += b''.join(w.to_bytes(4, 'little') for w in words)
        return out[addr - base:addr - base + n]

    def event_def(self):
        """Event currently on screen: FUN_10003258 picked table[counter % n], then incremented counter."""
        n = self.peek(EV_N)[0]
        idx = self.peek(EV_TABLE + 4 * ((self.peek(EV_COUNTER)[0] - 1) % n))[0]
        base = EV_DEFS + idx * 0x200
        raw = self.read(base, 0x200)
        u16 = lambda o: int.from_bytes(raw[o:o + 2], 'little')
        s16 = lambda o: int.from_bytes(raw[o:o + 2], 'little', signed=True)
        opts = []
        for i in range(raw[0xc]):
            o = 0x10 + i * 0x7c
            outs = []
            for k in range(max(1, raw[o + 8])):
                oc = o + 0xc + k * 0x1c
                outs.append({'w': raw[oc + 8] if raw[o + 8] else 1,
                             'effects': [(raw[oc + 10 + 4 * j], s16(oc + 12 + 4 * j)) for j in range(raw[oc + 9])]})
            opts.append({'flags': raw[o + 4], 'need': u16(o + 6), 'outcomes': outs})
        name = self.read(int.from_bytes(raw[4:8], 'little'), 40).split(b'\0')[0].decode('latin1')
        return idx, name, opts

    def full_crew(self):
        """Fill the roster with one of each role (CREW, patched-crew firmware). False on older firmware."""
        r = self.cmd('CREW')
        return bool(r and 'CREW: OK' in r)

    def snapshot(self):
        sh = self.peek(SHIP, 0x34)
        if sh is None:
            return None
        v = lambda o: s32(sh[o // 4])
        caps = [s32(x) for x in self.peek(CAPS, 3)]
        return {
            'where': self.where(), 'mode': (self.peek(MODE)[0] >> 16) & 0xff, 'in_run': self.peek(INRUN)[0],
            'pos': (v(0xa8), v(0xac)), 'hull': v(0xb4), 'fuel': v(0xb8), 'credits': v(0xbc),
            'cargo': v(0xc0), 'cargo_cap': caps[2], 'crew': self.peek(CREW)[0],
            'prices': [v(4 + 4 * i) for i in range(9)],
            'posts': [(v(0x28 + 8 * i), v(0x2c + 8 * i)) for i in range(9)],
            'nebula': (v(0x70), v(0x74)),
            'asteroids': [(v(0x78 + 8 * i), v(0x7c + 8 * i)) for i in range(6)],
        }


def hazards(st):
    nx, ny = st['nebula']
    bad = {(nx, ny), (nx + 1, ny), (nx + 1, ny - 1)}            # FUN_100005f4 type 1
    bad |= {a for a in st['asteroids'] if a != (100, 100)}      # type 2 (cleared = 100,100)
    return bad


def route(st, start, goal, avoid_posts=True):
    """BFS over hexes the map can centre on, avoiding hazards (and other trading posts)."""
    block = hazards(st) | (set(st['posts']) - {goal} if avoid_posts else set())
    prev, q = {start: None}, deque([start])
    while q:
        h = q.popleft()
        if h == goal:
            path = []
            while h != start:
                path.append(h)
                h = prev[h]
            return path[::-1]
        for d in NEIGHBOURS:
            n = (h[0] + d[0], h[1] + d[1])
            if n not in prev and n not in block and abs(n[0]) <= 11 and abs(n[1]) <= 12 and pan_for(n):
                prev[n] = h
                q.append(n)
    return None


class Run:
    """One cargo run as a state machine; state lives on the badge, this object only tracks intent."""

    def __init__(self, badge, log, run_no, dry=False):
        self.b, self.log, self.run_no, self.dry = badge, log, run_no, dry
        self.state, self.target, self.encounters, self.t0 = 'WAITING_FOR_RUN', None, 0, time.time()
        self.delivered = False

    def emit(self, kind, **kw):
        rec = {'t': round(time.time() - self.t0, 2), 'run': self.run_no, 'state': self.state, 'event': kind, **kw}
        self.log.write(json.dumps(rec) + '\n')
        self.log.flush()
        print(f"[run {self.run_no} {rec['t']:7.1f}s] {self.state:<20} {kind} "
              + ' '.join(f'{k}={v}' for k, v in kw.items()))

    def go(self, state, **kw):
        self.state = state
        self.emit('enter', **kw)

    def wait_change(self, prev_where, prev=None, timeout=12.0):
        """Poll until the screen (or the watched value) changes; tolerate console silence (animations)."""
        end = time.time() + timeout
        while time.time() < end:
            w = self.b.where()
            if w is not None and w not in TRANSIENT and (w != prev_where or (prev and prev())):
                return w
            time.sleep(0.15)
        return self.b.where()

    def available(self, opt, st):
        """FUN_10001564: crew role requirement, or cargo/credits/fuel >= need."""
        f, need = opt['flags'], opt['need']
        for bit, role in ((1, 'A'), (2, 'B'), (4, 'C'), (8, 'D'), (0x10, 'E')):
            if f & bit:
                roster = self.b.read(ROSTER, 5 * 0x1a)
                return any(roster[k * 0x1a] == ord(role) and need <= roster[k * 0x1a + 1] for k in range(5))
        if f & 0x20 and st['cargo'] < need:
            return False
        if f & 0x40 and st['credits'] < need:
            return False
        if f & 0x80 and st['fuel'] < need:
            return False
        return True

    def value(self, opt, st):
        """Expected score impact. Losing the last crew member ends the run, so it dominates."""
        total_w = sum(o['w'] for o in opt['outcomes']) or 1
        ev = 0.0
        for o in opt['outcomes']:
            v = 0.0
            for kind, amt in o['effects']:
                if kind == 3:
                    v += -1e6 if st['crew'] + amt < 1 else 10 * amt - (500 if amt < 0 else 0)
                elif kind == 4:
                    v += 300 * max(-st['cargo'], min(amt, st['cargo_cap'] - st['cargo']))
                elif kind == 2:
                    v += max(amt, -st['credits'])
                elif kind in (5, 6):
                    v += amt
                elif kind == 7:
                    v += 50
            ev += o['w'] * v
        return ev / total_w

    def choose_post(self, st):
        """Cheapest-per-trip post: price plus a distance penalty, among posts with a safe route."""
        best = None
        for i, p in enumerate(st['posts']):
            if st['prices'][i] > st['credits']:
                continue
            path = route(st, st['pos'], p)
            if path is None:
                continue
            cost = st['prices'][i] + 25 * len(path)
            if best is None or cost < best[0]:
                best = (cost, i, path)
        return best

    def step_to(self, goal, avoid_posts=True):
        """Move one hex along a fresh route. Returns the WHERE after the move."""
        st = self.b.snapshot()
        path = route(st, st['pos'], goal, avoid_posts)
        if not path:
            raise RuntimeError(f'no safe route {st["pos"]} -> {goal}')
        nxt = path[0]
        px, py = pan_for(nxt)
        self.b.pan(px, py)
        time.sleep(0.12)
        n = self.b.peek(PATH_N)[0]
        p1 = [s32(x) for x in self.b.peek(PATH + 8, 2)]
        if n != 2 or tuple(p1) != nxt:
            self.emit('pan_miss', want=nxt, got=p1, path_n=n)
            return MAP
        self.b.press('A')
        w = self.wait_change(MAP, prev=lambda: tuple(s32(x) for x in self.b.peek(SHIP + 0xa8, 2)) != st['pos'])
        self.emit('moved', to=nxt, remaining=len(path) - 1, fuel=self.b.snapshot()['fuel'])
        return w

    def handle_common(self, w):
        """Screens that can appear anywhere. Returns True if handled."""
        if w == EVENT:
            self.encounters += 1
            before = self.b.snapshot()
            prev = self.state
            self.state = 'PROCESSING_ENCOUNTER'
            idx, name, opts = self.b.event_def()
            avail = [i for i, o in enumerate(opts) if self.available(o, before)]
            values = {i: round(self.value(opts[i], before), 1) for i in avail}
            pick = max(avail, key=lambda i: values[i])
            self.emit('encounter_options', event_id=idx, name=name, values=values, pick=pick)
            for _ in range(avail.index(pick)):                  # cursor starts on the first available option
                self.b.press('DOWN')
                time.sleep(0.35)
            self.b.press('A')
            w2 = self.wait_change(EVENT)
            if w2 == EVENT_RESULT:
                self.b.press('A')
                self.wait_change(EVENT_RESULT)
            after = self.b.snapshot()
            delta = {k: after[k] - before[k] for k in ('hull', 'fuel', 'credits', 'cargo', 'crew') if after[k] != before[k]}
            self.emit('encounter', n=self.encounters, at=before['pos'], effect=delta)
            self.state = prev
            return True
        if w in ACK_ANY:
            self.emit('ack', screen=hex(w))
            self.b.press('A')
            self.wait_change(w)
            return True
        if w == ABANDON:
            self.b.press('B')                                   # never abandon
            self.wait_change(ABANDON)
            return True
        if w == POST and self.state != 'LOADING':
            self.b.press('B')                                   # wandered into a post we did not plan
            self.wait_change(POST)
            return True
        return False

    def run(self):
        b = self.b
        # WAITING_FOR_RUN: title screen, mode 0, not in a run
        st = b.snapshot()
        if st['in_run']:
            self.go('RESUMING', at=st['pos'], cargo=st['cargo'])   # picked up a run already in progress
            w = st['where']
            while w not in (MAP, None) and self.handle_common(w):
                w = b.where()
        elif st['where'] == TITLE and st['mode'] == 0:
            if self.b.full_crew():                              # roster survives into the run (FUN_10000850)
                self.emit('crew_filled', crew=self.b.peek(CREW)[0])
            self.go('STARTING')
            b.press('A')
            w = self.wait_change(TITLE)
            if w == LOG_FULL_START:
                self.handle_common(w)
                w = b.where()
        else:
            self.emit('not_at_title', where=hex(st['where'] or 0), mode=st['mode'], in_run=st['in_run'])
            return None
        if w == OUTFIT:
            b.press('B')                                        # fuel/hull are infinite: skip upgrades
            w = self.wait_change(OUTFIT)
        if w != MAP:
            self.emit('unexpected', where=hex(w or 0))
            return None

        # PLANNING_ROUTE -> IN_TRANSIT -> LOADING, repeated until the hold is full or nothing is affordable
        while True:
            st = b.snapshot()
            if st['cargo'] >= st['cargo_cap']:
                break
            pick = self.choose_post(st)
            if not pick:
                if st['cargo'] == 0:
                    self.emit('no_affordable_post', credits=st['credits'])
                    return None
                break
            _, i, path = pick
            self.target = st['posts'][i]
            self.go('PLANNING_ROUTE', post=i, at=self.target, price=st['prices'][i], hops=len(path))
            self.go('IN_TRANSIT', dest=self.target)
            if not self.travel(self.target):
                return self.finish()
            self.go('LOADING', post=i)
            if not self.load():
                return self.finish()

        # IN_TRANSIT home -> DELIVERING
        self.go('IN_TRANSIT', dest=(0, 0))
        if not self.travel((0, 0), arrive_screen=SCORE):
            return self.finish()
        st = b.snapshot()
        self.go('DELIVERING', cargo=st['cargo'], est_score=300 * st['cargo'] + 10 * st['crew'])
        self.delivered = True
        return self.finish()

    def travel(self, goal, arrive_screen=POST):
        b = self.b
        for _ in range(200):
            w = b.where()
            if w is None or w in TRANSIENT:
                time.sleep(0.3)                                 # animating / minigame
                continue
            if w == arrive_screen or (w == POST and goal != (0, 0)):
                return True
            if not b.peek(INRUN)[0]:
                return False                                    # run ended (game over)
            if w == MAP:
                if tuple(s32(x) for x in b.peek(SHIP + 0xa8, 2)) == goal:
                    if goal == (0, 0):
                        return True
                    b.pan(*pan_for(goal))                       # already on the post: A re-enters it
                    time.sleep(0.12)
                    b.press('A')
                    self.wait_change(MAP)
                    continue
                self.step_to(goal, avoid_posts=True)
                continue
            if not self.handle_common(w):
                self.emit('unexpected', where=hex(w))
                time.sleep(0.5)
        return False

    def load(self):
        """At a trading post: A on 'buy' until the hold is full or the next unit is unaffordable."""
        b = self.b
        st = b.snapshot()
        i = st['posts'].index(st['pos'])
        bought = 0
        while st['cargo'] < st['cargo_cap'] and st['prices'][i] <= st['credits']:
            if self.dry:
                break
            before = st['cargo']
            b.press('A')                                        # menu starts on 'buy'
            end = time.time() + 3
            while time.time() < end:
                st = b.snapshot()
                if st['cargo'] != before:
                    break
                time.sleep(0.1)
            if st['cargo'] == before:
                self.emit('buy_stalled', price=st['prices'][i], credits=st['credits'])
                break
            bought += 1
        self.emit('loaded', bought=bought, cargo=st['cargo'], credits=st['credits'], next_price=st['prices'][i])
        b.press('B')
        return self.wait_change(POST) == MAP

    def finish(self):
        """Ack the end-of-run screens (score, flight log) until the title screen is back."""
        b = self.b
        st = None
        for _ in range(40):
            st = b.snapshot()
            if st and st['where'] == TITLE and not st['in_run']:
                break
            if st and st['where'] == MAP and st['in_run']:
                self.go('FAILED', reason='run still active')
                return None
            if st and not self.handle_common(st['where']):
                time.sleep(0.4)
        if not self.delivered:
            self.go('FAILED', reason='run ended before delivery (game over)', encounters=self.encounters)
            return None
        self.go('COMPLETED', encounters=self.encounters, secs=round(time.time() - self.t0, 1))
        return st


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--runs', type=int, default=1)
    ap.add_argument('--log', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), '../cargoruns.jsonl'))
    ap.add_argument('--dry', action='store_true', help='plan + travel, but do not buy')
    a = ap.parse_args()
    b = Badge()
    with open(a.log, 'a') as log:
        for n in range(1, a.runs + 1):
            if Run(b, log, n, a.dry).run() is None:
                print('run did not complete; stopping', file=sys.stderr)
                sys.exit(1)


if __name__ == '__main__':
    main()
