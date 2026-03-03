#include <stdint.h>

// LM3S6965 UART0 base address
#define UART0_BASE  0x4000C000
#define UART0_DR    (*((volatile uint32_t *)(UART0_BASE + 0x000)))
#define UART0_FR    (*((volatile uint32_t *)(UART0_BASE + 0x018)))

// Flag register: bit 5 = TXFF (TX FIFO full)
#define UART_FR_TXFF (1 << 5)

void uart_putc(char c) {
    while (UART0_FR & UART_FR_TXFF);
    UART0_DR = c;
}

void uart_puts(const char *s) {
    while (*s) uart_putc(*s++);
}

int main(void) {
    uart_puts("BOOT OK\n");
    uart_puts("James Schiavo - ARM Cortex-M3 Firmware\n");
    uart_puts("QMP Emulation Harness v1.0\n");

    uint32_t count = 0;
    while (1) {
        uart_puts("HEARTBEAT ");
        // print count as decimal manually
        char buf[12];
        int i = 10;
        buf[11] = '\0';
        uint32_t n = count;
        if (n == 0) { buf[--i] = '0'; }
        else { while (n) { buf[--i] = '0' + (n % 10); n /= 10; } }
        uart_puts(&buf[i]);
        uart_putc('\n');
        count++;
        // simple delay loop
        for (volatile uint32_t d = 0; d < 500000; d++);
    }
    return 0;
}
