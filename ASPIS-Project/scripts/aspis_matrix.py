#!/usr/bin/env python3
"""Fast compatibility matrix of ASPIS on a set of programs.

Same combinations as the official harness (testing/test.py: 11 data
protection x 5 control-flow checking techniques), but every compilation and
every run is executed in its own process group with a hard wall-clock limit,
so that an `opt` process stuck in an infinite loop is really killed (the
pytest-timeout plugin only stops the Python test, the compiler keeps
running). Failures are classified, which makes it a convenient tool while
fixing ASPIS:

    pass          output identical to the unhardened build
    compile-error aspis.sh failed (first meaningful error line reported)
    compile-hang  aspis.sh did not finish within --compile-timeout
    crash         the hardened program was killed by a signal
    false-detect  the fault handler was called in a fault-free run
    exit-code     different exit status
    mismatch      different standard output
    run-hang      the hardened program did not finish within --run-timeout

Usage:
    aspis_matrix.py --aspis <ASPIS dir> --llvm-bin <dir> --tests <toml>
                    [--tests-root <dir>] [--jobs N] [--only a,b] [--out <dir>]
                    [--data "--eddi,--fdsc"] [--cfc "--no-cfc,--rasm"]
"""
import argparse
import csv
import glob
import os
import signal
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = ["--no-dup", "--eddi", "--eddi --multiple-errbb", "--eddi --coarse-grained",
        "--eddi --multiple-errbb --coarse-grained", "--reddi", "--reddi --multiple-errbb",
        "--reddi --coarse-grained", "--reddi --multiple-errbb --coarse-grained", "--seddi", "--fdsc"]
CFC = ["--no-cfc", "--cfcss", "--rasm", "--racfed", "--inter-rasm"]


def run(cmd, cwd=None, timeout=60, env=None):
    """Runs cmd in a new session; on timeout the whole process group is killed."""
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         start_new_session=True, env=env)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err, False
    except subprocess.TimeoutExpired:
        os.killpg(p.pid, signal.SIGKILL)
        out, err = p.communicate()
        return None, out, err, True


def first_error(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for key in ("Assertion", "error:", "ERROR", "does not match", "Stack dump", "Warning"):
        for l in lines:
            if key in l:
                return l[:200]
    return lines[-1][:200] if lines else ""


def golden(srcs, flags, llvm_bin, bdir):
    os.makedirs(bdir, exist_ok=True)
    exe = os.path.join(bdir, "golden")
    compiler = "clang++" if any(s.endswith(".cpp") for s in srcs) else "clang"
    rc, out, err, _ = run([os.path.join(llvm_bin, compiler)] + srcs + ["-o", exe] + flags.split() + ["-lm"], timeout=120)
    if rc != 0:
        raise RuntimeError("cannot compile %s: %s" % (srcs, err.decode()[-400:]))
    rc, out, err, hung = run([exe], timeout=30)
    return rc, out


def one(test, srcs, data, cfc, args, gold):
    combo = (data + " " + cfc).replace("--", "").replace(" ", "_")
    bdir = os.path.join(args.out, "build", test, combo)
    os.makedirs(bdir, exist_ok=True)
    cmd = [os.path.join(args.aspis, "aspis.sh"), "--llvm-bin", args.llvm_bin] + data.split() + \
        cfc.split() + args.extra.split() + test_flags[test].split() + srcs + ["-o", "prog", "--build-dir", bdir]
    t0 = time.time()
    # aspis.sh is run inside the build directory: EDDI writes the list of the
    # compiled functions (compiled_eddi_functions.csv) in the working
    # directory and DuplicateGlobals reads it back, so parallel builds sharing
    # the same directory would read each other's list.
    rc, out, err, hung = run(cmd, cwd=bdir, timeout=args.compile_timeout)
    ctime = time.time() - t0
    with open(os.path.join(bdir, "aspis.log"), "wb") as f:
        f.write(out + b"\n----- stderr -----\n" + err)
    res = {"test": test, "data": data, "cfc": cfc, "compile_s": "%.1f" % ctime, "detail": ""}
    if hung:
        res["outcome"] = "compile-hang"
        return res
    if rc != 0 or not os.path.exists(os.path.join(bdir, "prog")):
        res["outcome"] = "compile-error"
        res["detail"] = first_error(err.decode(errors="replace") + out.decode(errors="replace"))
        return res
    rc, out, err, hung = run([os.path.join(bdir, "prog")], timeout=args.run_timeout)
    with open(os.path.join(bdir, "run.stderr"), "wb") as f:
        f.write(err)
    grc, gout = gold
    if hung:
        res["outcome"] = "run-hang"
    elif rc < 0:
        res["outcome"] = "crash"
        res["detail"] = signal.Signals(-rc).name
    elif b"FAULT_DETECTED" in err:
        res["outcome"] = "false-detect"
        res["detail"] = err.decode(errors="replace").strip().splitlines()[-1][:120]
    elif out.strip() != gout.strip():  # the official harness compares stripped outputs
        res["outcome"] = "mismatch"
        with open(os.path.join(bdir, "run.stdout"), "wb") as f:
            f.write(out)
    elif rc != grc:
        res["outcome"] = "exit-code"
        res["detail"] = "%d vs %d" % (rc, grc)
    else:
        res["outcome"] = "pass"
    if res["outcome"] == "pass" and not args.keep:
        for name in os.listdir(bdir):
            if name.endswith(".ll"):
                os.remove(os.path.join(bdir, name))
    return res


test_flags = {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aspis", required=True)
    ap.add_argument("--llvm-bin", required=True)
    ap.add_argument("--tests", required=True)
    ap.add_argument("--tests-root", default=None, help="default: <ASPIS>/testing/tests")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--only", default="")
    ap.add_argument("--data", default=",".join(DATA))
    ap.add_argument("--cfc", default=",".join(CFC))
    ap.add_argument("--extra", default="", help="extra aspis.sh options for every build")
    ap.add_argument("--out", default="matrix-results")
    ap.add_argument("--compile-timeout", type=int, default=180)
    ap.add_argument("--run-timeout", type=int, default=20)
    ap.add_argument("--keep", action="store_true", help="keep the .ll files of passing builds")
    args = ap.parse_args()
    args.aspis = os.path.abspath(args.aspis)
    args.out = os.path.abspath(args.out)
    root = os.path.abspath(args.tests_root or os.path.join(args.aspis, "testing", "tests"))
    with open(args.tests, "rb") as f:
        entries = tomllib.load(f)["tests"]
    if args.only:
        wanted = set(args.only.split(","))
        entries = [e for e in entries if e["test_name"] in wanted]
    datas = [d for d in args.data.split(",") if d]
    cfcs = [c for c in args.cfc.split(",") if c]

    golds, jobs = {}, []
    for e in entries:
        name = e["test_name"]
        # source_file may be a shell pattern (e.g. cpp/complex/*.cpp)
        srcs = sorted(glob.glob(os.path.join(root, e["source_file"])))
        test_flags[name] = e.get("add_compiler_flags", "")
        try:
            golds[name] = golden(srcs, test_flags[name], args.llvm_bin, os.path.join(args.out, "build", name))
        except RuntimeError as exc:
            # e.g. a test that the host C++ library cannot compile at all
            print("skipping %s: %s" % (name, str(exc).splitlines()[0][:200]), flush=True)
            golds[name] = None
        for d in datas:
            for c in cfcs:
                skipped = golds[name] is None or any(x in e.get("black_list", []) for x in (d, c))
                jobs.append((name, srcs, d, c, skipped))
    print("%d builds (%d tests), %d workers" % (len(jobs), len(entries), args.jobs), flush=True)
    rows, t0 = [], time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = []
        for name, srcs, d, c, skipped in jobs:
            if skipped:
                rows.append({"test": name, "data": d, "cfc": c, "outcome": "skipped", "compile_s": "0", "detail": ""})
            else:
                futs.append(ex.submit(one, name, srcs, d, c, args, golds[name]))
        for i, fut in enumerate(as_completed(futs), 1):
            rows.append(fut.result())
            if i % 25 == 0 or i == len(futs):
                print("  %d/%d (%.0f s)" % (i, len(futs), time.time() - t0), flush=True)

    order = {(e["test_name"]): k for k, e in enumerate(entries)}
    rows.sort(key=lambda r: (order[r["test"]], datas.index(r["data"]), cfcs.index(r["cfc"])))
    with open(os.path.join(args.out, "matrix.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["test", "data", "cfc", "outcome", "compile_s", "detail"])
        w.writeheader()
        w.writerows(rows)
    sym = {"pass": ".", "compile-error": "E", "compile-hang": "H", "crash": "C", "false-detect": "D",
           "mismatch": "M", "exit-code": "X", "run-hang": "T", "skipped": "s"}
    with open(os.path.join(args.out, "matrix.md"), "w") as f:
        f.write("Legend: " + ", ".join("`%s` %s" % (v, k) for k, v in sym.items()) + "\n\n")
        f.write("Columns: data technique; each cell lists the CFC techniques in the order %s\n\n" %
                " ".join(c.replace("--", "") for c in cfcs))
        f.write("| test | " + " | ".join(d.replace("--", "").replace(" ", "+") for d in datas) + " |\n")
        f.write("|---" * (len(datas) + 1) + "|\n")
        by = {(r["test"], r["data"], r["cfc"]): r for r in rows}
        for e in entries:
            n = e["test_name"]
            cells = ["".join(sym[by[(n, d, c)]["outcome"]] for c in cfcs) for d in datas]
            f.write("| %s | %s |\n" % (n, " | ".join("`%s`" % c for c in cells)))
        f.write("\n## Failures\n\n")
        for r in rows:
            if r["outcome"] not in ("pass", "skipped"):
                f.write("- %s %s %s: **%s** %s\n" % (r["test"], r["data"], r["cfc"], r["outcome"], r["detail"]))
    tot = {}
    for r in rows:
        tot[r["outcome"]] = tot.get(r["outcome"], 0) + 1
    print("summary:", ", ".join("%s=%d" % kv for kv in sorted(tot.items())))
    print("results in", args.out)
    return 0 if set(tot) <= {"pass", "skipped"} else 1


if __name__ == "__main__":
    sys.exit(main())
