/*
 * unions_bitfields.c -- unions, type punning and bit-fields.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * Covers memory that is read with a different type than the one used to
 * write it (float/integer punning, word/byte views), bit-field
 * read-modify-write sequences with wrap-around, a tagged union processed by
 * a switch and an array of unions. Duplicated loads and stores must keep the
 * two copies of these objects bit-identical.
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

typedef union {
    float f;
    uint32_t u;
} FloatBits;

typedef union {
    uint32_t word;
    uint8_t bytes[4];
} WordBytes;

typedef struct {
    unsigned int version : 3;
    unsigned int type : 5;
    unsigned int length : 12;
    unsigned int flags : 4;
    unsigned int crc : 8;
} Header;

#define V_INT 0
#define V_REAL 1
#define V_TEXT 2

typedef struct {
    int tag;
    union {
        long i;
        double d;
        const char *s;
    } as;
} Variant;

static float make_float(int sign, int exponent, uint32_t mantissa) {
    FloatBits b;
    b.u = ((uint32_t)(sign & 1) << 31) | ((uint32_t)(exponent & 0xff) << 23) | (mantissa & 0x7fffffu);
    return b.f;
}

static uint32_t float_bits(float f) {
    FloatBits b;
    b.f = f;
    return b.u;
}

static uint32_t byte_swap(uint32_t x) {
    WordBytes in, out;
    int i;
    in.word = x;
    for (i = 0; i < 4; i++)
        out.bytes[i] = in.bytes[3 - i];
    return out.word;
}

static uint8_t header_crc(const Header *h) {
    unsigned int v = h->version * 31u + h->type * 7u + h->length + h->flags * 131u;
    return (uint8_t)(v ^ (v >> 8));
}

static double variant_value(const Variant *v) {
    switch (v->tag) {
    case V_INT: return (double)v->as.i;
    case V_REAL: return v->as.d;
    case V_TEXT: {
        double len = 0.0;
        const char *p = v->as.s;
        while (*p++)
            len += 1.0;
        return len;
    }
    default: return -1.0;
    }
}

int main(void) {
    Header h;
    Variant vars[5];
    WordBytes wb;
    double total = 0.0;
    float f;
    int i, wraps = 0;

    f = make_float(0, 127 + 3, 0x200000u); /* 1.25 * 2^3 = 10 */
    printf("float %.3f bits %08x neg %08x\n", f, (unsigned)float_bits(f),
           (unsigned)float_bits(-f));
    printf("swap %08x\n", (unsigned)byte_swap(0x11223344u));
    wb.word = 0xa1b2c3d4u;
    wb.bytes[1] = 0xee;
    printf("patched word %08x\n", (unsigned)wb.word);

    h.version = 5;
    h.type = 17;
    h.length = 4000;
    h.flags = 9;
    h.crc = 0;
    for (i = 0; i < 40; i++) {
        unsigned int before = h.length;
        h.length = h.length + 13;  /* wraps modulo 4096 */
        h.flags = h.flags + 1;     /* wraps modulo 16 */
        h.version = h.version ^ 3u;
        if (h.length < before)
            wraps++;
    }
    h.crc = header_crc(&h);
    printf("header v%u t%u len %u flags %u crc %u wraps %d\n", h.version, h.type, h.length,
           h.flags, h.crc, wraps);

    for (i = 0; i < 5; i++) {
        vars[i].tag = i % 3;
        if (vars[i].tag == V_INT)
            vars[i].as.i = 1000L * (i + 1);
        else if (vars[i].tag == V_REAL)
            vars[i].as.d = 0.5 * i;
        else
            vars[i].as.s = (i == 2) ? "variant" : "union";
    }
    for (i = 0; i < 5; i++)
        total += variant_value(&vars[i]);
    printf("variant total %.2f\n", total);

    printf("%s\n", (f == 10.0f && wraps == 1 && byte_swap(0x11223344u) == 0x44332211u) ? "SUCCESS" : "FAIL");
    return 0;
}
