# Parte III. Pratica ed esame

# 12. L'integrazione in ASPIS

Il terzo obiettivo è portare le applicazioni nel branch principale di ASPIS
come test di regressione. Il lavoro è pronto in `aspis-integration/`:

| File | Contenuto |
|---|---|
| `patches/0001-fix-RASM-RACFED-check-...` | la correzione del bug di RASM (`RASM.cpp`, `RACFED.cpp`, una riga ciascuno più un commento) |
| `patches/0002-test-add-the-applications-...` | le quattro applicazioni in `testing/tests/c/applications/` e le loro voci in `testing/config/tests.toml` |
| `bug_report.md` | il bug di EDDI, con riproduttore, causa e possibile correzione, pronto da aprire come *issue* |
| `reproducers/string_literal.c` | il riproduttore di cinque righe |

**Cos'è una patch di git.** È un file di testo che contiene un commit: autore,
data, messaggio e le differenze (*diff*) dei file. Si crea con
`git format-patch` e si applica, ricreando lo stesso commit, con `git am`:

```bash
# come le abbiamo create, dal nostro clone di ASPIS con i 2 commit
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
repository originale, descrivendo il lavoro (si può rimandare al report). Il
bug di EDDI si segnala aprendo una *issue* con il testo di `bug_report.md`.
Conviene parlarne prima con i supervisori, che sono anche gli sviluppatori di
ASPIS: potrebbero preferire ricevere la correzione separata dai test, o
discuterne durante la chiamata. Per ora **non è stato inviato nulla**.

# 13. Rifare tutto da zero

Requisiti: Linux x86-64 (anche WSL2 o una macchina virtuale), Python 3.11 o
successivo con `pytest`, `pytest-timeout` e `matplotlib`, CMake, Ninja, gcc;
per rigenerare il PDF del report anche `pandoc` e Node.js con Playwright.

```bash
# 1. LLVM 21.1.8 già compilato (circa 2 GB da scaricare, 11 GB estratto)
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

# 5. la campagna (circa 20 minuti con 4 core)
gcc -O2 -o <dir>/fi <repo>/ASPIS-Project/fault_injection/injector/fi.c
#    adattare i percorsi in fault_injection/campaign.toml, poi:
python3 <repo>/ASPIS-Project/fault_injection/campaign.py <repo>/ASPIS-Project/fault_injection/campaign.toml
python3 <repo>/ASPIS-Project/fault_injection/export.py <output della campagna> \
    <repo>/ASPIS-Project/results/fault_injection

# 6. tabelle, figure e report
cd <repo>/ASPIS-Project
python3 fault_injection/analyze.py --campaign results/fault_injection \
    --before results/fault_injection/before_fix --out report \
    --harness "first version, master=results/compatibility/harness_master_first_version.log.gz" \
    --harness "final, master=results/compatibility/harness_master.log.gz" \
    --harness "final, with patches=results/compatibility/harness_fixed.log.gz"
python3 report/build.py
```

Per la parte "prima della correzione di RASM" serve un secondo ASPIS, senza
patch (`b66a090` così com'è), con cui lanciare la campagna con la sola
configurazione EDDI+RASM (le cartelle di output devono essere diverse). Per
il log dei test su `master` si lancia `pytest` sull'ASPIS senza patch,
aggiungendo le nostre voci con `--tests-file config/tests.toml
<repo>/ASPIS-Project/aspis-integration/flc_tests.toml`; per quello della
prima versione delle applicazioni serve il codice di quella versione (commit
`7074cd6` del nostro repository).

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
| `aspis-integration/patches/0001-*.patch`, `0002-*.patch` | le patch per ASPIS (capitolo 12) |
| `aspis-integration/flc_tests.toml` | le voci dei test aggiunte a `tests.toml` |
| `aspis-integration/bug_report.md` | il bug report di EDDI (capitolo 8.2) |
| `aspis-integration/reproducers/string_literal.c` | il riproduttore del bug di EDDI; `handlers.h` contiene i due gestori d'errore |
| `fault_injection/injector/fi.c` | l'iniettore (capitolo 9) |
| `fault_injection/campaign.py`, `campaign.toml` | la campagna (capitolo 10) |
| `fault_injection/export.py` | copia i risultati nel repository e crea `raw.csv.gz` |
| `fault_injection/analyze.py` | tabelle e figure del report |
| `fault_injection/sdc_sites.py` | dove sono avvenute le SDC (capitolo 8.3) |
| `fault_injection/check_jumps.py` | quanti dei salti eseguiti appartengono ai controlli (capitolo 11.3) |
| `results/README.md` | descrizione dei risultati |
| `results/compatibility/harness_master_first_version.log.gz` | il log dei test con la prima versione delle applicazioni |
| `results/compatibility/harness_master.log.gz`, `harness_fixed.log.gz` | i log dei test con la versione finale, senza e con le patch |
| `results/fault_injection/metrics.csv` | costo: dimensione, controlli, istruzioni eseguite |
| `results/fault_injection/outcomes.csv` | esiti per applicazione, configurazione, modello |
| `results/fault_injection/raw.csv.gz` | i 48.000 esperimenti, uno per riga |
| `results/fault_injection/before_fix/` | gli stessi file per EDDI+RASM senza la correzione di RASM |
| `report/report.md` | il testo del report (Markdown, con i segnaposto `{{table:...}}` per le tabelle) |
| `report/build.py` | genera `report.html` e `report.pdf` (pandoc + Chromium) e la versione web |
| `report/style.css` | lo stile del report |
| `report/tables/`, `report/figures/` | tabelle e figure generate da `analyze.py` |
| `report/report.pdf` | **il report da consegnare** |

Nella radice del repository: `README.md`, la proposta del progetto (`FLC
Project Proposals AY 202627.txt`), le indicazioni dei supervisori
(`Buongiorno,.txt`) e, fuori dalla cartella del progetto, questa guida
(`guida/`).

# 15. Cosa è stato tolto (le versioni precedenti)

Il progetto è passato per tre versioni, tutte nella storia del repository:

| Versione | Commit | Cosa conteneva |
|---|---|---|
| prima (completa) | `e1d7e8b` | 22 programmi, 23 bug corretti, campagna di 240.900 esperimenti, report di 19 pagine |
| seconda | `7074cd6` | le quattro applicazioni attuali (nella prima versione delle stampe), tre bug corretti: due in EDDI e quello di RASM |
| terza (attuale) | `main` | le applicazioni che evitano il bug di EDDI, la sola correzione di RASM |

Per vedere una versione precedente:

```bash
git show e1d7e8b:ASPIS-Project/report/report.pdf > report-completo.pdf
git checkout 7074cd6      # tutto il repository com'era (poi: git checkout main)
```

o su GitHub, aprendo il commit e scegliendo "Browse files".

**La prima versione** conteneva, in più rispetto a quella attuale:

- **22 programmi** invece di 4: altre 4 applicazioni (un dizionario su albero
  binario di ricerca, un piccolo compilatore di espressioni con macchina
  virtuale, un risolutore LU, un filtro di Sobel) e 14 *microbenchmark*,
  ognuno dedicato a una caratteristica del C (puntatori a funzione richiamati
  dalla libreria, funzioni variadiche, struct passate per valore, array a
  lunghezza variabile, `setjmp`/`longjmp`, campi di bit, ...);
- **23 bug corretti**, in una serie di 19 commit: tra gli altri, la
  deduzione dei tipi che non terminava con le struct ricorsive (il
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
  un'analisi del rapporto costo/beneficio (*mean work to failure*).

**La seconda versione** correggeva, oltre a RASM, due bug di EDDI: quello
della copia dopo le chiamate di libreria (che ora evitiamo, capitolo 8.2) e
un bug dei controlli che leggevano attraverso puntatori nulli (per esempio
con `realloc(NULL, n)`), che le nostre applicazioni non attivano. Erano circa
160 righe di C++ dentro `EDDI.cpp`.

Le parti tolte richiederebbero a due studenti, a mano, molte più ore di
quante ne valga un progetto da 30% di un esame da 5 CFU, e sono le più
difficili da studiare e da difendere all'orale. Le correzioni restano
comunque utili: se un giorno vorrete proporle ad ASPIS, sono nei commit
indicati (`ASPIS-Project/aspis-integration/patches/`).
