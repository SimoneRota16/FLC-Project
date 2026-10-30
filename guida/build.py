#!/usr/bin/env python3
"""Costruisce la guida: capitoli/*.md (in ordine) -> guida.html (pandoc) ->
guida.pdf (Chromium attraverso Playwright, come il report).

Uso: python3 build.py [--no-pdf]
"""
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

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


def main():
    chapters = sorted(glob.glob(os.path.join(HERE, "capitoli", "*.md")))
    text = "\n\n".join(open(c).read() for c in chapters)
    left = re.findall("⟦[^⟧]*⟧", text)
    if left:
        sys.exit("segnaposto non risolti: %s" % ", ".join(left))
    # i titoli delle parti hanno uno stile proprio
    text = re.sub(r"^# (Parte [IVX]+\..*)$", r"# \1 {.parte .unnumbered}", text, flags=re.M)
    full = os.path.join(HERE, "guida.full.md")
    with open(full, "w") as f:
        f.write(text)
    html = os.path.join(HERE, "guida.html")
    try:
        subprocess.run(["pandoc", full, "--from", "markdown+pipe_tables+table_captions",
                        "--to", "html5", "--standalone", "--toc", "--toc-depth=2",
                        "--columns", "10000", "--css", "stile.css", "--embed-resources",
                        "--metadata", "lang=it", "-o", html], check=True, cwd=HERE)
    finally:
        os.remove(full)
    print("scritto", html)
    if "--no-pdf" not in sys.argv:
        js = os.path.join(HERE, ".pdf.js")
        with open(js, "w") as f:
            f.write(PDF_JS)
        try:
            subprocess.run(["node", js, html, os.path.join(HERE, "guida.pdf")], check=True, cwd=HERE)
        finally:
            os.remove(js)
        print("scritto", os.path.join(HERE, "guida.pdf"))


if __name__ == "__main__":
    main()
