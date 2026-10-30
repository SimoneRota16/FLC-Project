#!/usr/bin/env python3
"""Fault-injection campaign driver for ASPIS-hardened applications.

For every application and every hardening configuration listed in the
campaign file the driver:
  1. compiles the application with aspis.sh         (build/<app>/<config>/)
  2. records the size of .text and the number of consistency checks
  3. profiles the golden run with `fi profile`      (executed instructions)
  4. runs the fault-injection experiments with `fi inject`, in parallel
     chunks of `chunk` experiments, each with its own seed
  5. writes metrics.csv (cost) and outcomes.csv (outcome of the faults)

Every step is cached in the output directory: if the campaign is interrupted,
running the script again only does what is missing.

Usage:
    campaign.py <campaign.toml> [--jobs N]
"""
import argparse
import csv
import hashlib
import os
import re
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor

OUTCOMES = ["masked", "sdc", "detected_data", "detected_cfc", "crash", "hang", "not_injected"]


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


def text_size(binary, llvm_bin):
    out = subprocess.run([os.path.join(llvm_bin, "llvm-size"), "-A", binary],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0] == ".text":
            return int(parts[1])
    return -1


def build(cfg, app, conf, paths):
    """Compiles app with the flags of conf; returns the path of the binary."""
    bdir = os.path.join(paths["build"], app["name"], conf["name"])
    binary = os.path.join(bdir, "prog")
    meta = os.path.join(bdir, "build.txt")
    if os.path.exists(binary) and os.path.exists(meta):
        return binary
    os.makedirs(bdir, exist_ok=True)
    cmd = [os.path.join(paths["aspis"], "aspis.sh"), "--llvm-bin", paths["llvm_bin"]]
    cmd += conf["flags"].split() + app.get("flags", "").split()
    cmd += [os.path.join(cfg["root"], app["source"]), "-o", "prog", "--build-dir", bdir]
    # aspis.sh is run inside the build directory: EDDI writes the list of the
    # functions it compiled in the working directory, so parallel builds must
    # not share it
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=bdir)
    with open(os.path.join(bdir, "aspis.log"), "w") as f:
        f.write(res.stdout + res.stderr)
    if res.returncode != 0 or not os.path.exists(binary):
        raise RuntimeError("build failed: %s/%s (see %s/aspis.log)" % (app["name"], conf["name"], bdir))
    m = re.search(r"Comparison Counter:\s*(\d+)", res.stdout)
    with open(meta, "w") as f:
        f.write("text_bytes %d\n" % text_size(binary, paths["llvm_bin"]))
        f.write("comparisons %s\n" % (m.group(1) if m else "0"))
    return binary


def profile(binary, fi):
    """Golden run: profile of the executed instructions and reference output."""
    bdir = os.path.dirname(binary)
    prof, golden = os.path.join(bdir, "golden.prof"), os.path.join(bdir, "golden.stdout")
    if not os.path.exists(prof):
        # written to a temporary file and renamed at the end, so that an
        # interrupted campaign never finds a truncated profile
        res = subprocess.run([fi, "profile", prof + ".part", golden, "--", binary],
                             capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError("profiling failed for %s: %s" % (binary, res.stderr))
        os.replace(prof + ".part", prof)
    return prof, golden


def executed_instructions(prof):
    with open(prof) as f:
        f.readline()
        f.readline()
        return int(f.readline().split()[1])  # "dynamic <app> <total>"


def run_time_ms(binary, runs=5):
    """Shortest wall-clock time of a few runs, to choose the hang timeout."""
    best = None
    for _ in range(runs):
        start = time.perf_counter()
        subprocess.run([binary], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elapsed = (time.perf_counter() - start) * 1000
        best = elapsed if best is None else min(best, elapsed)
    return best


def seed_of(*parts):
    return int(hashlib.sha256("/".join(parts).encode()).hexdigest()[:15], 16)


def inject_chunk(fi, tmp, binary, prof, golden, model, seed, count, timeout_ms, out_csv):
    if os.path.exists(out_csv):
        return
    res = subprocess.run([fi, "inject", prof, golden, model, str(seed), str(count), str(timeout_ms),
                          os.path.join(tmp, "w%x" % (seed & 0xffffff)), "--", binary],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("injection failed (%s): %s" % (out_csv, res.stderr[-500:]))
    with open(out_csv + ".part", "w") as f:
        f.write(res.stdout)
    os.replace(out_csv + ".part", out_csv)


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
    camp = cfg["campaign"]
    cfg["root"] = os.path.abspath(os.path.join(os.path.dirname(args.campaign), camp.get("root", ".")))
    out = os.path.abspath(os.path.expanduser(camp["output"]))
    paths = {name: os.path.abspath(os.path.expanduser(camp[name])) for name in ("aspis", "llvm_bin", "fi")}
    paths["build"], raw = os.path.join(out, "build"), os.path.join(out, "raw")
    tmp = camp.get("tmp", "/dev/shm/aspis-fi")
    for d in (paths["build"], raw, tmp):
        os.makedirs(d, exist_ok=True)
    apps, confs, models = cfg["application"], cfg["config"], camp["models"]
    n_inj, chunk = int(camp["injections"]), int(camp.get("chunk", 100))
    pairs = [(a, c) for a in apps for c in confs]

    log("building %d applications x %d configurations" % (len(apps), len(confs)))
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        binaries = dict(zip([(a["name"], c["name"]) for a, c in pairs],
                            ex.map(lambda p: build(cfg, p[0], p[1], paths), pairs)))

    log("golden runs")
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        profiles = dict(zip(binaries, ex.map(lambda k: profile(binaries[k], paths["fi"]), binaries)))
    # the hardened programs must print exactly what the unprotected one prints
    base = confs[0]["name"]
    for a in apps:
        ref = open(profiles[(a["name"], base)][1], "rb").read()
        for c in confs:
            if open(profiles[(a["name"], c["name"])][1], "rb").read() != ref:
                raise RuntimeError("golden output of %s/%s differs from %s" % (a["name"], c["name"], base))

    metrics = []
    for a, c in pairs:
        key = (a["name"], c["name"])
        meta = dict(line.split() for line in open(os.path.join(os.path.dirname(binaries[key]), "build.txt")))
        metrics.append({"application": a["name"], "config": c["name"], "text_bytes": meta["text_bytes"],
                        "comparisons": meta["comparisons"],
                        "executed_instructions": executed_instructions(profiles[key][0])})
    with open(os.path.join(out, "metrics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(metrics[0].keys()))
        w.writeheader()
        w.writerows(metrics)

    tasks = []
    for a, c in pairs:
        key = (a["name"], c["name"])
        # a run is a hang if it lasts 20 times the normal run time (at least 300 ms)
        timeout_ms = max(int(camp.get("timeout_min_ms", 300)),
                         int(run_time_ms(binaries[key]) * camp.get("timeout_factor", 20)))
        for m in models:
            for k in range(0, n_inj, chunk):
                seed = seed_of(str(camp.get("seed", 1)), a["name"], c["name"], m, str(k))
                csv_path = os.path.join(raw, "%s__%s__%s__%05d.csv" % (a["name"], c["name"], m, k))
                tasks.append((binaries[key], *profiles[key], m, seed, min(chunk, n_inj - k), timeout_ms, csv_path))
    log("running %d experiments in %d chunks" % (sum(t[5] for t in tasks), len(tasks)))
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for i, _ in enumerate(ex.map(lambda t: inject_chunk(paths["fi"], tmp, *t), tasks), 1):
            if i % 40 == 0 or i == len(tasks):
                log("  %d/%d chunks done" % (i, len(tasks)))

    counts = {}
    for t in tasks:
        key = tuple(os.path.basename(t[-1]).split("__")[:3])
        acc = counts.setdefault(key, dict.fromkeys(OUTCOMES, 0))
        with open(t[-1]) as f:
            for r in csv.DictReader(f):
                acc[r["outcome"]] += 1
    with open(os.path.join(out, "outcomes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["application", "config", "model", "n"] + OUTCOMES + ["sdc_rate", "sdc_lo", "sdc_hi"])
        for (a, c, m), acc in sorted(counts.items()):
            n = sum(acc[o] for o in OUTCOMES if o != "not_injected")
            lo, hi = wilson(acc["sdc"], n)
            w.writerow([a, c, m, n] + [acc[o] for o in OUTCOMES] +
                       ["%.5f" % (acc["sdc"] / n if n else 0), "%.5f" % lo, "%.5f" % hi])
    log("results in %s (metrics.csv, outcomes.csv, raw/)" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
