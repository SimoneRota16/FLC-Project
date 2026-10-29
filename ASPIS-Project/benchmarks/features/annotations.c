/*
 * annotations.c -- selective hardening through ASPIS annotations.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * Uses every annotation recognised by ASPIS:
 *   - to_harden    on functions and globals (the only ones protected by
 *                  REDDI, together with the functions they call)
 *   - exclude      on a logging function, on a statistics counter and on a
 *                  function with side effects that must run exactly once
 *   - to_duplicate on a pure function whose calls are duplicated instead of
 *                  its body
 * The output must not depend on the chosen hardening technique.
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>

/* ASPIS fault handlers: invoked when a data mismatch (EDDI family) or a
 * control-flow signature mismatch (CFCSS/RASM/RACFED) is detected. */
void DataCorruption_Handler(void) {
    fprintf(stderr, "FAULT_DETECTED: DataCorruption\n");
    exit(2);
}

void SigMismatch_Handler(void) {
    fprintf(stderr, "FAULT_DETECTED: SigMismatch\n");
    exit(3);
}

__attribute__((annotate("to_harden"))) int g_setpoint = 1200;
__attribute__((annotate("to_harden"))) int g_history[8];
__attribute__((annotate("exclude"))) int g_log_lines;
int g_plain = 17;

__attribute__((annotate("exclude"))) static unsigned int g_event_id;

/* not protected: diagnostic output, must be called exactly once per event */
__attribute__((annotate("exclude"))) static void log_event(const char *what, int value) {
    g_log_lines++;
    g_event_id = g_event_id * 31u + (unsigned int)value;
    printf("[log %d] %s = %d\n", g_log_lines, what, value);
}

/* pure function: its calls are duplicated, its body is left untouched */
__attribute__((annotate("to_duplicate"))) static int scale(int raw, int num, int den) {
    return (raw * num) / den;
}

static int clamp(int v, int lo, int hi) {
    return v < lo ? lo : (v > hi ? hi : v);
}

__attribute__((annotate("to_harden"))) static int control_step(int measure, int k) {
    int error = g_setpoint - scale(measure, 3, 2);
    int out = clamp(error / 4, -100, 100);
    g_history[k % 8] = out;
    return out;
}

static int average_history(void) {
    int s = 0, i;
    for (i = 0; i < 8; i++)
        s += g_history[i];
    return s / 8;
}

int main(void) {
    int k, measure = 300, out = 0;
    for (k = 0; k < 20; k++) {
        out = control_step(measure, k);
        measure += out / 3 + g_plain % 5;
        if (k % 5 == 4)
            log_event("output", out);
    }
    printf("measure %d last %d average %d log lines %d event %u\n", measure, out,
           average_history(), g_log_lines, g_event_id);
    printf("%s\n", g_log_lines == 4 ? "SUCCESS" : "FAIL");
    return 0;
}
