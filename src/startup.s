    .syntax unified
    .cpu cortex-m3
    .thumb

    .section .vector_table, "a"
    .word 0x20010000        /* initial stack pointer: top of 64K RAM */
    .word Reset_Handler     /* reset vector */

    .text
    .thumb_func
    .global Reset_Handler
Reset_Handler:
    /* zero out bss */
    ldr r0, =__bss_start__
    ldr r1, =__bss_end__
    mov r2, #0
bss_loop:
    cmp r0, r1
    bge bss_done
    str r2, [r0], #4
    b bss_loop
bss_done:
    bl main
    b .

    .global __bss_start__
    .global __bss_end__
