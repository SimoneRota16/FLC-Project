/*
 * fft.c -- iterative radix-2 Cooley-Tukey FFT on 256 complex doubles.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Written from scratch for ASPIS regression
 * testing and fault-injection campaigns.
 *
 * A synthetic signal made of three tones plus deterministic noise is
 * transformed; the program reports the three dominant frequency bins,
 * verifies Parseval's theorem and checks that the inverse transform
 * reconstructs the input.
 *
 * ASPIS features stressed:
 *   - double-precision arithmetic and FP comparisons
 *   - arrays of structs (complex numbers) in global memory
 *   - calls to libm (sin, cos, sqrt) from hardened code
 *   - bit-reversal permutation (integer bit manipulation)
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

#define FFT_N 256
#define FFT_LOG2N 8
#define PI 3.14159265358979323846

typedef struct {
    double re;
    double im;
} complex_t;

static complex_t input[FFT_N];
static complex_t spectrum[FFT_N];
static double tw_re[FFT_N / 2];
static double tw_im[FFT_N / 2];
static unsigned int lcg_state = 20261029u;

static double noise(void) {
    lcg_state = lcg_state * 1103515245u + 12345u;
    return ((double)((lcg_state >> 16) & 0x7fff) / 32768.0 - 0.5) * 0.02;
}

static unsigned int bit_reverse(unsigned int x, int bits) {
    unsigned int r = 0;
    int i;
    for (i = 0; i < bits; i++) {
        r = (r << 1) | (x & 1u);
        x >>= 1;
    }
    return r;
}

static void init_twiddles(void) {
    int k;
    for (k = 0; k < FFT_N / 2; k++) {
        tw_re[k] = cos(2.0 * PI * k / FFT_N);
        tw_im[k] = -sin(2.0 * PI * k / FFT_N);
    }
}

static void fft(complex_t *x, int inverse) {
    unsigned int i, j;
    int size, start, k;
    for (i = 0; i < FFT_N; i++) {
        j = bit_reverse(i, FFT_LOG2N);
        if (j > i) {
            complex_t t = x[i];
            x[i] = x[j];
            x[j] = t;
        }
    }
    for (size = 2; size <= FFT_N; size *= 2) {
        int half = size / 2;
        int step = FFT_N / size;
        for (start = 0; start < FFT_N; start += size) {
            for (k = 0; k < half; k++) {
                double wr = tw_re[k * step];
                double wi = inverse ? -tw_im[k * step] : tw_im[k * step];
                complex_t a = x[start + k];
                complex_t b = x[start + k + half];
                double tr = b.re * wr - b.im * wi;
                double ti = b.re * wi + b.im * wr;
                x[start + k].re = a.re + tr;
                x[start + k].im = a.im + ti;
                x[start + k + half].re = a.re - tr;
                x[start + k + half].im = a.im - ti;
            }
        }
    }
    if (inverse) {
        for (i = 0; i < FFT_N; i++) {
            x[i].re /= FFT_N;
            x[i].im /= FFT_N;
        }
    }
}

static double magnitude(complex_t c) {
    return sqrt(c.re * c.re + c.im * c.im);
}

int main(void) {
    double energy_time = 0.0, energy_freq = 0.0, max_err = 0.0, mag_sum = 0.0;
    int peaks[3] = {-1, -1, -1};
    int n, k, p, ok = 1;

    init_twiddles();
    for (n = 0; n < FFT_N; n++) {
        input[n].re = 1.00 * sin(2.0 * PI * 5.0 * n / FFT_N) +
                      0.50 * cos(2.0 * PI * 12.0 * n / FFT_N) +
                      0.25 * sin(2.0 * PI * 40.0 * n / FFT_N) + noise();
        input[n].im = 0.0;
        spectrum[n] = input[n];
        energy_time += input[n].re * input[n].re;
    }

    fft(spectrum, 0);

    for (k = 0; k < FFT_N; k++) {
        double m = magnitude(spectrum[k]);
        energy_freq += m * m;
        if (k <= FFT_N / 2)
            mag_sum += m;
    }
    energy_freq /= FFT_N;

    /* three largest distinct bins in the first half of the spectrum */
    for (p = 0; p < 3; p++) {
        double best = -1.0;
        for (k = 1; k <= FFT_N / 2; k++) {
            double m = magnitude(spectrum[k]);
            if ((k == peaks[0]) || (k == peaks[1]))
                continue;
            if (m > best) {
                best = m;
                peaks[p] = k;
            }
        }
        printf("peak %d: bin %d magnitude %.6f\n", p, peaks[p], best);
    }
    if (peaks[0] != 5 || peaks[1] != 12 || peaks[2] != 40)
        ok = 0;

    printf("energy time %.9f freq %.9f\n", energy_time, energy_freq);
    if (fabs(energy_time - energy_freq) > 1e-9 * energy_time)
        ok = 0;
    printf("magnitude sum %.6f\n", mag_sum);

    fft(spectrum, 1);
    for (n = 0; n < FFT_N; n++) {
        double e = fabs(spectrum[n].re - input[n].re) + fabs(spectrum[n].im);
        if (e > max_err)
            max_err = e;
    }
    printf("ifft reconstruction: %s\n", max_err < 1e-9 ? "OK" : "MISMATCH");
    if (max_err >= 1e-9)
        ok = 0;

    printf("%s\n", ok ? "SUCCESS" : "FAIL");
    return ok ? 0 : 1;
}
