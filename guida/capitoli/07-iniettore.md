# 9. L'iniettore di guasti (`fi.c`)

`fault_injection/injector/fi.c` è un programma C di circa 550 righe che si
compila con `gcc -O2 -o fi fi.c` e ha due comandi: `fi profile` (esecuzione
di riferimento) e `fi inject` (gli esperimenti).

## 9.1 `ptrace` in breve

`ptrace` è la chiamata di sistema di Linux con cui un processo (il
*tracer*, qui `fi`) controlla un altro processo (il *tracee*, il programma
sotto test): è quella che usa `gdb`. Le operazioni che usiamo:

| Operazione | Cosa fa |
|---|---|
| `PTRACE_TRACEME` | chiamata dal figlio prima di `execve`: "fatti controllare da mio padre". Il figlio si ferma subito dopo l'`exec` |
| `waitpid` | il padre aspetta che il figlio si fermi (per un segnale) o termini |
| `PTRACE_GETREGS` / `PTRACE_SETREGS` | legge / scrive tutti i registri del figlio (`struct user_regs_struct`: `rax`, ..., `rip`, `eflags`) |
| `PTRACE_PEEKTEXT` / `PTRACE_POKETEXT` | legge / scrive 8 byte della memoria del figlio (anche il codice) |
| `PTRACE_SINGLESTEP` | esegue una sola istruzione e si ferma di nuovo |
| `PTRACE_CONT` | fa ripartire il figlio fino al prossimo segnale |
| `PTRACE_DETACH` | smette di controllare il figlio, che prosegue da solo |
| `PTRACE_O_EXITKILL` | se `fi` muore, il figlio viene ucciso (niente processi orfani) |

Quando il figlio esegue un'istruzione `int3` (il byte `0xcc`, il *breakpoint*
dei debugger) o termina un passo singolo, riceve un `SIGTRAP` e si ferma: il
padre lo vede con `waitpid`.

Il figlio viene avviato (funzione `spawn`) con `fork` ed `execve`, con
l'output rediretto su file, e con `personality(ADDR_NO_RANDOMIZE)`, che
**disattiva la randomizzazione degli indirizzi** (ASLR): così il codice del
programma sta allo stesso indirizzo in ogni esecuzione, e l'indirizzo di
un'istruzione trovato nel profilo vale anche negli esperimenti.

## 9.2 `fi profile`: l'esecuzione di riferimento

```bash
fi profile golden.prof golden.stdout -- ./prog
```

La funzione `cmd_profile`:

1. avvia il programma sotto `ptrace`;
2. legge `/proc/<pid>/maps` per trovare l'intervallo di indirizzi del
   **codice del programma** (la mappatura eseguibile del file del programma),
   così da distinguere le istruzioni del programma da quelle della libreria C
   e del caricatore dinamico (funzione `text_range`);
3. esegue il programma **un'istruzione alla volta** (`PTRACE_SINGLESTEP`). A
   ogni passo legge `rip`: se è nel codice del programma, incrementa il
   contatore di quell'indirizzo. La prima volta che incontra un indirizzo,
   legge i byte dell'istruzione e controlla se è un salto condizionale
   (`decode_jcc`);
4. alla fine scrive il profilo e salva l'output (il *golden output*).

Il profilo è un file di testo:

```text
fi-profile 1
text 555555555000 555555557000     # intervallo del codice del programma
dynamic 645680 774766              # istruzioni eseguite: nel programma, in totale
exit 0                             # codice d'uscita
pcs 1316                           # numero di indirizzi distinti eseguiti
0 1 0 0 0 0                        # offset, esecuzioni, jcc?, cc, lunghezza, spostamento
4 1 0 0 0 0
...
12 1 1 4 2 2                       # un salto condizionale (cc 4 = je), lungo 2 byte
...
```

(sono le prime righe del profilo di `aes128` senza protezione: 645.680
istruzioni nel programma, 774.766 contando anche la libreria C).

Ogni riga dice quante volte è stata eseguita l'istruzione a quell'offset e,
se è un salto condizionale, il suo *condition code*, la sua lunghezza in
byte e lo spostamento del salto.

Eseguire milioni di istruzioni una per una è lento (ogni passo sono due
cambi di contesto tra processi): il profilo dei programmi più grandi richiede
decine di secondi. Ma si fa una volta sola per ogni programma.

## 9.3 Riconoscere un salto condizionale

`decode_jcc` riconosce le due codifiche dei salti condizionali x86:

- `0x70`-`0x7f` + 1 byte di spostamento (salto corto, lunghezza 2);
- `0x0f` `0x80`-`0x8f` + 4 byte di spostamento (salto lungo, lunghezza 6);

eventualmente precedute da un prefisso di predizione (`0x2e` o `0x3e`). Il
*condition code* sono i 4 bit bassi dell'opcode. `jcc_taken` calcola, dai
flag, se il salto verrebbe preso:

| `cc >> 1` | condizione | salti |
|---|---|---|
| 0 | `OF` | `jo` / `jno` |
| 1 | `CF` | `jb` / `jae` |
| 2 | `ZF` | `je` / `jne` |
| 3 | `CF or ZF` | `jbe` / `ja` |
| 4 | `SF` | `js` / `jns` |
| 5 | `PF` | `jp` / `jnp` |
| 6 | `SF != OF` | `jl` / `jge` |
| 7 | `ZF or SF != OF` | `jle` / `jg` |

Se il bit basso di `cc` è 1 la condizione è negata (`jne` è "salta se **non**
ZF").

## 9.4 `fi inject`: gli esperimenti

```bash
fi inject golden.prof golden.stdout reg 12345 100 300 /dev/shm/tmp -- ./prog
#                                   modello seme  N  timeout(ms)
```

Per ognuno degli N esperimenti, la funzione `cmd_inject`:

1. **sceglie l'istante** (`pick_target`): estrae un numero `k` tra 0 e il
   totale delle istruzioni eseguite nel profilo, e scorre la lista degli
   indirizzi sottraendo i contatori finché `k` cade dentro uno di essi. Così
   ogni *esecuzione* di ogni istruzione ha la stessa probabilità: è come
   scegliere un istante a caso dell'esecuzione. Il risultato è una coppia
   (indirizzo, occorrenza): "la 37ª esecuzione dell'istruzione all'offset
   `0x1a2b`". Per il modello `branch` si considerano solo le esecuzioni dei
   salti condizionali;
2. sceglie a caso anche il registro (uno dei 16) e il bit (0-63) da
   invertire. I numeri casuali vengono da un generatore *splitmix64*
   inizializzato con il seme: stesso seme, stessi esperimenti;
3. **avvia** il programma sotto `ptrace`;
4. **lo ferma** subito prima dell'occorrenza scelta (`run_to_target`): scrive
   `0xcc` (`int3`) all'indirizzo dell'istruzione e lo lascia correre. A ogni
   `SIGTRAP` controlla che si sia fermato lì, rimette il byte originale,
   riporta `rip` indietro di uno e conta. Se non è ancora l'occorrenza
   giusta, esegue l'istruzione originale con un passo singolo, rimette
   l'`int3` e continua;
5. **inietta il guasto**: legge i registri e
   - modello `reg`: inverte il bit scelto del registro scelto
     (`*gpr(&regs, reg) ^= 1ull << bit`);
   - modello `branch`: guarda i flag con `jcc_taken`; se il salto verrebbe
     preso, mette in `rip` l'indirizzo dell'istruzione successiva (il salto
     "non viene preso"), altrimenti mette la destinazione del salto. Il salto
     non viene eseguito: il programma riparte direttamente dal successore
     sbagliato;

   e scrive i registri modificati;
6. **lo lascia andare** (`PTRACE_DETACH`) e aspetta che termini, al massimo per
   il tempo limite (`wait_with_timeout`, che controlla ogni 100 µs e uccide il
   programma allo scadere);
7. **classifica** l'esito, in quest'ordine:
   - `hang` se è scaduto il tempo limite;
   - `crash` se il programma è stato ucciso da un segnale;
   - `detected_data` se su stderr c'è `FAULT_DETECTED: DataCorruption`;
   - `detected_cfc` se su stderr c'è `FAULT_DETECTED: SigMismatch`;
   - `masked` se l'output è identico a quello di riferimento e il codice
     d'uscita è lo stesso;
   - `sdc` altrimenti (output diverso, oppure il programma stesso si è
     accorto dell'errore e ha stampato `FAIL`);
8. stampa una riga CSV: numero dell'esperimento, modello, offset e occorrenza
   dell'istruzione colpita, registro (o *condition code*), bit, esito, codice
   d'uscita, segnale, durata in microsecondi. Per esempio, dai risultati di
   `aes128` con EDDI:

```text
id,model,pc_off,occurrence,target,bit,injected,outcome,exit,signal,time_us
0,reg,5745,384,rsp,18,1,crash,-1,11,17309
1,reg,77bb,1031,rbx,51,1,masked,0,0,35805
```

   Il primo esperimento ha invertito il bit 18 di `rsp` (il puntatore allo
   stack) alla 385ª esecuzione dell'istruzione all'offset `0x5745`: il
   programma è stato ucciso dal segnale 11 (`SIGSEGV`). Il secondo ha
   colpito `rbx` senza effetti visibili.

Un esperimento dura in media circa 60 millisecondi: avvio del programma,
corsa fino al punto scelto (con due fermate per ogni passaggio
sull'istruzione bersaglio, che nei cicli possono essere migliaia), resto
dell'esecuzione.

## 9.5 Cosa l'iniettore non fa

- inietta solo mentre il programma esegue **il proprio codice**, mai nella
  libreria C (che ASPIS non protegge);
- non tocca i registri **SSE** (`xmm0`...), dove stanno i valori in virgola
  mobile: per `fft` e `pid_control` i guasti nei calcoli in virgola mobile
  sono rappresentati solo quando colpiscono indirizzi, indici o interi;
- un solo guasto per esecuzione, niente guasti in memoria.
