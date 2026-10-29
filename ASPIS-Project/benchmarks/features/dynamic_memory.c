/*
 * dynamic_memory.c -- heap data structures and memory intrinsics.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * Heap objects are not duplicated (malloc is called once), so the original
 * and the duplicated pointers of a hardened function refer to the very same
 * memory. The test checks that operations on that memory keep their
 * semantics when every instruction is executed twice: a growable vector
 * (realloc), a singly linked list (reverse, filter, free), a 2-D array of
 * row pointers and, most importantly, overlapping memmove() calls that
 * shift data inside a heap buffer (not idempotent if executed twice).
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

typedef struct {
    int *data;
    int size;
    int cap;
} Vec;

typedef struct Item {
    int value;
    struct Item *next;
} Item;

static void vec_push(Vec *v, int x) {
    if (v->size == v->cap) {
        v->cap = v->cap ? v->cap * 2 : 4;
        v->data = (int *)realloc(v->data, (size_t)v->cap * sizeof(int));
    }
    v->data[v->size++] = x;
}

/* insertion into a sorted heap array: shifts the tail with memmove */
static void sorted_insert(int *arr, int *n, int x) {
    int pos = 0;
    while (pos < *n && arr[pos] < x)
        pos++;
    memmove(&arr[pos + 1], &arr[pos], (size_t)(*n - pos) * sizeof(int));
    arr[pos] = x;
    (*n)++;
}

static Item *list_push(Item *head, int v) {
    Item *it = (Item *)malloc(sizeof(Item));
    it->value = v;
    it->next = head;
    return it;
}

static Item *list_reverse(Item *head) {
    Item *prev = NULL;
    while (head != NULL) {
        Item *next = head->next;
        head->next = prev;
        prev = head;
        head = next;
    }
    return prev;
}

static Item *list_remove_multiples(Item *head, int k, int *removed) {
    Item **link = &head;
    while (*link != NULL) {
        if ((*link)->value % k == 0) {
            Item *dead = *link;
            *link = dead->next;
            free(dead);
            (*removed)++;
        } else {
            link = &(*link)->next;
        }
    }
    return head;
}

static long list_checksum(const Item *head) {
    long s = 0;
    int pos = 1;
    for (; head != NULL; head = head->next)
        s += (long)head->value * pos++;
    return s;
}

int main(void) {
    Vec v = {NULL, 0, 0};
    Item *list = NULL;
    int *sorted = (int *)malloc(32 * sizeof(int));
    int **rows, i, j, n = 0, removed = 0;
    long vsum = 0, tsum = 0;
    char *text, *copy;

    for (i = 0; i < 100; i++)
        vec_push(&v, (i * 37) % 101);
    for (i = 0; i < v.size; i++)
        vsum += v.data[i] * (i % 3);
    printf("vector size %d cap %d sum %ld\n", v.size, v.cap, vsum);

    for (i = 0; i < 12; i++)
        sorted_insert(sorted, &n, (i * 7) % 12);
    printf("sorted insert:");
    for (i = 0; i < n; i++)
        printf(" %d", sorted[i]);
    printf("\n");
    memmove(sorted + 2, sorted, 6 * sizeof(int)); /* overlapping, forward */
    memmove(sorted, sorted + 5, 4 * sizeof(int)); /* overlapping, backward */
    printf("after memmove:");
    for (i = 0; i < n; i++)
        printf(" %d", sorted[i]);
    printf("\n");

    for (i = 1; i <= 20; i++)
        list = list_push(list, i);
    list = list_reverse(list);
    list = list_remove_multiples(list, 3, &removed);
    printf("list removed %d checksum %ld\n", removed, list_checksum(list));

    rows = (int **)malloc(4 * sizeof(int *));
    for (i = 0; i < 4; i++) {
        rows[i] = (int *)calloc(5, sizeof(int));
        for (j = 0; j < 5; j++)
            rows[i][j] = i * 5 + j;
    }
    for (i = 0; i < 4; i++)
        for (j = 0; j < 5; j++)
            tsum += rows[i][j] * rows[3 - i][4 - j];
    printf("rows product sum %ld\n", tsum);

    text = (char *)malloc(64);
    strcpy(text, "soft");
    strcat(text, " error");
    copy = (char *)malloc(strlen(text) + 1);
    memcpy(copy, text, strlen(text) + 1);
    memset(text, '*', 4);
    printf("strings: %s / %s\n", text, copy);

    while (list != NULL) {
        Item *next = list->next;
        free(list);
        list = next;
    }
    for (i = 0; i < 4; i++)
        free(rows[i]);
    free(rows);
    free(sorted);
    free(v.data);
    free(text);
    free(copy);
    printf("%s\n", (removed == 6 && v.size == 100) ? "SUCCESS" : "FAIL");
    return 0;
}
