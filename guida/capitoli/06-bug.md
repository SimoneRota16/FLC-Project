# 8. I tre bug e le correzioni

## 8.1 Come si cerca un bug in un pass

Quando un programma protetto da ASPIS non funziona, il metodo è sempre lo
stesso:

1. **riprodurre**: trovare la combinazione di opzioni che fallisce (il log
   del sistema di test la dice) e ripetere la compilazione a mano con
   `aspis.sh ... --no-cleanup`, così restano i file intermedi;
2. **capire dove**: se il programma va in crash, eseguirlo con `gdb` (`run`,
   poi `bt` per lo stack delle chiamate e `x/10i $pc` per le istruzioni
   vicine); se il compilatore si ferma con un errore, leggere il messaggio
   di `opt`; poi guardare l'IR in `out.ll` intorno al punto incriminato;
3. **ridurre**: scrivere un programma minimo, di poche righe, che mostra lo
   stesso problema (un *riproduttore*). Serve a capire la causa e a
   verificare la correzione;
4. **leggere il codice del pass** che produce l'IR sbagliato e capire perché;
5. **correggere**, ricompilare ASPIS (`cmake --build build`) e verificare:
   il riproduttore deve funzionare, e **tutti** i test di ASPIS devono dare
   gli stessi risultati di prima.

## 8.2 Bug 1: i controlli che leggono da un puntatore nullo

**Sintomo.** Il riproduttore `aspis-integration/reproducers/null_pointer.c`:

```c
int main(void) {
    int *v = NULL;
    v = realloc(v, 4 * sizeof(int));   /* realloc(NULL, n) equivale a malloc(n) */
    v[0] = 42;
    printf("%d\n", v[0]);
    free(v);
    return 0;
}
```

compilato con `--eddi` va in *segmentation fault* sul branch principale.
Questo bug non colpisce direttamente le nostre quattro applicazioni, ma la
correzione del bug 2 (sezione 8.3) deve leggere memoria attraverso puntatori
che possono essere nulli, e quindi ha bisogno di questa: le due patch vanno
insieme.

**Causa.** Prima di una chiamata EDDI controlla gli argomenti, e per un
puntatore confronta i **valori puntati** (vedi 5.6). Il codice
(`comparePtrs` in `EDDI.cpp`) caricava `*v` e `*v_dup` senza chiedersi se `v`
fosse nullo: con `realloc(NULL, ...)` il controllo stesso dereferenzia il
puntatore nullo e il programma va in crash, anche senza nessun guasto. Lo
stesso succede alla fine di una lista concatenata, o con `free(NULL)`.

**Correzione** (patch 0001). Una nuova funzione, `getNullSafePointer`,
restituisce un puntatore da cui si può sempre leggere:

```cpp
// se Ptr è nullo, legge da una costante globale piena di zeri
Value *EDDI::getNullSafePointer(Value *Ptr, Type *Ty, IRBuilder<> &B) {
  GlobalVariable *&Guard = NullGuards[Ty];          // una costante per tipo
  if (Guard == nullptr)
    Guard = new GlobalVariable(..., Constant::getNullValue(Ty), "aspis_null_guard");
  return B.CreateSelect(B.CreateIsNull(Ptr), Guard, Ptr);   // p == NULL ? guard : p
}
```

Nell'IR prodotto ogni lettura di un controllo diventa:

```llvm
%isnull = icmp eq ptr %p, null
%safe   = select i1 %isnull, ptr @aspis_null_guard, ptr %p
%val    = load i32, ptr %safe
```

Se entrambe le copie del puntatore sono nulle, si leggono due zeri e il
controllo passa (giusto: le due copie sono coerenti). Se solo una è nulla
(per esempio per un guasto), si legge zero da una parte e il valore vero
dall'altra: i valori differiscono e il guasto viene **rilevato**.

Nella stessa patch abbiamo sistemato anche `compareValues`, la funzione che
sceglie come confrontare due valori. Prima la scelta dipendeva dal tipo
*dedotto*, cioè quello del sorgente C; ma il compilatore a volte rappresenta
un valore con un tipo diverso: una piccola struct passata per valore
diventa un `i64`. Il vecchio codice la trattava da struct ed estraeva i campi
da un intero, facendo andare in crash il compilatore. Ora il confronto
dipende dal **tipo LLVM** del valore: `icmp eq` per gli interi, `fcmp ueq`
per la virgola mobile, confronto dei valori puntati per i puntatori. I
valori aggregati (struct e array interi) **non** vengono confrontati: il
vecchio codice generava confronti senza effetto, e comunque il loro
*padding* (i byte di riempimento tra i campi) può legittimamente differire
tra le due copie.

## 8.3 Bug 2: la copia dopo le chiamate di libreria

**Sintomo.** È il bug che faceva andare in crash **tutte e quattro** le
applicazioni con EDDI, sEDDI e FDSC. Con `gdb` si vede che il crash è sempre
una scrittura di 8 byte (`mov %rcx,(%rax)`) subito dopo una chiamata a
`printf`, e che l'indirizzo scritto è una **stringa letterale**, che sta in
memoria di sola lettura (la sezione `.rodata`):

| Applicazione | Stringa sovrascritta | Codice C |
|---|---|---|
| `aes128` | `"kat ct: "` | `print_hex("kat ct: ", ...)`, che fa `printf("%s", label)` |
| `fft` | `"OK"` | `printf("ifft reconstruction: %s\n", max_err < 1e-9 ? "OK" : "MISMATCH")` |
| `huffman` | `"OK"` | `printf("roundtrip: %s\n", ok ? "OK" : "MISMATCH")` |
| `pid_control` | `"SUCCESS"` | `printf("%s\n", ok ? "SUCCESS" : "FAIL")` |

Il riproduttore `reproducers/string_literal.c` è di cinque righe:

```c
static void show(const char *label) { printf("%s\n", label); }
int main(void) { show("hello"); return 0; }
```

**Causa.** Ricordate la risincronizzazione dopo le chiamate esterne (5.6):
dopo `printf`, EDDI copia i valori puntati dagli argomenti dalla versione
originale a quella duplicata. Il vecchio codice di
`fixFuncValsPassedByReference` faceva, per ogni argomento che fosse il
risultato di un'istruzione e avesse una copia:

```cpp
// vecchio codice (semplificato)
Value *Original = argomento, *Copy = la sua copia;
Instruction *TmpLoad  = B.CreateLoad(Original->getType(), Original);  // legge un ptr: 8 byte
Instruction *TmpStore = B.CreateStore(TmpLoad, Copy);                 // li scrive nella copia
```

I problemi sono tre:

1. **la dimensione è sbagliata**: legge e scrive sempre un valore di tipo
   puntatore, cioè 8 byte, qualunque sia il tipo puntato. Per un `int` (4
   byte) scrive oltre la fine della copia; per un buffer di 100 byte ne copia
   solo 8;
2. **non distingue la memoria condivisa**: quando l'argomento è una stringa
   letterale, la "copia" del puntatore punta **alla stessa stringa**: nel
   caso di `show("hello")` il parametro `label` e la sua copia valgono
   entrambi l'indirizzo di `"hello"`; nel caso di `ok ? "SUCCESS" : "FAIL"`
   l'istruzione `select` e la sua copia scelgono la stessa costante. Copiare
   da una a sull'altra non servirebbe a nulla, ma soprattutto **scrive in
   memoria di sola lettura**, e il programma va in crash;
3. **copia anche quando non serve**: `printf` non scrive mai attraverso i suoi
   argomenti.

**Correzione** (patch 0002). La funzione è stata riscritta. Per ogni argomento
puntatore di una chiamata a una funzione non duplicata:

1. se la funzione (o quell'argomento) **non può scrivere** in memoria
   (`onlyReadsMemory`, un'informazione che LLVM conosce per molte funzioni di
   libreria e per i parametri `readonly`), non si fa nulla;
2. si risale all'**oggetto** a cui punta l'argomento (`getUnderlyingObject`:
   una variabile locale, una globale, o "sconosciuto"); se l'oggetto è una
   **globale costante** (come una stringa letterale) si salta;
3. se l'originale e la copia sono due **variabili distinte di dimensione
   nota**, si copia l'intero oggetto con un `memcpy` della dimensione giusta;
4. altrimenti (memoria dinamica, puntatori ricevuti come parametro) si usa il
   tipo dedotto da TDA per sapere **quanti byte** copiare, e si genera codice
   che controlla **a tempo di esecuzione** se i due puntatori sono uguali (o
   se la copia è nulla): in quel caso la memoria è condivisa e la copia viene
   dirottata su un buffer di appoggio (*scratch*) sullo stack, dove non fa
   danni:

```cpp
Value *Shared = B.CreateOr(B.CreateICmpEQ(Original, Duplicate),   // stessi indirizzi?
                           B.CreateIsNull(Duplicate));            // copia nulla?
Value *Dest   = B.CreateSelect(Shared, Scratch, Duplicate);       // se sì, nel buffer
Value *Source = getNullSafePointer(Original, BytesTy, B);         // lettura sicura (bug 1)
B.CreateMemCpy(Dest, ..., Source, ..., Size);                     // la dimensione giusta
```

Notate l'uso di `getNullSafePointer`: la copia legge attraverso il puntatore
originale, che potrebbe essere nullo. È per questo che la patch 0002 dipende
dalla 0001 e le due vanno applicate insieme.

## 8.4 Bug 3: RASM non controllava i blocchi creati da EDDI

Questo bug **non fa fallire nessun programma**: i test di compatibilità non
potevano trovarlo. L'ha trovato la fault injection.

**Sintomo.** Ci si aspetta che EDDI+RASM protegga almeno quanto RASM da solo,
visto che aggiunge altri controlli. Invece, contro i salti invertiti,
EDDI+RASM lasciava il **10,5%** di SDC, contro lo **0,73%** di RASM da solo
(capitolo 11).

**Come l'abbiamo trovato.** Il file dei risultati grezzi
(`results/fault_injection/before_fix/raw.csv.gz`) ha una riga per esperimento,
con l'indirizzo dell'istruzione colpita (`pc_off`, la distanza dall'inizio del
codice). Prendendo gli esperimenti finiti in SDC e disassemblando il
programma a quegli indirizzi (con `objdump -d`), si vede che **tutte** le 421
SDC sono avvenute su salti condizionali i cui due successori cominciano con
la stessa istruzione: `mov DWORD PTR [rbp-0x4], <costante>`, cioè la
scrittura di una costante nella variabile della firma di RASM. In altre
parole, in quei blocchi RASM non controllava la firma: la reimpostava. Lo
script `fault_injection/sdc_sites.py` fa esattamente questa analisi:

```text
$ python3 fault_injection/sdc_sites.py results/fault_injection/before_fix/raw.csv.gz \
      <campagna> huffman EDDI+RASM
huffman EDDI+RASM branch: 139 SDC at 17 instructions
    33 x  b362  fn_2_ret_dup         jne    b369 <fn_2_ret_dup+0x279>
            not taken -> jmp    b440 <fn_2_ret_dup+0x350>
            taken     -> mov    DWORD PTR [rbp-0x4],0x46c
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

**Correzione** (patch 0003). La condizione diventa
`BB.getName().starts_with("RASM_")`: l'eccezione vale solo per i blocchi creati
da RASM stesso (e per i *landing pad*, i blocchi di gestione delle eccezioni
del C++). Lo stesso errore c'era, identico, in `RACFED.cpp` (con
`starts_with("RACFED_")`), e la patch corregge anche quello.

**Verifica.** Abbiamo rifatto gli esperimenti di EDDI+RASM con la correzione:
nessuna SDC sui 4000 salti invertiti (prima erano 421), e i controlli di RASM
ne rilevano il 66,0% invece del 34,6% (il resto lo rilevano i controlli di
EDDI). La tabella completa è nel capitolo 11.
