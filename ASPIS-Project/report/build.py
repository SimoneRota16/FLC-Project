#!/usr/bin/env python3
"""Builds the report: report.md + the generated tables -> report.html
(pandoc) -> report.pdf (Chromium through Playwright), and report.web.html, a
self-contained page (figures inlined, light and dark theme) to publish.

Usage: build.py [--no-pdf]

{{table:NAME}} in report.md is replaced by tables/NAME.md, produced by
../fault_injection/analyze.py (and by the reproducers runner).
"""
import argparse
import base64
import os
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# pandoc gives a pipe table relative column widths (from the dashes of its
# separator line) when a row is longer than --columns: with a large value the
# browser sizes the columns to their content instead
PANDOC_COLUMNS = 10000
# tables with more rows than this may be split across pages in the PDF
LONG_TABLE_ROWS = 15

PDF_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + process.argv[2], { waitUntil: 'load' });
  await page.emulateMedia({ media: 'print' });
  await page.pdf({
    path: process.argv[3], format: 'A4', printBackground: true, preferCSSPageSize: true,
    displayHeaderFooter: true, headerTemplate: '<span></span>',
    footerTemplate: '<div style="width:100%;font-family:Inter,sans-serif;font-size:7.5pt;color:#898781;' +
      'text-align:center;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>',
  });
  await browser.close();
})();
"""

WEB_TEMPLATE = """<title>$pagetitle$</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&display=swap">
<style>
$css$
</style>
<div class="page">
<header class="masthead">
<p class="kicker">Formal Languages and Compilers &middot; Politecnico di Milano &middot; A.Y. 2026/27</p>
<h1>$title$</h1>
<p class="subtitle">$subtitle$</p>
<p class="byline">$for(author)$$author$$sep$, $endfor$</p>
<p class="supervisors">Supervisors: Davide Baroffio, Emilio Corigliano</p>
</header>
<details class="toc" open>
<summary>Contents</summary>
$table-of-contents$
</details>
<main>
$body$
</main>
</div>
"""

WEB_CSS = """
/* Layout: one reading column, tables and code scroll inside their own box. */
:root {
  --bg: #fcfcfb; --fg: #1b1b19; --fg-2: #52514e; --muted: #7a7973; --rule: #e1e0d9;
  --accent: #256abf; --code-bg: #f1f0ec; --row: #f6f6f3; --fig-bg: #ffffff;
  --serif: "Source Serif 4", "Charter", Georgia, serif;
  --sans: "IBM Plex Sans", "Helvetica Neue", Arial, sans-serif;
  --mono: "IBM Plex Mono", "SFMono-Regular", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #1a1a19; --fg: #ecebe7; --fg-2: #c3c2b7; --muted: #8f8e88; --rule: #34342f;
    --accent: #6da7ec; --code-bg: #24241f; --row: #20201d; --fig-bg: #f4f3ef;
    color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --bg: #1a1a19; --fg: #ecebe7; --fg-2: #c3c2b7; --muted: #8f8e88; --rule: #34342f;
  --accent: #6da7ec; --code-bg: #24241f; --row: #20201d; --fig-bg: #f4f3ef;
  color-scheme: dark;
}
body { background: var(--bg); color: var(--fg); font-family: var(--serif); font-size: 17px; line-height: 1.6; }
.page {
  max-width: 46rem; margin: 0 auto;
  padding-left: max(16px, env(safe-area-inset-left, 0px));
  padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 2.5rem 5rem;
}
.masthead { border-bottom: 1px solid var(--rule); padding-bottom: 1.5rem; margin-bottom: 1.5rem; }
.kicker { font-family: var(--sans); font-size: 0.72rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin: 0 0 1rem; }
.masthead h1 { font-family: var(--sans); font-weight: 600; font-size: clamp(1.9rem, 5vw, 2.6rem); line-height: 1.12; letter-spacing: -0.015em; margin: 0; text-wrap: balance; }
.subtitle { font-size: 1.15rem; color: var(--fg-2); margin: 0.5rem 0 1.2rem; }
.byline { font-family: var(--sans); font-weight: 500; margin: 0; }
.supervisors { font-family: var(--sans); font-size: 0.85rem; color: var(--fg-2); margin: 0.2rem 0 0; }
.toc { font-family: var(--sans); font-size: 0.88rem; border-bottom: 1px solid var(--rule); padding-bottom: 1rem; margin-bottom: 1rem; }
.toc summary { cursor: pointer; font-weight: 600; color: var(--fg-2); }
.toc ul { list-style: none; padding-left: 0; margin: 0.5rem 0 0; }
.toc ul ul { padding-left: 1.1rem; margin: 0; }
.toc li { margin: 0.15rem 0; }
.toc a { color: var(--fg); text-decoration: none; }
.toc a:hover, .toc a:focus-visible { color: var(--accent); }
main h1, main h2, main h3 { font-family: var(--sans); font-weight: 600; line-height: 1.25; text-wrap: balance; }
main h1 { font-size: 1.45rem; margin: 3rem 0 0.8rem; padding-top: 0.6rem; border-top: 1px solid var(--rule); }
main h2 { font-size: 1.12rem; margin: 2rem 0 0.5rem; }
main h3 { font-size: 1rem; margin: 1.5rem 0 0.4rem; }
main p { margin: 0.7rem 0; }
main a { color: var(--accent); }
main a:focus-visible, .toc summary:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
main ul, main ol { padding-left: 1.3rem; }
main li { margin: 0.3rem 0; }
code { font-family: var(--mono); font-variant-ligatures: none; font-size: 0.84em; background: var(--code-bg); padding: 0.08em 0.3em; border-radius: 3px; }
pre { font-family: var(--mono); font-variant-ligatures: none; font-size: 0.8rem; line-height: 1.45; background: var(--code-bg); padding: 0.9rem 1rem; border-radius: 4px; overflow-x: auto; }
pre code { background: none; padding: 0; font-size: inherit; }
.table-wrap { overflow-x: auto; margin: 1.2rem 0 0.4rem; }
table { border-collapse: collapse; font-family: var(--sans); font-size: 0.8rem; line-height: 1.35; min-width: 100%; font-variant-numeric: tabular-nums; }
.table-caption { font-family: var(--sans); font-size: 0.78rem; line-height: 1.45; color: var(--fg-2); margin: 0.5rem 0 1.4rem; }
thead th { text-align: left; font-weight: 600; color: var(--fg-2); border-bottom: 1px solid var(--muted); white-space: nowrap; }
th, td { padding: 0.35rem 0.6rem; vertical-align: top; }
td[style*="right"] { white-space: nowrap; }
tbody tr { border-bottom: 1px solid var(--rule); }
tbody tr:nth-child(even) { background: var(--row); }
figure { margin: 1.8rem 0; }
/* the figures are drawn on white: in the dark theme they sit on a light card */
figure img { display: block; width: 100%; height: auto; border-radius: 4px; background: var(--fig-bg); padding: 6px; box-sizing: border-box; }
.fig-scroll { overflow-x: auto; }
.fig-scroll.wide img { min-width: 640px; }
figcaption { font-family: var(--sans); font-size: 0.78rem; color: var(--fg-2); margin-top: 0.5rem; }
@media (max-width: 480px) { body { font-size: 16px; } }
"""


def web_page(md_path, out_path):
    """Self-contained page for the Artifact viewer: no head/body tags (the
    viewer adds them), fonts from Google Fonts, figures as data URIs."""
    tpl = os.path.join(HERE, ".web.tpl")
    with open(tpl, "w") as f:
        f.write(WEB_TEMPLATE.replace("$css$", WEB_CSS))
    try:
        body = subprocess.run(["pandoc", md_path, "--from",
                               "markdown+pipe_tables+table_captions+implicit_figures", "--to", "html5",
                               "--columns", str(PANDOC_COLUMNS), "--standalone", "--template", tpl, "--toc", "--toc-depth=2",
                               "--no-highlight", "--metadata", "pagetitle=Hardening C applications with ASPIS"],
                              check=True, capture_output=True, text=True, cwd=HERE).stdout
    finally:
        os.remove(tpl)

    def data_uri(name):
        with open(os.path.join(HERE, "figures", name + ".png"), "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()

    def figure(m):
        name, rest = m.group(1), m.group(2)
        with open(os.path.join(HERE, "figures", name + ".png"), "rb") as f:
            width, height = struct.unpack(">II", f.read(24)[16:24])
        # on a phone the figures with several panels scroll instead of shrinking
        wide = " wide" if width > 1.8 * height else ""
        return '<div class="fig-scroll%s"><img src="%s"%s</div>' % (wide, data_uri(name), rest)
    body = re.sub(r'<img src="figures/([a-z_0-9]+)\.svg"([^>]*>)', figure, body)

    def table(m):
        # the caption goes below the scrolling box, so that it wraps to the width of the page
        html = m.group(0)
        cap = re.search(r"<caption>(.*?)</caption>\s*", html, flags=re.S)
        if cap:
            html = html.replace(cap.group(0), "", 1)
        return '<div class="table-wrap">%s</div>%s' % (
            html, '<p class="table-caption">%s</p>' % cap.group(1) if cap else "")
    body = re.sub(r"<table>.*?</table>", table, body, flags=re.S)
    with open(out_path, "w") as f:
        f.write(body)


def mark_long_tables(path):
    """class="long" on the tables that the print style lets break across pages."""
    with open(path) as f:
        html = f.read()

    def mark(m):
        rows = m.group(0).count("<tr")
        return m.group(0).replace("<table>", '<table class="long">', 1) if rows > LONG_TABLE_ROWS else m.group(0)
    with open(path, "w") as f:
        f.write(re.sub(r"<table>.*?</table>", mark, html, flags=re.S))


def expand(text):
    def table(m):
        path = os.path.join(HERE, "tables", m.group(1) + ".md")
        if not os.path.exists(path):
            sys.exit("missing table %s (run analyze.py first)" % path)
        return open(path).read().strip()
    text = re.sub(r"\{\{table:([a-z_0-9]+)\}\}", table, text)
    left = re.findall(r"\{\{[^}]*\}\}", text)
    if left:
        sys.exit("unresolved placeholders: %s" % ", ".join(sorted(set(left))))
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--no-pdf", action="store_true")
    args = ap.parse_args()
    src = expand(open(os.path.join(HERE, "report.md")).read())
    full = os.path.join(HERE, "report.full.md")
    with open(full, "w") as f:
        f.write(src)
    html = os.path.join(HERE, "report.html")
    common = ["pandoc", full, "--from", "markdown+pipe_tables+table_captions+implicit_figures",
              "--to", "html5", "--columns", str(PANDOC_COLUMNS), "--standalone", "--toc", "--toc-depth=2", "--css", "style.css",
              "--metadata", "lang=en", "--resource-path", HERE]
    subprocess.run(common + ["-o", html], check=True, cwd=HERE)
    mark_long_tables(html)
    # self-contained copy (figures and style inlined), e.g. to publish it
    subprocess.run(common + ["--embed-resources", "-o", os.path.join(HERE, "report.standalone.html")],
                   check=True, cwd=HERE)
    web_page(full, os.path.join(HERE, "report.web.html"))
    os.remove(full)
    print("written", html)
    if not args.no_pdf:
        js = os.path.join(HERE, ".pdf.js")
        with open(js, "w") as f:
            f.write(PDF_JS)
        try:
            subprocess.run(["node", js, html, os.path.join(HERE, "report.pdf")], check=True, cwd=HERE)
        finally:
            os.remove(js)
        print("written", os.path.join(HERE, "report.pdf"))


if __name__ == "__main__":
    main()
