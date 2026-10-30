#!/usr/bin/env python3
"""Copies the results of a campaign into the repository: metrics.csv,
outcomes.csv and all the experiments in one compressed CSV (raw.csv.gz, one
row per injected fault, with the benchmark, configuration and fault model).

Usage: export.py <campaign output dir> <destination dir>
"""
import csv
import glob
import gzip
import os
import shutil
import sys


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    os.makedirs(dst, exist_ok=True)
    for name in ("metrics.csv", "outcomes.csv"):
        shutil.copy(os.path.join(src, name), os.path.join(dst, name))
    files = sorted(glob.glob(os.path.join(src, "raw", "*.csv")))
    rows = 0
    with gzip.open(os.path.join(dst, "raw.csv.gz"), "wt", newline="") as out:
        w = None
        for path in files:
            bench, conf, model, chunk = os.path.basename(path)[:-4].split("__")
            with open(path, newline="") as f:
                for r in csv.DictReader(f):
                    r = {"benchmark": bench, "config": conf, "chunk": int(chunk), **r}
                    if w is None:
                        w = csv.DictWriter(out, fieldnames=list(r.keys()))
                        w.writeheader()
                    w.writerow(r)
                    rows += 1
    print("%d experiments from %d chunks written to %s" % (rows, len(files), dst))


if __name__ == "__main__":
    main()
