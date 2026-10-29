/*
 * setjmp_longjmp.c -- non-local exits from a recursive evaluator.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * A recursive evaluator of prefix expressions aborts with longjmp() when it
 * meets a division by zero or an unknown symbol. setjmp() returns twice and
 * longjmp() leaves several stack frames at once without executing their
 * epilogues: both are hard cases for control-flow checking schemes that keep
 * a run-time signature in a global variable.
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>
#include <setjmp.h>

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

#define ERR_DIV0 1
#define ERR_SYMBOL 2

static jmp_buf g_env;
static const char *g_pos;
static int g_depth_max;

static long eval_prefix(int depth) {
    char c;
    long a, b;
    if (depth > g_depth_max)
        g_depth_max = depth;
    while (*g_pos == ' ')
        g_pos++;
    c = *g_pos++;
    if (c >= '0' && c <= '9')
        return c - '0';
    if (c != '+' && c != '-' && c != '*' && c != '/')
        longjmp(g_env, ERR_SYMBOL);
    a = eval_prefix(depth + 1);
    b = eval_prefix(depth + 1);
    switch (c) {
    case '+': return a + b;
    case '-': return a - b;
    case '*': return a * b;
    default:
        if (b == 0)
            longjmp(g_env, ERR_DIV0);
        return a / b;
    }
}

static int evaluate(const char *text, long *result) {
    int err;
    g_pos = text;
    err = setjmp(g_env);
    if (err != 0)
        return err;
    *result = eval_prefix(0);
    return 0;
}

int main(void) {
    static const char *inputs[] = {"+ 1 * 2 3", "* + 1 2 - 9 / 8 4", "/ 9 - 3 3",
                                   "+ 1 ? 2", "- * 9 9 / + 7 7 * 1 2"};
    int i, errors = 0;
    long sum = 0;
    for (i = 0; i < 5; i++) {
        long r = 0;
        int err = evaluate(inputs[i], &r);
        if (err) {
            errors++;
            printf("input %d: error %d\n", i, err);
        } else {
            sum += r;
            printf("input %d: %ld\n", i, r);
        }
    }
    printf("sum %ld errors %d max depth %d\n", sum, errors, g_depth_max);
    printf("%s\n", (sum == 102 && errors == 2) ? "SUCCESS" : "FAIL");
    return 0;
}
