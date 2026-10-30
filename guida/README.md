# Guida al progetto (in italiano)

`guida.pdf` spiega tutto il progetto partendo da zero: i concetti del corso
che servono (compilatori, LLVM, guasti transitori, tecniche di protezione),
il lavoro fatto (ASPIS, applicazioni, test, bug, iniettore, campagna,
risultati), come rifare gli esperimenti e le domande probabili all'orale.

I sorgenti sono in `capitoli/` (Markdown, uno per capitolo); il PDF si
rigenera con `python3 build.py` (servono pandoc e Node.js con Playwright).
