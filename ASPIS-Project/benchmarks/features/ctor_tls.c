/*
 * ctor_tls.c -- global constructors and thread-local variables.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * Code that runs before main() (functions in llvm.global_ctors) must
 * initialise both copies of the globals it writes, and thread-local
 * variables must be duplicated keeping their thread-local storage class.
 * An atexit() handler checks the state at program termination.
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

#define TABLE 32

static int g_squares[TABLE];
static int g_ctor_runs;
static __thread int t_calls;
static __thread long t_accumulator = 5;

/* explicit priorities: init_squares must run before init_second */
__attribute__((constructor(101))) static void init_squares(void) {
    int i;
    for (i = 0; i < TABLE; i++)
        g_squares[i] = i * i;
    g_ctor_runs++;
}

__attribute__((constructor(102))) static void init_second(void) {
    g_squares[0] = -1;
    g_ctor_runs++;
}

static void at_exit_report(void) {
    printf("atexit: calls %d accumulator %ld\n", t_calls, t_accumulator);
}

static long lookup_sum(int from, int to) {
    long s = 0;
    int i;
    t_calls++;
    for (i = from; i <= to && i < TABLE; i++)
        s += g_squares[i];
    t_accumulator += s % 97;
    return s;
}

int main(void) {
    long a, b;
    atexit(at_exit_report);
    a = lookup_sum(1, 10);
    b = lookup_sum(0, TABLE - 1);
    printf("ctor runs %d, sums %ld %ld, tls calls %d acc %ld\n", g_ctor_runs, a, b, t_calls,
           t_accumulator);
    printf("%s\n", (g_ctor_runs == 2 && a == 385 && b == 10415) ? "SUCCESS" : "FAIL");
    return 0;
}
