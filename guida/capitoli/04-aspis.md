# Parte II. Il lavoro fatto

# 5. ASPIS in pratica

## 5.1 Il repository di ASPIS

ASPIS (*Automatic Software-based Protection and Integrity Suite*) è sviluppato
dal gruppo HEAPLab del Politecnico (articolo di riferimento: Baroffio,
Reghenzani, Fornaciari, ACM TODAES 2024) ed è su GitHub in `HEAPLab/ASPIS`.
Abbiamo lavorato sul commit `b66a090`, l'ultimo del branch principale quando
è iniziato il progetto. Le parti che ci interessano:

| Percorso | Contenuto |
|---|---|
| `aspis.sh` | lo script che compila un programma applicando le protezioni |
| `passes/EDDI.cpp` | EDDI e le sue varianti (sEDDI, FDSC, REDDI): circa 2000 righe |
| `passes/FuncRetToRef.cpp` | trasforma i valori di ritorno in parametri puntatore |
| `passes/DuplicateGlobals.cpp` | duplica le variabili globali |
| `passes/CFCSS.cpp`, `RASM.cpp`, `RACFED.cpp` | le tecniche di controllo del flusso (inter-RASM è RASM compilato con un'opzione) |
| `passes/ASPIS.h` | le dichiarazioni delle classi dei pass |
| `libs/TypeDeductionAnalysis/` | la libreria che deduce i tipi puntati (un *submodule* git) |
| `testing/` | il sistema di test: `test.py`, `config/tests.toml`, `tests/` con i programmi |

## 5.2 Compilare ASPIS

Serve LLVM 21.1.8 (scaricato già compilato), CMake e Ninja:

```bash
git clone --recursive https://github.com/HEAPLab/ASPIS
cd ASPIS && git checkout b66a090
cmake -B build -G Ninja -DLLVM_DIR=<llvm>/lib/cmake/llvm
cmake --build build
```

Il risultato sono le librerie dei pass in `build/passes/`: `libEDDI.so`,
`libSEDDI.so`, `libFDSC.so`, `libREDDI.so`, `libCFCSS.so`, `libRASM.so`,
`libINTER_RASM.so`, `libRACFED.so`. La compilazione richiede circa un
minuto.

## 5.3 Usare ASPIS

```bash
./aspis.sh --llvm-bin <llvm>/bin --eddi --rasm programma.c -o programma
```

Le opzioni principali: una tecnica dei dati (`--no-dup`, `--eddi`, `--seddi`,
`--fdsc`, `--reddi`, con eventuali `--multiple-errbb` e `--coarse-grained`),
una tecnica del flusso (`--no-cfc`, `--cfcss`, `--rasm`, `--inter-rasm`,
`--racfed`), `--build-dir` per la cartella dei file intermedi e
`--no-cleanup` per non cancellarli alla fine. Con `--no-cleanup` nella
cartella resta `out.ll`, l'IR finale: è il file da guardare quando qualcosa
non funziona.

Il programma deve definire le due funzioni che ASPIS chiama quando un
controllo fallisce:

```c
void DataCorruption_Handler(void) {     /* controlli sui dati (EDDI & co.) */
    fprintf(stderr, "FAULT_DETECTED: DataCorruption\n");
    exit(2);
}
void SigMismatch_Handler(void) {        /* controlli sulle firme (CFC) */
    fprintf(stderr, "FAULT_DETECTED: SigMismatch\n");
    exit(3);
}
```

## 5.4 La pipeline di `aspis.sh`

Questi sono, nell'ordine, i comandi che `aspis.sh` esegue (semplificati):

```bash
# 1. ogni sorgente diventa IR, senza ottimizzazioni
clang file.c -S -emit-llvm -O0 -Xclang -disable-O0-optnone -o file.ll
# 2. tutti i file IR vengono uniti in un solo modulo
llvm-link *.ll -o out.ll
# 3. preparazione: via le informazioni di debug, switch trasformati in br
opt --passes="strip" out.ll -o out.ll
opt --passes="lower-switch" out.ll -o out.ll
# 4. i valori di ritorno diventano parametri (vedi 5.5)
opt -load-pass-plugin=libEDDI.so --passes="func-ret-to-ref" out.ll -o out.ll
# 5. protezione dei dati: libEDDI.so, libSEDDI.so, libFDSC.so o libREDDI.so
opt -load-pass-plugin=libEDDI.so --passes="eddi-verify" out.ll -o out.ll
# 6. semplificazione del grafo dei blocchi
opt --passes="simplifycfg" out.ll -o out.ll
# 7. controllo del flusso: cfcss-verify, rasm-verify o racfed-verify
opt -load-pass-plugin=libRASM.so --passes="rasm-verify" out.ll -o out.ll
# 8. coerenza delle variabili globali duplicate
opt -load-pass-plugin=libEDDI.so --passes="duplicate-globals" out.ll -o out.ll
# 9. back-end: IR -> eseguibile
clang out.ll -o programma
```

Due osservazioni:

- l'IR viene prodotto con `-O0` e **nessun passo di ottimizzazione** viene
  eseguito dopo le protezioni. È voluto: un ottimizzatore riconoscerebbe che
  le due copie calcolano la stessa cosa e le fonderebbe, cancellando la
  protezione. Il prezzo è un codice lento, con ogni variabile sullo stack;
- la protezione del flusso viene applicata **dopo** quella dei dati, quindi
  lavora sul codice già duplicato, compresi i blocchi creati da EDDI.

## 5.5 FuncRetToRef

Una funzione duplicata deve restituire **due** risultati, uno per copia, ma in
C (e in LLVM) una funzione restituisce un solo valore. `FuncRetToRef` risolve
il problema prima di EDDI: per ogni funzione `int f(int x)` crea una
versione `void f_ret(int x, int *ret)` che scrive il risultato attraverso un
puntatore, e sostituisce le chiamate. EDDI poi duplica anche il puntatore di
ritorno, così le due copie del risultato finiscono in due posti diversi.

## 5.6 Come EDDI trasforma il codice

Per ogni funzione `f` del programma, EDDI crea una versione `f_dup` che
riceve **ogni parametro due volte** (prima le copie duplicate, poi gli
originali) e dentro la quale ogni istruzione è eseguita due volte. Mantiene
una mappa "istruzione originale → istruzione copia". Ogni variabile globale
`g` ottiene una copia `g_dup`.

Ai punti di sincronizzazione (store, salti condizionali, chiamate) la
funzione `addConsistencyChecks` (in `EDDI.cpp`):

1. spezza il basic block prima dell'istruzione da proteggere;
2. inserisce un nuovo blocco chiamato **`VerificationBB`** con i confronti tra
   le due copie degli operandi (`icmp eq` per gli interi, `fcmp ueq` per i
   numeri in virgola mobile, confronto dei valori puntati per i puntatori);
3. termina il blocco con un salto: se tutti i confronti sono veri si
   prosegue con l'istruzione, altrimenti si va in **`ErrBB`**, un blocco che
   chiama `DataCorruption_Handler`.

Questo è l'esempio del report: `int scale(int v) { return v * g; }`, con `g`
globale, compilato con EDDI (e le nostre correzioni):

```llvm
define void @scale_ret_dup(i32 %0, ptr %1, i32 %2, ptr %3) {
VerificationBB:
  %4 = alloca i32                       ; v
  %5 = alloca i32                       ; la sua copia
  store i32 %2, ptr %4
  store i32 %0, ptr %5
  %6 = load i32, ptr %4
  %7 = load i32, ptr %5
  %8 = load i32, ptr @g
  %9 = load i32, ptr @g_dup             ; la copia della globale
  %10 = mul nsw i32 %6, %8
  %11 = mul nsw i32 %7, %9              ; il calcolo è fatto due volte
  %12 = icmp eq i32 %10, %11            ; controllo di consistenza
  br i1 %12, label %13, label %ErrBB
13:
  store volatile i32 %10, ptr %3        ; "restituisce" le due copie
  store volatile i32 %11, ptr %1
  ret void
ErrBB:
  call void @DataCorruption_Handler()
  unreachable
}
```

Si riconoscono tutti gli ingredienti: il nome `scale_ret_dup` (prima
`FuncRetToRef` ha creato `scale_ret`, poi EDDI `scale_ret_dup`), i quattro
parametri (`%0` e `%2` sono le due copie di `v`, `%1` e `%3` i due puntatori
di ritorno), le operazioni raddoppiate, il confronto prima delle store che
fanno uscire il risultato, il blocco `ErrBB`. Il primo blocco si chiama
`VerificationBB` perché EDDI lo ha creato spezzando il blocco d'ingresso.

**Le chiamate.** Se la funzione chiamata ha una versione `_dup` (perché è nel
programma ed è stata duplicata), EDDI chiama quella, passando entrambe le
copie degli argomenti. Se invece la funzione è esterna (`printf`, `memcpy`,
`sin` della libreria C), non può essere duplicata: EDDI la chiama una volta
sola con gli argomenti originali. Ma una funzione esterna può **scrivere**
attraverso i puntatori che riceve (pensate a `memcpy(dst, src, n)` o
`scanf`), aggiornando solo la copia originale dei dati. Per questo, dopo la
chiamata, EDDI **risincronizza** la memoria: copia i valori puntati dagli
argomenti dalla versione originale a quella duplicata. È la funzione
`fixFuncValsPassedByReference`, dove stava il secondo bug.

**I puntatori.** Le due copie di un puntatore possono legittimamente avere
valori diversi: se `p` punta a `x`, la sua copia punta a `x_dup`. Quindi
confrontare gli indirizzi non ha senso: EDDI confronta i **valori puntati**
(`*p` con `*p_dup`), e se sono a loro volta puntatori scende ancora, fino a
un valore non puntatore. Per sapere di che tipo è il valore puntato (con i
puntatori opachi, vedi 2.6) usa i tipi dedotti da TypeDeductionAnalysis. È
in questo codice (`comparePtrs` e `compareValues`) che stava il primo bug.

## 5.7 Le altre parti

- **DuplicateGlobals** chiude il lavoro sulle variabili globali: le globali
  scritte da funzioni non duplicate vengono mantenute coerenti con le loro
  copie;
- le **annotazioni** permettono di scegliere cosa proteggere:
  `__attribute__((annotate("exclude")))` lascia una funzione o una globale
  senza protezione, `to_duplicate` duplica le chiamate a una funzione invece
  del suo corpo, `to_harden` indica cosa deve proteggere REDDI. Le nostre
  applicazioni non usano annotazioni: vogliamo proteggere tutto;
- EDDI, a fine compilazione, stampa `Comparison Counter: N`, il numero di
  controlli inseriti; lo usiamo come misura della quantità di controlli.

## 5.8 Come si vede RASM nel codice

RASM tiene la firma di esecuzione in una variabile sullo stack (`%2`
nell'esempio sotto), letta e scritta con accessi `volatile` perché il
compilatore non li elimini. Per ogni blocco
`B` crea un blocco **`RASM_Verification_BB`**, lo mette davanti a `B` e ci fa
arrivare tutti i salti che andavano in `B`: lì sottrae il correttivo e
controlla la firma. Alla fine di ogni blocco aggiunge l'aggiornamento con la
`select` (capitolo 4.4).

Questo è un estratto di una piccola funzione compilata con `--eddi --rasm`
(`void clamp(int v) { if (v > 10) g = 10; else g = v; }`):

```llvm
14:
  %15 = select i1 %8, i32 -3, i32 -5          ; correttivo scelto con la condizione
  %16 = load volatile i32, ptr %2             ; firma di esecuzione
  %17 = sub i32 %16, %15
  store volatile i32 %17, ptr %2              ; firma aggiornata
  br i1 %8, label %RASM_Verification_BB2, label %RASM_Verification_BB3

RASM_Verification_BB2:                        ; ingresso del ramo "vero"
  %18 = load volatile i32, ptr %2
  %19 = sub i32 %18, 1                        ; S = S - sub(B)
  store volatile i32 %19, ptr %2
  %20 = icmp eq i32 %19, 24                   ; S == sig(B) ?
  br i1 %20, label %VerificationBB2, label %ErrBB1

VerificationBB2:                              ; blocco creato da EDDI per la store
  store i32 10, ptr @g
  store i32 10, ptr @g_dup
  ...
```

Si vede bene l'intreccio delle due protezioni: il salto condizionale porta
prima al controllo di RASM, poi al blocco `VerificationBB2` creato da EDDI.
Nel capitolo 8 vedremo cosa succedeva prima della correzione del terzo bug.
