# One fault-injection experiment, run inside gdb:
#
#     gdb -batch -nx -x gdb_inject.py --args <program>
#
# gdb stops the program at the k-th execution of the instruction at FI_ADDR
# (an address as printed by objdump), injects the fault, lets the program go
# on and prints one line: "FI-RESULT <injected> <exit code> <signal>", where the
# exit code is -1 if the program was killed by a signal.
#
# Parameters, in the environment:
#   FI_ADDR, FI_K       where and when: the k-th execution of that instruction
#   FI_MODEL            reg: flip bit FI_BIT of register FI_REG
#                       branch: the conditional jump at FI_ADDR goes the other way
#   FI_OUT, FI_ERR      files for the standard output and error of the program
#   FI_TIMEOUT_MS       after the injection, the program is a hang if it does not
#                       end within this time
#
# Part of the FLC 2026/27 project "Harden a C application with ASPIS".
# Copyright (c) 2026 Alberto Rotolo, Simone Rota. SPDX-License-Identifier: MIT
import os
import signal
import subprocess

import gdb

env = os.environ
stops = []      # one entry per stop of the program: the signal, or None for a breakpoint
gdb.events.stop.connect(lambda event: stops.append(getattr(event, "stop_signal", None)))
gdb.execute("set pagination off")

# The program is position independent: its addresses at run time are the ones
# of objdump plus the address where it is loaded (fixed, as gdb disables ASLR).
link_main = int(gdb.parse_and_eval("(long) &main"))
gdb.execute("starti > %s 2> %s" % (env["FI_OUT"], env["FI_ERR"]), to_string=True)
base = int(gdb.parse_and_eval("(long) &main")) - link_main

bp = gdb.Breakpoint("*%d" % (base + int(env["FI_ADDR"], 16)), internal=True)
bp.ignore_count = int(env["FI_K"]) - 1          # stop at the k-th execution
gdb.execute("continue", to_string=True)
inferior = gdb.selected_inferior()
injected = inferior.pid != 0 and stops[-1] is None
if injected:
    bp.delete()
    if env["FI_MODEL"] == "reg":
        reg, bit = env["FI_REG"], int(env["FI_BIT"])
        value = int(gdb.parse_and_eval("(unsigned long) $" + reg))
        gdb.execute("set $%s = %d" % (reg, value ^ (1 << bit)))
    else:
        pc = int(gdb.parse_and_eval("$pc"))
        insn = gdb.selected_frame().architecture().disassemble(pc)[0]
        target, next_insn = int(insn["asm"].split()[1], 16), pc + insn["length"]
        gdb.execute("stepi", to_string=True)    # execute the jump: where does it go?
        went = int(gdb.parse_and_eval("$pc"))
        gdb.execute("set $pc = %d" % (next_insn if went == target else target))
    # a watchdog kills the program with SIGKILL if it does not end in time (a hang)
    watchdog = subprocess.Popen(["sh", "-c", "sleep %.3f; kill -KILL %d" % (
        int(env["FI_TIMEOUT_MS"]) / 1000, inferior.pid)], start_new_session=True)
    gdb.execute("continue", to_string=True)
    try:
        os.killpg(watchdog.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    watchdog.wait()

if inferior.pid != 0:                           # stopped by a signal, such as SIGSEGV
    exit_code, sig = -1, stops[-1]
    gdb.execute("kill", to_string=True)
else:
    code, signo = gdb.parse_and_eval("$_exitcode"), gdb.parse_and_eval("$_exitsignal")
    exit_code = -1 if code.type.code == gdb.TYPE_CODE_VOID else int(code)
    sig = "-" if signo.type.code == gdb.TYPE_CODE_VOID else signal.Signals(int(signo)).name
print("FI-RESULT %d %d %s" % (injected, exit_code, sig))
