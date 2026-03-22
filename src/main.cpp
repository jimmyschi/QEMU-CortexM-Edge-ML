#include <stddef.h>
#include <stdint.h>

#include "ml/mnist_model.hpp"
#include "ml/mnist_weights_generated.h"

// LM3S6965 UART0 base address
#define UART0_BASE 0x4000C000
#define UART0_DR (*((volatile uint32_t *)(UART0_BASE + 0x000)))
#define UART0_FR (*((volatile uint32_t *)(UART0_BASE + 0x018)))
#define UART_FR_TXFF (1u << 5)

// Cortex-M SysTick registers
#define SYST_CSR (*((volatile uint32_t *)0xE000E010))
#define SYST_RVR (*((volatile uint32_t *)0xE000E014))
#define SYST_CVR (*((volatile uint32_t *)0xE000E018))
#define SYST_ENABLE (1u << 0)
#define SYST_CLKSRC (1u << 2)

static void uart_putc(char c) {
    while (UART0_FR & UART_FR_TXFF) {
    }
    UART0_DR = (uint32_t)c;
}

static void uart_puts(const char *s) {
    while (*s != '\0') {
        uart_putc(*s++);
    }
}

static void uart_put_u32(uint32_t n) {
    char buf[11];
    int i = 10;
    buf[i] = '\0';

    if (n == 0) {
        buf[--i] = '0';
    } else {
        while (n > 0 && i > 0) {
            buf[--i] = (char)('0' + (n % 10u));
            n /= 10u;
        }
    }
    uart_puts(&buf[i]);
}

static void systick_init(void) {
    SYST_RVR = 0x00FFFFFFu;
    SYST_CVR = 0u;
    SYST_CSR = SYST_ENABLE | SYST_CLKSRC;
}

static uint32_t systick_now(void) {
    return SYST_CVR;
}

static uint32_t elapsed_ticks(uint32_t start, uint32_t end) {
    if (start >= end) {
        return start - end;
    }
    return start + (0x00FFFFFFu - end);
}

static void image_u8_to_f32(const uint8_t *src, float *dst, uint32_t n) {
    for (uint32_t i = 0; i < n; ++i) {
        dst[i] = (float)src[i] / 255.0f;
    }
}

extern "C" int main(void) {
    uart_puts("EDGE-ML BOOT OK\n");
    uart_puts("James Schiavo - ARM Cortex-M3 Bare-Metal C++\n");
    uart_puts("QMP + ML Inference Harness v2.0\n");

    systick_init();

    ml::MnistFcModel model;
    float input_buf[MNIST_INPUT_SIZE];
    uint32_t hb = 0;

    while (1) {
        uint32_t correct = 0;
        uint32_t tick_sum = 0;

        for (uint32_t i = 0; i < MNIST_EVAL_SAMPLES; ++i) {
            const uint8_t *img = &g_eval_images_u8[i * MNIST_INPUT_SIZE];
            image_u8_to_f32(img, input_buf, MNIST_INPUT_SIZE);

            const uint32_t t0 = systick_now();
            const int pred = model.predict(input_buf);
            const uint32_t t1 = systick_now();

            const uint32_t ticks = elapsed_ticks(t0, t1);
            tick_sum += ticks;
            if ((uint32_t)pred == (uint32_t)g_eval_labels[i]) {
                correct++;
            }
        }

        const uint32_t acc_x100 = (correct * 10000u) / MNIST_EVAL_SAMPLES;
        const uint32_t avg_ticks = tick_sum / MNIST_EVAL_SAMPLES;

        uart_puts("ML_BENCH samples=");
        uart_put_u32(MNIST_EVAL_SAMPLES);
        uart_puts(" correct=");
        uart_put_u32(correct);
        uart_puts(" acc_x100=");
        uart_put_u32(acc_x100);
        uart_puts(" avg_ticks=");
        uart_put_u32(avg_ticks);
        uart_putc('\n');

        uart_puts("HEARTBEAT ");
        uart_put_u32(hb++);
        uart_putc('\n');

        for (volatile uint32_t d = 0; d < 200000u; ++d) {
        }
    }

    return 0;
}
