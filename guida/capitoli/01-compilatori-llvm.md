# 2. Compilatori e LLVM: il minimo indispensabile

## 2.1 Cosa fa un compilatore

Un compilatore traduce un programma da un linguaggio sorgente (per noi il C)
a codice macchina. Lo fa in fasi successive:

1. **analisi lessicale**: il testo viene spezzato in *token* (parole chiave,
   identificatori, numeri, operatori). È qui che entrano in gioco le
   espressioni regolari e gli automi a stati finiti, la parte "linguaggi
   formali" del corso;
2. **analisi sintattica** (*parsing*): i token vengono organizzati in un
   albero sintattico secondo una grammatica libera dal contesto;
3. **analisi semantica**: si controllano tipi, dichiarazioni, regole del
   linguaggio;
4. **generazione della rappresentazione intermedia** (*IR, intermediate
   representation*): il programma viene tradotto in un linguaggio più
   semplice e regolare, indipendente sia dal C sia dalla macchina;
5. **ottimizzazione**: trasformazioni dell'IR che lo rendono più veloce o più
   piccolo senza cambiarne il significato;
6. **generazione del codice**: l'IR viene tradotto nelle istruzioni del
   processore (per noi x86-64), con l'allocazione dei registri.

Le fasi 1-4 formano il **front-end** (dipende dal linguaggio sorgente), la 5 il
**middle-end** (non dipende né dal sorgente né dalla macchina), la 6 il
**back-end** (dipende dalla macchina). Il vantaggio di un IR comune è che si
scrive una trasformazione una volta sola e funziona per tutti i linguaggi e
tutte le architetture.

ASPIS lavora nel middle-end: le sue protezioni sono **trasformazioni dell'IR**.
Non tocca né il parsing del C né la generazione del codice x86.

## 2.2 LLVM

LLVM è l'infrastruttura di compilazione più usata nella ricerca e in molti
prodotti (Apple, Google, Rust, Swift usano LLVM). I programmi che ci
interessano sono:

| Programma | Cosa fa |
|---|---|
| `clang` | front-end per C e C++: produce l'IR (con `-S -emit-llvm`) oppure direttamente l'eseguibile |
| `opt` | esegue dei *pass* (trasformazioni o analisi) su un file IR e scrive l'IR trasformato |
| `llvm-link` | unisce più file IR in un unico modulo |
| `clang` su un file `.ll` | fa da back-end: traduce l'IR in codice macchina e collega l'eseguibile |
| `llvm-size` | stampa la dimensione delle sezioni di un eseguibile (`.text` è il codice) |

Il file IR in forma testuale ha estensione `.ll`. Si può leggere, ed è molto
utile farlo: quando ASPIS ha un problema, il primo passo è guardare l'IR che
produce.

Noi usiamo **LLVM 21.1.8**, la versione richiesta da ASPIS, scaricata già
compilata dal sito di LLVM.

## 2.3 L'IR di LLVM

Un file IR contiene un **modulo**, cioè un insieme di variabili globali e di
funzioni. Ogni funzione è fatta di **basic block** (blocchi di base), ciascuno
con un'etichetta, e ogni blocco è una sequenza di **istruzioni**.

L'IR è in forma **SSA** (*static single assignment*): ogni valore ha un nome
(`%a`, `%0`, `%add`...) e viene assegnato **una sola volta**. Le variabili del
C che cambiano valore non diventano valori SSA, ma celle di memoria sullo
stack, create con `alloca` e lette e scritte con `load` e `store`. Questo è
esattamente quello che fa `clang` senza ottimizzazioni (`-O0`), che è il modo
in cui lo usa ASPIS.

Esempio. Questa funzione C:

```c
int sum(int *a, int n) {
  int s = 0;
  for (int i = 0; i < n; i++)
    s += a[i];
  return s;
}
```

diventa (con `clang -S -emit-llvm -O0`, tolti alcuni attributi):

```llvm
define i32 @sum(ptr %a, i32 %n) {
entry:
  %a.addr = alloca ptr               ; cella sullo stack per il parametro a
  %n.addr = alloca i32               ; ... per n
  %s = alloca i32                    ; variabile locale s
  %i = alloca i32                    ; variabile locale i
  store ptr %a, ptr %a.addr          ; copia i parametri nelle celle
  store i32 %n, ptr %n.addr
  store i32 0, ptr %s                ; s = 0
  store i32 0, ptr %i                ; i = 0
  br label %for.cond                 ; salto incondizionato

for.cond:                            ; condizione del ciclo
  %0 = load i32, ptr %i
  %1 = load i32, ptr %n.addr
  %cmp = icmp slt i32 %0, %1         ; i < n ? (slt = signed less than)
  br i1 %cmp, label %for.body, label %for.end   ; salto condizionale

for.body:                            ; s += a[i]
  %2 = load ptr, ptr %a.addr
  %3 = load i32, ptr %i
  %idxprom = sext i32 %3 to i64      ; estensione di segno a 64 bit
  %arrayidx = getelementptr inbounds i32, ptr %2, i64 %idxprom   ; &a[i]
  %4 = load i32, ptr %arrayidx       ; a[i]
  %5 = load i32, ptr %s
  %add = add nsw i32 %5, %4
  store i32 %add, ptr %s
  br label %for.inc

for.inc:                             ; i++
  %6 = load i32, ptr %i
  %inc = add nsw i32 %6, 1
  store i32 %inc, ptr %i
  br label %for.cond

for.end:
  %7 = load i32, ptr %s
  ret i32 %7                         ; return s
}
```

Le istruzioni da conoscere:

| Istruzione | Significato |
|---|---|
| `alloca T` | riserva sullo stack lo spazio per un valore di tipo `T`, restituisce il puntatore |
| `load T, ptr p` | legge un valore di tipo `T` dall'indirizzo `p` |
| `store T v, ptr p` | scrive `v` all'indirizzo `p` |
| `getelementptr` (GEP) | calcola un indirizzo (elemento di un array, campo di una struct) senza leggere la memoria |
| `add`, `sub`, `mul`, `xor`, ... | aritmetica intera; `fadd`, `fmul`, ... per i numeri in virgola mobile |
| `icmp`, `fcmp` | confronti (interi e in virgola mobile): danno un `i1`, cioè un booleano |
| `br i1 c, label A, label B` | salto condizionale: va in `A` se `c` è vero, altrimenti in `B` |
| `br label A` | salto incondizionato |
| `select i1 c, T x, T y` | `c ? x : y` senza salti |
| `call` | chiamata di funzione |
| `ret` | ritorno dalla funzione |
| `phi` | sceglie un valore a seconda del blocco da cui si è arrivati (con `-O0` è rara) |

I tipi: `i1`, `i8`, `i32`, `i64` sono interi di 1, 8, 32, 64 bit; `float`,
`double`; `ptr` è un puntatore; poi ci sono struct (`{ i32, float }`) e array
(`[16 x i8]`). I nomi che cominciano con `@` sono globali (funzioni e
variabili globali), quelli con `%` sono locali alla funzione.

ASPIS non usa i nomi leggibili come `%a.addr`: `clang` di default li scarta e
numera i valori (`%0`, `%1`, ...). Il significato non cambia.

## 2.4 Basic block e grafo di controllo del flusso

Un **basic block** è una sequenza di istruzioni senza salti al suo interno:
si entra solo dall'inizio e si esce solo dalla fine. L'ultima istruzione è un
*terminatore* (`br`, `ret`, `unreachable`, ...), che dice dove si va dopo.

I blocchi di una funzione e i salti tra di loro formano il **grafo di
controllo del flusso** (CFG, *control-flow graph*). Per `sum`:

```text
          +-------+
          | entry |
          +-------+
              |
              v
        +----------+   falso   +---------+
   +--->| for.cond |---------->| for.end |  (return s)
   |    +----------+           +---------+
   |         | vero
   |         v
   |    +----------+
   |    | for.body |
   |    +----------+
   |         |
   |         v
   |    +----------+
   +----| for.inc  |
        +----------+
```

Un'esecuzione corretta percorre sempre archi di questo grafo. Le tecniche di
*control-flow checking* (capitolo 4) controllano proprio questo: che il
programma segua gli archi giusti.

## 2.5 I pass

Un **pass** è un pezzo di codice che analizza o trasforma l'IR: per esempio
`simplifycfg` semplifica il grafo dei blocchi, `lower-switch` trasforma gli
`switch` in catene di `br`. Si eseguono con `opt`:

```bash
opt --passes="lower-switch" in.ll -o out.ll
```

Un pass può stare fuori dal codice di LLVM, in una libreria condivisa (un
*plugin*) caricata al momento:

```bash
opt -load-pass-plugin=build/passes/libEDDI.so --passes="eddi-verify" in.ll -o out.ll
```

Le protezioni di ASPIS sono pass di questo tipo (*out-of-tree*): sono scritte
in C++ usando le classi di LLVM (`Module`, `Function`, `BasicBlock`,
`Instruction`, `IRBuilder` per creare nuove istruzioni) e compilate in file
`.so`.

## 2.6 I puntatori opachi e la deduzione dei tipi

Nelle versioni recenti di LLVM i puntatori sono **opachi**: il tipo `ptr` non
dice a cosa punta. Una `load i32, ptr %p` dice che in quel punto si legge un
`i32`, ma `%p` da solo non lo dice. Questo crea un problema ad ASPIS: per
confrontare due puntatori deve confrontare i valori puntati, e quindi deve
sapere di che tipo sono. Per questo ASPIS usa una libreria esterna,
**TypeDeductionAnalysis** (TDA), che ricostruisce il tipo puntato
guardando come il puntatore viene usato.

## 2.7 Un minimo di x86-64

L'iniettore di guasti lavora sul programma già compilato, quindi serve
qualche nozione di x86-64:

- **16 registri generali** a 64 bit: `rax`, `rbx`, `rcx`, `rdx`, `rsi`, `rdi`,
  `rbp`, `rsp`, `r8`...`r15`. `rsp` è il puntatore alla cima dello stack,
  `rbp` di solito punta al record di attivazione (*frame*) della funzione
  corrente;
- **`rip`**, il *program counter*: l'indirizzo della prossima istruzione;
- **`rflags`**, il registro dei flag, impostato dalle istruzioni aritmetiche
  e di confronto: `ZF` (risultato zero), `SF` (segno), `CF` (riporto), `OF`
  (overflow), `PF` (parità);
- i **salti condizionali** (`jcc`: `je`, `jne`, `jl`, `jge`, ...) saltano o
  meno a seconda dei flag. Sono codificati come `0x70`-`0x7f` seguito da uno
  spostamento di 8 bit, oppure `0x0f 0x80`-`0x8f` seguito da uno spostamento
  di 32 bit. I 4 bit bassi dell'opcode sono il *condition code* (`cc`);
- con `-O0` ogni variabile vive sullo stack, a un indirizzo come
  `[rbp - 20]`.

Il ciclo di `sum` compilato con `-O0` (sintassi Intel):

```text
.LBB0_1:                                ; for.cond
    mov  eax, dword ptr [rbp - 20]      ; eax = i
    cmp  eax, dword ptr [rbp - 12]      ; confronta i con n (imposta i flag)
    jge  .LBB0_4                        ; se i >= n esce dal ciclo
    mov  rax, qword ptr [rbp - 8]       ; rax = a
    movsxd rcx, dword ptr [rbp - 20]    ; rcx = i (esteso a 64 bit)
    mov  eax, dword ptr [rax + 4*rcx]   ; eax = a[i]
    add  eax, dword ptr [rbp - 16]      ; eax += s
    mov  dword ptr [rbp - 16], eax      ; s = eax
    ...                                 ; i++
    jmp  .LBB0_1
.LBB0_4:
```

Un bit-flip in `rcx` subito prima di `mov eax, dword ptr [rax + 4*rcx]` fa
leggere un elemento sbagliato (o un indirizzo non valido, e allora il
programma va in crash). Invertire il `jge` fa uscire dal ciclo troppo presto
o eseguire un'iterazione di troppo. Sono esattamente i due modelli di guasto
del progetto.
