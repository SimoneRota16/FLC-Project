#!/usr/bin/env python3
"""Share of the executed conditional jumps that belong to the checks inserted
by ASPIS, i.e. whose one successor calls DataCorruption_Handler or
SigMismatch_Handler. Counted on the golden run of each application (the
profile written by `fi profile`).

Usage:
    check_jumps.py <campaign output dir> <config> [application ...]

<campaign output dir> is the directory written by campaign.py, which contains
build/<application>/<config>/prog and golden.prof. Needs readelf and objdump.
"""
import os
import re
import subprocess
import sys

from sdc_sites import disassemble, text_base


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
    campaign, conf = sys.argv[1:3]
    apps = sys.argv[3:] or sorted(os.listdir(os.path.join(campaign, "build")))
    total = checks = 0
    for app in apps:
        d = os.path.join(campaign, "build", app, conf)
        prog = os.path.join(d, "prog")
        base = text_base(prog)
        insn, _, nxt = disassemble(prog)
        app_total = app_checks = 0
        with open(os.path.join(d, "golden.prof")) as f:
            lines = f.read().split("\n")[5:]
        for line in lines:
            # offset, executions, is a jcc, condition code, length, displacement
            p = line.split()
            if len(p) != 6 or p[2] != "1":
                continue
            a, count = base + int(p[0], 16), int(p[1])
            succ = (a + int(p[4]), a + int(p[4]) + int(p[5]))
            app_total += count
            if any(calls_handler(s, insn, nxt) for s in succ):
                app_checks += count
        print("%-12s %5.1f%% of %d executed conditional jumps belong to checks" % (
            app, 100 * app_checks / app_total, app_total))
        total, checks = total + app_total, checks + app_checks
    print("%-12s %5.1f%%" % ("all", 100 * checks / total))


if __name__ == "__main__":
    main()
