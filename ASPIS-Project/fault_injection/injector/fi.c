/*
 * fi.c -- ptrace-based software fault injector for x86-64 Linux binaries.
 *
 * Part of the FLC 2026/27 project "Harden a C application with ASPIS"
 * (Politecnico di Milano).
 *
 * The injector emulates Single Event Upsets that hit the processor while the
 * program is running. Faults are only injected while the program executes
 * instructions of its own executable (the code hardened by ASPIS), never in
 * the dynamic loader or in the C library.
 *
 *   fi profile <out.prof> <out.stdout> -- <program> [args]
 *       Golden run: single-steps the whole execution, counts how many times
 *       every instruction of the executable is executed and decodes the
 *       conditional jumps. The program output is stored as reference.
 *
 *   fi inject <prof> <golden.stdout> <model> <seed> <count> <timeout_ms>
 *             <tmp_dir> -- <program> [args]
 *       Runs <count> experiments. Each one picks a dynamic instruction
 *       uniformly at random (i.e. a random point in time), stops the program
 *       right before that instruction with a software breakpoint, corrupts
 *       the processor state according to <model>, detaches and classifies the
 *       outcome. One CSV line per experiment is written to stdout.
 *       Models:
 *         reg     single bit-flip in one of the 16 general purpose registers
 *         branch  the outcome of a conditional jump is inverted
 *         jump    the program counter is set to a random instruction of the
 *                 executable (illegal control-flow transfer)
 *
 *   fi bench <runs> -- <program> [args]
 *       Runs the program <runs> times without tracing and prints the
 *       minimum and median wall-clock time in microseconds.
 *
 * The program under test must report the ASPIS detections on stderr with
 * "FAULT_DETECTED: DataCorruption" (EDDI family) or
 * "FAULT_DETECTED: SigMismatch" (control-flow checking).
 *
 * Copyright (c) 2026 Alberto Rotolo, Simone Rota
 * SPDX-License-Identifier: MIT
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/personality.h>
#include <sys/ptrace.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/user.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define KIND_OTHER 0
#define KIND_JCC 1

typedef struct {
    uint64_t off;   /* offset from the start of the executable text */
    uint64_t count; /* dynamic executions in the golden run */
    int kind;       /* KIND_OTHER or KIND_JCC */
    int cc;         /* condition code of a jcc */
    int len;        /* instruction length of a jcc */
    int64_t rel;    /* displacement of a jcc */
} PcInfo;

typedef struct {
    uint64_t text_lo, text_hi;
    uint64_t n_app, n_total, n_jcc;
    int exit_status;
    size_t npcs;
    PcInfo *pcs;
} Profile;

static char *child_env[] = {"LANG=C", "LC_ALL=C", "PATH=/usr/bin:/bin", NULL};

static void die(const char *msg) {
    fprintf(stderr, "fi: %s: %s\n", msg, strerror(errno));
    exit(100);
}

static uint64_t now_us(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000u + (uint64_t)ts.tv_nsec / 1000u;
}

/* ------------------------------------------------------------- PRNG */
static uint64_t rng_state;

static uint64_t rng_next(void) { /* splitmix64 */
    uint64_t z = (rng_state += 0x9e3779b97f4a7c15ull);
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
    return z ^ (z >> 31);
}

static uint64_t rng_below(uint64_t n) {
    return n ? rng_next() % n : 0;
}

/* ------------------------------------------------------- process spawn */
static pid_t spawn(char **argv, const char *out_path, const char *err_path, int traced) {
    pid_t pid = fork();
    if (pid < 0)
        die("fork");
    if (pid == 0) {
        int in = open("/dev/null", O_RDONLY);
        int out = open(out_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        int err = open(err_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
        if (in < 0 || out < 0 || err < 0)
            _exit(126);
        dup2(in, 0);
        dup2(out, 1);
        dup2(err, 2);
        close(in);
        close(out);
        close(err);
        personality(ADDR_NO_RANDOMIZE); /* same addresses in every run */
        if (traced)
            ptrace(PTRACE_TRACEME, 0, NULL, NULL);
        execve(argv[0], argv, child_env);
        _exit(127);
    }
    if (traced) {
        int status;
        if (waitpid(pid, &status, 0) < 0 || !WIFSTOPPED(status)) {
            fprintf(stderr, "fi: the child did not stop after exec (status 0x%x)\n", status);
            exit(100);
        }
        ptrace(PTRACE_SETOPTIONS, pid, NULL, (void *)(long)PTRACE_O_EXITKILL);
    }
    return pid;
}

/* finds the executable mapping of the program in /proc/<pid>/maps */
static int text_range(pid_t pid, const char *prog, uint64_t *lo, uint64_t *hi) {
    char path[64], line[PATH_MAX + 128], real[PATH_MAX];
    FILE *f;
    int found = 0;
    if (realpath(prog, real) == NULL)
        return 0;
    snprintf(path, sizeof(path), "/proc/%d/maps", (int)pid);
    f = fopen(path, "r");
    if (!f)
        return 0;
    while (fgets(line, sizeof(line), f)) {
        unsigned long a, b;
        char perms[8], file[PATH_MAX];
        file[0] = '\0';
        if (sscanf(line, "%lx-%lx %7s %*s %*s %*s %4095s", &a, &b, perms, file) < 3)
            continue;
        if (perms[2] == 'x' && strcmp(file, real) == 0) {
            if (!found || a < *lo)
                *lo = a;
            if (!found || b > *hi)
                *hi = b;
            found = 1;
        }
    }
    fclose(f);
    return found;
}

/* decodes "jcc rel8" (70-7f) and "jcc rel32" (0f 80-8f), optionally with a
 * branch-hint prefix */
static void decode_jcc(const unsigned char *b, PcInfo *pi) {
    int p = 0;
    pi->kind = KIND_OTHER;
    if (b[0] == 0x2e || b[0] == 0x3e)
        p = 1;
    if (b[p] >= 0x70 && b[p] <= 0x7f) {
        pi->kind = KIND_JCC;
        pi->cc = b[p] & 0xf;
        pi->len = p + 2;
        pi->rel = (int8_t)b[p + 1];
    } else if (b[p] == 0x0f && b[p + 1] >= 0x80 && b[p + 1] <= 0x8f) {
        int32_t rel;
        memcpy(&rel, &b[p + 2], 4);
        pi->kind = KIND_JCC;
        pi->cc = b[p + 1] & 0xf;
        pi->len = p + 6;
        pi->rel = rel;
    }
}

static int jcc_taken(int cc, uint64_t fl) {
    int cf = (fl >> 0) & 1, pf = (fl >> 2) & 1, zf = (fl >> 6) & 1;
    int sf = (fl >> 7) & 1, of = (fl >> 11) & 1, r;
    switch (cc >> 1) {
    case 0: r = of; break;
    case 1: r = cf; break;
    case 2: r = zf; break;
    case 3: r = cf | zf; break;
    case 4: r = sf; break;
    case 5: r = pf; break;
    case 6: r = sf != of; break;
    default: r = zf | (sf != of); break;
    }
    return (cc & 1) ? !r : r;
}

/* --------------------------------------------------------------- profile */
static int cmd_profile(const char *prof_path, const char *stdout_path, char **argv) {
    char err_path[PATH_MAX];
    uint64_t lo = 0, hi = 0, n_app = 0, n_total = 0;
    uint64_t *counts;
    unsigned char *decoded;
    PcInfo *info;
    struct user_regs_struct regs;
    int status, sig = 0;
    size_t size, i, npcs = 0;
    FILE *f;
    pid_t pid;

    snprintf(err_path, sizeof(err_path), "%s.stderr", stdout_path);
    pid = spawn(argv, stdout_path, err_path, 1);
    if (!text_range(pid, argv[0], &lo, &hi)) {
        fprintf(stderr, "fi: cannot find the text segment of %s\n", argv[0]);
        kill(pid, SIGKILL);
        return 100;
    }
    size = hi - lo;
    counts = (uint64_t *)calloc(size, sizeof(uint64_t));
    decoded = (unsigned char *)calloc(size, 1);
    info = (PcInfo *)calloc(size, sizeof(PcInfo));
    if (!counts || !decoded || !info)
        die("calloc");

    for (;;) {
        if (ptrace(PTRACE_GETREGS, pid, NULL, &regs) < 0)
            die("PTRACE_GETREGS");
        n_total++;
        if (regs.rip >= lo && regs.rip < hi) {
            uint64_t off = regs.rip - lo;
            n_app++;
            if (counts[off]++ == 0) {
                unsigned char bytes[16];
                long w0 = ptrace(PTRACE_PEEKTEXT, pid, (void *)regs.rip, NULL);
                long w1 = ptrace(PTRACE_PEEKTEXT, pid, (void *)(regs.rip + 8), NULL);
                memcpy(bytes, &w0, 8);
                memcpy(bytes + 8, &w1, 8);
                decode_jcc(bytes, &info[off]);
                decoded[off] = 1;
            }
        }
        if (ptrace(PTRACE_SINGLESTEP, pid, NULL, (void *)(long)sig) < 0)
            die("PTRACE_SINGLESTEP");
        sig = 0;
        if (waitpid(pid, &status, 0) < 0)
            die("waitpid");
        if (WIFEXITED(status) || WIFSIGNALED(status))
            break;
        if (WIFSTOPPED(status) && WSTOPSIG(status) != SIGTRAP)
            sig = WSTOPSIG(status);
    }

    f = fopen(prof_path, "w");
    if (!f)
        die("fopen profile");
    for (i = 0; i < size; i++)
        if (counts[i])
            npcs++;
    fprintf(f, "fi-profile 1\n");
    fprintf(f, "text %lx %lx\n", (unsigned long)lo, (unsigned long)hi);
    fprintf(f, "dynamic %lu %lu\n", (unsigned long)n_app, (unsigned long)n_total);
    fprintf(f, "exit %d\n", WIFEXITED(status) ? WEXITSTATUS(status) : 128 + WTERMSIG(status));
    fprintf(f, "pcs %lu\n", (unsigned long)npcs);
    for (i = 0; i < size; i++) {
        if (!counts[i])
            continue;
        fprintf(f, "%lx %lu %d %d %d %ld\n", (unsigned long)i, (unsigned long)counts[i],
                info[i].kind, info[i].cc, info[i].len, (long)info[i].rel);
    }
    fclose(f);
    printf("profile: %lu app instructions (%lu total), %lu distinct pcs, exit %d\n",
           (unsigned long)n_app, (unsigned long)n_total, (unsigned long)npcs,
           WIFEXITED(status) ? WEXITSTATUS(status) : -1);
    free(counts);
    free(decoded);
    free(info);
    return 0;
}

static void load_profile(const char *path, Profile *p) {
    FILE *f = fopen(path, "r");
    unsigned long lo, hi, napp, ntot, npcs, i;
    if (!f)
        die("open profile");
    memset(p, 0, sizeof(*p));
    if (fscanf(f, "fi-profile 1\ntext %lx %lx\ndynamic %lu %lu\nexit %d\npcs %lu\n", &lo, &hi,
               &napp, &ntot, &p->exit_status, &npcs) != 6) {
        fprintf(stderr, "fi: malformed profile %s\n", path);
        exit(100);
    }
    p->text_lo = lo;
    p->text_hi = hi;
    p->n_app = napp;
    p->n_total = ntot;
    p->npcs = npcs;
    p->pcs = (PcInfo *)calloc(npcs, sizeof(PcInfo));
    for (i = 0; i < npcs; i++) {
        unsigned long off, cnt;
        long rel;
        PcInfo *pi = &p->pcs[i];
        if (fscanf(f, "%lx %lu %d %d %d %ld\n", &off, &cnt, &pi->kind, &pi->cc, &pi->len, &rel) != 6) {
            fprintf(stderr, "fi: malformed profile line %lu\n", i);
            exit(100);
        }
        pi->off = off;
        pi->count = cnt;
        pi->rel = rel;
        if (pi->kind == KIND_JCC)
            p->n_jcc += cnt;
    }
    fclose(f);
}

/* picks the k-th dynamic instruction among the ones selected by only_jcc */
static size_t pick_target(const Profile *p, int only_jcc, uint64_t *occurrence) {
    uint64_t total = only_jcc ? p->n_jcc : p->n_app;
    uint64_t k = rng_below(total);
    size_t i;
    for (i = 0; i < p->npcs; i++) {
        const PcInfo *pi = &p->pcs[i];
        if (only_jcc && pi->kind != KIND_JCC)
            continue;
        if (k < pi->count) {
            *occurrence = k;
            return i;
        }
        k -= pi->count;
    }
    *occurrence = 0;
    return p->npcs - 1;
}

static unsigned long long *gpr(struct user_regs_struct *r, int idx) {
    switch (idx) {
    case 0: return &r->rax;
    case 1: return &r->rbx;
    case 2: return &r->rcx;
    case 3: return &r->rdx;
    case 4: return &r->rsi;
    case 5: return &r->rdi;
    case 6: return &r->rbp;
    case 7: return &r->rsp;
    case 8: return &r->r8;
    case 9: return &r->r9;
    case 10: return &r->r10;
    case 11: return &r->r11;
    case 12: return &r->r12;
    case 13: return &r->r13;
    case 14: return &r->r14;
    default: return &r->r15;
    }
}

static const char *gpr_name[16] = {"rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
                                   "r8",  "r9",  "r10", "r11", "r12", "r13", "r14", "r15"};

static char *read_file(const char *path, size_t *len) {
    FILE *f = fopen(path, "rb");
    char *buf;
    long n;
    *len = 0;
    if (!f)
        return NULL;
    fseek(f, 0, SEEK_END);
    n = ftell(f);
    fseek(f, 0, SEEK_SET);
    buf = (char *)malloc((size_t)n + 1);
    if (n > 0 && fread(buf, 1, (size_t)n, f) != (size_t)n)
        n = 0;
    buf[n] = '\0';
    fclose(f);
    *len = (size_t)n;
    return buf;
}

/* waits for the child up to timeout_us; returns 0 on exit, 1 on timeout */
static int wait_with_timeout(pid_t pid, int *status, uint64_t timeout_us) {
    uint64_t start = now_us();
    struct timespec pause = {0, 100000}; /* 100 us */
    for (;;) {
        pid_t r = waitpid(pid, status, WNOHANG);
        if (r == pid)
            return 0;
        if (r < 0)
            die("waitpid");
        if (now_us() - start > timeout_us) {
            kill(pid, SIGKILL);
            waitpid(pid, status, 0);
            return 1;
        }
        nanosleep(&pause, NULL);
    }
}

static int cmd_inject(const char *prof_path, const char *golden_path, const char *model,
                      uint64_t seed, long count, long timeout_ms, const char *tmp_dir, char **argv) {
    Profile prof;
    char out_path[PATH_MAX], err_path[PATH_MAX];
    size_t golden_len;
    char *golden = read_file(golden_path, &golden_len);
    int m_reg = strcmp(model, "reg") == 0, m_branch = strcmp(model, "branch") == 0;
    int m_jump = strcmp(model, "jump") == 0;
    long e;

    if (!golden)
        die("read golden output");
    if (!m_reg && !m_branch && !m_jump) {
        fprintf(stderr, "fi: unknown model %s\n", model);
        return 100;
    }
    load_profile(prof_path, &prof);
    if (mkdir(tmp_dir, 0755) < 0 && errno != EEXIST)
        die("mkdir tmp_dir");
    if (m_branch && prof.n_jcc == 0) {
        fprintf(stderr, "fi: no conditional jumps in the profile\n");
        return 100;
    }
    rng_state = seed;
    snprintf(out_path, sizeof(out_path), "%s/fi_%d.out", tmp_dir, (int)getpid());
    snprintf(err_path, sizeof(err_path), "%s/fi_%d.err", tmp_dir, (int)getpid());

    printf("id,model,pc_off,occurrence,target,bit,injected,outcome,exit,signal,time_us\n");
    for (e = 0; e < count; e++) {
        uint64_t occurrence = 0, hits = 0, start;
        size_t idx = pick_target(&prof, m_branch, &occurrence);
        const PcInfo *pi = &prof.pcs[idx];
        uint64_t pc = prof.text_lo + pi->off;
        int reg = (int)rng_below(16), bit = (int)rng_below(64);
        uint64_t jump_to = 0;
        int injected = 0, status = 0, timed_out = 0, sig = 0;
        long orig, patched;
        struct user_regs_struct regs;
        const char *outcome;
        char target[32];
        pid_t pid;

        if (m_jump) {
            size_t j = (size_t)rng_below(prof.npcs);
            if (j == idx)
                j = (j + 1) % prof.npcs;
            jump_to = prof.text_lo + prof.pcs[j].off;
            snprintf(target, sizeof(target), "%lx", (unsigned long)prof.pcs[j].off);
            bit = -1;
        } else if (m_branch) {
            snprintf(target, sizeof(target), "cc%x", pi->cc);
            bit = -1;
        } else {
            snprintf(target, sizeof(target), "%s", gpr_name[reg]);
        }

        start = now_us();
        pid = spawn(argv, out_path, err_path, 1);
        orig = ptrace(PTRACE_PEEKTEXT, pid, (void *)pc, NULL);
        patched = (orig & ~0xffL) | 0xcc;
        ptrace(PTRACE_POKETEXT, pid, (void *)pc, (void *)patched);
        for (;;) {
            if (ptrace(PTRACE_CONT, pid, NULL, (void *)(long)sig) < 0)
                die("PTRACE_CONT");
            sig = 0;
            if (waitpid(pid, &status, 0) < 0)
                die("waitpid");
            if (WIFEXITED(status) || WIFSIGNALED(status))
                break; /* target never reached */
            if (WSTOPSIG(status) != SIGTRAP) {
                sig = WSTOPSIG(status);
                continue;
            }
            ptrace(PTRACE_GETREGS, pid, NULL, &regs);
            if (regs.rip - 1 != pc) {
                sig = 0;
                continue;
            }
            ptrace(PTRACE_POKETEXT, pid, (void *)pc, (void *)orig);
            regs.rip = pc;
            if (hits == occurrence) {
                if (m_reg) {
                    *gpr(&regs, reg) ^= 1ull << bit;
                } else if (m_branch) {
                    uint64_t next = pc + (uint64_t)pi->len;
                    regs.rip = jcc_taken(pi->cc, regs.eflags) ? next : next + (uint64_t)pi->rel;
                } else {
                    regs.rip = jump_to;
                }
                ptrace(PTRACE_SETREGS, pid, NULL, &regs);
                ptrace(PTRACE_DETACH, pid, NULL, NULL);
                injected = 1;
                timed_out = wait_with_timeout(pid, &status, (uint64_t)timeout_ms * 1000u);
                break;
            }
            hits++;
            ptrace(PTRACE_SETREGS, pid, NULL, &regs);
            if (ptrace(PTRACE_SINGLESTEP, pid, NULL, NULL) < 0)
                die("PTRACE_SINGLESTEP");
            if (waitpid(pid, &status, 0) < 0)
                die("waitpid");
            if (WIFEXITED(status) || WIFSIGNALED(status))
                break;
            ptrace(PTRACE_POKETEXT, pid, (void *)pc, (void *)patched);
        }

        if (timed_out) {
            outcome = "hang";
        } else if (WIFSIGNALED(status)) {
            outcome = "crash";
        } else {
            size_t out_len, err_len;
            char *out = read_file(out_path, &out_len);
            char *err = read_file(err_path, &err_len);
            if (err && strstr(err, "FAULT_DETECTED: DataCorruption"))
                outcome = "detected_data";
            else if (err && strstr(err, "FAULT_DETECTED: SigMismatch"))
                outcome = "detected_cfc";
            else if (out && out_len == golden_len && memcmp(out, golden, golden_len) == 0 &&
                     WEXITSTATUS(status) == prof.exit_status)
                outcome = injected ? "masked" : "not_injected";
            else
                outcome = injected ? "sdc" : "not_injected";
            free(out);
            free(err);
        }
        printf("%ld,%s,%lx,%lu,%s,%d,%d,%s,%d,%d,%lu\n", e, model, (unsigned long)pi->off,
               (unsigned long)occurrence, target, bit, injected, outcome,
               (!timed_out && WIFEXITED(status)) ? WEXITSTATUS(status) : -1,
               (!timed_out && WIFSIGNALED(status)) ? WTERMSIG(status) : 0,
               (unsigned long)(now_us() - start));
        fflush(stdout);
    }
    unlink(out_path);
    unlink(err_path);
    free(golden);
    return 0;
}

static int cmp_u64(const void *a, const void *b) {
    uint64_t x = *(const uint64_t *)a, y = *(const uint64_t *)b;
    return (x > y) - (x < y);
}

static int cmd_bench(long runs, char **argv) {
    uint64_t *t = (uint64_t *)calloc((size_t)runs, sizeof(uint64_t));
    long i;
    for (i = 0; i < runs; i++) {
        int status;
        uint64_t start = now_us();
        pid_t pid = spawn(argv, "/dev/null", "/dev/null", 0);
        waitpid(pid, &status, 0);
        t[i] = now_us() - start;
    }
    qsort(t, (size_t)runs, sizeof(uint64_t), cmp_u64);
    printf("bench runs %ld min_us %lu median_us %lu\n", runs, (unsigned long)t[0],
           (unsigned long)t[runs / 2]);
    free(t);
    return 0;
}

static char **after_dashes(int argc, char **argv, int from) {
    int i;
    for (i = from; i < argc; i++)
        if (strcmp(argv[i], "--") == 0 && i + 1 < argc)
            return &argv[i + 1];
    fprintf(stderr, "fi: missing '-- <program>'\n");
    exit(100);
}

int main(int argc, char **argv) {
    if (argc >= 6 && strcmp(argv[1], "profile") == 0)
        return cmd_profile(argv[2], argv[3], after_dashes(argc, argv, 4));
    if (argc >= 11 && strcmp(argv[1], "inject") == 0)
        return cmd_inject(argv[2], argv[3], argv[4], strtoull(argv[5], NULL, 0),
                          strtol(argv[6], NULL, 0), strtol(argv[7], NULL, 0), argv[8],
                          after_dashes(argc, argv, 9));
    if (argc >= 5 && strcmp(argv[1], "bench") == 0)
        return cmd_bench(strtol(argv[2], NULL, 0), after_dashes(argc, argv, 3));
    fprintf(stderr,
            "usage:\n"
            "  fi profile <out.prof> <out.stdout> -- <program> [args]\n"
            "  fi inject <prof> <golden.stdout> reg|branch|jump <seed> <count> <timeout_ms> "
            "<tmp_dir> -- <program> [args]\n"
            "  fi bench <runs> -- <program> [args]\n");
    return 100;
}
