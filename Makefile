CC       = arm-none-eabi-gcc
CXX      = arm-none-eabi-g++
CXXFLAGS = -mcpu=cortex-m3 -mthumb -ffreestanding -fno-exceptions -fno-rtti -fno-use-cxa-atexit -fno-threadsafe-statics -std=c++17 -Os -I src
LDFLAGS  = -nostdlib -T src/lm3s6965.ld -Wl,--defsym=__bss_start__=0x20000000 -Wl,--defsym=__bss_end__=0x20000100 -Wl,--gc-sections
LDLIBS   = -lgcc

SRCS     = src/startup.s src/main.cpp src/ml/mnist_model.cpp
WEIGHTS  = src/ml/mnist_weights_generated.h
TARGET   = build/firmware.elf
PYTHON   = python3

QEMU       = qemu-system-arm
MACHINE    = lm3s6965evb
QMP_SOCK   = build/qmp.sock
SERIAL_LOG = build/serial.log
PID_FILE   = build/qemu.pid

.PHONY: all build run stop test clean export-weights train-cnn-metrics

all: build

build: $(TARGET)

$(TARGET): $(SRCS) $(WEIGHTS)
	mkdir -p build
	$(CXX) $(CXXFLAGS) $(LDFLAGS) -o $@ $(SRCS) $(LDLIBS)
	@arm-none-eabi-objdump -f $@ | grep -E "architecture|start address"

export-weights:
	$(PYTHON) tools/train_export_mnist.py --epochs 6 --export-samples 100 --output src/ml/mnist_weights_generated.h --metrics-output build/training_metrics_fc.json

train-cnn-metrics:
	$(PYTHON) tools/train_cnn_mnist_metrics.py --epochs 3 --metrics-output build/training_metrics_cnn.json

run: build
	$(QEMU) -machine $(MACHINE) -kernel $(TARGET) -serial file:$(SERIAL_LOG) -qmp unix:$(QMP_SOCK),server,wait=off -daemonize -pidfile $(PID_FILE) -display none
	@sleep 0.5
	@head -5 $(SERIAL_LOG)

stop:
	@if [ -f $(PID_FILE) ]; then kill $$(cat $(PID_FILE)) 2>/dev/null || true; rm -f $(PID_FILE) $(QMP_SOCK) $(SERIAL_LOG); fi

test: run
	@sleep 1
	$(PYTHON) qmp_client.py
	@$(MAKE) stop

clean:
	rm -rf build/
