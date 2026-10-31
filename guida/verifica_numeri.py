#!/usr/bin/env python3
"""Ricalcola dai file dei risultati tutti i numeri citati nel report, nella
guida e nelle slide, in modo indipendente da analyze.py (vedi l'appendice
"Verifica dei fatti" della guida).

Uso:
    python3 guida/verifica_numeri.py ASPIS-Project [cartella della campagna]

Con la sola cartella del progetto usa i file di results/ e benchmarks/. Se si
indica anche la cartella di lavoro della campagna (quella con build/), ricalcola
anche le quote dei salti dei controlli (check_jumps.py) e il punto delle SDC di
RASM (sdc_sites.py), che hanno bisogno degli eseguibili.
"""
import collections
import csv
import gzip
import math
import os
import re
import subprocess
import sys
from decimal import ROUND_HALF_UP, Decimal

OUT = ["masked", "detected_data", "detected_cfc", "crash", "hang", "sdc"]
CONFIGS = ["baseline", "EDDI", "CFCSS", "RASM", "EDDI+CFCSS", "EDDI+RASM"]
APPS = ["aes128", "fft", "huffman", "pid_control"]


def rows(path):
    with (gzip.open(path, "rt") if path.endswith(".gz") else open(path)) as f:
        return list(csv.DictReader(f))


def pct(k, n, digits=1):
    """Percentuale arrotondata per eccesso sul 5, come nelle tabelle del report."""
    q = Decimal(1).scaleb(-digits)
    return str((Decimal(100 * k) / Decimal(n)).quantize(q, rounding=ROUND_HALF_UP))


def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, c - h), min(1.0, c + h)


def ci(k, n):
    lo, hi = wilson(k, n)
    return "%s-%s" % (pct(lo * n, n, 2), pct(hi * n, n, 2))


def pooled(outcomes):
    agg = collections.defaultdict(collections.Counter)
    for r in outcomes:
        for k in OUT + ["n"]:
            agg[(r["config"], r["model"])][k] += int(r[k])
    return agg


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    proj = sys.argv[1]
    camp = sys.argv[2] if len(sys.argv) == 3 else None
    res = os.path.join(proj, "results")
    oc = rows(os.path.join(res, "fault_injection/outcomes.csv"))
    ob = rows(os.path.join(res, "fault_injection/before_fix/outcomes.csv"))
    me = rows(os.path.join(res, "fault_injection/metrics.csv"))
    raw = rows(os.path.join(res, "fault_injection/raw.csv.gz"))
    rawb = rows(os.path.join(res, "fault_injection/before_fix/raw.csv.gz"))
    A, B = pooled(oc), pooled(ob)

    print("== esperimenti: %d (righe grezze %d), prima della correzione %d (righe %d)" % (
        sum(c["n"] for c in A.values()), len(raw), sum(c["n"] for c in B.values()), len(rawb)))
    for model in ("reg", "branch"):
        print("== esiti, modello %s (%% su n guasti; SDC con intervallo di Wilson al 95%%)" % model)
        groups = [(c, A[(c, model)]) for c in CONFIGS] + [("EDDI+RASM prima", B[("EDDI+RASM", model)])]
        for name, c in groups:
            n = c["n"]
            print("   %-16s n=%d masked %s, rilevati dati %s, rilevati CFC %s, crash %s, hang %s, "
                  "SDC %d = %s%% [%s]" % (name, n, pct(c["masked"], n), pct(c["detected_data"], n),
                                         pct(c["detected_cfc"], n), pct(c["crash"], n), pct(c["hang"], n),
                                         c["sdc"], pct(c["sdc"], n, 2), ci(c["sdc"], n)))

    print("== costo (media geometrica dei rapporti con la baseline; tra parentesi le applicazioni)")
    by = {(r["application"], r["config"]): r for r in me}
    for conf in CONFIGS:
        size = [int(by[(a, conf)]["text_bytes"]) / int(by[(a, "baseline")]["text_bytes"]) for a in APPS]
        dyn = [int(by[(a, conf)]["executed_instructions"]) / int(by[(a, "baseline")]["executed_instructions"])
               for a in APPS]
        gm = lambda v: math.exp(sum(map(math.log, v)) / len(v))
        checks = sum(int(by[(a, conf)]["comparisons"]) for a in APPS)
        print("   %-11s codice %.2fx  istruzioni %.2fx (%s)  controlli %d" % (
            conf, gm(size), gm(dyn), " ".join("%.2f" % x for x in dyn), checks))
    print("   istruzioni eseguite dalla baseline: " +
          ", ".join("%s %s" % (a, by[(a, "baseline")]["executed_instructions"]) for a in APPS))

    print("== SDC per applicazione (%, 1000 guasti per cella)")
    cell = {(r["application"], r["config"], r["model"]): r for r in oc}
    for model in ("reg", "branch"):
        for a in APPS:
            print("   %-6s %-12s " % (model, a) + "  ".join(
                "%s %s" % (c, pct(int(cell[(a, c, model)]["sdc"]), int(cell[(a, c, model)]["n"])))
                for c in CONFIGS))

    crashes = collections.Counter(r["target"] for r in raw if r["config"] == "baseline"
                                  and r["model"] == "reg" and r["outcome"] == "crash")
    tot = sum(crashes.values())
    print("== crash della baseline con i bit-flip nei registri: %d; " % tot +
          ", ".join("%s %d (%s%%)" % (k, v, pct(v, tot, 0)) for k, v in crashes.most_common(4)))
    times = sorted(int(r["time_ms"]) for r in raw)
    print("== durata di un esperimento (con gdb): media %.0f ms, mediana %d ms" % (
        sum(times) / len(times), times[len(times) // 2]))
    print("== righe delle applicazioni: " + ", ".join(
        "%s %d" % (a, sum(1 for _ in open(os.path.join(proj, "benchmarks", a + ".c")))) for a in APPS))

    print("== log dei test di ASPIS")
    line = re.compile(r"^test\.py::test_aspis\[(.+?)-(--no-cfc|--cfcss|--rasm|--racfed|--inter-rasm)-"
                      r"(--[^\]]+)\] (PASSED|FAILED|SKIPPED|ERROR)")
    ours = {"c_" + a for a in APPS}
    for name in ("harness_master_first_version", "harness_master", "harness_fixed"):
        res_ = {}
        last = ""
        with gzip.open(os.path.join(res, "compatibility", name + ".log.gz"), "rt") as f:
            for text in f:
                m = line.match(text)
                if m:
                    res_[(m.group(1), m.group(2), m.group(3))] = m.group(4)
                last = text.strip() or last
        mine = [v for (t, _, _), v in res_.items() if t in ours]
        other = collections.Counter(v for (t, _, _), v in res_.items() if t not in ours)
        failed = collections.Counter(t for (t, _, _), v in res_.items() if t not in ours and v == "FAILED")
        print("   %-29s test %d, compilazioni %d; nostre %d/%d passate; esistenti %s; falliti per test %s" % (
            name, len({t for (t, _, _) in res_}), len(res_), mine.count("PASSED"), len(mine),
            dict(other), dict(failed)))
        print("   %-29s %s" % ("", last))

    if camp:
        fi = os.path.join(proj, "fault_injection")
        for conf in ("EDDI", "CFCSS", "RASM"):
            out = subprocess.run([sys.executable, os.path.join(fi, "check_jumps.py"), camp, conf],
                                 capture_output=True, text=True).stdout.split("\n")
            print("== salti dei controlli con %s: %s" % (conf, [x for x in out if x.startswith("all")]))
        out = subprocess.run([sys.executable, os.path.join(fi, "sdc_sites.py"),
                              os.path.join(res, "fault_injection/raw.csv.gz"), camp, "pid_control", "RASM"],
                             capture_output=True, text=True).stdout.split("\n")
        print("== SDC di RASM in pid_control:\n   " + "\n   ".join(out[:4]))


if __name__ == "__main__":
    main()
