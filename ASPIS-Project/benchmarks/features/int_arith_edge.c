/*
 * int_arith_edge.c -- integer corner cases of every width.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano). Microbenchmark for ASPIS regression testing.
 *
 * Checks that duplicated arithmetic and its consistency checks work on 8,
 * 16, 32, 64 and 128-bit integers: unsigned wrap-around, sign and zero
 * extension, truncation, arithmetic and logical shifts, division and modulo
 * of negative operands, overflow intrinsics (which return a {value, flag}
 * struct), bit-counting and byte-swap intrinsics and a 64x64->128 multiply.
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

static uint64_t xorshift64(uint64_t *state) {
    uint64_t x = *state;
    x ^= x << 13;
    x ^= x >> 7;
    x ^= x << 17;
    *state = x;
    return x;
}

static uint32_t fletcher32(const uint16_t *data, int words) {
    uint32_t a = 0xffff, b = 0xffff;
    int i;
    for (i = 0; i < words; i++) {
        a = (a + data[i]) % 65535u;
        b = (b + a) % 65535u;
    }
    return (b << 16) | a;
}

static int saturating_add16(int16_t a, int16_t b, int16_t *out) {
    int sum = a + b;
    if (sum > INT16_MAX) {
        *out = INT16_MAX;
        return 1;
    }
    if (sum < INT16_MIN) {
        *out = INT16_MIN;
        return 1;
    }
    *out = (int16_t)sum;
    return 0;
}

static uint32_t rotl32(uint32_t x, int r) {
    return (x << r) | (x >> ((32 - r) & 31));
}

int main(void) {
    uint8_t u8 = 250;
    int8_t s8 = -100;
    uint16_t words[16];
    int16_t sat;
    int32_t q[4], r[4];
    uint64_t state = 0x9e3779b97f4a7c15ull, h = 0;
    unsigned __int128 wide;
    int i, overflow_count = 0, sat_count = 0, ovf_flag;
    int32_t ovf_result;
    long long mixed;

    for (i = 0; i < 10; i++)
        u8 = (uint8_t)(u8 + 3); /* wraps */
    s8 = (int8_t)(s8 - 30);     /* -130 truncated to 126 */
    printf("u8 %u s8 %d sext %d zext %u\n", u8, s8, (int)(int8_t)0xf0, (unsigned)(uint8_t)0xf0);

    q[0] = -7 / 2;  r[0] = -7 % 2;
    q[1] = 7 / -2;  r[1] = 7 % -2;
    q[2] = -7 / -2; r[2] = -7 % -2;
    q[3] = INT32_MIN / 3; r[3] = INT32_MIN % 3;
    printf("div/mod: %d %d | %d %d | %d %d | %d %d\n", q[0], r[0], q[1], r[1], q[2], r[2],
           q[3], r[3]);
    printf("shifts: %d %u %d %u\n", -64 >> 3, 0x80000000u >> 31, (int32_t)(-1) >> 31,
           (uint32_t)(-1) >> 28);

    for (i = 0; i < 16; i++) {
        uint64_t v = xorshift64(&state);
        words[i] = (uint16_t)(v >> 32);
        h ^= v + (h << 6) + (h >> 2);
        if (__builtin_add_overflow((int32_t)(v >> 33), (int32_t)(v >> 34), &ovf_result))
            overflow_count++;
        if (saturating_add16((int16_t)(v & 0xffff), (int16_t)(v >> 48), &sat))
            sat_count++;
    }
    ovf_flag = __builtin_mul_overflow(65536, 65536, &ovf_result);
    printf("hash %016llx fletcher %08x\n", (unsigned long long)h, (unsigned)fletcher32(words, 16));
    printf("overflows %d saturations %d mul flag %d\n", overflow_count, sat_count, ovf_flag);
    printf("popcount %d clz %d ctz %d bswap %08x rotl %08x\n", __builtin_popcountll(h),
           __builtin_clz(0x00f00000u), __builtin_ctzll(0x100000000ull),
           (unsigned)__builtin_bswap32(0xdeadbeefu), (unsigned)rotl32(0x80000001u, 4));

    wide = (unsigned __int128)0xfedcba9876543210ull * 0x0123456789abcdefull;
    printf("128-bit product hi %016llx lo %016llx\n", (unsigned long long)(wide >> 64),
           (unsigned long long)wide);

    mixed = (long long)(int32_t)0xffffffffu * 3 + (unsigned short)65535 - (signed char)0x80;
    printf("mixed %lld\n", mixed);

    printf("%s\n", (u8 == 24 && s8 == 126 && q[0] == -3 && r[0] == -1) ? "SUCCESS" : "FAIL");
    return 0;
}
