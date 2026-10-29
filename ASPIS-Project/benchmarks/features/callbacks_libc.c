/*
 * callbacks_libc.c -- function pointers and callbacks invoked by libc.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * qsort() and bsearch() are not compiled by ASPIS, but they call back
 * hardened comparison functions and they read/write hardened arrays. The
 * test also covers a global table of function pointers, a function that
 * returns a function pointer and a higher-order "map" over an array.
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

#define N_DATA 24

typedef struct {
    int key;
    char name[8];
} Record;

typedef int (*binop_t)(int, int);

static Record g_records[6] = {
    {42, "delta"}, {7, "alpha"}, {19, "gamma"}, {3, "omega"}, {25, "beta"}, {11, "kappa"}};

static int cmp_int_asc(const void *a, const void *b) {
    int x = *(const int *)a, y = *(const int *)b;
    return (x > y) - (x < y);
}

static int cmp_int_desc(const void *a, const void *b) {
    return cmp_int_asc(b, a);
}

static int cmp_record_key(const void *a, const void *b) {
    const Record *r1 = (const Record *)a, *r2 = (const Record *)b;
    return r1->key - r2->key;
}

static int cmp_record_name(const void *a, const void *b) {
    return strcmp(((const Record *)a)->name, ((const Record *)b)->name);
}

static int op_add(int a, int b) { return a + b; }
static int op_sub(int a, int b) { return a - b; }
static int op_mul(int a, int b) { return a * b; }
static int op_max(int a, int b) { return a > b ? a : b; }

static binop_t g_ops[4] = {op_add, op_sub, op_mul, op_max};

static binop_t select_op(char c) {
    switch (c) {
    case '+': return op_add;
    case '-': return op_sub;
    case '*': return op_mul;
    default: return op_max;
    }
}

static int square(int v) { return v * v; }
static int negate(int v) { return -v; }

static void map_array(int *a, int n, int (*f)(int)) {
    int i;
    for (i = 0; i < n; i++)
        a[i] = f(a[i]);
}

int main(void) {
    int data[N_DATA];
    int i, acc, found = 0, keys[4] = {5, 17, 40, 99};
    unsigned int seed = 12345u;
    const char *program = "+*-m+*";

    for (i = 0; i < N_DATA; i++) {
        seed = seed * 1103515245u + 12345u;
        data[i] = (int)((seed >> 16) % 50u);
    }
    qsort(data, N_DATA, sizeof(int), cmp_int_asc);
    printf("sorted:");
    for (i = 0; i < N_DATA; i++)
        printf(" %d", data[i]);
    printf("\n");
    for (i = 0; i < 4; i++) {
        int *p = (int *)bsearch(&keys[i], data, N_DATA, sizeof(int), cmp_int_asc);
        if (p != NULL)
            found++;
        printf("bsearch %d: %s\n", keys[i], p ? "found" : "absent");
    }
    qsort(data, N_DATA, sizeof(int), cmp_int_desc);
    printf("max %d min %d\n", data[0], data[N_DATA - 1]);

    qsort(g_records, 6, sizeof(Record), cmp_record_key);
    printf("by key:");
    for (i = 0; i < 6; i++)
        printf(" %s(%d)", g_records[i].name, g_records[i].key);
    qsort(g_records, 6, sizeof(Record), cmp_record_name);
    printf("\nby name:");
    for (i = 0; i < 6; i++)
        printf(" %s", g_records[i].name);
    printf("\n");

    acc = 1;
    for (i = 0; i < 8; i++)
        acc = g_ops[i % 4](acc, i + 2);
    printf("op table: %d\n", acc);
    acc = 3;
    for (i = 0; program[i] != '\0'; i++)
        acc = select_op(program[i])(acc, i + 1);
    printf("op program: %d\n", acc);

    map_array(data, 6, square);
    map_array(data, 3, negate);
    printf("mapped: %d %d %d %d %d %d\n", data[0], data[1], data[2], data[3], data[4], data[5]);

    printf("%s\n", found >= 1 ? "SUCCESS" : "FAIL");
    return 0;
}
