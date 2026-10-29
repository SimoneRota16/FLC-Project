/*
 * varargs.c -- user-defined variadic functions.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * EDDI duplicates the fixed parameters of a hardened function and passes the
 * variadic ones only once. This test exercises va_start/va_arg/va_end with
 * int, double and pointer arguments, va_copy, a sentinel-terminated list and
 * a va_list forwarded to vsnprintf() (a libc function writing into a
 * hardened buffer).
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

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

static int sum_ints(int count, ...) {
    va_list ap;
    int s = 0, i;
    va_start(ap, count);
    for (i = 0; i < count; i++)
        s += va_arg(ap, int);
    va_end(ap);
    return s;
}

static double mean_doubles(int count, ...) {
    va_list ap;
    double s = 0.0;
    int i;
    va_start(ap, count);
    for (i = 0; i < count; i++)
        s += va_arg(ap, double);
    va_end(ap);
    return count > 0 ? s / count : 0.0;
}

/* list terminated by a negative value */
static int max_until_negative(int first, ...) {
    va_list ap;
    int best = first, v;
    va_start(ap, first);
    while ((v = va_arg(ap, int)) >= 0)
        if (v > best)
            best = v;
    va_end(ap);
    return best;
}

/* (weight, value) pairs, consumed twice thanks to va_copy */
static long weighted_sum(int pairs, ...) {
    va_list ap, again;
    long s = 0, w = 0;
    int i;
    va_start(ap, pairs);
    va_copy(again, ap);
    for (i = 0; i < pairs; i++) {
        int weight = va_arg(ap, int);
        long value = va_arg(ap, long);
        s += weight * value;
    }
    for (i = 0; i < pairs; i++) {
        w += va_arg(again, int);
        (void)va_arg(again, long);
    }
    va_end(again);
    va_end(ap);
    return w ? s / w : 0;
}

static int concat_lengths(int count, ...) {
    va_list ap;
    int total = 0, i;
    va_start(ap, count);
    for (i = 0; i < count; i++) {
        const char *s = va_arg(ap, const char *);
        while (*s++)
            total++;
    }
    va_end(ap);
    return total;
}

static int format_into(char *buf, int size, const char *fmt, ...) {
    va_list ap;
    int n;
    va_start(ap, fmt);
    n = vsnprintf(buf, (size_t)size, fmt, ap);
    va_end(ap);
    return n;
}

int main(void) {
    char line[96];
    int n, s1, s2, mx, len;
    double mean;
    long ws;

    s1 = sum_ints(5, 1, 2, 3, 4, 5);
    s2 = sum_ints(0);
    mean = mean_doubles(4, 1.5, 2.5, -1.0, 10.0);
    mx = max_until_negative(3, 9, 27, 4, 81, 0, -1);
    ws = weighted_sum(3, 1, 10L, 2, 20L, 3, 30L);
    len = concat_lengths(3, "fault", "tolerant", "compiler");
    printf("sum %d %d mean %.3f max %d weighted %ld len %d\n", s1, s2, mean, mx, ws, len);

    n = format_into(line, (int)sizeof(line), "[%s:%04d] %5.2f%% %c", "aspis", 42, 99.5, 'Z');
    printf("formatted (%d): %s\n", n, line);

    printf("%s\n", (s1 == 15 && mx == 81 && ws == 23 && len == 21) ? "SUCCESS" : "FAIL");
    return 0;
}
