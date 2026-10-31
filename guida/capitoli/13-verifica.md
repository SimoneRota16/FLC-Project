# Appendice. La verifica dei fatti

Prima della consegna è stato ricontrollato tutto quello che affermano il
report, questa guida, le slide e i README: ogni numero, ogni comportamento
descritto e ogni citazione. Questa appendice dice cosa è stato controllato,
con quale fonte, e cosa è stato corretto. La verifica è stata fatta il 31
ottobre 2026 sulla versione finale del progetto (quella con la sola
correzione di RASM).

## A.1 Il metodo

- **Numeri.** Ricalcolati da zero dai file dei risultati con uno script
  indipendente da `analyze.py`, `guida/verifica_numeri.py`, e confrontati con
  le tabelle del report, i capitoli 7-11 della guida e le slide, con lo
  stesso arrotondamento (per eccesso sul 5). Lo potete rilanciare voi:
  `python3 guida/verifica_numeri.py ASPIS-Project` (aggiungendo la cartella
  della campagna ricalcola anche le parti che richiedono gli eseguibili).
- **Comportamenti.** Rifatti davvero: il riproduttore compilato e lanciato,
  le patch applicate su un clone pulito, una parte degli esperimenti
  ripetuta, gli eseguibili disassemblati.
- **Affermazioni sul codice di ASPIS.** Lette nei sorgenti del commit
  `b66a090`.
- **Citazioni e fonti.** Confrontate con i documenti originali.

Legenda: ✓ confermato; **corretto** = era sbagliato ed è stato corretto (i
dettagli in A.9).

## A.2 La fault injection

| Affermazione | Fonte del controllo | Esito |
|---|---|---|
| 48.000 esperimenti più 8000 prima della correzione, tutti con il guasto iniettato | righe di `raw.csv.gz` e `before_fix/raw.csv.gz` | ✓ |
| SDC dei bit-flip nei registri: 1,43% (baseline), 0,20% (EDDI), 0,80% (CFCSS), 0,60% (RASM), 0,03% e 0,05% (EDDI con CFCSS e con RASM), con gli intervalli di Wilson delle tabelle | `outcomes.csv`, ricalcolo | ✓ |
| SDC dei salti invertiti: 80,30%, 17,80%, 30,00%, 0,88%, 7,80%, 0,00% | `outcomes.csv`, ricalcolo | ✓ |
| EDDI+RASM prima della correzione: 407 SDC (10,18%) e 35,1% rilevati dalle firme; dopo: 0 SDC e 65,0% | `before_fix/outcomes.csv` | ✓ |
| Le tabelle per applicazione (report 5.5, guida 11.5) | `outcomes.csv`, ricalcolo | ✓ |
| Crash della baseline: 479, di cui rsp 52% e rbp 36% (insieme 88%) | `raw.csv.gz` | ✓ |
| Costo: EDDI 3,74x istruzioni e 9,27x codice, CFCSS 1,65x, RASM 2,33x, EDDI+CFCSS 5,46x, EDDI+RASM 5,95x; 1283 controlli; EDDI tra 3,56x e 4,12x | `metrics.csv`, media geometrica | ✓ |
| Un esperimento dura in media circa 60 ms | `time_us`: media 62,6 ms, mediana 31,3 ms | ✓ |
| Salti dei controlli: 76,3% con EDDI, 62,4% con CFCSS, 67,4% con RASM | `check_jumps.py` sugli eseguibili della campagna | ✓ |
| EDDI e CFCSS rilevano quasi solo i salti dei loro controlli | classificazione dei salti colpiti: tutti i 2481 rilevamenti di CFCSS e 3066 dei 3126 di EDDI sono salti dei controlli | ✓ (aggiunto alla guida, cap. 11.3) |
| Le 35 SDC di RASM vengono tutte da un solo salto di `load_at` | `sdc_sites.py`: tutte al `jne` di `0x1de8`; nel disassemblato la funzione (`__unnamed_8`) confronta con `0x4b0` = 1200 e `0x514` = 1300 | ✓ |
| Con EDDI la `select` di `load_at` diventa due salti, uno per copia, e la loro inversione viene rilevata | disassemblato di `pid_control` con EDDI: 33 rilevamenti ai due salti | ✓ |
| Le 407 SDC prima della correzione sono tutte su salti verso blocchi che scrivono una costante nella firma; in 406 casi entrambi i successori, in 1 solo uno | disassemblato degli eseguibili senza correzione: nell'unico caso l'altro successore legge la firma per controllarla | ✓ |
| Gli esperimenti sono ripetibili | rilanciati 3 blocchi da 100 esperimenti con gli stessi semi: 300 risultati su 300 identici (tempo escluso) | ✓ |
| Ricompilando, l'eseguibile di EDDI può cambiare un poco | tre compilazioni di `aes128` con EDDI: stessa dimensione e stessi 284 controlli, ma codice diverso | ✓ |

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
| 645.668, 367.759, 170.974 e 477.391 istruzioni eseguite senza protezione | `metrics.csv` (profilo della golden run) | ✓ |
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

La campagna principale è durata circa 18 minuti su 4 core (circa 6 di
compilazione e golden run e 12 di esperimenti, dai tempi dei file prodotti);
quella senza correzione circa 5 minuti. Report e guida dicevano "circa 25
minuti": **corretto** in "circa 20 minuti". I tempi dipendono comunque dalla
macchina.

## A.9 Cosa è stato corretto

In questa verifica:

- **report**: durata della campagna (da 25 a 20 minuti); nel riassunto "0,9%"
  diventa "0,88%", come nel resto del report;
- **guida, capitoli 11 e 17** (risultati e domande): avevano ancora i numeri
  della seconda versione (per esempio 0,15% invece di 0,20%, 421 SDC invece di
  407), ora aggiornati;
- **guida, capitoli 8, 9 e 10**: i numeri del bug di RASM, l'output reale di
  `sdc_sites.py`, il profilo e le righe CSV d'esempio presi dagli eseguibili
  finali, gli esempi di intervalli e di medie geometriche; i rimandi al
  capitolo 8.4, che non esiste più, ora puntano all'8.3;
- **guida, capitolo 11.5**: diceva che le applicazioni si comportano in modo
  simile, ma nella baseline dei salti invertiti le differenze (dal 65,8% al
  90,4%) sono reali; ora lo dice;
- **guida, capitolo 1**: la frase sulla chiamata ora riporta fedelmente il
  messaggio dei supervisori (il report serve per la valutazione), e un costo
  di 3,7 volte non è più descritto come "raddoppia abbondantemente";
- **README**: `aspis-integration/` era descritto con quattro patch e due
  riproduttori (la versione precedente): ora due patch, il bug report e un
  riproduttore; aggiunto in `results/README.md` il log della prima versione
  delle applicazioni;
- **slide**: la descrizione di FuncRetToRef è stata resa precisa.

Nelle verifiche delle versioni precedenti erano già stati corretti: la
citazione dei supervisori nel report (ora testuale), le descrizioni di FDSC e
REDDI, il numero di righe di `EDDI.cpp`, la dimensione di LLVM e
l'arrotondamento delle tabelle (ora per eccesso sul 5: 35,05% diventa 35,1%).

## A.10 Cosa resta fuori

- La dimensione dello scaricamento di LLVM (circa 2 GB) non è stata
  ricontrollata in questa verifica.
- La stima del lavoro (circa 75-90 ore in due, con il progetto ridotto) è
  una stima, non una misura.
- I numeri della campagna valgono per questi eseguibili: ricompilando, il
  codice prodotto da EDDI cambia un poco (A.2) e i risultati possono
  variare di qualche caso.
