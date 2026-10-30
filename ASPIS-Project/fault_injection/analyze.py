#!/usr/bin/env python3
"""Turns the results of the experiments into the tables and figures of the
report.

Usage:
    analyze.py --campaign <dir> [--before <dir>] [--harness name=<log> ...] --out <dir>

  --campaign  output of campaign.py (metrics.csv, outcomes.csv)
  --before    output of the same campaign run with ASPIS before the RASM fix
  --harness   log of the official ASPIS harness (pytest test.py -v, also
              gzipped), e.g. master=harness_master.log.gz

Writes <out>/figures/*.svg|png and <out>/tables/*.md.
"""
import argparse
import csv
import gzip
import math
import os
import re
from collections import Counter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

CONFIGS = ["baseline", "EDDI", "CFCSS", "RASM", "EDDI+CFCSS", "EDDI+RASM"]
MODELS = [("reg", "Register bit-flip"), ("branch", "Inverted branch")]
OUTCOMES = ["masked", "detected_data", "detected_cfc", "crash", "hang", "sdc"]
LABELS = {"masked": "Masked", "detected_data": "Detected (data check)",
          "detected_cfc": "Detected (signature check)", "crash": "Crash", "hang": "Hang", "sdc": "SDC"}
APPS = ["c_aes128", "c_fft", "c_huffman", "c_pid_control"]  # our tests in the ASPIS harness

# outcomes are status values: masked is neutral, detections are good,
# crash / hang / SDC are serious / warning / critical
INK, INK2, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"
COLORS = {"masked": "#c3c2b7", "detected_data": "#0ca30c", "detected_cfc": "#0ca30c",
          "crash": "#ec835a", "hang": "#fab219", "sdc": "#d03b3b"}
HATCH = {"detected_cfc": "////"}
BLUE = "#2a78d6"
plt.rcParams.update({
    "font.family": ["Inter", "DejaVu Sans"], "font.size": 9, "axes.edgecolor": AXIS,
    "axes.labelcolor": INK2, "svg.fonttype": "none", "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.linewidth": 0.8, "hatch.color": "#006300", "hatch.linewidth": 0.8,
})


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def wilson(k, n, z=1.96):
    """95% Wilson score interval of a binomial proportion."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def gmean(values):
    return math.exp(sum(math.log(v) for v in values) / len(values))


def pct(x, digits=1):
    return ("%." + str(digits) + "f") % (100 * x)


def style(ax):
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, out, name):
    os.makedirs(os.path.join(out, "figures"), exist_ok=True)
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(out, "figures", name + "." + ext), dpi=200, bbox_inches="tight")
    plt.close(fig)


def write(out, name, lines):
    os.makedirs(os.path.join(out, "tables"), exist_ok=True)
    with open(os.path.join(out, "tables", name + ".md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def aggregate(outcomes):
    """(config, model) -> counts summed over the applications."""
    agg = {}
    for r in outcomes:
        acc = agg.setdefault((r["config"], r["model"]), Counter())
        for o in OUTCOMES + ["n"]:
            acc[o] += int(r[o])
    return agg


# ------------------------------------------------------------------- cost
def costs(metrics):
    """config -> {application: (code size, executed instructions)} relative to the baseline."""
    by = {(r["application"], r["config"]): r for r in metrics}
    apps = sorted({r["application"] for r in metrics})
    res = {}
    for conf in CONFIGS:
        res[conf] = {}
        for a in apps:
            r, base = by[(a, conf)], by[(a, "baseline")]
            res[conf][a] = (int(r["text_bytes"]) / int(base["text_bytes"]),
                            int(r["executed_instructions"]) / int(base["executed_instructions"]))
    return res


def table_cost(cost, metrics, out):
    checks = Counter()
    for r in metrics:
        checks[r["config"]] += int(r["comparisons"])
    lines = ["| configuration | code size | executed instructions | consistency checks |",
             "|---|---:|---:|---:|"]
    for conf in CONFIGS:
        size = gmean([v[0] for v in cost[conf].values()])
        dyn = gmean([v[1] for v in cost[conf].values()])
        lines.append("| %s | %.2fx | %.2fx | %d |" % (conf, size, dyn, checks[conf]))
    write(out, "cost", lines)


def fig_cost(cost, out):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
    ypos = list(range(len(CONFIGS)))[::-1]
    for ax, idx, title in ((axes[0], 0, "Code size (.text), x baseline"),
                           (axes[1], 1, "Executed instructions, x baseline")):
        xmax = max(v[idx] for c in CONFIGS for v in cost[c].values()) * 1.25
        for y, conf in zip(ypos, CONFIGS):
            vals = [v[idx] for v in cost[conf].values()]
            g = gmean(vals)
            ax.barh(y, g, height=0.5, color=BLUE)
            ax.scatter(vals, [y] * len(vals), s=12, color=INK2, zorder=3, linewidths=0)
            ax.text(max(vals) + 0.02 * xmax, y, "%.1fx" % g, va="center", fontsize=8, color=INK2)
        ax.axvline(1, color=AXIS, linewidth=0.8)
        ax.set_xlim(0, xmax)
        ax.set_title(title, loc="left", fontsize=10, pad=8)
        style(ax)
    axes[0].set_yticks(ypos)
    axes[0].set_yticklabels(CONFIGS)
    fig.tight_layout()
    save(fig, out, "cost")


# ---------------------------------------------------------- fault injection
def fig_outcomes(agg, out):
    fig, axes = plt.subplots(1, len(MODELS), figsize=(9, 3.4), sharey=True)
    ypos = list(range(len(CONFIGS)))[::-1]
    for ax, (model, title) in zip(axes, MODELS):
        for y, conf in zip(ypos, CONFIGS):
            c = agg[(conf, model)]
            left = 0.0
            for o in OUTCOMES:
                w = c[o] / c["n"]
                if w > 0:
                    ax.barh(y, w, left=left, height=0.62, color=COLORS[o], hatch=HATCH.get(o),
                            edgecolor="white", linewidth=1)
                left += w
            ax.text(1.015, y, "%s%%" % pct(c["sdc"] / c["n"]), va="center", fontsize=8, color=INK2)
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.set_title(title, loc="left", fontsize=10, pad=8)
        style(ax)
    axes[0].set_yticks(ypos)
    axes[0].set_yticklabels(CONFIGS)
    handles = [Patch(facecolor=COLORS[o], hatch=HATCH.get(o), edgecolor="white", label=LABELS[o])
               for o in OUTCOMES]
    fig.legend(handles=handles, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.08),
               fontsize=8)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    save(fig, out, "fi_outcomes")


def table_outcomes(agg, out):
    for model, _ in MODELS:
        lines = ["| configuration | n | masked | detected (data) | detected (CFC) | crash | hang | SDC | SDC 95% CI |",
                 "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for conf in CONFIGS:
            c = agg[(conf, model)]
            n = c["n"]
            lo, hi = wilson(c["sdc"], n)
            lines.append("| %s | %d | %s | %s | %s | %s | %s | %s | %s–%s |" % (
                conf, n, pct(c["masked"] / n), pct(c["detected_data"] / n), pct(c["detected_cfc"] / n),
                pct(c["crash"] / n), pct(c["hang"] / n), pct(c["sdc"] / n, 2), pct(lo, 2), pct(hi, 2)))
        write(out, "outcomes_%s" % model, lines)


def table_sdc_per_app(outcomes, out):
    by = {(r["application"], r["config"], r["model"]): r for r in outcomes}
    apps = sorted({r["application"] for r in outcomes})
    for model, _ in MODELS:
        lines = ["| application | " + " | ".join(CONFIGS) + " |", "|---" + "|---:" * len(CONFIGS) + "|"]
        for a in apps:
            lines.append("| %s | %s |" % (a, " | ".join(
                pct(int(by[(a, c, model)]["sdc"]) / int(by[(a, c, model)]["n"])) for c in CONFIGS)))
        write(out, "sdc_%s_per_app" % model, lines)


def table_before_after(before, after, out, conf="EDDI+RASM"):
    lines = ["| fault model | SDC before | SDC after | detected (CFC) before | detected (CFC) after |",
             "|---|---:|---:|---:|---:|"]
    for model, title in MODELS:
        b, a = before[(conf, model)], after[(conf, model)]
        lines.append("| %s | %s%% | %s%% | %s%% | %s%% |" % (
            title, pct(b["sdc"] / b["n"], 2), pct(a["sdc"] / a["n"], 2),
            pct(b["detected_cfc"] / b["n"]), pct(a["detected_cfc"] / a["n"])))
    write(out, "before_after", lines)


# ------------------------------------------------------------ compatibility
HARNESS_LINE = re.compile(r"^test\.py::test_aspis\[(.+)-(--no-cfc|--cfcss|--rasm|--racfed|--inter-rasm)"
                          r"-(--[^\]]+)\] (PASSED|FAILED|SKIPPED|ERROR)")


def read_harness(path):
    """{(test, data technique, cfc technique): result} from a `pytest -v` log (also .gz)."""
    res = {}
    with (gzip.open(path, "rt") if path.endswith(".gz") else open(path)) as f:
        for line in f:
            m = HARNESS_LINE.match(line)
            if m:
                res[(m.group(1), m.group(3), m.group(2))] = m.group(4)
    return res


def tables_compat(runs, out):
    names = [n for n, _ in runs]
    # our applications, per family of data protection techniques
    families = [("none (`--no-dup`)", lambda d: d == "--no-dup"), ("EDDI, 4 variants", lambda d: d.startswith("--eddi")),
                ("sEDDI", lambda d: d == "--seddi"), ("FDSC", lambda d: d == "--fdsc"),
                ("REDDI, 4 variants", lambda d: d.startswith("--reddi"))]
    lines = ["| data protection | " + " | ".join("%s: pass" % n for n in names) + " |",
             "|---" + "|---:" * len(names) + "|"]
    for label, match in families:
        cells = []
        for _, res in runs:
            mine = [v for (t, d, c), v in res.items() if t in APPS and match(d)]
            cells.append("%d / %d" % (mine.count("PASSED"), len(mine)))
        lines.append("| %s | %s |" % (label, " | ".join(cells)))
    cells = []
    for _, res in runs:
        mine = [v for (t, d, c), v in res.items() if t in APPS]
        cells.append("**%d / %d**" % (mine.count("PASSED"), len(mine)))
    lines.append("| **total** | %s |" % " | ".join(cells))
    write(out, "compat_apps", lines)
    # the existing tests of ASPIS
    lines = ["| ASPIS tests | " + " | ".join(names) + " |", "|---" + "|---:" * len(names) + "|"]
    for result in ("PASSED", "FAILED", "SKIPPED"):
        lines.append("| %s | %s |" % (result.lower(), " | ".join(
            str(sum(1 for (t, d, c), v in res.items() if t not in APPS and v == result)) for _, res in runs)))
    write(out, "compat_suite", lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign")
    ap.add_argument("--before")
    ap.add_argument("--harness", action="append", default=[], help="name=<pytest -v log>")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    if args.campaign:
        metrics = read_csv(os.path.join(args.campaign, "metrics.csv"))
        outcomes = read_csv(os.path.join(args.campaign, "outcomes.csv"))
        agg = aggregate(outcomes)
        cost = costs(metrics)
        table_cost(cost, metrics, args.out)
        fig_cost(cost, args.out)
        fig_outcomes(agg, args.out)
        table_outcomes(agg, args.out)
        table_sdc_per_app(outcomes, args.out)
        if args.before:
            before = aggregate(read_csv(os.path.join(args.before, "outcomes.csv")))
            table_before_after(before, agg, args.out)
    if args.harness:
        tables_compat([(h.split("=", 1)[0], read_harness(h.split("=", 1)[1])) for h in args.harness], args.out)


if __name__ == "__main__":
    main()
