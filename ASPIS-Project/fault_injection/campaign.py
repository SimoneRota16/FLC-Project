#!/usr/bin/env python3
"""Fault-injection campaign driver for ASPIS-hardened benchmarks.

For every benchmark and every hardening configuration listed in the campaign
file the driver:
  1. compiles the benchmark with aspis.sh            (build/<bench>/<config>/)
  2. records static metrics (.text size, compile time, EDDI comparison count)
  3. profiles the golden run with `fi profile`       (dynamic instruction mix)
  4. measures the native run time with `fi bench`
  5. runs the fault injection experiments with `fi inject`, in parallel
     chunks, every process pinned to its own CPU (ptrace on WSL2/VMs is much
     faster when tracer and tracee share a core)
  6. aggregates the outcomes into results/*.csv

Every step is cached: re-running the script only does what is missing, so a
campaign can be extended (more injections, new configurations) incrementally.

Usage:
    campaign.py <campaign.toml> [--jobs N] [--only-build] [--skip-inject]
"""
import argparse
import csv
import hashlib
import os
import queue
import re
import shutil
import subprocess
import sys
import time
import tomllib
from concurrent.futures import ThreadPoolExecutor, as_completed

OUTCOMES = ["masked", "sdc", "detected_data", "detected_cfc", "crash", "hang", "not_injected"]


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


class CpuPool:
    """Hands out CPU ids so that every concurrent task runs on its own core."""

    def __init__(self, jobs):
        ncpu = os.cpu_count() or 1
        self.q = queue.Queue()
        for i in range(jobs):
            self.q.put(i % ncpu)

    def run(self, cmd, **kw):
        cpu = self.q.get()
        try:
            return subprocess.run(["taskset", "-c", str(cpu)] + cmd, **kw)
        finally:
            self.q.put(cpu)


def text_size(binary, llvm_bin):
    out = subprocess.run([os.path.join(llvm_bin, "llvm-size"), "-A", binary],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if parts and parts[0] == ".text":
            return int(parts[1])
    return -1


def build(cfg, bench, conf, paths):
    bdir = os.path.join(paths["build"], bench["name"], conf["name"])
    binary = os.path.join(bdir, "prog")
    meta = os.path.join(bdir, "build.txt")
    src = os.path.join(cfg["root"], bench["source"])
    if os.path.exists(binary) and os.path.exists(meta) and \
            os.path.getmtime(meta) >= os.path.getmtime(src):
        return binary
    os.makedirs(bdir, exist_ok=True)
    cmd = [os.path.join(paths["aspis"], "aspis.sh"), "--llvm-bin", paths["llvm_bin"]]
    cmd += conf["flags"].split() + bench.get("flags", "").split()
    cmd += [src, "-o", "prog", "--build-dir", bdir]
    start = time.time()
    # run inside the build directory: EDDI writes compiled_eddi_functions.csv in
    # the working directory and DuplicateGlobals reads it back, so parallel
    # builds must not share it
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=bdir)
    elapsed = time.time() - start
    with open(os.path.join(bdir, "aspis.log"), "w") as f:
        f.write(res.stdout + res.stderr)
    if res.returncode != 0 or not os.path.exists(binary):
        raise RuntimeError("build failed: %s/%s (see %s/aspis.log)" % (bench["name"], conf["name"], bdir))
    m = re.search(r"Comparison Counter:\s*(\d+)", res.stdout)
    with open(meta, "w") as f:
        f.write("compile_s %.3f\n" % elapsed)
        f.write("text_bytes %d\n" % text_size(binary, paths["llvm_bin"]))
        f.write("comparisons %s\n" % (m.group(1) if m else "0"))
    return binary


def read_kv(path):
    kv = {}
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                kv[parts[0]] = parts[1]
    return kv


def valid_profile(path):
    """True if path is a complete profile written by `fi profile`."""
    try:
        with open(path) as f:
            lines = f.read().split("\n")
        return lines[0] == "fi-profile 1" and len(lines) >= 6 + int(lines[4].split()[1])
    except (OSError, IndexError, ValueError):
        return False


def profile(pool, binary, paths):
    bdir = os.path.dirname(binary)
    prof, golden = os.path.join(bdir, "golden.prof"), os.path.join(bdir, "golden.stdout")
    bench_path = os.path.join(bdir, "bench.txt")
    if valid_profile(prof) and os.path.getmtime(prof) >= os.path.getmtime(binary) and \
            os.path.exists(bench_path):
        return prof, golden
    # the profile is written to a temporary file and renamed at the end, so
    # that an interrupted campaign never finds a truncated profile
    res = pool.run([paths["fi"], "profile", prof + ".part", golden, "--", binary],
                   capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("profiling failed for %s: %s" % (binary, res.stderr))
    bench = pool.run([paths["fi"], "bench", "31", "--", binary], capture_output=True, text=True)
    with open(bench_path + ".part", "w") as f:
        f.write(bench.stdout)
    os.replace(bench_path + ".part", bench_path)
    os.replace(prof + ".part", prof)
    return prof, golden


def profile_info(prof):
    with open(prof) as f:
        f.readline()
        text = f.readline().split()
        dyn = f.readline().split()
        exit_line = f.readline().split()
        pcs = f.readline().split()
    return {"text_lo": int(text[1], 16), "text_hi": int(text[2], 16), "dyn_app": int(dyn[1]),
            "dyn_total": int(dyn[2]), "golden_exit": int(exit_line[1]), "static_pcs": int(pcs[1])}


def bench_time(binary):
    path = os.path.join(os.path.dirname(binary), "bench.txt")
    m = re.search(r"min_us (\d+) median_us (\d+)", open(path).read())
    return int(m.group(1)), int(m.group(2))


def seed_of(*parts):
    return int(hashlib.sha256("/".join(parts).encode()).hexdigest()[:15], 16)


def inject_chunk(pool, paths, binary, prof, golden, model, seed, count, timeout_ms, out_csv):
    if os.path.exists(out_csv):
        with open(out_csv) as f:
            if sum(1 for _ in f) == count + 1:
                return out_csv
    tmp = os.path.join(paths["tmp"], "w%x" % (seed & 0xffffff))
    res = pool.run([paths["fi"], "inject", prof, golden, model, str(seed), str(count),
                    str(timeout_ms), tmp, "--", binary], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError("injection failed (%s): %s" % (out_csv, res.stderr[-500:]))
    with open(out_csv + ".part", "w") as f:
        f.write(res.stdout)
    os.replace(out_csv + ".part", out_csv)
    return out_csv


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
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--only-build", action="store_true")
    ap.add_argument("--skip-inject", action="store_true")
    args = ap.parse_args()

    with open(args.campaign, "rb") as f:
        cfg = tomllib.load(f)
    camp = cfg["campaign"]
    cfg["root"] = os.path.abspath(os.path.join(os.path.dirname(args.campaign), camp.get("root", ".")))
    out = os.path.abspath(os.path.expanduser(camp["output"]))
    paths = {
        "aspis": os.path.abspath(os.path.expanduser(camp["aspis"])),
        "llvm_bin": os.path.abspath(os.path.expanduser(camp["llvm_bin"])),
        "fi": os.path.abspath(os.path.expanduser(camp["fi"])),
        "build": os.path.join(out, "build"),
        "raw": os.path.join(out, "raw"),
        "tmp": camp.get("tmp", "/dev/shm/aspis-fi"),
    }
    for d in ("build", "raw"):
        os.makedirs(paths[d], exist_ok=True)
    os.makedirs(paths["tmp"], exist_ok=True)
    benches, confs = cfg["benchmark"], cfg["config"]
    models = camp["models"]
    n_inj, chunk = int(camp["injections"]), int(camp.get("chunk", 100))
    pool = CpuPool(args.jobs)

    # 1-2. build
    log("building %d benchmarks x %d configurations" % (len(benches), len(confs)))
    binaries = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(build, cfg, b, c, paths): (b["name"], c["name"]) for b in benches for c in confs}
        for fut in as_completed(futs):
            binaries[futs[fut]] = fut.result()
    if args.only_build:
        return 0

    # 3-4. golden runs
    log("profiling golden runs")
    profiles = {}
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = {ex.submit(profile, pool, binaries[key], paths): key for key in binaries}
        for fut in as_completed(futs):
            profiles[futs[fut]] = fut.result()

    # golden outputs of all the configurations must match the baseline one
    base = confs[0]["name"]
    for b in benches:
        ref = open(profiles[(b["name"], base)][1], "rb").read()
        for c in confs:
            if open(profiles[(b["name"], c["name"])][1], "rb").read() != ref:
                raise RuntimeError("golden output of %s/%s differs from %s" % (b["name"], c["name"], base))

    metrics = []
    for b in benches:
        for c in confs:
            binary = binaries[(b["name"], c["name"])]
            info = profile_info(profiles[(b["name"], c["name"])][0])
            kv = read_kv(os.path.join(os.path.dirname(binary), "build.txt"))
            tmin, tmed = bench_time(binary)
            metrics.append({"benchmark": b["name"], "config": c["name"], "text_bytes": kv["text_bytes"],
                            "compile_s": kv["compile_s"], "comparisons": kv["comparisons"],
                            "dyn_app": info["dyn_app"], "dyn_total": info["dyn_total"],
                            "static_pcs": info["static_pcs"], "time_min_us": tmin, "time_median_us": tmed})
    with open(os.path.join(out, "metrics.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(metrics[0].keys()))
        w.writeheader()
        w.writerows(metrics)
    log("metrics written")
    if args.skip_inject:
        return 0

    # 5. fault injection
    tasks = []
    for b in benches:
        for c in confs:
            binary = binaries[(b["name"], c["name"])]
            prof, golden = profiles[(b["name"], c["name"])]
            _, tmed = bench_time(binary)
            timeout_ms = max(int(camp.get("timeout_min_ms", 300)), int(tmed * camp.get("timeout_factor", 20) / 1000))
            # a benchmark can override the number of injections
            n_bench = int(b.get("injections", n_inj))
            for m in models:
                for k in range(0, n_bench, chunk):
                    cnt = min(chunk, n_bench - k)
                    seed = seed_of(str(camp.get("seed", 1)), b["name"], c["name"], m, str(k))
                    csv_path = os.path.join(paths["raw"], "%s__%s__%s__%05d.csv" % (b["name"], c["name"], m, k))
                    tasks.append((binary, prof, golden, m, seed, cnt, timeout_ms, csv_path))
    log("running %d injection chunks (%d experiments)" % (len(tasks), sum(t[5] for t in tasks)))
    done, start = 0, time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        futs = [ex.submit(inject_chunk, pool, paths, *t) for t in tasks]
        for fut in as_completed(futs):
            fut.result()
            done += 1
            if done % 50 == 0 or done == len(tasks):
                rate = done / max(1e-9, time.time() - start)
                log("  %d/%d chunks, ETA %.1f min" % (done, len(tasks), (len(tasks) - done) / max(rate, 1e-9) / 60))

    # 6. aggregation
    rows = {}
    for t in tasks:
        name = os.path.basename(t[7]).split("__")
        key = (name[0], name[1], name[2])
        acc = rows.setdefault(key, {o: 0 for o in OUTCOMES})
        with open(t[7]) as f:
            for r in csv.DictReader(f):
                acc[r["outcome"]] = acc.get(r["outcome"], 0) + 1
    with open(os.path.join(out, "outcomes.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["benchmark", "config", "model", "n"] + OUTCOMES +
                    ["sdc_rate", "sdc_lo", "sdc_hi", "detected_rate", "due_rate"])
        for (b, c, m), acc in sorted(rows.items()):
            n = sum(acc[o] for o in OUTCOMES if o != "not_injected")
            lo, hi = wilson(acc["sdc"], n)
            w.writerow([b, c, m, n] + [acc[o] for o in OUTCOMES] +
                       ["%.5f" % (acc["sdc"] / n if n else 0), "%.5f" % lo, "%.5f" % hi,
                        "%.5f" % ((acc["detected_data"] + acc["detected_cfc"]) / n if n else 0),
                        "%.5f" % ((acc["crash"] + acc["hang"]) / n if n else 0)])
    log("outcomes written to %s" % os.path.join(out, "outcomes.csv"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
