# ARM Cortex-M3 Bare-Metal Emulation & QMP Test Harness

Cross-architecture firmware development and automated testing pipeline targeting
the TI Stellaris LM3S6965 (ARM Cortex-M3), emulated on QEMU from a macOS host.

## Overview

This project demonstrates the full embedded firmware development loop without
physical hardware:

1. **Bare-metal firmware** written in C with hand-rolled startup assembly
2. **Cross-compiled** on macOS (x86_64/ARM64) for ARM Cortex-M3 using `arm-none-eabi-gcc`
3. **Emulated** on QEMU's lm3s6965evb machine target (Cortex-M3)
4. **Automated testing** via QMP (QEMU Machine Protocol) over a Unix socket

The QMP harness connects to the running emulator, queries CPU architecture and
machine state, and validates firmware execution through UART serial output —
verifying bidirectional host-guest communication programmatically.

## Project Structure
```
qemu-cortexm-demo/
├── src/
│   ├── main.c          # Bare-metal firmware (UART driver, heartbeat loop)
│   ├── startup.s       # ARM Cortex-M3 vector table + Reset_Handler
│   └── lm3s6965.ld     # Linker script (FLASH/RAM memory map)
├── build/              # Compiled output (generated)
├── qmp_client.py       # Python QMP test harness
├── Makefile
└── README.md
```

## Requirements

- QEMU: `brew install qemu`
- ARM GCC toolchain: `brew install --cask gcc-arm-embedded`
- Python 3 (standard library only)

## Usage
```bash
# Build firmware binary
make build

# Launch QEMU emulator as background daemon
make run

# Run full QMP automated test suite
make test

# Stop the emulator
make stop
```

## Test Report
```
=======================================================
  ARM Cortex-M3 Emulation QMP Test Report
  James Schiavo | lm3s6965evb | QEMU
=======================================================

[QMP HOST-GUEST COMMUNICATION]
  QMP socket connected   : PASS
  QEMU version           : 10.2.1
  Capabilities exchange  : PASS

[EMULATED MACHINE STATE]
  VM status              : RUNNING
  VM running             : PASS
  CPU architecture       : ARM
  ARM target confirmed   : PASS
  RAM allocated          : 131072 KB

[FIRMWARE VALIDATION]
  Boot banner received   : PASS
  Identity string found  : PASS
  Version string found   : PASS
  Firmware executing     : PASS
  Heartbeat count        : 73074
  Sequential heartbeats  : PASS

  RESULT: 7/7 tests passed ✓ ALL PASS
=======================================================
```

## Technical Details

**Firmware** (`src/main.c`): Bare-metal C targeting the LM3S6965 UART0
peripheral at base address `0x4000C000`. Polls the TX FIFO full flag before
writing each character — no libc, no OS, no HAL.

**Startup** (`src/startup.s`): Thumb-mode assembly placing the vector table at
address `0x0`. The reset vector points to `Reset_Handler`, which zeroes the BSS
segment and calls `main()` — replicating the exact boot sequence of real
Cortex-M3 silicon.

**Linker Script** (`src/lm3s6965.ld`): Maps 256K FLASH at `0x00000000` and 64K
SRAM at `0x20000000`, matching the physical memory map of the LM3S6965
microcontroller.

**QMP Harness** (`qmp_client.py`): Connects via Unix domain socket, performs
QMP capability negotiation, then issues `query-status`, `query-target`, and
`query-memory-size-summary` commands. Independently validates firmware execution
by parsing UART serial log for boot sequence and monotonically incrementing
heartbeat counter.

## Relevance to Semiconductor/Embedded Roles

This workflow directly mirrors pre-silicon validation practices used at chip
design companies: firmware is written and tested against an emulated target
before physical silicon is available. The QMP interface is analogous to JTAG
debug access — a programmatic channel for querying and controlling processor
state from a host machine.
