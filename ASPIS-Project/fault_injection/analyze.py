#!/usr/bin/env python3
"""Turns the results of the campaign (campaign.py) and of the compatibility
matrices (scripts/aspis_matrix.py) into the tables and figures of the report.

Usage:
    analyze.py --campaign <campaign output dir> --out <dir>
               [--matrix name=<matrix dir> ...]

Writes <out>/figures/*.svg|png and <out>/tables/*.md.
"""
import argparse
import csv
import math
import os
from collections import defaultdict

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

CONFIGS = ["baseline", "EDDI", "sEDDI", "FDSC", "CFCSS", "RASM", "interRASM", "RACFED",
           "EDDI+CFCSS", "EDDI+RASM", "EDDI+RACFED"]
MODELS = [("reg", "Register bit-flip"), ("branch", "Inverted branch"), ("jump", "Wrong jump target")]
OUTCOMES = ["masked", "detected_data", "detected_cfc", "crash", "hang", "sdc"]
LABELS = {"masked": "Masked", "detected_data": "Detected (data check)",
          "detected_cfc": "Detected (signature check)", "crash": "Crash",
          "hang": "Hang", "sdc": "SDC"}

# Reference palette of the dataviz method. The outcomes are status values:
# masked is neutral, detection is good, crash/hang/SDC are serious/warning/
# critical. Every figure is drawn twice, for light and dark pages; the dark
# version uses the dark steps of the same palette, not an inversion.
THEMES = {
    "light": dict(SURFACE="#fcfcfb", INK="#0b0b0b", INK2="#52514e", MUTED="#898781", GRID="#e1e0d9",
                  AXIS="#c3c2b7", MASKED="#c3c2b7", HATCH_INK="#006300", SERIES=["#2a78d6", "#eb6834"],
                  SEQ=["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]),
    "dark": dict(SURFACE="#1a1a19", INK="#f0efec", INK2="#c3c2b7", MUTED="#898781", GRID="#2c2c2a",
                 AXIS="#383835", MASKED="#6b6a65", HATCH_INK="#004d00", SERIES=["#3987e5", "#d95926"],
                 SEQ=["#104281", "#184f95", "#1c5cab", "#256abf", "#3987e5", "#6da7ec", "#9ec5f4"]),
}
HATCH = {"detected_cfc": "////"}
SUFFIX = ""


def set_theme(name):
    """Sets the module-level colors and the matplotlib defaults for a theme."""
    global SURFACE, INK, INK2, MUTED, GRID, AXIS, COLORS, SERIES, SEQ, SUFFIX
    t = THEMES[name]
    SURFACE, INK, INK2, MUTED, GRID, AXIS = t["SURFACE"], t["INK"], t["INK2"], t["MUTED"], t["GRID"], t["AXIS"]
    SERIES, SEQ = t["SERIES"], t["SEQ"]
    COLORS = {"masked": t["MASKED"], "detected_data": "#0ca30c", "detected_cfc": "#0ca30c",
              "crash": "#ec835a", "hang": "#fab219", "sdc": "#d03b3b"}
    SUFFIX = "" if name == "light" else "_" + name
    plt.rcParams.update({
        "font.family": ["Inter", "DejaVu Sans"], "font.size": 9, "axes.edgecolor": AXIS,
        "axes.labelcolor": INK2, "svg.fonttype": "none", "xtick.color": INK2, "ytick.color": INK2,
        "text.color": INK, "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "axes.linewidth": 0.8, "hatch.color": t["HATCH_INK"],
        "hatch.linewidth": 0.8, "legend.labelcolor": INK2,
    })


set_theme("light")


def ink_on(fill):
    """Near-black or white text, whichever reads better on the fill color."""
    rgb = [int(fill[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    lum = 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    return "#0b0b0b" if lum > 0.25 else "#ffffff"


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return max(0.0, centre - half), min(1.0, centre + half)


def gmean(values):
    return math.exp(sum(math.log(v) for v in values) / len(values))


def style(ax, grid_axis="x"):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def save(fig, out, name):
    os.makedirs(os.path.join(out, "figures"), exist_ok=True)
    for ext in ("svg", "png"):
        fig.savefig(os.path.join(out, "figures", name + SUFFIX + "." + ext), dpi=200, bbox_inches="tight")
    plt.close(fig)


def write(out, name, text):
    os.makedirs(os.path.join(out, "tables"), exist_ok=True)
    with open(os.path.join(out, "tables", name + ".md"), "w") as f:
        f.write(text)


def pct(x, digits=1):
    return ("%." + str(digits) + "f") % (100 * x)


# ------------------------------------------------------------ fault injection
def aggregate(outcomes):
    """(config, model) -> counts summed over the benchmarks."""
    agg = defaultdict(lambda: defaultdict(int))
    for r in outcomes:
        key = (r["config"], r["model"])
        for o in OUTCOMES + ["n"]:
            agg[key][o] += int(r[o])
    return agg


def fig_outcomes(agg, benches, out):
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 4.4), sharey=True)
    ypos = list(range(len(CONFIGS)))[::-1]
    for ax, (model, title) in zip(axes, MODELS):
        for y, conf in zip(ypos, CONFIGS):
            c = agg[(conf, model)]
            n = c["n"]
            left = 0.0
            for o in OUTCOMES:
                w = c[o] / n if n else 0
                if w > 0:
                    ax.barh(y, w, left=left, height=0.62, color=COLORS[o], hatch=HATCH.get(o),
                            edgecolor=SURFACE, linewidth=1.2)
                left += w
            ax.text(1.015, y, "%s%%" % pct(c["sdc"] / n if n else 0), va="center", ha="left",
                    fontsize=8, color=INK2)
        ax.set_xlim(0, 1)
        ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
        ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"])
        ax.set_title(title, loc="left", fontsize=10, color=INK, pad=8)
        style(ax)
        ax.spines["left"].set_visible(False)
    axes[0].set_yticks(ypos)
    axes[0].set_yticklabels(CONFIGS)
    handles = [Patch(facecolor=COLORS[o], hatch=HATCH.get(o), edgecolor=SURFACE, label=LABELS[o])
               for o in OUTCOMES]
    fig.legend(handles=handles, loc="lower center", ncol=6, frameon=False, bbox_to_anchor=(0.5, -0.06),
               fontsize=8.5)
    fig.text(0.995, 0.955, "value at the right of each bar: SDC rate", ha="right", fontsize=7.5,
             color=MUTED)
    fig.suptitle("Outcome of the injected faults: %d applications, %s faults per configuration and model"
                 % (len(benches), "{:,}".format(agg[(CONFIGS[0], MODELS[0][0])]["n"])),
                 x=0.01, ha="left", fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    save(fig, out, "fi_outcomes")


def table_outcomes(agg, out):
    lines = []
    for model, title in MODELS:
        lines.append("**%s**\n" % title)
        lines.append("| configuration | n | masked | detected (data) | detected (CFC) | crash | hang | SDC [95% CI] |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for conf in CONFIGS:
            c = agg[(conf, model)]
            n = c["n"]
            lo, hi = wilson(c["sdc"], n)
            lines.append("| %s | %d | %s | %s | %s | %s | %s | %s [%s, %s] |" % (
                conf, n, pct(c["masked"] / n), pct(c["detected_data"] / n), pct(c["detected_cfc"] / n),
                pct(c["crash"] / n), pct(c["hang"] / n), pct(c["sdc"] / n, 2), pct(lo, 2), pct(hi, 2)))
        lines.append("")
    write(out, "fi_outcomes", "\n".join(lines))


def table_sdc_per_benchmark(outcomes, benches, out, model):
    by = {(r["benchmark"], r["config"], r["model"]): r for r in outcomes}
    lines = ["| benchmark | " + " | ".join(CONFIGS) + " |", "|---" + "|---:" * len(CONFIGS) + "|"]
    for b in benches:
        cells = []
        for conf in CONFIGS:
            r = by.get((b, conf, model))
            cells.append(pct(int(r["sdc"]) / int(r["n"])) if r and int(r["n"]) else "-")
        lines.append("| %s | %s |" % (b, " | ".join(cells)))
    write(out, "fi_sdc_%s" % model, "\n".join(lines) + "\n")


# ------------------------------------------------------------------ overhead
def overheads(metrics, benches):
    """config -> {benchmark: (size ratio, time ratio, dynamic instr ratio)}"""
    by = {(r["benchmark"], r["config"]): r for r in metrics}
    res = defaultdict(dict)
    for b in benches:
        base = by[(b, "baseline")]
        for conf in CONFIGS:
            r = by[(b, conf)]
            res[conf][b] = (int(r["text_bytes"]) / int(base["text_bytes"]),
                            int(r["time_median_us"]) / int(base["time_median_us"]),
                            int(r["dyn_app"]) / int(base["dyn_app"]))
    return res


def fig_overhead(ovh, benches, out):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2), sharey=True)
    ypos = list(range(len(CONFIGS)))[::-1]
    for ax, idx, title in ((axes[0], 0, "Code size (.text), x baseline"),
                           (axes[1], 2, "Executed instructions, x baseline")):
        for y, conf in zip(ypos, CONFIGS):
            vals = [ovh[conf][b][idx] for b in benches]
            g = gmean(vals)
            ax.barh(y, g, height=0.5, color=SERIES[0], edgecolor=SURFACE, linewidth=1)
            ax.scatter(vals, [y] * len(vals), s=14, color=INK2, zorder=3, linewidths=0)
            ax.text(max(vals) + 0.12, y, "%.2fx" % g, va="center", fontsize=8, color=INK2)
        ax.axvline(1, color=AXIS, linewidth=0.8)
        ax.set_title(title, loc="left", fontsize=10, color=INK, pad=8)
        style(ax)
        ax.spines["left"].set_visible(False)
        ax.set_xlim(0, max(max(v[idx] for v in ovh[c].values()) for c in CONFIGS) * 1.18)
    axes[0].set_yticks(ypos)
    axes[0].set_yticklabels(CONFIGS)
    handles = [Patch(facecolor=SERIES[0], label="geometric mean"),
               plt.Line2D([], [], marker="o", linestyle="", color=INK2, markersize=4, label="one benchmark")]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False, bbox_to_anchor=(0.5, -0.04),
               fontsize=8.5)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    save(fig, out, "overhead")


def table_overhead(ovh, metrics, benches, out):
    lines = ["| configuration | code size | executed instructions | consistency checks |",
             "|---|---:|---:|---:|"]
    comps = defaultdict(int)
    for r in metrics:
        comps[r["config"]] += int(r["comparisons"])
    for conf in CONFIGS:
        sz = gmean([ovh[conf][b][0] for b in benches])
        dy = gmean([ovh[conf][b][2] for b in benches])
        lines.append("| %s | %.2fx | %.2fx | %d |" % (conf, sz, dy, comps[conf]))
    write(out, "overhead", "\n".join(lines) + "\n")
    lines = ["| benchmark | baseline .text (B) | baseline instructions | " +
             " | ".join(c for c in CONFIGS[1:]) + " |", "|---|---:|---:" + "|---:" * (len(CONFIGS) - 1) + "|"]
    by = {(r["benchmark"], r["config"]): r for r in metrics}
    for b in benches:
        base = by[(b, "baseline")]
        lines.append("| %s | %s | %s | %s |" % (b, "{:,}".format(int(base["text_bytes"])),
                                                "{:,}".format(int(base["dyn_app"])),
                                                " | ".join("%.2f" % ovh[c][b][2] for c in CONFIGS[1:])))
    write(out, "overhead_per_benchmark", "\n".join(lines) + "\n")


def table_mwtf(agg, ovh, benches, out):
    """Mean work to failure gain: SDC per run is proportional to (SDC rate x
    number of executed instructions), faults being uniform in time."""
    lines = ["| configuration | " + " | ".join("%s: SDC reduction / MWTF gain" % m for m, _ in MODELS) + " |",
             "|---" + "|---:" * len(MODELS) + "|"]
    for conf in CONFIGS:
        cells = []
        for model, _ in MODELS:
            base, c = agg[("baseline", model)], agg[(conf, model)]
            sb, sc = base["sdc"] / base["n"], c["sdc"] / c["n"]
            dyn = gmean([ovh[conf][b][2] for b in benches])
            if sc == 0:
                cells.append("no SDC")
            else:
                cells.append("%.1fx / %.1fx" % (sb / sc, sb / (sc * dyn)))
        lines.append("| %s | %s |" % (conf, " | ".join(cells)))
    write(out, "mwtf", "\n".join(lines) + "\n")


def table_before_after(before, after, out, confs=("EDDI+RASM", "EDDI+RACFED")):
    """SDC and detection rates of the configurations changed by a fix."""
    lines = ["| configuration | fault model | SDC before | SDC after | detected (CFC) before | detected (CFC) after |",
             "|---|---|---:|---:|---:|---:|"]
    for conf in confs:
        for model, title in MODELS:
            b, a = before[(conf, model)], after[(conf, model)]
            lines.append("| %s | %s | %s%% | %s%% | %s%% | %s%% |" % (
                conf, title, pct(b["sdc"] / b["n"], 2), pct(a["sdc"] / a["n"], 2),
                pct(b["detected_cfc"] / b["n"]), pct(a["detected_cfc"] / a["n"])))
    write(out, "fi_before_after", "\n".join(lines) + "\n")


def fig_tradeoff(agg, ovh, benches, out):
    fig, ax = plt.subplots(figsize=(6.4, 4.4))
    base = agg[("baseline", "reg")]
    for conf in CONFIGS:
        c = agg[(conf, "reg")]
        x = gmean([ovh[conf][b][2] for b in benches])
        y = c["sdc"] / c["n"]
        lo, hi = wilson(c["sdc"], c["n"])
        ax.plot([x, x], [100 * lo, 100 * hi], color=AXIS, linewidth=2, solid_capstyle="round")
        ax.scatter([x], [100 * y], s=36, color=SERIES[0], edgecolors=SURFACE, linewidths=1.5, zorder=3)
        dx = 0.05
        ax.text(x + dx, 100 * y, conf, fontsize=8, color=INK2, va="center")
    ax.set_xlabel("executed instructions (geometric mean, x baseline)")
    ax.set_ylabel("SDC rate, register bit-flips (%)")
    ax.set_title("Silent data corruptions vs. cost (95% Wilson interval)", loc="left", fontsize=10, pad=8)
    ax.set_ylim(bottom=0)
    style(ax, "both")
    save(fig, out, "tradeoff")


# ------------------------------------------------------------ compatibility
def compat(matrices, out):
    data = {name: read_csv(os.path.join(d, "matrix.csv")) for name, d in matrices}
    datas = []
    for r in next(iter(data.values())):
        if r["data"] not in datas:
            datas.append(r["data"])
    cfcs = ["--no-cfc", "--cfcss", "--rasm", "--racfed", "--inter-rasm"]
    lines = ["| data technique | " + " | ".join("%s: pass" % n for n, _ in matrices) + " |",
             "|---" + "|---:" * len(matrices) + "|"]
    totals = {}
    for d in datas:
        cells = []
        for name, _ in matrices:
            rows = [r for r in data[name] if r["data"] == d]
            ok = sum(r["outcome"] == "pass" for r in rows)
            cells.append("%d / %d" % (ok, len(rows)))
        lines.append("| `%s` | %s |" % (d, " | ".join(cells)))
    for name, _ in matrices:
        ok = sum(r["outcome"] == "pass" for r in data[name])
        totals[name] = (ok, len(data[name]))
    lines.append("| **total** | %s |" % " | ".join("**%d / %d**" % totals[n] for n, _ in matrices))
    write(out, "compat_by_technique", "\n".join(lines) + "\n")

    # outcome classes per checkout
    lines = ["| outcome | " + " | ".join(n for n, _ in matrices) + " |", "|---" + "|---:" * len(matrices) + "|"]
    classes = sorted({r["outcome"] for rows in data.values() for r in rows})
    for o in classes:
        lines.append("| %s | %s |" % (o, " | ".join(str(sum(r["outcome"] == o for r in data[n]))
                                                     for n, _ in matrices)))
    write(out, "compat_outcomes", "\n".join(lines) + "\n")

    # per test
    tests = []
    for r in next(iter(data.values())):
        if r["test"] not in tests:
            tests.append(r["test"])
    lines = ["| test | " + " | ".join(n for n, _ in matrices) + " |", "|---" + "|---:" * len(matrices) + "|"]
    for t in tests:
        lines.append("| %s | %s |" % (t, " | ".join("%d / %d" % (
            sum(r["outcome"] == "pass" for r in data[n] if r["test"] == t),
            sum(1 for r in data[n] if r["test"] == t)) for n, _ in matrices)))
    write(out, "compat_by_test", "\n".join(lines) + "\n")

    # heatmap: pass count over the tests, per (data technique, cfc)
    fig, axes = plt.subplots(1, len(matrices), figsize=(5.2 * len(matrices), 4.6), sharey=True)
    if len(matrices) == 1:
        axes = [axes]
    ntests = len(tests)
    for ax, (name, _) in zip(axes, matrices):
        for i, d in enumerate(datas):
            for j, c in enumerate(cfcs):
                ok = sum(r["outcome"] == "pass" for r in data[name] if r["data"] == d and r["cfc"] == c)
                level = min(len(SEQ) - 1, int(ok / ntests * (len(SEQ) - 1) + 0.5))
                ax.add_patch(plt.Rectangle((j, len(datas) - 1 - i), 0.94, 0.9, color=SEQ[level]))
                ax.text(j + 0.47, len(datas) - 1 - i + 0.45, str(ok), ha="center", va="center", fontsize=7.5,
                        color=ink_on(SEQ[level]))
        ax.set_xlim(0, len(cfcs))
        ax.set_ylim(0, len(datas))
        ax.set_xticks([j + 0.47 for j in range(len(cfcs))])
        ax.set_xticklabels([c.replace("--", "") for c in cfcs], rotation=0, fontsize=8)
        ax.set_yticks([len(datas) - 1 - i + 0.45 for i in range(len(datas))])
        ax.set_yticklabels([d.replace("--", "").replace(" ", " ") for d in datas], fontsize=8)
        ax.set_title("%s: %d / %d builds pass" % (name, totals[name][0], totals[name][1]), loc="left",
                     fontsize=10, pad=8)
        for side in ax.spines.values():
            side.set_visible(False)
        ax.tick_params(length=0)
    fig.text(0.01, -0.02, "Each cell: number of the %d benchmarks whose hardened build prints the same output "
             "as the unhardened one (%s = more)." % (ntests, "darker" if SUFFIX == "" else "brighter"),
             fontsize=8, color=MUTED)
    fig.tight_layout()
    save(fig, out, "compat")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", default=None)
    ap.add_argument("--matrix", action="append", default=[], help="name=<dir with matrix.csv>")
    ap.add_argument("--out", required=True)
    ap.add_argument("--before", default=None,
                    help="outcomes of the same campaign before a fix, to compare EDDI+RASM and EDDI+RACFED")
    args = ap.parse_args()
    for theme in ("light", "dark"):
        set_theme(theme)
        tables = theme == "light"  # the tables do not depend on the theme
        if args.campaign:
            outcomes = read_csv(os.path.join(args.campaign, "outcomes.csv"))
            metrics = read_csv(os.path.join(args.campaign, "metrics.csv"))
            benches = []
            for r in metrics:
                if r["benchmark"] not in benches:
                    benches.append(r["benchmark"])
            agg = aggregate(outcomes)
            ovh = overheads(metrics, benches)
            fig_outcomes(agg, benches, args.out)
            fig_overhead(ovh, benches, args.out)
            fig_tradeoff(agg, ovh, benches, args.out)
            if tables:
                table_outcomes(agg, args.out)
                for model, _ in MODELS:
                    table_sdc_per_benchmark(outcomes, benches, args.out, model)
                table_overhead(ovh, metrics, benches, args.out)
                table_mwtf(agg, ovh, benches, args.out)
                if args.before:
                    before = aggregate(read_csv(os.path.join(args.before, "outcomes.csv")))
                    table_before_after(before, agg, args.out)
        if args.matrix:
            compat([m.split("=", 1) for m in args.matrix], args.out)


if __name__ == "__main__":
    main()
