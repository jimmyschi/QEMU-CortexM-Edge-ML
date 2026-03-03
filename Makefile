CC      = arm-none-eabi-gcc
CFLAGS  = -mcpu=cortex-m3 -mthumb -nostdlib
LDFLAGS = -T src/lm3s6965.ld -Wl,--defsym=__bss_start__=0x20000000 -Wl,--defsym=__bss_end__=0x20000100

SRCS    = src/startup.s src/main.c
TARGET  = build/firmware.elf

QEMU       = qemu-system-arm
MACHINE    = lm3s6965evb
QMP_SOCK   = build/qmp.sock
SERIAL_LOG = build/serial.log
PID_FILE   = build/qemu.pid

.PHONY: all build run stop test clean

all: build

build: $(TARGET)

$(TARGET): $(SRCS)
	mkdir -p build
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $(SRCS)
	@arm-none-eabi-objdump -f $@ | grep -E "architecture|start address"

run: build
	$(QEMU) -machine $(MACHINE) -kernel $(TARGET) -serial file:$(SERIAL_LOG) -qmp unix:$(QMP_SOCK),server,wait=off -daemonize -pidfile $(PID_FILE) -display none
	@sleep 0.5
	@head -5 $(SERIAL_LOG)

stop:
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE) $(QMP_SOCK) $(SERIAL_LOG); fi

test: run
	@sleep 1
	python3 qmp_client.py
	@$(MAKE) stop

clean:
	rm -rf build/
