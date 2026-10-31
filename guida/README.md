# Guida al progetto (in italiano)

`guida.pdf` spiega tutto il progetto partendo da zero: i concetti del corso
che servono (compilatori, LLVM, guasti transitori, tecniche di protezione),
il lavoro fatto (ASPIS, applicazioni, test, bug, iniettore, campagna,
risultati), come rifare gli esperimenti, cosa dire nella chiamata con i
supervisori, le domande probabili all'orale e, in appendice, la verifica dei
fatti (cosa è stato controllato, come e cosa è stato corretto).

- Slide per la chiamata con i supervisori:
  <https://claude.ai/artifact/R4PFNt1VCATSuovbDMCFzV> (private finché non le
  condividete).
- `verifica_numeri.py` ricalcola dai risultati tutti i numeri citati nel
  report, nella guida e nelle slide:
  `python3 guida/verifica_numeri.py ASPIS-Project`.

I sorgenti sono in `capitoli/` (Markdown, uno per capitolo); il PDF si
rigenera con `python3 build.py` (servono pandoc e Node.js con Playwright).
