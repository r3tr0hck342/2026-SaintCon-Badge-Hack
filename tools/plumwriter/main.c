// RAM-only helper: writes "PLUM" to badge EEPROM bytes 0..3 (I2C0, SDA=GP4, SCL=GP5, addr 0x50),
// matching the FLAG 2 gate in the badge firmware. Waits for a command over USB serial:
//   R = read bytes 0..15   W = write PLUM to 0..3   S = restore "SC_S" to 0..3
//   D = dump all 1 KB as hex   L = load 1 KB raw image from host (verified)
// Factory contents of bytes 0..15 were "SC_SIGNAL_GHOST\0" (the bit-11 unlock code).
#include <stdio.h>
#include <string.h>
#include "pico/stdlib.h"
#include "hardware/i2c.h"

#define EEPROM_ADDR 0x50

static int ee_read(uint8_t off, uint8_t *buf, size_t n) {
    if (i2c_write_blocking(i2c0, EEPROM_ADDR, &off, 1, true) != 1) return -1;
    return i2c_read_blocking(i2c0, EEPROM_ADDR, buf, n, false);
}

static void dump(void) {
    uint8_t b[16];
    int r = ee_read(0, b, sizeof b);
    if (r != sizeof b) { printf("READ FAILED (%d)\n", r); return; }
    printf("EEPROM[0..15]:");
    for (int i = 0; i < 16; i++) printf(" %02x", b[i]);
    printf("  |");
    for (int i = 0; i < 16; i++) putchar(b[i] >= 32 && b[i] < 127 ? b[i] : '.');
    printf("|\n");
}

// Full 1 KB as hex lines "OOO: xx xx ..." (24C08: device address 0x50 + bits 9..8 of the offset)
static void dump_all(void) {
    for (int off = 0; off < 1024; off += 16) {
        uint8_t a = off & 0xff, b[16];
        uint8_t dev = EEPROM_ADDR + (off >> 8);
        if (i2c_write_blocking(i2c0, dev, &a, 1, true) != 1 ||
            i2c_read_blocking(i2c0, dev, b, 16, false) != 16) { printf("%03x: READ FAILED\n", off); continue; }
        printf("%03x:", off);
        for (int i = 0; i < 16; i++) printf(" %02x", b[i]);
        printf("\n");
    }
    printf("DUMP END\n");
}

// Wait out the EEPROM's internal write cycle by polling for an ACK
static bool ack_poll(uint8_t dev) {
    uint8_t dummy;
    absolute_time_t until = make_timeout_time_ms(50);
    while (i2c_read_blocking(i2c0, dev, &dummy, 1, false) < 0)
        if (time_reached(until)) return false;
    return true;
}

// Receive exactly 1024 raw bytes from the host, write them as 16-byte pages, then verify by readback.
// Nothing is written unless all 1024 bytes arrive.
static void load_all(void) {
    static uint8_t img[1024];
    printf("LOAD READY\n");
    for (int i = 0; i < 1024; i++) {
        int c = getchar_timeout_us(5 * 1000 * 1000);
        if (c < 0) { printf("LOAD ABORTED: got %d of 1024 bytes, nothing written\n", i); return; }
        img[i] = (uint8_t)c;
    }
    for (int off = 0; off < 1024; off += 16) {
        uint8_t dev = EEPROM_ADDR + (off >> 8), pkt[17];
        pkt[0] = off & 0xff;
        memcpy(pkt + 1, img + off, 16);
        if (i2c_write_blocking(i2c0, dev, pkt, sizeof pkt, false) != sizeof pkt || !ack_poll(dev)) {
            printf("LOAD FAILED at %03x\n", off); return;
        }
    }
    int bad = 0;
    for (int off = 0; off < 1024; off += 16) {
        uint8_t a = off & 0xff, b[16], dev = EEPROM_ADDR + (off >> 8);
        if (i2c_write_blocking(i2c0, dev, &a, 1, true) != 1 || i2c_read_blocking(i2c0, dev, b, 16, false) != 16 ||
            memcmp(b, img + off, 16)) bad++;
    }
    printf(bad ? "LOAD VERIFY FAILED (%d pages)\n" : "LOAD OK\n", bad);
}

static void write4(const char *v) {
    const uint8_t pkt[5] = {0x00, v[0], v[1], v[2], v[3]};  // word address 0, then data
    int r = i2c_write_blocking(i2c0, EEPROM_ADDR, pkt, sizeof pkt, false);
    if (r != sizeof pkt) { printf("WRITE FAILED (%d)\n", r); return; }
    // ACK-poll until the internal write cycle finishes (max ~5 ms per datasheet)
    uint8_t dummy;
    absolute_time_t until = make_timeout_time_ms(50);
    while (i2c_read_blocking(i2c0, EEPROM_ADDR, &dummy, 1, false) < 0)
        if (time_reached(until)) { printf("WRITE TIMEOUT\n"); return; }
    printf("WRITE OK\n");
    dump();
}

int main(void) {
    stdio_init_all();
    i2c_init(i2c0, 400 * 1000);
    gpio_set_function(4, GPIO_FUNC_I2C);
    gpio_set_function(5, GPIO_FUNC_I2C);
    gpio_pull_up(4);
    gpio_pull_up(5);
    for (;;) {
        int c = getchar_timeout_us(1000000);
        if (c == 'R' || c == 'r') dump();
        else if (c == 'W') write4("PLUM");
        else if (c == 'S') write4("SC_S");
        else if (c == 'D') dump_all();
        else if (c == 'L') load_all();
        else if (c == PICO_ERROR_TIMEOUT) printf("plumwriter ready: R=read W=write PLUM S=restore SC_S D=dump 1KB L=load 1KB\n");
    }
}
