/*
 * struct_by_value.c -- structs passed and returned by value.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * FuncRetToRef rewrites every function so that the return value is written
 * through an extra pointer argument, and EDDI duplicates every argument.
 * This test covers the ABI corner cases: small structs returned in
 * registers, large structs returned through a hidden sret pointer and passed
 * byval, structs of floats (SSE classes), nested structs with arrays, mixed
 * scalar types with padding, arrays of structs and calls through a pointer
 * to a struct-returning function.
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
    int x, y;
} Point;

typedef struct {
    double m[3][3];
} Mat3;

typedef struct {
    Point a, b;
    char tag[8];
} Segment;

typedef struct {
    float r, g, b;
} Color;

typedef struct {
    char c;
    short s;
    int i;
    long long l;
    unsigned char flags;
} Mixed;

static Point point_add(Point p, Point q) {
    Point r;
    r.x = p.x + q.x;
    r.y = p.y + q.y;
    return r;
}

static Point point_scale(Point p, int k) {
    p.x *= k;
    p.y *= k;
    return p;
}

static Mat3 mat3_identity(void) {
    Mat3 r;
    int i, j;
    for (i = 0; i < 3; i++)
        for (j = 0; j < 3; j++)
            r.m[i][j] = (i == j) ? 1.0 : 0.0;
    return r;
}

static Mat3 mat3_mul(Mat3 a, Mat3 b) {
    Mat3 r;
    int i, j, k;
    for (i = 0; i < 3; i++) {
        for (j = 0; j < 3; j++) {
            r.m[i][j] = 0.0;
            for (k = 0; k < 3; k++)
                r.m[i][j] += a.m[i][k] * b.m[k][j];
        }
    }
    return r;
}

static double mat3_trace(Mat3 a) {
    return a.m[0][0] + a.m[1][1] + a.m[2][2];
}

static Segment make_segment(Point a, Point b, const char *tag) {
    Segment s;
    s.a = a;
    s.b = b;
    strncpy(s.tag, tag, sizeof(s.tag) - 1);
    s.tag[sizeof(s.tag) - 1] = '\0';
    return s;
}

static int segment_len2(Segment s) {
    int dx = s.b.x - s.a.x, dy = s.b.y - s.a.y;
    return dx * dx + dy * dy;
}

static Color blend(Color c1, Color c2, float t) {
    Color r;
    r.r = c1.r + (c2.r - c1.r) * t;
    r.g = c1.g + (c2.g - c1.g) * t;
    r.b = c1.b + (c2.b - c1.b) * t;
    return r;
}

static Mixed mixed_update(Mixed m, int delta) {
    m.c = (char)(m.c + delta);
    m.s = (short)(m.s * 2 - delta);
    m.i += delta * 1000;
    m.l = m.l * 3 + m.i;
    m.flags = (unsigned char)(m.flags ^ (1u << (delta & 7)));
    return m;
}

int main(void) {
    Point pts[6], acc = {0, 0};
    Point (*op)(Point, Point) = point_add;
    Mat3 rot, r2, id;
    Segment seg;
    Color c, red = {1.0f, 0.0f, 0.0f}, blue = {0.0f, 0.2f, 1.0f};
    Mixed m = {'A', 7, -3, 1234567890123LL, 0x5a};
    int i;

    for (i = 0; i < 6; i++) {
        Point p;
        p.x = i;
        p.y = 10 - 2 * i;
        pts[i] = point_scale(p, i + 1);
        acc = op(acc, pts[i]);
    }
    printf("points sum (%d, %d)\n", acc.x, acc.y);

    /* 90 degree rotation about z: rot^4 == identity */
    id = mat3_identity();
    rot = id;
    rot.m[0][0] = 0.0;
    rot.m[0][1] = -1.0;
    rot.m[1][0] = 1.0;
    rot.m[1][1] = 0.0;
    r2 = mat3_mul(rot, rot);
    printf("trace rot %.1f rot^2 %.1f rot^4 %.1f\n", mat3_trace(rot), mat3_trace(r2),
           mat3_trace(mat3_mul(r2, r2)));

    seg = make_segment(pts[1], pts[4], "diagonal-long-name");
    printf("segment %s len2 %d\n", seg.tag, segment_len2(seg));

    c = blend(red, blue, 0.25f);
    printf("blend %.3f %.3f %.3f\n", c.r, c.g, c.b);

    for (i = 1; i <= 3; i++)
        m = mixed_update(m, i);
    printf("mixed %c %d %d %lld %02x\n", m.c, m.s, m.i, m.l, m.flags);

    printf("%s\n", (acc.x == 70 && segment_len2(seg) == 360) ? "SUCCESS" : "FAIL");
    return 0;
}
