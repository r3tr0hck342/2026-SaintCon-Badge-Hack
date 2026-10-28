/* Console hook for the badge firmware: BTN, PEEK, PAN, WHERE and CREW commands.
 * Called from the dispatcher's "Unknown command" branch (0x100102e8) with r0 = the line buffer.
 * Placed at 0x10180000 (unused flash after the image). Only calls firmware functions by address. */
#define FW_STRNCMP ((int (*)(const char *, const char *, unsigned))0x100135b5)
#define FW_PUTS    ((int (*)(const char *))0x1000aa29)
#define FW_PRINTF  ((int (*)(const char *, ...))0x1000ab29)
#define UNKNOWN    ((const char *)0x10027df8)            /* "Unknown command. Type HELP for commands." */
#define BTN_EVENTS (*(volatile unsigned *)0x20002e1c)    /* latched press mask, read+cleared by 0x1000dcb0 */
#define MAP_PAN    ((volatile int *)0x20044534)          /* nav map pan x,y (FUN_100025c8); centre hex = target */
#define FW_CREW    ((void (*)(const char *))0x10003941)  /* station $CREW parser: 5 x [role A-E][id5][name14] */
#define CREW_COUNT (*(volatile int *)0x20003990)
#define CALLER_LR  0x8c                                  /* line buf is dispatcher sp+0x38; its saved lr is at sp+0xc4 */

static const struct { char name[8]; unsigned mask; } buttons[] = {
    {"UP", 1}, {"DOWN", 2}, {"LEFT", 4}, {"RIGHT", 8}, {"SEL", 16}, {"B", 32}, {"A", 64},
};

static const char *skip(const char *p) { while (*p == ' ') p++; return p; }

static const char *hex(const char *p, unsigned *out, int *ok) {
    unsigned v = 0; int n = 0;
    for (;; p++, n++) {
        char c = *p;
        if (c >= '0' && c <= '9') v = v * 16 + (c - '0');
        else if (c >= 'A' && c <= 'F') v = v * 16 + (c - 'A' + 10);
        else if (c >= 'a' && c <= 'f') v = v * 16 + (c - 'a' + 10);
        else break;
    }
    *out = v; *ok = n > 0 && n <= 8;
    return p;
}

static const char *dec(const char *p, int *out, int *ok) {
    int neg = *p == '-', v = 0, n = 0;
    if (neg) p++;
    for (; *p >= '0' && *p <= '9' && n < 6; p++, n++) v = v * 10 + (*p - '0');
    *out = neg ? -v : v; *ok = n > 0 && (*p == 0 || *p == ' ');
    return p;
}

static int word_is(const char *p, const char *w) {
    for (; *w; p++, w++) if ((*p >= 'a' && *p <= 'z' ? *p - 32 : *p) != *w) return 0;
    return *p == 0 || *p == ' ';
}

__attribute__((section(".text.hook"), used))
void hook(char *line) {
    if (!FW_STRNCMP(line, "BTN ", 4)) {
        unsigned mask = 0;
        for (const char *p = skip(line + 4); *p; p = skip(p)) {
            unsigned m = 0; int ok = 0;
            for (unsigned i = 0; i < sizeof buttons / sizeof *buttons; i++)
                if (word_is(p, buttons[i].name)) { m = buttons[i].mask; ok = 1; }
            if (ok) { while (*p && *p != ' ') p++; }
            else {
                const char *q = hex(p, &m, &ok);
                if (!ok || (*q && *q != ' ') || m > 0x7f) { FW_PUTS("BTN: ERR"); return; }
                p = q;
            }
            mask |= m;
        }
        unsigned primask;
        __asm volatile("mrs %0, primask\n cpsid i" : "=r"(primask));
        BTN_EVENTS |= mask;
        __asm volatile("msr primask, %0" ::"r"(primask));
        FW_PRINTF("BTN: OK %02X\r\n", mask);
        return;
    }
    if (!FW_STRNCMP(line, "PEEK ", 5)) {
        unsigned addr, n = 1; int ok, ok2 = 1;
        const char *p = hex(skip(line + 5), &addr, &ok);
        if (*skip(p)) hex(skip(p), &n, &ok2);
        /* RAM (0x20000000..0x20082000) or flash only; word aligned; up to 64 words */
        int in_ram = addr >= 0x20000000 && addr + 4 * n <= 0x20082000;
        int in_flash = addr >= 0x10000000 && addr + 4 * n <= 0x10400000;
        if (!ok || !ok2 || (addr & 3) || n == 0 || n > 64 || !(in_ram || in_flash)) { FW_PUTS("PEEK: ERR"); return; }
        FW_PRINTF("PEEK %08X", addr);
        for (unsigned i = 0; i < n; i++) FW_PRINTF(" %08X", ((volatile unsigned *)addr)[i]);
        FW_PUTS("");
        return;
    }
    if (!FW_STRNCMP(line, "PAN ", 4)) {
        int x, y, ok, ok2 = 0;
        const char *p = dec(skip(line + 4), &x, &ok);
        if (ok) dec(skip(p), &y, &ok2);
        if (!ok || !ok2) { FW_PUTS("PAN: ERR"); return; }
        MAP_PAN[0] = x; MAP_PAN[1] = y;
        FW_PRINTF("PAN: OK %d %d\r\n", x, y);
        return;
    }
    if (!FW_STRNCMP(line, "CREW", 4) && (line[4] == 0 || line[4] == ' ')) {
        /* one of each role, so every role-gated event option is available; same path as a station dock */
        FW_CREW("AVC001Pilot Vega    "
                "BVC002Eng. Torque   "
                "CVC003Sci. Halley   "
                "DVC004Sec. Kestrel  "
                "EVC005Medic Okafor  ");
        FW_PRINTF("CREW: OK %d\r\n", CREW_COUNT);
        return;
    }
    if (!FW_STRNCMP(line, "WHERE", 5) && (line[5] == 0 || line[5] == ' ')) {
        /* the dispatcher's caller = the wait loop polling the console = current screen */
        unsigned lr = *(unsigned *)(line + CALLER_LR);
        FW_PRINTF("WHERE %08X\r\n", (lr & ~1u) - 4);
        return;
    }
    FW_PUTS(UNKNOWN);
}
