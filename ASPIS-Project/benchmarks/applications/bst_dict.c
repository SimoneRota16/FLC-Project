/*
 * bst_dict.c -- word-frequency dictionary on a heap-allocated binary search
 *               tree (insert, lookup, in-order visit, delete, destroy).
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Written from scratch for ASPIS regression
 * testing and fault-injection campaigns.
 *
 * The words of a fixed text are lower-cased and inserted in an unbalanced
 * BST whose nodes and keys are allocated with malloc(). The program prints
 * the most frequent words, the tree height, the alphabetically first words,
 * looks some keys up, deletes a few nodes (leaf, one child, two children)
 * and finally frees the whole tree checking that no allocation leaked.
 *
 * ASPIS features stressed:
 *   - dynamic memory (malloc/free) and pointers to heap structures
 *   - pointer-to-pointer manipulation (Node **link)
 *   - recursion on heap data (height, visit, destroy)
 *   - calls to libc string functions (strcmp, strlen, memcpy)
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

#define MAX_WORD 32
#define MAX_VISIT 256

typedef struct Node {
    char *key;
    int count;
    struct Node *left;
    struct Node *right;
} Node;

static const char text[] =
    "A compiler translates a program written in a source language into an "
    "equivalent program in a target language. The front end of the compiler "
    "checks the program, the middle end optimises the intermediate "
    "representation and the back end emits the target code. A hardening "
    "compiler adds a second copy of the data and a signature for each basic "
    "block, so the program can detect when a fault corrupts the data or the "
    "control flow. The price of the protection is a larger and slower program, "
    "but the program does not have to be changed by hand.";

static Node *root;
static int allocations;
static int releases;
static Node *visit_buf[MAX_VISIT];
static int visit_len;

static Node *new_node(const char *key) {
    Node *n = (Node *)malloc(sizeof(Node));
    size_t len = strlen(key);
    n->key = (char *)malloc(len + 1);
    memcpy(n->key, key, len + 1);
    n->count = 1;
    n->left = NULL;
    n->right = NULL;
    allocations += 2;
    return n;
}

static void free_node(Node *n) {
    free(n->key);
    free(n);
    releases += 2;
}

static int insert(const char *key) {
    Node **link = &root;
    while (*link != NULL) {
        int c = strcmp(key, (*link)->key);
        if (c == 0) {
            (*link)->count++;
            return 0;
        }
        link = (c < 0) ? &(*link)->left : &(*link)->right;
    }
    *link = new_node(key);
    return 1;
}

static Node *lookup(const char *key) {
    Node *n = root;
    while (n != NULL) {
        int c = strcmp(key, n->key);
        if (c == 0)
            return n;
        n = (c < 0) ? n->left : n->right;
    }
    return NULL;
}

/* Deletes key from the tree, returns 1 if it was present. */
static int delete_key(const char *key) {
    Node **link = &root;
    Node *n;
    while (*link != NULL && strcmp(key, (*link)->key) != 0)
        link = (strcmp(key, (*link)->key) < 0) ? &(*link)->left : &(*link)->right;
    n = *link;
    if (n == NULL)
        return 0;
    if (n->left == NULL) {
        *link = n->right;
    } else if (n->right == NULL) {
        *link = n->left;
    } else {
        /* two children: unlink the in-order successor and put it in place */
        Node **succ_link = &n->right;
        Node *succ;
        while ((*succ_link)->left != NULL)
            succ_link = &(*succ_link)->left;
        succ = *succ_link;
        *succ_link = succ->right;
        succ->left = n->left;
        succ->right = n->right;
        *link = succ;
    }
    free_node(n);
    return 1;
}

static int height(const Node *n) {
    int hl, hr;
    if (n == NULL)
        return 0;
    hl = height(n->left);
    hr = height(n->right);
    return 1 + (hl > hr ? hl : hr);
}

static int size(const Node *n) {
    if (n == NULL)
        return 0;
    return 1 + size(n->left) + size(n->right);
}

static void visit(Node *n) {
    if (n == NULL)
        return;
    visit(n->left);
    if (visit_len < MAX_VISIT)
        visit_buf[visit_len++] = n;
    visit(n->right);
}

static void destroy(Node *n) {
    if (n == NULL)
        return;
    destroy(n->left);
    destroy(n->right);
    free_node(n);
}

static int tokenize_and_insert(const char *s) {
    char word[MAX_WORD];
    int len = 0, words = 0, i;
    for (i = 0;; i++) {
        char c = s[i];
        if (c >= 'A' && c <= 'Z')
            c = (char)(c - 'A' + 'a');
        if (c >= 'a' && c <= 'z') {
            if (len < MAX_WORD - 1)
                word[len++] = c;
        } else {
            if (len > 0) {
                word[len] = '\0';
                insert(word);
                words++;
                len = 0;
            }
            if (c == '\0')
                break;
        }
    }
    return words;
}

int main(void) {
    static const char *queries[] = {"compiler", "program", "fault", "parser", "the", "zebra"};
    static const char *removals[] = {"a", "compiler", "signature", "program", "missing"};
    int words, distinct, i, best = 0, ok = 1, removed = 0;

    words = tokenize_and_insert(text);
    distinct = size(root);
    printf("words %d, distinct %d, height %d\n", words, distinct, height(root));

    visit_len = 0;
    visit(root);
    for (i = 0; i < visit_len; i++)
        if (visit_buf[i]->count > best)
            best = visit_buf[i]->count;
    printf("most frequent (%d):", best);
    for (i = 0; i < visit_len; i++)
        if (visit_buf[i]->count == best)
            printf(" %s", visit_buf[i]->key);
    printf("\nfirst words:");
    for (i = 0; i < 6 && i < visit_len; i++)
        printf(" %s/%d", visit_buf[i]->key, visit_buf[i]->count);
    printf("\n");
    for (i = 1; i < visit_len; i++)
        if (strcmp(visit_buf[i - 1]->key, visit_buf[i]->key) >= 0)
            ok = 0; /* in-order visit must be sorted */

    for (i = 0; i < (int)(sizeof(queries) / sizeof(queries[0])); i++) {
        Node *n = lookup(queries[i]);
        printf("lookup %s: %d\n", queries[i], n ? n->count : 0);
    }

    for (i = 0; i < (int)(sizeof(removals) / sizeof(removals[0])); i++)
        removed += delete_key(removals[i]);
    printf("removed %d, distinct now %d, height %d\n", removed, size(root), height(root));
    if (size(root) != distinct - removed || lookup("compiler") != NULL)
        ok = 0;

    destroy(root);
    root = NULL;
    printf("allocations %d, releases %d\n", allocations, releases);
    if (allocations != releases)
        ok = 0;
    printf("%s\n", ok ? "SUCCESS" : "FAIL");
    return ok ? 0 : 1;
}
