#!/usr/bin/env python3
"""Share of the executed conditional jumps that belong to the checks inserted
by ASPIS, i.e. whose one successor calls DataCorruption_Handler or
SigMismatch_Handler. Counted on the golden run of each application (the
profile.csv written by campaign.py).

Usage:
    check_jumps.py <campaign work dir> <config> [application ...]

<campaign work dir> is the directory written by campaign.py, which contains
build/<application>/<config>/prog and profile.csv. Needs objdump.
"""
import csv
import os
import re
import sys

from sdc_sites import disassemble


def calls_handler(a, insn, nxt):
    """True if the code at a (after unconditional jumps) calls a fault handler."""
    for _ in range(6):
        m = re.match(r"jmp\s+([0-9a-f]+) <", insn.get(a, ""))
        if not m:
            break
        a = int(m.group(1), 16)
    for _ in range(3):
        if re.search(r"call\s+[0-9a-f]+ <(DataCorruption|SigMismatch)_Handler", insn.get(a, "")):
            return True
        a = nxt.get(a, a)
    return False


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    work, conf = sys.argv[1:3]
    apps = sys.argv[3:] or sorted(os.listdir(os.path.join(work, "build")))
    total = checks = 0
    for app in apps:
        d = os.path.join(work, "build", app, conf)
        insn, _, nxt = disassemble(os.path.join(d, "prog"))
        app_total = app_checks = 0
        for r in csv.DictReader(open(os.path.join(d, "profile.csv"))):
            if r["jcc"] != "1":
                continue
            a, count = int(r["address"], 16), int(r["executions"])
            target = int(re.match(r"j\w+\s+([0-9a-f]+) <", insn[a]).group(1), 16)
            app_total += count
            if calls_handler(nxt[a], insn, nxt) or calls_handler(target, insn, nxt):
                app_checks += count
        print("%-12s %5.1f%% of %d executed conditional jumps belong to checks" % (
            app, 100 * app_checks / app_total, app_total))
        total, checks = total + app_total, checks + app_checks
    print("%-12s %5.1f%%" % ("all", 100 * checks / total))


if __name__ == "__main__":
    main()
