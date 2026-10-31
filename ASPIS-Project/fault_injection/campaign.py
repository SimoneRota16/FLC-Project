#!/usr/bin/env python3
"""Fault-injection campaign for the applications hardened with ASPIS.

For every application and every hardening configuration of the campaign file:
  1. compiles the application with aspis.sh                (<work>/build/<app>/<config>/)
  2. records the size of .text and the number of checks inserted by EDDI
  3. golden run: the reference output and, with valgrind (callgrind), how many
     times every instruction of the program is executed
  4. runs the experiments: each one picks at random one execution of one
     instruction (for inverted branches: of a conditional jump) and injects
     the fault there with gdb (gdb_inject.py)
  5. writes metrics.csv, outcomes.csv and raw.csv.gz in the results directory

Every step is cached in the work directory: if the campaign is interrupted,
running the script again only does what is missing.

Usage:
    campaign.py <campaign.toml> [--jobs N]

Part of the FLC 2026/27 project "Harden a C application with ASPIS".
Copyright (c) 2026 Alberto Rotolo, Simone Rota. SPDX-License-Identifier: MIT
"""
import argparse
import csv
import gzip
import hashlib
import os
import random
import re
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor

OUTCOMES = ["masked", "sdc", "detected_data", "detected_cfc", "crash", "hang", "not_injected"]
REGISTERS = ["rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rbp", "rsp",
             "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15"]
GDB = ["gdb", "-batch", "-nx", "-iex", "set debuginfod enabled off",
       "-x", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gdb_inject.py"), "--args"]
FIELDS = ["application", "config", "model", "id", "address", "occurrence", "target", "bit",
          "outcome", "exit", "signal", "time_ms"]


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def build(cfg, app, conf, paths):
    """Compiles app with the flags of conf; returns the directory of the build."""
    bdir = os.path.join(paths["work"], "build", app["name"], conf["name"])
    meta = os.path.join(bdir, "build.txt")
    if os.path.exists(meta):
        return bdir
    os.makedirs(bdir, exist_ok=True)
    cmd = [os.path.join(paths["aspis"], "aspis.sh"), "--llvm-bin", paths["llvm_bin"]]
    cmd += conf["flags"].split() + app.get("flags", "").split()
    cmd += [os.path.join(cfg["root"], app["source"]), "-o", "prog", "--build-dir", bdir]
    # run inside the build directory: EDDI writes the list of the functions it
    # compiled in the working directory, so parallel builds must not share it
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=bdir)
    with open(os.path.join(bdir, "aspis.log"), "w") as f:
        f.write(res.stdout + res.stderr)
    if res.returncode != 0 or not os.path.exists(os.path.join(bdir, "prog")):
        raise RuntimeError("build failed: %s/%s (see %s/aspis.log)" % (app["name"], conf["name"], bdir))
    size = subprocess.run([os.path.join(paths["llvm_bin"], "llvm-size"), "-A", os.path.join(bdir, "prog")],
                          capture_output=True, text=True).stdout
    text = [line.split()[1] for line in size.splitlines() if line.startswith(".text ")]
    checks = re.search(r"Comparison Counter:\s*(\d+)", res.stdout)
    with open(meta, "w") as f:
        f.write("text_bytes %s\ncomparisons %s\n" % (text[0], checks.group(1) if checks else "0"))
    return bdir


def golden(bdir):
    """Reference output and run time; profile of the executed instructions:
    {address: (executions, is a conditional jump)}."""
    prog, prof = os.path.join(bdir, "prog"), os.path.join(bdir, "profile.csv")
    times = []
    for _ in range(5):
        start = time.perf_counter()
        res = subprocess.run([prog], capture_output=True)
        times.append((time.perf_counter() - start) * 1000)
    if res.returncode != 0:
        raise RuntimeError("%s fails without faults" % prog)
    if not os.path.exists(prof):
        cg = os.path.join(bdir, "callgrind.out")
        subprocess.run(["valgrind", "--tool=callgrind", "--dump-instr=yes", "--dump-line=no",
                        "--compress-pos=no", "--compress-strings=no", "--callgrind-out-file=" + cg, prog],
                       capture_output=True, check=True)
        counts, obj, skip = {}, None, False
        for line in open(cg):
            if line.startswith("ob="):
                obj = line[3:].strip()
            elif line.startswith("calls="):
                skip = True              # the next line is the cost of a call, not of an instruction
            elif line.startswith("0x"):
                if not skip and obj == prog:
                    addr, n = line.split()
                    counts[int(addr, 16)] = counts.get(int(addr, 16), 0) + int(n)
                skip = False
        dis = subprocess.run(["objdump", "-d", "--no-show-raw-insn", prog], capture_output=True, text=True).stdout
        jcc = {int(m.group(1), 16) for m in re.finditer(r"^\s*([0-9a-f]+):\s+j(?!mp)[a-z]+\s", dis, re.M)}
        with open(prof + ".part", "w") as f:
            f.write("address,executions,jcc\n")
            for a in sorted(counts):
                f.write("%x,%d,%d\n" % (a, counts[a], a in jcc))
        os.replace(prof + ".part", prof)
    profile = {int(r["address"], 16): (int(r["executions"]), r["jcc"] == "1") for r in csv.DictReader(open(prof))}
    return res.stdout, min(times), profile


def seed_of(*parts):
    return int(hashlib.sha256("/".join(parts).encode()).hexdigest()[:15], 16)


def experiment(prog, ref, timeout_ms, tmp, exp):
    """Runs one experiment with gdb and classifies its outcome."""
    out, err = (os.path.join(tmp, "%d_%s" % (exp["id"], s)) for s in ("out", "err"))
    env = dict(os.environ, FI_ADDR="%x" % exp["address"], FI_K=str(exp["occurrence"]),
               FI_MODEL=exp["model"], FI_REG=exp["target"], FI_BIT=str(exp["bit"]),
               FI_OUT=out, FI_ERR=err, FI_TIMEOUT_MS=str(timeout_ms))
    start = time.perf_counter()
    res = subprocess.run(GDB + [prog], env=env, capture_output=True, text=True, timeout=600)
    found = re.search(r"^FI-RESULT (\d) (-?\d+) (\S+)$", res.stdout, re.M)
    if not found:
        raise RuntimeError("gdb failed on %s: %s" % (prog, res.stderr[-500:]))
    injected, code, sig = int(found.group(1)), int(found.group(2)), found.group(3)
    stdout, stderr = open(out, "rb").read(), open(err, "rb").read()
    os.remove(out)
    os.remove(err)
    if not injected:
        outcome = "not_injected"
    elif sig == "SIGKILL":                  # killed by the watchdog of gdb_inject.py
        outcome = "hang"
    elif sig != "-":
        outcome = "crash"
    elif b"FAULT_DETECTED: DataCorruption" in stderr:
        outcome = "detected_data"
    elif b"FAULT_DETECTED: SigMismatch" in stderr:
        outcome = "detected_cfc"
    elif code == 0 and stdout == ref:
        outcome = "masked"
    else:
        outcome = "sdc"
    return dict(exp, address="%x" % exp["address"], outcome=outcome, exit=code, signal=sig,
                time_ms=round((time.perf_counter() - start) * 1000))


def wilson(k, n, z=1.96):
    """95% Wilson score interval of a binomial proportion."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("campaign")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 1)
    args = ap.parse_args()

    with open(args.campaign, "rb") as f:
        cfg = tomllib.load(f)
    camp, here = cfg["campaign"], os.path.dirname(os.path.abspath(args.campaign))
    path = lambda p: os.path.join(here, os.path.expanduser(p))
    cfg["root"] = path(camp.get("root", "."))
    paths = {name: path(camp[name]) for name in ("work", "results", "aspis", "llvm_bin", "tmp")}
    for d in (paths["work"], paths["results"], paths["tmp"], os.path.join(paths["work"], "raw")):
        os.makedirs(d, exist_ok=True)
    apps, confs, models = cfg["application"], cfg["config"], camp["models"]
    pairs = [(a, c) for a in apps for c in confs]

    log("building %d applications x %d configurations" % (len(apps), len(confs)))
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        bdirs = dict(zip([(a["name"], c["name"]) for a, c in pairs],
                         ex.map(lambda p: build(cfg, p[0], p[1], paths), pairs)))
    log("golden runs")
    gold = {key: golden(bdirs[key]) for key in bdirs}
    for a in apps:          # the hardened programs must print exactly what the unprotected one prints
        for c in confs:
            if gold[(a["name"], c["name"])][0] != gold[(a["name"], confs[0]["name"])][0]:
                raise RuntimeError("golden output of %s/%s differs" % (a["name"], c["name"]))

    with open(os.path.join(paths["results"], "metrics.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["application", "config", "text_bytes", "comparisons", "executed_instructions"])
        for (a, c), bdir in bdirs.items():
            meta = dict(line.split() for line in open(os.path.join(bdir, "build.txt")))
            w.writerow([a, c, meta["text_bytes"], meta["comparisons"],
                        sum(n for n, _ in gold[(a, c)][2].values())])

    n_inj = int(camp["injections"])
    for (a, c), bdir in bdirs.items():
        ref, run_ms, profile = gold[(a, c)]
        # after the fault, a run is a hang if it lasts 20 times the normal run time (at least 1 s)
        timeout_ms = max(int(camp.get("timeout_min_ms", 1000)), int(run_ms * camp.get("timeout_factor", 20)))
        for m in models:
            raw = os.path.join(paths["work"], "raw", "%s__%s__%s.csv" % (a, c, m))
            if os.path.exists(raw):
                continue
            # a random execution of a random instruction: an instruction is picked with a
            # probability proportional to its executions, then one of its executions
            rng = random.Random(seed_of(str(camp.get("seed", 1)), a, c, m))
            sites = [addr for addr, (n, jcc) in profile.items() if m == "reg" or jcc]
            weights = [profile[addr][0] for addr in sites]
            exps = []
            for i in range(n_inj):
                addr = rng.choices(sites, weights)[0]
                exps.append({"application": a, "config": c, "model": m, "id": i, "address": addr,
                             "occurrence": rng.randint(1, profile[addr][0]),
                             "target": rng.choice(REGISTERS) if m == "reg" else "-",
                             "bit": rng.randrange(64) if m == "reg" else -1})
            log("%s %s %s: %d experiments" % (a, c, m, n_inj))
            tmp = os.path.join(paths["tmp"], "%s_%s_%s" % (a, c, m))
            os.makedirs(tmp, exist_ok=True)
            with ThreadPoolExecutor(max_workers=args.jobs) as ex:
                rows = list(ex.map(lambda e: experiment(os.path.join(bdir, "prog"), ref, timeout_ms, tmp, e), exps))
            with open(raw + ".part", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=FIELDS)
                w.writeheader()
                w.writerows(rows)
            os.replace(raw + ".part", raw)

    counts, n_rows = {}, 0
    with gzip.open(os.path.join(paths["results"], "raw.csv.gz"), "wt", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for a, c in pairs:
            for m in models:
                acc = counts.setdefault((a["name"], c["name"], m), dict.fromkeys(OUTCOMES, 0))
                for r in csv.DictReader(open(os.path.join(paths["work"], "raw", "%s__%s__%s.csv" % (
                        a["name"], c["name"], m)))):
                    acc[r["outcome"]] += 1
                    w.writerow(r)
                    n_rows += 1
    with open(os.path.join(paths["results"], "outcomes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["application", "config", "model", "n"] + OUTCOMES + ["sdc_rate", "sdc_lo", "sdc_hi"])
        for (a, c, m), acc in sorted(counts.items()):
            n = sum(acc[o] for o in OUTCOMES if o != "not_injected")
            lo, hi = wilson(acc["sdc"], n)
            w.writerow([a, c, m, n] + [acc[o] for o in OUTCOMES] +
                       ["%.5f" % (acc["sdc"] / n if n else 0), "%.5f" % lo, "%.5f" % hi])
    log("%d experiments; results in %s" % (n_rows, paths["results"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
