/*
 * vla_alloca.c -- dynamically sized stack allocations.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * EDDI duplicates every alloca. Here the size of the allocations is known
 * only at run time: variable-length arrays (one- and two-dimensional, in
 * nested scopes inside loops, which makes the compiler emit
 * stacksave/stackrestore) and explicit alloca() calls.
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <alloca.h>

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

static long prefix_sums(int n) {
    long sums[n];
    long total = 0;
    int i;
    for (i = 0; i < n; i++)
        sums[i] = (i == 0 ? 0 : sums[i - 1]) + (long)i * i;
    for (i = 0; i < n; i += 3)
        total += sums[i];
    return total;
}

static int pascal_row_sum(int rows) {
    int tri[rows][rows];
    int r, c, s = 0;
    for (r = 0; r < rows; r++) {
        for (c = 0; c < rows; c++)
            tri[r][c] = 0;
        tri[r][0] = 1;
        for (c = 1; c <= r; c++)
            tri[r][c] = tri[r - 1][c - 1] + tri[r - 1][c];
    }
    for (c = 0; c < rows; c++)
        s += tri[rows - 1][c] % 1000;
    return s;
}

static unsigned int reverse_words(const char *text) {
    size_t len = strlen(text);
    char *buf = (char *)alloca(len + 1);
    unsigned int h = 0;
    size_t i;
    for (i = 0; i < len; i++)
        buf[i] = text[len - 1 - i];
    buf[len] = '\0';
    for (i = 0; i < len; i++)
        h = h * 131u + (unsigned char)buf[i];
    printf("reversed: %s\n", buf);
    return h;
}

int main(void) {
    int n, round, histogram_total = 0;
    long ps = 0;

    for (n = 1; n <= 40; n += 13)
        ps += prefix_sums(n);
    for (round = 1; round <= 6; round++) {
        int width = round * 3;
        int hist[width];
        int i;
        for (i = 0; i < width; i++)
            hist[i] = (i * round) % 7;
        for (i = 0; i < width; i++)
            histogram_total += hist[i];
    }
    printf("prefix sums %ld, pascal %d, histograms %d\n", ps, pascal_row_sum(12),
           histogram_total);
    printf("hash %08x\n", reverse_words("dynamic stack allocation"));
    printf("%s\n", pascal_row_sum(12) == 2048 ? "SUCCESS" : "FAIL");
    return 0;
}
