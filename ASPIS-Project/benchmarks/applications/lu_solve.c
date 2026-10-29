/*
 * lu_solve.c -- dense linear solver: LU decomposition with partial pivoting.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Written from scratch for ASPIS regression
 * testing and fault-injection campaigns.
 *
 * A pseudo-random 12x12 matrix with a small diagonal (so that row swaps are
 * really needed) is factorised as P*A = L*U. The factors are used to solve
 * A*x = b for a known solution, to compute the determinant and to build the
 * inverse matrix, whose product with A is checked against the identity.
 *
 * ASPIS features stressed:
 *   - two-dimensional global arrays of doubles
 *   - pointer-to-row arithmetic and row swaps
 *   - data-dependent control flow (pivot search)
 *   - floating-point accumulation in triple-nested loops
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

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

#define LU_N 12

static double A[LU_N][LU_N];
static double LU[LU_N][LU_N];
static double INV[LU_N][LU_N];
static int perm[LU_N];
static unsigned int seed = 7u;

static double uniform(void) {
    seed = seed * 1664525u + 1013904223u;
    return (double)(seed >> 8) / 16777216.0; /* [0, 1) */
}

static void generate_matrix(void) {
    int i, j;
    for (i = 0; i < LU_N; i++)
        for (j = 0; j < LU_N; j++)
            A[i][j] = 2.0 * uniform() - 1.0;
    /* small diagonal entries force partial pivoting to swap rows */
    for (i = 0; i < LU_N; i++)
        A[i][i] *= 0.01;
}

/* In-place Doolittle factorisation. Returns the permutation sign, 0 if the
 * matrix is (numerically) singular. */
static int lu_decompose(double m[LU_N][LU_N], int *p, int *swaps) {
    int i, j, k, sign = 1;
    for (i = 0; i < LU_N; i++)
        p[i] = i;
    *swaps = 0;
    for (k = 0; k < LU_N; k++) {
        int piv = k;
        double best = fabs(m[k][k]);
        for (i = k + 1; i < LU_N; i++) {
            if (fabs(m[i][k]) > best) {
                best = fabs(m[i][k]);
                piv = i;
            }
        }
        if (best < 1e-12)
            return 0;
        if (piv != k) {
            for (j = 0; j < LU_N; j++) {
                double t = m[k][j];
                m[k][j] = m[piv][j];
                m[piv][j] = t;
            }
            i = p[k];
            p[k] = p[piv];
            p[piv] = i;
            sign = -sign;
            (*swaps)++;
        }
        for (i = k + 1; i < LU_N; i++) {
            double *row = m[i];
            const double *prow = m[k];
            row[k] /= prow[k];
            for (j = k + 1; j < LU_N; j++)
                row[j] -= row[k] * prow[j];
        }
    }
    return sign;
}

static void lu_solve(double m[LU_N][LU_N], const int *p, const double *b, double *x) {
    double y[LU_N];
    int i, j;
    for (i = 0; i < LU_N; i++) {
        double s = b[p[i]];
        for (j = 0; j < i; j++)
            s -= m[i][j] * y[j];
        y[i] = s;
    }
    for (i = LU_N - 1; i >= 0; i--) {
        double s = y[i];
        for (j = i + 1; j < LU_N; j++)
            s -= m[i][j] * x[j];
        x[i] = s / m[i][i];
    }
}

int main(void) {
    double x_true[LU_N], b[LU_N], x[LU_N], e[LU_N], col[LU_N];
    double det, max_err = 0.0, max_res = 0.0, max_id = 0.0, inv_sum = 0.0;
    int i, j, k, sign, swaps, ok = 1;

    generate_matrix();
    for (i = 0; i < LU_N; i++)
        for (j = 0; j < LU_N; j++)
            LU[i][j] = A[i][j];

    sign = lu_decompose(LU, perm, &swaps);
    if (sign == 0) {
        printf("singular matrix\nFAIL\n");
        return 1;
    }
    det = (double)sign;
    for (i = 0; i < LU_N; i++)
        det *= LU[i][i];
    printf("row swaps: %d\n", swaps);
    printf("determinant: %.10e\n", det);

    /* solve for a known solution */
    for (i = 0; i < LU_N; i++)
        x_true[i] = 0.5 * (i + 1) - 3.0;
    for (i = 0; i < LU_N; i++) {
        b[i] = 0.0;
        for (j = 0; j < LU_N; j++)
            b[i] += A[i][j] * x_true[j];
    }
    lu_solve(LU, perm, b, x);
    for (i = 0; i < LU_N; i++) {
        double r = 0.0;
        if (fabs(x[i] - x_true[i]) > max_err)
            max_err = fabs(x[i] - x_true[i]);
        for (j = 0; j < LU_N; j++)
            r += A[i][j] * x[j];
        if (fabs(r - b[i]) > max_res)
            max_res = fabs(r - b[i]);
    }
    printf("solution error: %s\n", max_err < 1e-9 ? "OK" : "TOO LARGE");
    printf("residual: %s\n", max_res < 1e-9 ? "OK" : "TOO LARGE");
    if (max_err >= 1e-9 || max_res >= 1e-9)
        ok = 0;

    /* inverse, one column at a time */
    for (j = 0; j < LU_N; j++) {
        for (i = 0; i < LU_N; i++)
            e[i] = (i == j) ? 1.0 : 0.0;
        lu_solve(LU, perm, e, col);
        for (i = 0; i < LU_N; i++) {
            INV[i][j] = col[i];
            inv_sum += col[i];
        }
    }
    for (i = 0; i < LU_N; i++) {
        for (j = 0; j < LU_N; j++) {
            double s = 0.0;
            for (k = 0; k < LU_N; k++)
                s += A[i][k] * INV[k][j];
            s -= (i == j) ? 1.0 : 0.0;
            if (fabs(s) > max_id)
                max_id = fabs(s);
        }
    }
    printf("inverse sum: %.8f\n", inv_sum);
    printf("A*inv(A) = I: %s\n", max_id < 1e-9 ? "OK" : "TOO LARGE");
    if (max_id >= 1e-9)
        ok = 0;

    printf("%s\n", ok ? "SUCCESS" : "FAIL");
    return ok ? 0 : 1;
}
