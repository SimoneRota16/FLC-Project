# Appendice. La verifica dei fatti

Prima della consegna è stato ricontrollato tutto quello che affermano il
report, questa guida, le slide e i README: ogni numero, ogni comportamento
descritto e ogni citazione. Questa appendice dice cosa è stato controllato,
con quale fonte, e cosa è stato corretto. La verifica è stata fatta il 31
ottobre 2026 sulla versione finale del progetto (la sola correzione di RASM,
i guasti iniettati con gdb).

## A.1 Il metodo

- **Numeri.** Ricalcolati da zero dai file dei risultati con uno script
  indipendente da `analyze.py`, `guida/verifica_numeri.py`, e confrontati con
  le tabelle del report, i capitoli 7-11 della guida e le slide, con lo
  stesso arrotondamento (per eccesso sul 5). Lo potete rilanciare voi:
  `python3 guida/verifica_numeri.py ASPIS-Project` (aggiungendo la cartella di
  lavoro della campagna ricalcola anche le parti che richiedono gli
  eseguibili).
- **Comportamenti.** Rifatti davvero: il riproduttore compilato e lanciato,
  le patch applicate su un clone pulito, una parte degli esperimenti
  ripetuta, gli eseguibili disassemblati, il metodo di iniezione provato su
  casi noti.
- **Affermazioni sul codice di ASPIS.** Lette nei sorgenti del commit
  `b66a090`.
- **Citazioni e fonti.** Confrontate con i documenti originali.

Legenda: ✓ confermato; **corretto** = era sbagliato ed è stato corretto (i
dettagli in A.9).

## A.2 La fault injection

| Affermazione | Fonte del controllo | Esito |
|---|---|---|
| 24.000 esperimenti più 4000 prima della correzione; 11 bit-flip non iniettati (9 in `fft`, che chiama spesso la libreria matematica), esclusi dai conteggi | righe di `raw.csv.gz` e `before_fix/raw.csv.gz`, `outcomes.csv` | ✓ |
| SDC dei bit-flip nei registri: 2,11% (baseline), 0,00% (EDDI), 0,75% (CFCSS), 0,80% (RASM), 0,05% e 0,20% (EDDI con CFCSS e con RASM), con gli intervalli di Wilson delle tabelle | `outcomes.csv`, ricalcolo | ✓ |
| SDC dei salti invertiti: 79,30%, 18,75%, 29,05%, 0,70%, 7,70%, 0,00% | `outcomes.csv`, ricalcolo | ✓ |
| EDDI+RASM prima della correzione: 194 SDC (9,70%) e 36,4% rilevati dalle firme; dopo: 0 SDC e 67,1% | `before_fix/outcomes.csv` | ✓ |
| Le tabelle per applicazione (report 5.5, guida 11.5) | `outcomes.csv`, ricalcolo | ✓ |
| Crash della baseline: 286, di cui rsp 47% e rbp 42% (insieme 89%) | `raw.csv.gz` | ✓ |
| Costo: EDDI 3,74x istruzioni e 9,27x codice, CFCSS 1,65x, RASM 2,33x, EDDI+CFCSS 5,46x, EDDI+RASM 5,95x; 1283 controlli; EDDI tra 3,56x e 4,12x | `metrics.csv`, media geometrica | ✓ |
| Un esperimento dura in media circa 0,4 secondi | `time_ms`: media 376 ms, mediana 283 ms | ✓ |
| Salti dei controlli: 76,3% con EDDI, 62,4% con CFCSS, 67,4% con RASM | `check_jumps.py` sugli eseguibili della campagna | ✓ |
| EDDI e CFCSS rilevano quasi solo i salti dei loro controlli | classificazione dei salti colpiti: tutti i 1249 rilevamenti di CFCSS e 1517 dei 1543 di EDDI sono salti dei controlli | ✓ |
| Le 14 SDC di RASM vengono tutte da un solo salto di `load_at` | `sdc_sites.py`: tutte al `jne` di `0x1de8`; nel disassemblato la funzione (`__unnamed_8`) confronta con `0x4b0` = 1200 e `0x514` = 1300 | ✓ |
| Con EDDI la `select` di `load_at` diventa due salti, uno per copia, e la loro inversione viene rilevata | disassemblato di `pid_control` con EDDI: 11 rilevamenti ai due salti | ✓ |
| Le 194 SDC prima della correzione sono tutte su salti verso blocchi che scrivono una costante nella firma, in tutti i casi con entrambi i successori | disassemblato degli eseguibili senza correzione | ✓ |
| Gli esperimenti sono ripetibili | 30 esperimenti già fatti, rilanciati con gli stessi parametri: stesso esito, codice d'uscita e segnale in 30 casi su 30 | ✓ |
| Ricompilando, l'eseguibile di EDDI può cambiare un poco | tre compilazioni di `aes128` con EDDI: stessa dimensione e stessi 284 controlli, ma codice diverso | ✓ |

**Il metodo di iniezione.** Prima di usare gdb e valgrind abbiamo verificato
che facciano quello che diciamo:

| Affermazione | Fonte del controllo | Esito |
|---|---|---|
| valgrind conta le istruzioni eseguite correttamente | sui 24 programmi della campagna precedente, i totali di valgrind e del nostro vecchio iniettore (che eseguiva il programma un'istruzione alla volta) differiscono sempre di 12 istruzioni, quelle di `_init`, `_fini` e di un salto della PLT, che valgrind non attribuisce al programma; istruzione per istruzione i conteggi coincidono, tranne per la PLT, che valgrind conta insieme alle `call` | ✓ |
| Un breakpoint con *ignore count* `k`-1 ferma il programma alla `k`-esima esecuzione | sessione gdb del capitolo 9.3: con `ignore 1 1807` gdb riporta "breakpoint already hit 1808 times" | ✓ |
| Gli *hang* vengono rilevati | un programma con un ciclo infinito: ucciso dal processo di guardia (`SIGKILL`) e classificato come *hang* | ✓ |
| I risultati non dipendono dall'iniettore | per tutti i 14 tassi di SDC (6 configurazioni × 2 modelli, più EDDI+RASM senza correzione) gli intervalli al 95% della campagna con gdb e di quella precedente, fatta con il nostro iniettore, si sovrappongono | ✓ |

## A.3 I test di compatibilità

| Affermazione | Fonte del controllo | Esito |
|---|---|---|
| 52 test × 55 combinazioni = 2860 compilazioni per esecuzione | i tre log | ✓ |
| Prima versione su `master`: 100 combinazioni su 220; versione finale: 220 su 220, su `master` e con le patch | i tre log | ✓ |
| Test esistenti: 2453 superati, 33 falliti, 154 saltati, identici nei tre log | i tre log | ✓ |
| I 33 falliti sono tutti di `cpp_complex` | i log: 55 combinazioni meno le 22 della sua `black_list` | ✓ |
| I 154 saltati sono le combinazioni delle `black_list` | i log: 14 coppie test-tecnica del flusso × 11 opzioni dei dati | ✓ |
| Ogni esecuzione dura circa 9 minuti | ultima riga dei log: da 8 min 55 s a 9 min 13 s | ✓ |
| 11 opzioni dei dati × 5 del flusso, riferimento compilato con `clang++`, limite di 60 s | `testing/test.py` | ✓ |

## A.4 Le applicazioni

| Affermazione | Fonte del controllo | Esito |
|---|---|---|
| 329, 186, 225 e 159 righe | `wc -l` | ✓ |
| 645.656, 367.747, 170.962 e 477.379 istruzioni eseguite senza protezione | `metrics.csv` (conteggio di valgrind) | ✓ |
| La versione finale stampa esattamente lo stesso output della prima | le due versioni compilate con `gcc` e confrontate byte per byte | ✓ |
| Terminano con `SUCCESS` e codice 0; sono valide anche in C++; licenza MIT | esecuzione, `g++ -x c++`, intestazioni SPDX | ✓ |
| Le copie nella patch 0002 sono uguali a `benchmarks/` | confronto dei file | ✓ |

## A.5 Il bug di EDDI

| Affermazione | Fonte del controllo | Esito |
|---|---|---|
| Il riproduttore va in crash su `b66a090` con EDDI, sEDDI e FDSC, con qualunque tecnica del flusso, e stampa `hello` senza duplicazione | compilato e lanciato: *segmentation fault* (codice 139) con `--eddi`, `--seddi`, `--fdsc` e con le 4 varianti di EDDI per le 5 tecniche del flusso; `hello` con `--no-dup` | ✓ |
| Il comando del README del riproduttore funziona come scritto | eseguito tale e quale | ✓ |
| `fixFuncValsPassedByReference` legge un valore della dimensione di un puntatore dall'originale e lo scrive nella copia, per ogni operando con una copia | `passes/EDDI.cpp` | ✓ |
| Le nostre patch non correggono questo bug | il riproduttore va in crash anche con le patch | ✓ |

## A.6 La correzione di RASM e le patch

| Affermazione | Fonte del controllo | Esito |
|---|---|---|
| Le due patch si applicano con `git am` su un clone pulito di `b66a090` | applicate | ✓ |
| Il risultato è l'ASPIS usato per tutti gli esperimenti | confronto di `passes/` e `testing/` | ✓ |
| La correzione cambia una riga in `RASM.cpp` e una in `RACFED.cpp`, più un commento | la patch 0001 | ✓ |
| `EDDI.cpp` ha circa 2400 righe; la seconda versione vi aggiungeva circa 160 righe | 2441 righe; le due patch della seconda versione: 66 + 92 righe aggiunte | ✓ |
| DuplicateGlobals tiene coerenti le copie delle globali scritte da funzioni non duplicate; il passo `strip` toglie i nomi delle funzioni `static` | `passes/DuplicateGlobals.cpp`, `aspis.sh` | ✓ |

## A.7 Fonti e citazioni

| Affermazione | Fonte del controllo | Esito |
|---|---|---|
| Le frasi dei supervisori (uso dell'IA, chiamata, report) | `Buongiorno,.txt` | ✓ (corretta una parafrasi nel capitolo 1) |
| Articolo di ASPIS: ACM TODAES 29(5), articolo 91, 2024, doi 10.1145/3660524 | il link nell'e-mail dei supervisori | ✓ |
| EDDI e CFCSS: Oh, Shirvani, McCluskey, IEEE Transactions on Reliability 51(1), 2002; RASM: Vankeirsbilck et al., IEEE Transactions on Reliability 66(4), 2017 | riferimenti bibliografici | ✓ |
| LLVM 21.1.8 estratto occupa circa 11 GB | `du` | ✓ |

## A.8 I tempi

La campagna principale è durata circa 38 minuti su 4 core (pochi secondi per
compilazioni e golden run, il resto esperimenti, dai tempi del suo log);
quella senza correzione circa 6 minuti. Report e guida dicono "circa 40
minuti" per la campagna principale. La versione precedente, con il nostro
iniettore, ne richiedeva circa 18 per il doppio degli esperimenti: gdb è
circa sei volte più lento per esperimento. I tempi dipendono comunque dalla
macchina.

## A.9 Cosa è stato corretto

Nella verifica di questa versione:

- **report**: il numero di righe di `gdb_inject.py` (una prima stesura diceva
  "circa 80, metà commenti": sono 72, di cui 45 di codice) e la didascalia
  della tabella delle applicazioni (le istruzioni le conta valgrind, non più
  un profiler nostro);
- **guida, capitolo 9**: una prima stesura diceva che con un profilo corretto
  nessun esperimento resta "non iniettato"; invece 11 lo sono stati, per come
  valgrind conta le chiamate attraverso la PLT, e ora è spiegato;
- **guida, capitolo 17**: una risposta attribuiva a EDDI la percentuale della
  baseline, e un'altra diceva che EDDI+RASM lascia "quasi nessuna" SDC sui
  registri senza dire che non si distingue da EDDI da solo; corrette.

Nella verifica della versione precedente (commit `0609127`) erano stati
corretti: la durata della campagna nel report e nella guida; i capitoli 11 e
17 della guida, che avevano ancora numeri vecchi; i rimandi al capitolo 8.4;
il paragrafo sui risultati per applicazione; una parafrasi dei supervisori e
la descrizione di un costo nel capitolo 1; i README di `aspis-integration/` e
`results/`; la descrizione di FuncRetToRef nelle slide. Prima ancora: la
citazione dei supervisori nel report (ora testuale), le descrizioni di FDSC e
REDDI, il numero di righe di `EDDI.cpp`, la dimensione di LLVM e
l'arrotondamento delle tabelle (ora per eccesso sul 5: 35,05% diventa 35,1%).

## A.10 Cosa resta fuori

- La dimensione dello scaricamento di LLVM (circa 2 GB) non è stata
  ricontrollata in questa verifica.
- La stima del lavoro (circa 60-75 ore in due, con il progetto ridotto) è
  una stima, non una misura.
- I numeri della campagna valgono per questi eseguibili: ricompilando, il
  codice prodotto da EDDI cambia un poco (A.2) e i risultati possono
  variare di qualche caso.
- Sotto gdb il programma non gira esattamente come da solo: gdb aggiunge
  all'ambiente le variabili `LINES` e `COLUMNS`, e lo stack comincia 64 byte
  più in basso. Questo può cambiare di poco quali indirizzi sbagliati portano
  a un crash (nella campagna con gdb i crash della baseline sono il 14,3%,
  nella precedente il 12,0%), ma non il confronto tra le configurazioni, che
  girano tutte sotto gdb.
