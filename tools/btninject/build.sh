#!/bin/sh
# Builds hook.bin (code for 0x10180000). Needs arm-none-eabi-gcc.
set -e
cd "$(dirname "$0")"
arm-none-eabi-gcc -mcpu=cortex-m33 -mthumb -Os -ffreestanding -nostdlib -fno-builtin -Wall -Wextra \
    -Wl,-Ttext=0x10180000 -Wl,-e,hook -Wl,--gc-sections -o hook.elf hook.c
arm-none-eabi-objcopy -O binary hook.elf hook.bin
arm-none-eabi-nm hook.elf | grep ' hook$'
wc -c hook.bin
