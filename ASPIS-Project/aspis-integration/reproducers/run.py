#!/usr/bin/env python3
"""Builds every reproducer with one or more ASPIS checkouts and reports what
happens, compared with the program compiled without ASPIS.

Usage:
    run.py --llvm-bin <dir> --aspis name=<ASPIS dir> [--aspis name=<dir> ...]
           [--out <build dir>] [--markdown <table.md>]
"""
import argparse
import os
import signal
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# reproducer -> aspis.sh options that expose the bug
CASES = [
    ("r01_string_param.c", "--eddi --no-cfc"),
    ("r02_linked_list.c", "--eddi --no-cfc"),
    ("r03_null_argument.c", "--eddi --no-cfc"),
    ("r04_qsort_callback.c", "--eddi --no-cfc"),
    ("r05_global_pointer_init.c", "--eddi --no-cfc"),
    ("r06_matrix_constant_index.c", "--eddi --no-cfc"),
    ("r07_memmove_heap.c", "--eddi --no-cfc"),
    ("r08_variadic.c", "--eddi --no-cfc"),
    ("r09_struct_by_value.c", "--eddi --no-cfc"),
    ("r10_vla.c", "--eddi --no-cfc"),
    ("r11_setjmp.c", "--no-dup --cfcss"),
    ("r12_reddi_return.c", "--reddi --no-cfc"),
    ("r13_two_calls.c", "--eddi --no-cfc"),
    ("r14_inter_rasm_callback.c", "--no-dup --inter-rasm"),
]


def run(cmd, cwd=None, timeout=60):
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err, False
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
        return None, out, err, True


def outcome(aspis, llvm_bin, src, flags, bdir, golden):
    os.makedirs(bdir, exist_ok=True)
    cmd = [os.path.join(aspis, "aspis.sh"), "--llvm-bin", llvm_bin] + flags.split() + \
        [src, "-o", "prog", "--build-dir", bdir]
    rc, out, err, hung = run(cmd, cwd=bdir, timeout=60)
    if hung:
        return "compiler hangs"
    if rc != 0:
        text = (err + out).decode(errors="replace")
        if "does not dominate" in text:
            return "broken module (dominance)"
        if "does not match function signature" in text:
            return "broken module (call signature)"
        if "Broken module" in text:
            return "broken module"
        return "compiler crash"
    rc, out, err, hung = run([os.path.join(bdir, "prog")], timeout=10)
    if hung:
        return "hang"
    if rc < 0:
        return "crash (%s)" % signal.Signals(-rc).name
    if b"DataCorruption" in err:
        return "false DataCorruption"
    if b"SigMismatch" in err:
        return "false SigMismatch"
    if (rc, out) != golden:
        return "wrong output"
    return "ok"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llvm-bin", required=True)
    ap.add_argument("--aspis", action="append", required=True, help="name=path")
    ap.add_argument("--out", default="reproducers-build")
    ap.add_argument("--markdown", default=None)
    args = ap.parse_args()
    out = os.path.abspath(args.out)
    checkouts = [a.split("=", 1) for a in args.aspis]
    rows = []
    for src, flags in CASES:
        path = os.path.join(HERE, src)
        gdir = os.path.join(out, "native", src[:-2])
        os.makedirs(gdir, exist_ok=True)
        rc, _, err, _ = run([os.path.join(args.llvm_bin, "clang"), path, "-o", os.path.join(gdir, "prog")])
        if rc != 0:
            sys.exit("cannot compile %s: %s" % (src, err.decode()))
        rc, gout, _, _ = run([os.path.join(gdir, "prog")])
        golden = (rc, gout)
        res = [outcome(os.path.abspath(p), args.llvm_bin, path, flags,
                       os.path.join(out, name, src[:-2]), golden) for name, p in checkouts]
        rows.append((src, flags, res))
        print("%-30s %-24s %s" % (src, flags, " | ".join(res)), flush=True)
    if args.markdown:
        with open(args.markdown, "w") as f:
            f.write("| reproducer | options | %s |\n" % " | ".join(n for n, _ in checkouts))
            f.write("|---|---|%s\n" % ("---|" * len(checkouts)))
            for src, flags, res in rows:
                f.write("| `%s` | `%s` | %s |\n" % (src, flags, " | ".join(res)))


if __name__ == "__main__":
    main()
