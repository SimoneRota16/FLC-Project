/*
 * globals_pointers.c -- global variables reached through pointers.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * DuplicateGlobals creates a "_dup" copy of every non-constant global. This
 * test checks the corner cases of that transformation: globals whose
 * initialiser is the address of another global, pointers to pointers,
 * pointer arithmetic on global arrays, function-scope static variables,
 * struct globals reached through a global pointer and constant tables
 * (which are not duplicated).
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

typedef struct {
    int id;
    int weights[4];
    const char *name;
} Config;

int g_counter;
int g_table[16] = {3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3};
int g_matrix[4][4];
int *g_cursor = &g_table[5];
int **g_cursor_ref = &g_cursor;
static const int g_primes[8] = {2, 3, 5, 7, 11, 13, 17, 19};
Config g_cfg = {7, {1, 2, 3, 4}, "default"};
Config *g_cfg_ptr = &g_cfg;
static long g_accumulator;
static const char *g_names[3] = {"alpha", "beta", "gamma"};

static int next_id(void) {
    static int s_next = 100;
    return s_next++;
}

static void bump(int *p, int k) {
    *p += k;
    g_counter++;
}

static int sum_array(const int *a, int n) {
    int s = 0, i;
    for (i = 0; i < n; i++)
        s += a[i];
    return s;
}

static void swap_ints(int *a, int *b) {
    int t = *a;
    *a = *b;
    *b = t;
}

int main(void) {
    int i, j, (*row)[4];

    /* access through pointers initialised with addresses of globals */
    printf("cursor %d, via ref %d\n", *g_cursor, **g_cursor_ref);
    bump(g_cursor, 10);
    bump(*g_cursor_ref, 5);
    g_cursor += 3;
    *g_cursor = 42;
    printf("table[5] %d table[8] %d\n", g_table[5], g_table[8]);

    /* pointer to row of a global 2-D array */
    for (i = 0; i < 4; i++) {
        row = &g_matrix[i];
        for (j = 0; j < 4; j++)
            (*row)[j] = g_primes[i + j] * (i - j);
    }
    for (i = 0; i < 4; i++)
        swap_ints(&g_matrix[i][0], &g_matrix[3 - i][3]);
    printf("matrix:");
    for (i = 0; i < 4; i++)
        printf(" %d", sum_array(g_matrix[i], 4));
    printf("\n");

    /* struct global reached through a global pointer */
    for (i = 0; i < 4; i++)
        g_cfg_ptr->weights[i] *= g_primes[i];
    g_cfg_ptr->id = next_id();
    g_cfg_ptr->id += next_id();
    g_cfg.name = g_names[g_cfg.id % 3];
    printf("cfg id %d name %s weights %d\n", g_cfg.id, g_cfg_ptr->name,
           sum_array(g_cfg.weights, 4));

    /* static accumulator and counters */
    for (i = 0; i < 16; i++)
        g_accumulator += (long)g_table[i] * (i + 1);
    printf("accumulator %ld counter %d next id %d\n", g_accumulator, g_counter, next_id());

    printf("%s\n", (g_table[5] == 24 && g_table[8] == 42 && g_counter == 2) ? "SUCCESS" : "FAIL");
    return 0;
}
