#!/usr/bin/env python3
"""Run the official ASPIS pytest harness (testing/test.py) on a set of tests,
one pytest process per test entry, several processes in parallel.

The upstream harness compiles every entry with all the combinations of data
protection (11) and control-flow checking (5) techniques and compares the
output of the hardened binary with the output of the unhardened one. Every
pytest process runs in its own directory next to testing/ (a "symlink farm"
pointing to test.py, conftest.py, config/ and tests/), so that the processes
never share testing/build/. Each process is started in a new session and the
whole session is killed when it ends: when pytest-timeout stops a test, the
opt process that was hanging is not left running.

Usage:
    run_aspis_harness.py --aspis <ASPIS dir> --tests <toml> [--jobs N]
                         [--only name1,name2] [--out <results dir>]

Outputs, in the results directory:
    <test_name>.xml       JUnit report of each pytest process
    <test_name>.log       pytest console output
    summary.csv           one row per (test, data technique, cfc technique)
    summary.md            pass/fail/skip matrix per test
"""
import argparse
import csv
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import tomllib
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor


def toml_entry(entry):
    """Serialise one [[tests]] table (only the keys used by test.py)."""
    lines = ["[[tests]]"]
    for key, value in entry.items():
        if isinstance(value, list):
            items = ", ".join('"%s"' % v for v in value)
            lines.append("%s = [%s]" % (key, items))
        else:
            lines.append('%s = "%s"' % (key, value))
    return "\n".join(lines) + "\n"


def make_workdir(testing_dir, name):
    """Creates <ASPIS>/.harness-<name>/ with links to the harness files, so that
    ../aspis.sh still resolves and build/ is private to this process."""
    work = os.path.join(os.path.dirname(testing_dir), ".harness-" + name)
    if os.path.isdir(work):
        shutil.rmtree(work)
    os.makedirs(work)
    for item in ("test.py", "conftest.py", "config", "tests"):
        os.symlink(os.path.join(testing_dir, item), os.path.join(work, item))
    return work


def run_one(entry, testing_dir, out_dir, timeout):
    name = entry["test_name"]
    toml_path = os.path.join(out_dir, name + ".toml")
    with open(toml_path, "w") as f:
        f.write(toml_entry(entry))
    xml_path = os.path.join(out_dir, name + ".xml")
    log_path = os.path.join(out_dir, name + ".log")
    work = make_workdir(testing_dir, name)
    cmd = [sys.executable, "-m", "pytest", "test.py", "--no-header", "-q",
           "-p", "no:cacheprovider", "--tests-file", toml_path,
           "--junitxml", xml_path]
    start = time.time()
    with open(log_path, "w") as log:
        proc = subprocess.Popen(cmd, cwd=work, stdout=log, stderr=subprocess.STDOUT,
                                start_new_session=True)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            log.write("\n[run_aspis_harness] TIMEOUT\n")
        finally:
            try:
                os.killpg(proc.pid, signal.SIGKILL)  # leftovers of timed-out tests
            except ProcessLookupError:
                pass
            proc.wait()
    failed_ir = os.path.join(work, "failed-out-ll")
    if os.path.isdir(failed_ir):
        shutil.copytree(failed_ir, os.path.join(out_dir, "failed-out-ll", name), dirs_exist_ok=True)
    shutil.rmtree(work, ignore_errors=True)
    return name, time.time() - start


# test ids look like: test_aspis[c_aes128---eddi---rasm]
ID_RE = re.compile(r"test_aspis\[(?P<test>.+?)-(?P<cfc>--[a-z-]+)-(?P<data>--.+)\]$")


def parse_case(case_name):
    m = ID_RE.match(case_name)
    if not m:
        return None, case_name, ""
    return m.group("test"), m.group("data"), m.group("cfc")


def collect(out_dir, names):
    rows = []
    for name in names:
        xml_path = os.path.join(out_dir, name + ".xml")
        if not os.path.exists(xml_path):
            rows.append({"test": name, "data": "-", "cfc": "-", "outcome": "no-report",
                         "time": 0.0, "message": "pytest produced no report"})
            continue
        root = ET.parse(xml_path).getroot()
        for case in root.iter("testcase"):
            test, data, cfc = parse_case(case.get("name", ""))
            outcome, message = "passed", ""
            for child in case:
                if child.tag in ("failure", "error"):
                    outcome = "failed"
                    message = (child.get("message") or "").splitlines()[0][:300]
                elif child.tag == "skipped":
                    outcome = "skipped"
                    message = (child.get("message") or "")[:200]
            rows.append({"test": test or name, "data": data, "cfc": cfc, "outcome": outcome,
                         "time": float(case.get("time", 0.0)), "message": message})
    return rows


def write_reports(rows, out_dir):
    with open(os.path.join(out_dir, "summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["test", "data", "cfc", "outcome", "time", "message"])
        w.writeheader()
        w.writerows(rows)
    per_test = {}
    for r in rows:
        t = per_test.setdefault(r["test"], {"passed": 0, "failed": 0, "skipped": 0,
                                            "no-report": 0, "time": 0.0, "fails": []})
        t[r["outcome"]] += 1
        t["time"] += r["time"]
        if r["outcome"] == "failed":
            t["fails"].append("%s %s: %s" % (r["data"], r["cfc"], r["message"]))
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("| test | passed | failed | skipped | time (s) |\n|---|---|---|---|---|\n")
        for name, t in sorted(per_test.items()):
            f.write("| %s | %d | %d | %d | %.1f |\n" % (name, t["passed"], t["failed"],
                                                       t["skipped"], t["time"]))
        for name, t in sorted(per_test.items()):
            if t["fails"]:
                f.write("\n### Failures of %s\n\n" % name)
                for line in t["fails"]:
                    f.write("- %s\n" % line)
    return per_test


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aspis", required=True, help="ASPIS repository root")
    ap.add_argument("--tests", required=True, help="TOML file with [[tests]] entries")
    ap.add_argument("--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("--only", default="", help="comma-separated test names to run")
    ap.add_argument("--out", default="harness-results")
    ap.add_argument("--timeout", type=int, default=7200, help="per-entry wall-clock limit (s)")
    args = ap.parse_args()

    with open(args.tests, "rb") as f:
        entries = tomllib.load(f).get("tests", [])
    if args.only:
        wanted = set(args.only.split(","))
        entries = [e for e in entries if e["test_name"] in wanted]
    os.makedirs(args.out, exist_ok=True)
    out_dir = os.path.abspath(args.out)
    testing_dir = os.path.join(os.path.abspath(args.aspis), "testing")

    print("running %d entries with %d parallel pytest processes" % (len(entries), args.jobs))
    start = time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_one, e, testing_dir, out_dir, args.timeout) for e in entries]
        for fut in futures:
            name, elapsed = fut.result()
            print("  done %-32s %7.1f s" % (name, elapsed), flush=True)
    rows = collect(out_dir, [e["test_name"] for e in entries])
    per_test = write_reports(rows, out_dir)
    total = {k: sum(t[k] for t in per_test.values()) for k in ("passed", "failed", "skipped")}
    print("total: %(passed)d passed, %(failed)d failed, %(skipped)d skipped" % total)
    print("wall clock: %.1f s, results in %s" % (time.time() - start, out_dir))
    return 1 if total["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
