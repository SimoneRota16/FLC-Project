/*
 * float_special.c -- IEEE-754 special values flowing through hardened code.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * EDDI compares the two copies of every floating-point value before stores,
 * branches and calls. A NaN is never equal to itself with an ordered
 * comparison, so the checks must use an unordered comparison or a bitwise
 * one, otherwise a fault-free program producing a NaN would be reported as
 * corrupted. The test produces and propagates NaN, infinities, signed zeros
 * and subnormals, compares them, converts them and uses long double too.
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <float.h>

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

static volatile double zero = 0.0;
static double g_nan_store[4];

static double div_by(double a, double b) {
    return a / b;
}

static const char *classify(double x) {
    if (x != x)
        return "nan";
    if (x == 1.0 / zero)
        return "+inf";
    if (x == -1.0 / zero)
        return "-inf";
    if (x == 0.0)
        return signbit(x) ? "-zero" : "+zero";
    if (fabs(x) < DBL_MIN)
        return "subnormal";
    return "normal";
}

static int count_ordered(const double *v, int n, double pivot) {
    int i, c = 0;
    for (i = 0; i < n; i++)
        if (v[i] < pivot || v[i] > pivot || v[i] == pivot)
            c++;
    return c;
}

static double nan_safe_max(double a, double b) {
    if (a != a)
        return b;
    if (b != b)
        return a;
    return a > b ? a : b;
}

int main(void) {
    double values[8];
    double sum = 0.0, best = -1.0 / zero, tiny;
    float fsum = 0.0f;
    long double ld = 1.0L;
    int i, nans = 0, conv[3];

    values[0] = div_by(0.0, zero);      /* NaN */
    values[1] = div_by(1.0, zero);      /* +inf */
    values[2] = div_by(-1.0, zero);     /* -inf */
    values[3] = -0.0;
    values[4] = values[1] - values[1];  /* NaN */
    values[5] = sqrt(-1.0 + zero);      /* NaN */
    values[6] = DBL_MIN / 1024.0;       /* subnormal */
    values[7] = 3.5;

    for (i = 0; i < 8; i++) {
        printf("v%d %s\n", i, classify(values[i]));
        if (isnan(values[i])) {
            g_nan_store[nans % 4] = values[i];
            nans++;
        }
        best = nan_safe_max(best, values[i]);
    }
    printf("nans %d ordered vs 1.0: %d best %s\n", nans, count_ordered(values, 8, 1.0),
           classify(best));

    /* NaN propagation through arithmetic and stored copies */
    sum = g_nan_store[0] + 1.0;
    printf("nan + 1 is %s, nan == nan is %d, nan != nan is %d\n", classify(sum),
           g_nan_store[0] == g_nan_store[0], g_nan_store[0] != g_nan_store[0]);
    printf("1/-0 is %s, -0 == +0 is %d\n", classify(1.0 / values[3]), values[3] == 0.0);

    /* gradual underflow */
    tiny = DBL_MIN;
    for (i = 0; i < 60; i++)
        tiny /= 2.0;
    printf("underflow to %s (%.3e)\n", classify(tiny), tiny);

    for (i = 0; i < 10; i++)
        fsum += 0.1f;
    printf("ten times 0.1f == 1.0f: %d (%.9f)\n", fsum == 1.0f, (double)fsum);

    conv[0] = (int)3.99;
    conv[1] = (int)-3.99;
    conv[2] = (int)(float)16777217;
    printf("conversions %d %d %d\n", conv[0], conv[1], conv[2]);

    for (i = 0; i < 20; i++)
        ld = ld * 3.0L + 0.5L;
    printf("long double %.6Le\n", ld);

    printf("%s\n", (nans == 3 && conv[0] == 3 && conv[1] == -3) ? "SUCCESS" : "FAIL");
    return 0;
}
