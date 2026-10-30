#!/usr/bin/env python3
"""Shows where the silent data corruptions of a configuration happened: the
instructions hit by the faults that ended in an SDC, how many times, and, for
a conditional jump, the first instruction of its two successors.

Usage:
    sdc_sites.py <raw.csv.gz> <campaign output dir> <application> <config> [model]

<campaign output dir> is the directory written by campaign.py, which contains
the binaries (build/<application>/<config>/prog). Needs readelf and objdump.
"""
import collections
import csv
import gzip
import re
import subprocess
import sys


def disassemble(prog):
    """{address: instruction}, {address: function}, {address: next address}"""
    dis = subprocess.run(["objdump", "-d", "--no-show-raw-insn", "-M", "intel", prog],
                         capture_output=True, text=True).stdout
    insn, func, order, cur = {}, {}, [], None
    for line in dis.splitlines():
        m = re.match(r"^([0-9a-f]+) <(.+)>:$", line)
        if m:
            cur = m.group(2)
            continue
        m = re.match(r"^\s+([0-9a-f]+):\s+(.*)$", line)
        if m:
            a = int(m.group(1), 16)
            insn[a], func[a] = m.group(2).strip(), cur
            order.append(a)
    return insn, func, dict(zip(order, order[1:]))


def main():
    if len(sys.argv) not in (5, 6):
        sys.exit(__doc__)
    raw, campaign, app, conf = sys.argv[1:5]
    model = sys.argv[5] if len(sys.argv) == 6 else "branch"
    prog = "%s/build/%s/%s/prog" % (campaign, app, conf)
    # pc_off is relative to the start of the executable segment
    loads = [line.split() for line in subprocess.run(["readelf", "-lW", prog], capture_output=True,
                                                     text=True).stdout.splitlines()
             if line.strip().startswith("LOAD") and "R E" in line]
    base = int(loads[0][2], 16)
    insn, func, nxt = disassemble(prog)
    with gzip.open(raw, "rt") as f:
        sites = collections.Counter(int(r["pc_off"], 16) + base for r in csv.DictReader(f)
                                    if r["application"] == app and r["config"] == conf
                                    and r["model"] == model and r["outcome"] == "sdc")
    print("%s %s %s: %d SDC at %d instructions" % (app, conf, model, sum(sites.values()), len(sites)))
    for a, n in sites.most_common():
        line = "%6d x  %x  %-20s %s" % (n, a, func[a], insn[a])
        target = re.match(r"j(?!mp)\w+\s+([0-9a-f]+) <", insn[a])
        if target:  # conditional jump: show its two successors
            line += "\n            not taken -> %s\n            taken     -> %s" % (
                insn.get(nxt[a], "?"), insn.get(int(target.group(1), 16), "?"))
        print(line)


if __name__ == "__main__":
    main()
