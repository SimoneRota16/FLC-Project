/*
 * sobel.c -- edge detection on a synthetic 48x48 grey-scale image.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Written from scratch for ASPIS regression
 * testing and fault-injection campaigns.
 *
 * A procedurally generated picture (gradient background, a disc, a square
 * and a diagonal bar, plus deterministic noise) is smoothed with a 3x3
 * Gaussian kernel, then the Sobel operator computes the gradient magnitude
 * that is thresholded into an edge map. The program prints the edge count,
 * the edge centroid, a 8-bin histogram of the magnitude and Adler-32
 * checksums of the intermediate images.
 *
 * ASPIS features stressed:
 *   - two-dimensional global arrays of unsigned bytes
 *   - integer arithmetic with clamping and border replication
 *   - small helper functions called in tight loops
 *   - convolution kernels stored in constant tables
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

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

#define W 48
#define H 48
#define EDGE_THRESHOLD 96

static uint8_t image[H][W];
static uint8_t smooth[H][W];
static uint8_t magnitude[H][W];
static uint8_t edges[H][W];
static unsigned int rng = 99991u;

static const int gauss[3][3] = {{1, 2, 1}, {2, 4, 2}, {1, 2, 1}};
static const int sobel_x[3][3] = {{-1, 0, 1}, {-2, 0, 2}, {-1, 0, 1}};
static const int sobel_y[3][3] = {{-1, -2, -1}, {0, 0, 0}, {1, 2, 1}};

static int clamp(int v, int lo, int hi) {
    if (v < lo)
        return lo;
    if (v > hi)
        return hi;
    return v;
}

static int noise(void) {
    rng = rng * 69069u + 1u;
    return (int)((rng >> 24) % 17u) - 8; /* [-8, 8] */
}

static void generate_image(void) {
    int x, y;
    for (y = 0; y < H; y++) {
        for (x = 0; x < W; x++) {
            int v = 20 + 2 * x + y;
            int dx = x - 17, dy = y - 20;
            if (dx * dx + dy * dy <= 11 * 11)
                v = 210;
            if (x >= 30 && x <= 42 && y >= 6 && y <= 18)
                v = 90;
            if (y - x >= 18 && y - x <= 21)
                v = 160;
            image[y][x] = (uint8_t)clamp(v + noise(), 0, 255);
        }
    }
}

static int pixel(uint8_t img[H][W], int y, int x) {
    return img[clamp(y, 0, H - 1)][clamp(x, 0, W - 1)];
}

static void gaussian_blur(void) {
    int x, y, i, j;
    for (y = 0; y < H; y++) {
        for (x = 0; x < W; x++) {
            int acc = 0;
            for (i = -1; i <= 1; i++)
                for (j = -1; j <= 1; j++)
                    acc += gauss[i + 1][j + 1] * pixel(image, y + i, x + j);
            smooth[y][x] = (uint8_t)((acc + 8) / 16);
        }
    }
}

static void sobel(void) {
    int x, y, i, j;
    for (y = 0; y < H; y++) {
        for (x = 0; x < W; x++) {
            int gx = 0, gy = 0;
            for (i = -1; i <= 1; i++) {
                for (j = -1; j <= 1; j++) {
                    int p = pixel(smooth, y + i, x + j);
                    gx += sobel_x[i + 1][j + 1] * p;
                    gy += sobel_y[i + 1][j + 1] * p;
                }
            }
            magnitude[y][x] = (uint8_t)clamp(abs(gx) + abs(gy), 0, 255);
            edges[y][x] = magnitude[y][x] > EDGE_THRESHOLD ? 255 : 0;
        }
    }
}

static uint32_t adler32(uint8_t img[H][W]) {
    uint32_t a = 1, b = 0;
    int x, y;
    for (y = 0; y < H; y++) {
        for (x = 0; x < W; x++) {
            a = (a + img[y][x]) % 65521u;
            b = (b + a) % 65521u;
        }
    }
    return (b << 16) | a;
}

int main(void) {
    int hist[8] = {0, 0, 0, 0, 0, 0, 0, 0};
    long sum_x = 0, sum_y = 0;
    int x, y, count = 0, ok = 1;

    generate_image();
    gaussian_blur();
    sobel();

    for (y = 0; y < H; y++) {
        for (x = 0; x < W; x++) {
            hist[magnitude[y][x] >> 5]++;
            if (edges[y][x]) {
                count++;
                sum_x += x;
                sum_y += y;
            }
        }
    }
    printf("image adler32 %08x, smooth adler32 %08x\n", (unsigned)adler32(image),
           (unsigned)adler32(smooth));
    printf("magnitude adler32 %08x, edges adler32 %08x\n", (unsigned)adler32(magnitude),
           (unsigned)adler32(edges));
    printf("histogram:");
    for (x = 0; x < 8; x++)
        printf(" %d", hist[x]);
    printf("\n");
    if (count == 0) {
        ok = 0;
        printf("no edges found\n");
    } else {
        printf("edge pixels %d, centroid (%ld, %ld)\n", count, sum_x / count, sum_y / count);
    }
    printf("%s\n", ok ? "SUCCESS" : "FAIL");
    return ok ? 0 : 1;
}
