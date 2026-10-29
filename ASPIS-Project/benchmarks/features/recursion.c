/*
 * recursion.c -- direct, mutual and tree recursion.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * Hardened functions call the "_dup" version of their callees, so recursive
 * calls must be redirected to the function itself. The test covers simple
 * recursion with deep call chains, mutual recursion, multi-way recursion
 * (Ackermann, Hanoi), recursion with pointer arguments to global data
 * (flood fill) and backtracking (N-Queens, permutations).
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

#define GRID 8
#define QUEENS 6

static char grid[GRID][GRID + 1] = {
    "..#.....", ".##..#..", "..#..#..", "###..###",
    ".....#..", "..####..", "..#.....", "..#....."};
static int queens[QUEENS];
static long hanoi_moves;

static long fib(int n) {
    return n < 2 ? n : fib(n - 1) + fib(n - 2);
}

static int is_odd(unsigned int n);
static int is_even(unsigned int n) {
    return n == 0 ? 1 : is_odd(n - 1);
}
static int is_odd(unsigned int n) {
    return n == 0 ? 0 : is_even(n - 1);
}

static int ackermann(int m, int n) {
    if (m == 0)
        return n + 1;
    if (n == 0)
        return ackermann(m - 1, 1);
    return ackermann(m - 1, ackermann(m, n - 1));
}

static void hanoi(int n, int from, int to, int via) {
    if (n == 0)
        return;
    hanoi(n - 1, from, via, to);
    hanoi_moves++;
    hanoi(n - 1, via, to, from);
}

static int flood_fill(char g[GRID][GRID + 1], int r, int c) {
    if (r < 0 || r >= GRID || c < 0 || c >= GRID || g[r][c] != '.')
        return 0;
    g[r][c] = 'o';
    return 1 + flood_fill(g, r + 1, c) + flood_fill(g, r - 1, c) +
           flood_fill(g, r, c + 1) + flood_fill(g, r, c - 1);
}

static int safe(int row, int col) {
    int r;
    for (r = 0; r < row; r++) {
        int d = queens[r] - col;
        if (d == 0 || d == row - r || d == r - row)
            return 0;
    }
    return 1;
}

static int solve_queens(int row) {
    int col, count = 0;
    if (row == QUEENS)
        return 1;
    for (col = 0; col < QUEENS; col++) {
        if (safe(row, col)) {
            queens[row] = col;
            count += solve_queens(row + 1);
        }
    }
    return count;
}

static void swap_chars(char *a, char *b) {
    char t = *a;
    *a = *b;
    *b = t;
}

/* counts the permutations of s[k..] that keep the first char lower than
 * the last one */
static int permute(char *s, int k, int n) {
    int i, count = 0;
    if (k == n - 1)
        return s[0] < s[n - 1];
    for (i = k; i < n; i++) {
        swap_chars(&s[k], &s[i]);
        count += permute(s, k + 1, n);
        swap_chars(&s[k], &s[i]);
    }
    return count;
}

static unsigned long power_mod(unsigned long b, unsigned int e, unsigned long m) {
    unsigned long half;
    if (e == 0)
        return 1 % m;
    half = power_mod(b, e / 2, m);
    half = (half * half) % m;
    return (e & 1u) ? (half * (b % m)) % m : half;
}

int main(void) {
    char word[6] = "edcba";
    long f = fib(18);
    int even = is_even(41), ack = ackermann(2, 3), filled, sols, perms;
    unsigned long pm = power_mod(7ul, 560u, 561ul);

    hanoi(10, 1, 3, 2);
    filled = flood_fill(grid, 0, 0);
    sols = solve_queens(0);
    perms = permute(word, 0, 5);
    printf("fib %ld even %d ackermann %d hanoi %ld\n", f, even, ack, hanoi_moves);
    printf("flood %d queens %d perms %d powmod %lu\n", filled, sols, perms, pm);
    printf("grid row 0: %s\n", grid[0]);
    printf("%s\n", (f == 2584 && ack == 9 && hanoi_moves == 1023 && sols == 4) ? "SUCCESS" : "FAIL");
    return 0;
}
