# 8. I due bug trovati in ASPIS

Il progetto ha trovato due bug di ASPIS:

- un bug di **EDDI**, trovato dai test di compatibilità, che faceva andare in
  crash la prima versione delle nostre applicazioni. Non lo abbiamo corretto
  dentro ASPIS: lo abbiamo isolato in un programma di cinque righe,
  descritto in un *bug report* e aggirato nelle applicazioni;
- un bug di **RASM**, trovato dalla fault injection, che abbiamo corretto
  cambiando una riga di codice.

## 8.1 Come si cerca un bug in un pass

Quando un programma protetto da ASPIS non funziona, il metodo è sempre lo
stesso:

1. **riprodurre**: trovare la combinazione di opzioni che fallisce (il log
   del sistema di test la dice) e ripetere la compilazione a mano con
   `aspis.sh ... --no-cleanup`, così restano i file intermedi;
2. **capire dove**: se il programma va in crash, eseguirlo con `gdb` (`run`,
   poi `bt` per lo stack delle chiamate e `x/10i $pc` per le istruzioni
   vicine); poi guardare l'IR in `out.ll` intorno al punto incriminato;
3. **ridurre**: scrivere un programma minimo, di poche righe, che mostra lo
   stesso problema (un *riproduttore*). Serve a capire la causa e a
   comunicarla a chi mantiene ASPIS;
4. **leggere il codice del pass** che produce l'IR sbagliato e capire perché;
5. **decidere**: correggere ASPIS (e verificare che tutti i suoi test diano
   gli stessi risultati di prima) oppure, se la correzione è complessa,
   segnalare il bug ed evitarlo.

## 8.2 Il bug di EDDI: la copia dopo le chiamate di libreria

**Sintomo.** Con la prima versione delle applicazioni, EDDI, sEDDI e FDSC le
facevano andare in crash **tutte e quattro** (*segmentation fault*). Con `gdb`
si vede che il crash è sempre una scrittura di 8 byte (`mov %rcx,(%rax)`)
subito dopo una chiamata a `printf`, e che l'indirizzo scritto è una **stringa
letterale**, che sta in memoria di sola lettura (la sezione `.rodata`):

| Applicazione | Stringa sovrascritta | Codice C della prima versione |
|---|---|---|
| `aes128` | `"kat ct: "` | `print_hex("kat ct: ", ...)`, che faceva `printf("%s", label)` |
| `fft` | `"OK"` | `printf("ifft reconstruction: %s\n", max_err < 1e-9 ? "OK" : "MISMATCH")` |
| `huffman` | `"OK"` | `printf("roundtrip: %s\n", ok ? "OK" : "MISMATCH")` |
| `pid_control` | `"SUCCESS"` | `printf("%s\n", ok ? "SUCCESS" : "FAIL")` |

Il riproduttore `aspis-integration/reproducers/string_literal.c` è di cinque
righe:

```c
static void show(const char *label) { printf("%s\n", label); }
int main(void) { show("hello"); return 0; }
```

Compilato con `--eddi` sul branch principale di ASPIS va in crash invece di
stampare `hello`.

**Causa.** Ricordate la risincronizzazione dopo le chiamate esterne (5.6):
dopo una chiamata a una funzione che non ha una versione `_dup` (come
`printf`), EDDI copia i valori puntati dagli argomenti dalla versione
originale a quella duplicata, perché la funzione chiamata potrebbe averli
modificati. Il codice (`fixFuncValsPassedByReference` in `EDDI.cpp`) fa, per
ogni argomento che sia il risultato di un'istruzione e abbia una copia,
una lettura e una scrittura di un valore **della dimensione di un puntatore**
(8 byte):

```cpp
// codice di ASPIS b66a090 (semplificato)
Instruction *TmpLoad  = B.CreateLoad(Original->getType(), Original);  // legge 8 byte
Instruction *TmpStore = B.CreateStore(TmpLoad, Copy);                 // li scrive nella copia
```

Quando l'argomento è una stringa letterale, la "copia" del puntatore punta
**alla stessa stringa**: nel caso di `show("hello")` il parametro `label` e la
sua copia valgono entrambi l'indirizzo di `"hello"`; nel caso di
`ok ? "SUCCESS" : "FAIL"` l'istruzione `select` (il `? :`) e la sua copia
scelgono la stessa costante. La scrittura finisce quindi nella memoria di
sola lettura, e il sistema operativo uccide il programma. A parte questo
caso, copiare sempre 8 byte è sbagliato anche in generale: per un `int` (4
byte) si scrive oltre la fine della copia, per un buffer di 100 byte se ne
copiano solo 8.

Perché `printf("SUCCESS\n")` invece funziona? Perché lì la stringa è passata
direttamente come **costante**, non come risultato di un'istruzione, e il
codice di EDDI salta le costanti.

**Cosa abbiamo fatto.** Correggere questa funzione richiede di riscriverla
(copiare la dimensione giusta dell'oggetto, saltare la memoria di sola
lettura e gli argomenti che la funzione non può modificare): un intervento
complesso dentro EDDI. Abbiamo scelto di:

1. **aggirarlo** nelle applicazioni: ora stampano solo stringhe letterali
   dirette (`if (ok) printf("SUCCESS\n"); else printf("FAIL\n");`), con lo
   stesso identico output. Un commento in cima a ogni file spiega il motivo.
   Con questa modifica tutte le 220 combinazioni passano sul branch
   principale;
2. **segnalarlo**: `aspis-integration/bug_report.md` descrive il bug, il
   riproduttore, la causa e una possibile correzione, pronto per essere
   aperto come *issue* sul repository di ASPIS.

La correzione completa esiste (era nella seconda versione del progetto,
capitolo 15), ma non fa parte del progetto consegnato.

## 8.3 Il bug di RASM: i blocchi di EDDI non venivano controllati

Questo bug **non fa fallire nessun programma**: i test di compatibilità non
potevano trovarlo. L'ha trovato la fault injection.

**Sintomo.** Ci si aspetta che EDDI+RASM protegga almeno quanto RASM da solo,
visto che aggiunge altri controlli. Invece, contro i salti invertiti,
EDDI+RASM lasciava il **10,2%** di SDC, contro lo **0,88%** di RASM da solo
(capitolo 11).

**Come l'abbiamo trovato.** Il file dei risultati grezzi
(`results/fault_injection/before_fix/raw.csv.gz`) ha una riga per esperimento,
con l'indirizzo dell'istruzione colpita (`pc_off`, la distanza dall'inizio del
codice). Prendendo gli esperimenti finiti in SDC e disassemblando il
programma a quegli indirizzi (con `objdump -d`), si vede che **tutte** le 407
SDC sono avvenute su salti condizionali verso blocchi che cominciano con la
stessa istruzione: `mov DWORD PTR [rbp-0x4], <costante>`, cioè la scrittura di
una costante nella variabile della firma di RASM. In altre parole, in quei
blocchi RASM non controllava la firma: la reimpostava. In 406 casi su 407
entrambi i successori del salto erano blocchi così; nell'unico caso restante
solo uno, quello sbagliato (l'altro controllava la firma, e se il salto fosse
finito lì l'errore sarebbe stato rilevato). Lo script
`fault_injection/sdc_sites.py` fa esattamente questa analisi:

```text
$ python3 fault_injection/sdc_sites.py results/fault_injection/before_fix/raw.csv.gz \
      <campagna> huffman EDDI+RASM
huffman EDDI+RASM branch: 153 SDC at 20 instructions
    36 x  b752  fn_2_ret_dup         jne    b759 <fn_2_ret_dup+0x279>
            not taken -> jmp    b830 <fn_2_ret_dup+0x350>
            taken     -> mov    DWORD PTR [rbp-0x4],0x4a6
    ...
```

**Causa.** In `RASM.cpp`, all'ingresso di ogni blocco, c'è questa scelta:

```cpp
// codice originale
if (isa<LandingPadInst>(BB.getFirstNonPHI()) ||
    BB.getName().contains_insensitive("verification")) {
  // NON controlla la firma: la reimposta al valore atteso del blocco
  BChecker.CreateStore(ConstantInt::get(IntType, randomNumberBB), &RuntimeSig, true);
} else {
  // crea il blocco RASM_Verification_BB che controlla la firma
}
```

L'eccezione serviva per i blocchi creati da RASM stesso (che si chiamano
`RASM_Verification_BB...`), dove la firma non va controllata due volte. Ma il
test sul nome (`contains_insensitive("verification")`, cioè "il nome contiene
*verification*, maiuscole o minuscole") è troppo largo: vale anche per i
blocchi **`VerificationBB`** creati da EDDI. E con EDDI questi blocchi sono
dappertutto, perché EDDI ne crea uno prima di ogni store, salto e chiamata:
sono le destinazioni di quasi tutti i salti.

Ecco la stessa funzione del capitolo 5.8 (`clamp`) compilata **prima** della
correzione:

```llvm
  br i1 %8, label %VerificationBB2, label %VerificationBB3   ; salto condizionale

VerificationBB2:                    ; nessun controllo di RASM davanti
  store volatile i32 24, ptr %2     ; firma REIMPOSTATA al valore atteso, senza controllo
  store i32 10, ptr @g
  ...
VerificationBB3:
  store volatile i32 26, ptr %2     ; idem
  ...
```

Se il salto viene invertito, il programma entra nel blocco sbagliato, ma la
prima cosa che fa è sovrascrivere la firma con il valore "giusto" per quel
blocco: l'errore viene cancellato prima di poter essere controllato. Con la
correzione (capitolo 5.8) il salto va prima in `RASM_Verification_BB2` o
`RASM_Verification_BB3`, che controllano la firma.

**Correzione** (patch 0001). Una riga: la condizione diventa
`BB.getName().starts_with("RASM_")`, così l'eccezione vale solo per i blocchi
creati da RASM stesso (e per i *landing pad*, i blocchi di gestione delle
eccezioni del C++). Lo stesso errore c'era, identico, in `RACFED.cpp` (con
`starts_with("RACFED_")`), e la patch corregge anche quello.

**Verifica.** Abbiamo rifatto gli esperimenti di EDDI+RASM con la correzione:
nessuna SDC sui 4000 salti invertiti (prima erano 407), e i controlli di RASM
ne rilevano il 65,0% invece del 35,1% (il resto lo rilevano i controlli di
EDDI). La tabella completa è nel capitolo 11. Sui 48 test già presenti
in ASPIS la correzione non cambia nessun risultato (capitolo 7).
