# Parte III. Pratica ed esame

# 12. L'integrazione in ASPIS

Il terzo obiettivo è portare le applicazioni nel branch principale di ASPIS
come test di regressione. Il lavoro è pronto in
`aspis-integration/patches/` come quattro *patch* di git:

| Patch | Contenuto |
|---|---|
| `0001-fix-EDDI-null-safe-...` | bug 1: controlli sicuri con i puntatori nulli (`EDDI.cpp`, `ASPIS.h`) |
| `0002-fix-EDDI-re-synchronise-...` | bug 2: nuova risincronizzazione dopo le chiamate esterne (`EDDI.cpp`) |
| `0003-fix-RASM-RACFED-check-...` | bug 3: controllo della firma nei blocchi di EDDI (`RASM.cpp`, `RACFED.cpp`) |
| `0004-test-add-the-applications-...` | le quattro applicazioni in `testing/tests/c/applications/` e le loro voci in `testing/config/tests.toml` |

**Cos'è una patch di git.** È un file di testo che contiene un commit: autore,
data, messaggio e le differenze (*diff*) dei file. Si crea con
`git format-patch` e si applica, ricreando lo stesso commit, con `git am`:

```bash
# come le abbiamo create, dal nostro clone di ASPIS con i 4 commit
git format-patch b66a090..HEAD -o patches/
# come si applicano su un clone pulito di ASPIS
git checkout b66a090
git am patches/*.patch
```

Ogni messaggio di commit spiega il problema e la correzione, così chi deve
accettare le modifiche può valutarle una per una. Abbiamo verificato che le
patch si applicano senza conflitti su `b66a090` e che il risultato è
identico alla versione di ASPIS usata per tutti gli esperimenti.

**Come proporle (quando deciderete di farlo).** Il modo normale è una *pull
request* su GitHub: si fa un *fork* di `HEAPLab/ASPIS`, si applicano le patch
su un branch del fork, lo si pubblica e si apre la pull request verso il
repository originale, descrivendo il lavoro (si può rimandare al report).
Conviene parlarne prima con i supervisori, che sono anche gli sviluppatori di
ASPIS: potrebbero preferire ricevere le correzioni separate dai test, o
discuterle durante la chiamata. Per ora le patch **non sono state inviate**.

# 13. Rifare tutto da zero

Requisiti: Linux x86-64 (anche WSL2 o una macchina virtuale), Python 3.11 o
successivo con `pytest`, `pytest-timeout` e `matplotlib`, CMake, Ninja, gcc;
per rigenerare il PDF del report anche `pandoc` e Node.js con Playwright.

```bash
# 1. LLVM 21.1.8 già compilato (circa 1 GB)
curl -LO https://github.com/llvm/llvm-project/releases/download/llvmorg-21.1.8/LLVM-21.1.8-Linux-X64.tar.xz
tar xf LLVM-21.1.8-Linux-X64.tar.xz            # <llvm> = la cartella estratta

# 2. ASPIS con le nostre patch (circa 1 minuto)
git clone --recursive https://github.com/HEAPLab/ASPIS && cd ASPIS
git checkout b66a090
git am <repo>/ASPIS-Project/aspis-integration/patches/*.patch
cmake -B build -G Ninja -DLLVM_DIR=<llvm>/lib/cmake/llvm && cmake --build build

# 3. i test di ASPIS (circa 9 minuti)
#    prima scrivere llvm_bin = "<llvm>/bin" in testing/config/llvm.toml
cd testing && pytest test.py -v > harness_fixed.log && cd ..

# 4. un programma a mano, per vedere cosa succede
./aspis.sh --llvm-bin <llvm>/bin --eddi --rasm <repo>/ASPIS-Project/benchmarks/aes128.c \
    -o aes128 --build-dir /tmp/aes --no-cleanup && ./aes128
less /tmp/aes/out.ll                           # l'IR finale

# 5. la campagna (circa 25 minuti con 4 core)
gcc -O2 -o <dir>/fi <repo>/ASPIS-Project/fault_injection/injector/fi.c
#    adattare i percorsi in fault_injection/campaign.toml, poi:
python3 <repo>/ASPIS-Project/fault_injection/campaign.py <repo>/ASPIS-Project/fault_injection/campaign.toml
python3 <repo>/ASPIS-Project/fault_injection/export.py <output della campagna> \
    <repo>/ASPIS-Project/results/fault_injection

# 6. tabelle, figure e report
cd <repo>/ASPIS-Project
python3 fault_injection/analyze.py --campaign results/fault_injection \
    --before results/fault_injection/before_fix --out report \
    --harness master=results/compatibility/harness_master.log.gz \
    --harness fixed=results/compatibility/harness_fixed.log.gz
python3 report/build.py
```

Per la parte "prima della correzione del bug 3" bisogna compilare un secondo
ASPIS con le sole patch 0001 e 0002 e lanciare la campagna con la sola
configurazione EDDI+RASM (le cartelle di output devono essere diverse). Per
il log dei test su `master` si lancia `pytest` su un ASPIS senza patch,
aggiungendo le nostre voci con `--tests-file config/tests.toml
<repo>/ASPIS-Project/aspis-integration/flc_tests.toml`.

Le golden run e gli esperimenti sono deterministici (stessi semi, indirizzi
fissi): rifacendo la campagna con gli stessi eseguibili si ottengono gli
stessi numeri. Ricompilando le applicazioni, però, l'eseguibile prodotto da
EDDI può cambiare un poco, perché EDDI visita le istruzioni in un ordine che
dipende dagli indirizzi di memoria del compilatore (usa un `std::set` di
puntatori); quindi anche i numeri possono variare di poco.

# 14. Mappa dei file

Tutti i percorsi sono relativi a `ASPIS-Project/`.

| File | Cosa contiene |
|---|---|
| `README.md` | presentazione del progetto e indice |
| `benchmarks/aes128.c`, `fft.c`, `huffman.c`, `pid_control.c` | le quattro applicazioni (capitolo 6) |
| `aspis-integration/README.md` | come applicare le patch |
| `aspis-integration/patches/0001...0004-*.patch` | le patch per ASPIS (capitolo 12) |
| `aspis-integration/flc_tests.toml` | le voci dei test aggiunte a `tests.toml` |
| `aspis-integration/reproducers/null_pointer.c`, `string_literal.c` | i riproduttori dei bug 1 e 2; `handlers.h` contiene i due gestori d'errore |
| `fault_injection/injector/fi.c` | l'iniettore (capitolo 9) |
| `fault_injection/campaign.py`, `campaign.toml` | la campagna (capitolo 10) |
| `fault_injection/export.py` | copia i risultati nel repository e crea `raw.csv.gz` |
| `fault_injection/analyze.py` | tabelle e figure del report |
| `fault_injection/sdc_sites.py` | dove sono avvenute le SDC (capitolo 8.4) |
| `results/README.md` | descrizione dei risultati |
| `results/compatibility/harness_master.log.gz`, `harness_fixed.log.gz` | i log dei test di ASPIS, prima e dopo le patch |
| `results/fault_injection/metrics.csv` | costo: dimensione, controlli, istruzioni eseguite |
| `results/fault_injection/outcomes.csv` | esiti per applicazione, configurazione, modello |
| `results/fault_injection/raw.csv.gz` | i 48.000 esperimenti, uno per riga |
| `results/fault_injection/before_fix/` | gli stessi file per EDDI+RASM prima della patch 0003 |
| `report/report.md` | il testo del report (Markdown, con i segnaposto `{{table:...}}` per le tabelle) |
| `report/build.py` | genera `report.html` e `report.pdf` (pandoc + Chromium) e la versione web |
| `report/style.css` | lo stile del report |
| `report/tables/`, `report/figures/` | tabelle e figure generate da `analyze.py` |
| `report/report.pdf` | **il report da consegnare** |

Nella radice del repository: `README.md`, la proposta del progetto (`FLC
Project Proposals AY 202627.txt`), le indicazioni dei supervisori
(`Buongiorno,.txt`) e, solo nel branch di lavoro, questa guida (`guida/`).

# 15. Cosa è stato tolto (la versione completa)

La prima versione del progetto, prima della riduzione, è nel commit
`e1d7e8b` del repository. Per vederla:

```bash
git show e1d7e8b:ASPIS-Project/report/report.pdf > report-completo.pdf
git checkout e1d7e8b      # tutto il repository com'era (poi: git checkout main)
```

o su GitHub, aprendo il commit `e1d7e8b` e scegliendo "Browse files".
Conteneva, in più rispetto alla versione attuale:

- **22 programmi** invece di 4: altre 4 applicazioni (un dizionario su albero
  binario di ricerca, un piccolo compilatore di espressioni con macchina
  virtuale, un risolutore LU, un filtro di Sobel) e 14 *microbenchmark*,
  ognuno dedicato a una caratteristica del C (puntatori a funzione richiamati
  dalla libreria, funzioni variadiche, struct passate per valore, array a
  lunghezza variabile, `setjmp`/`longjmp`, campi di bit, ...);
- **23 bug corretti** invece di 3, in una serie di 19 commit: tra gli altri,
  la deduzione dei tipi che non terminava con le struct ricorsive (il
  compilatore si bloccava), i puntatori a funzione passati a `qsort`, le
  inizializzazioni delle globali duplicate, le espressioni costanti annidate,
  `memmove`, le funzioni variadiche, gli array a lunghezza variabile, REDDI,
  i campi di bit, `setjmp`/`longjmp` nelle tecniche a firme, inter-RASM con le
  funzioni chiamate dalla libreria. Con quelle correzioni passavano tutte le
  1210 combinazioni dei 22 programmi (contro 435 sul branch principale) e 23
  combinazioni escluse dalle `black_list` di ASPIS;
- due **strumenti di test** propri, più robusti del sistema di test
  ufficiale;
- un **iniettore** più veloce, che usava i *breakpoint hardware* del
  processore (con la chiamata di sistema `perf_event_open`) invece di
  `int3`, e un terzo modello di guasto (salto a un indirizzo casuale);
- una **campagna di 240.900 esperimenti**: 8 applicazioni, 11 configurazioni
  (anche sEDDI, FDSC, inter-RASM, RACFED, EDDI+RACFED), 3 modelli di guasto, e
  un'analisi del rapporto costo/beneficio (*mean work to failure*);
- un report di 19 pagine.

È stato tolto perché richiederebbe a due studenti, a mano, diverse centinaia
di ore: molto più di quanto ci si aspetta da un progetto che vale il 30% di un
esame da 5 CFU. Le correzioni in più restano comunque utili: se un giorno
vorrete proporle ad ASPIS, sono tutte in quel commit
(`ASPIS-Project/aspis-integration/patches/`).
