# 9. Iniettare i guasti con gdb e valgrind

Non abbiamo scritto un iniettore: usiamo due strumenti che si trovano su
qualunque Linux (`sudo apt install gdb valgrind`), guidati da due brevi
script Python.

- **valgrind** esegue il programma su un processore simulato e, con lo
  strumento `callgrind`, conta quante volte viene eseguita ogni istruzione.
  Lo usiamo una volta per programma, nella esecuzione senza guasti (la
  *golden run*).
- **gdb**, il debugger, sa fermare un programma su qualunque istruzione,
  leggere e cambiare i registri e farlo ripartire: è esattamente quello che
  serve per iniettare un guasto. Lo usiamo in ogni esperimento.

Lo script `fault_injection/gdb_inject.py` (circa 80 righe, metà commenti) fa
un esperimento dentro gdb; `fault_injection/campaign.py` prepara gli
esperimenti, li lancia e ne classifica l'esito (capitolo 10).

## 9.1 La golden run

Per ogni programma, `campaign.py`:

1. lo esegue normalmente cinque volte: l'output è quello di riferimento (il
   *golden output*) e il tempo più breve serve per il limite degli *hang*
   (9.4);
2. lo esegue una volta sotto valgrind:

   ```bash
   valgrind --tool=callgrind --dump-instr=yes --dump-line=no \
       --compress-pos=no --compress-strings=no --callgrind-out-file=callgrind.out ./prog
   ```

   Il file `callgrind.out` contiene, per ogni istruzione eseguita, il suo
   indirizzo e il numero di esecuzioni, raggruppati per file eseguibile
   (`ob=`): teniamo solo le istruzioni del programma, non quelle della
   libreria C e del caricatore dinamico;
3. con `objdump -d` segna quali di quelle istruzioni sono salti condizionali
   (`je`, `jne`, `jl`, ..., tutti i `j...` tranne `jmp`);
4. scrive il profilo `profile.csv`. Le prime righe di quello di `aes128` senza
   protezione:

   ```text
   address,executions,jcc
   1080,1,0
   1084,1,0
   1086,1,0
   ...
   10c1,1,1          # 10c1: je 10d8 <deregister_tm_clones+0x28>, un salto condizionale
   ```

   In tutto 1289 istruzioni diverse e 645.656 esecuzioni: sono le
   istruzioni eseguite nel codice del programma, la misura del costo del
   capitolo 11.1. Anche il codice di avvio che il compilatore aggiunge a ogni
   programma (`_start`, `deregister_tm_clones`) fa parte dell'eseguibile.

Gli indirizzi sono quelli che stampa `objdump`, cioè relativi all'inizio del
file: il programma è *position independent* e a ogni esecuzione viene
caricato a un indirizzo base diverso, a meno di disattivare la
randomizzazione degli indirizzi (ASLR), che gdb disattiva da solo.

## 9.2 Scegliere l'istante

Un guasto transitorio può arrivare in qualunque momento, quindi vogliamo un
istante a caso dell'esecuzione, cioè **un'esecuzione a caso di un'istruzione
qualsiasi**. Dal profilo `campaign.py` estrae:

1. un'istruzione, con probabilità proporzionale al numero delle sue
   esecuzioni (un'istruzione eseguita 1000 volte ha 1000 volte più
   probabilità di una eseguita una volta);
2. una delle sue esecuzioni, la *k*-esima, con *k* uniforme tra 1 e il
   numero di esecuzioni.

Così ogni esecuzione di ogni istruzione ha la stessa probabilità di essere
scelta. Per i salti invertiti si sceglie solo tra le esecuzioni dei salti
condizionali. Per i bit-flip si estraggono anche il registro (uno dei 16
registri generali, da `rax` a `r15`) e il bit (da 0 a 63). I numeri casuali
vengono da un generatore inizializzato con un seme ricavato dai nomi di
applicazione, configurazione e modello: rifacendo la campagna si ottengono
gli stessi esperimenti.

## 9.3 Un esperimento con gdb

`campaign.py` lancia gdb così, passando l'esperimento nelle variabili
d'ambiente (`FI_ADDR`, `FI_K`, `FI_MODEL`, `FI_REG`, `FI_BIT`, ...):

```bash
gdb -batch -nx -iex "set debuginfod enabled off" -x gdb_inject.py --args ./prog
```

e lo script fa, con l'API Python di gdb, quello che si farebbe a mano. Ecco la
stessa cosa in una sessione interattiva, per l'esperimento "inverti il bit 11
di `r11` alla 1808ª esecuzione dell'istruzione `0x12ea`" (in `main` di
`pid_control` con EDDI, dove viene eseguita 2000 volte):

```text
$ gdb ./prog
(gdb) print &main                      # indirizzo di main nel file: 0x1200
(gdb) starti > out.txt 2> err.txt      # avvia il programma e fermalo subito
(gdb) print &main                      # ora vale 0x555555555200: la base è 0x555555554000
(gdb) break *(0x555555554000 + 0x12ea)
(gdb) ignore 1 1807                    # ignora i primi 1807 passaggi
(gdb) continue                         # si ferma prima della 1808ª esecuzione
(gdb) set $r11 = $r11 ^ (1 << 11)      # il guasto
(gdb) delete
(gdb) continue                         # il programma prosegue con il guasto
```

I passi dello script:

1. **avvio**: `starti` avvia il programma (con l'output rediretto su due
   file) e lo ferma alla prima istruzione; la differenza tra l'indirizzo di
   `main` prima e dopo l'avvio è la base a cui è stato caricato;
2. **fermata**: un breakpoint sull'istruzione scelta, con *ignore count*
   *k*-1: gdb lo ignora per *k*-1 volte e ferma il programma subito prima
   della *k*-esima esecuzione. Se il programma termina prima, l'esperimento è
   "non iniettato" e viene scartato. Succede di rado, per un dettaglio di
   valgrind: le poche istruzioni con cui il programma salta a una funzione
   della libreria C (la *PLT*) vengono contate insieme all'istruzione `call`
   che la chiama, quindi per quelle `call` il profilo indica qualche
   esecuzione in più di quelle reali. Gli esperimenti rimasti sono comunque
   distribuiti in modo uniforme su tutte le esecuzioni reali;
3. **guasto**:
   - bit-flip: legge il registro, inverte il bit con uno XOR e lo riscrive
     (`set $rax = ...`);
   - salto invertito: esegue il salto con `stepi`, guarda dove è andato e
     sposta il *program counter* (`$pc`) sull'altro successore: la
     destinazione del salto se il salto non è stato preso, l'istruzione
     successiva se è stato preso;
4. **prosecuzione**: toglie il breakpoint e lascia correre il programma. Un
   piccolo processo di guardia (un `sleep` seguito da `kill -KILL`) uccide il
   programma se non termina entro il tempo limite: è un *hang*;
5. **risultato**: stampa una riga `FI-RESULT` con tre informazioni: se il
   guasto è stato iniettato, il codice d'uscita e l'eventuale segnale che ha
   fermato il programma (per esempio `SIGSEGV`).

## 9.4 Classificare l'esito

`campaign.py` legge la riga `FI-RESULT` e i due file di output e classifica
l'esperimento, in quest'ordine:

- `hang` se il programma è stato ucciso dal processo di guardia: dopo il
  guasto non è terminato entro 20 volte il suo tempo normale, e comunque
  almeno 1 secondo;
- `crash` se è stato fermato da un altro segnale;
- `detected_data` se su stderr c'è `FAULT_DETECTED: DataCorruption`;
- `detected_cfc` se su stderr c'è `FAULT_DETECTED: SigMismatch`;
- `masked` se l'output è identico a quello di riferimento e il codice
  d'uscita è 0;
- `sdc` altrimenti (output diverso, oppure il programma stesso si è accorto
  dell'errore e ha stampato `FAIL`).

Ogni esperimento diventa una riga di `raw.csv.gz`. Per esempio, dai risultati
di `aes128` con EDDI:

```text
⟦csv_example⟧
```

⟦csv_comment⟧

## 9.5 Quanto costa un esperimento

⟦exp_time⟧ La maggior parte del tempo è di gdb: l'avvio (circa un decimo di
secondo) e le fermate sul breakpoint, perché per ignorare i primi *k*-1
passaggi gdb ferma comunque il programma ogni volta e lo fa ripartire
(circa un decimo di millisecondo per passaggio, che nei cicli sono migliaia).
Gli esperimenti sono indipendenti, quindi `campaign.py` ne esegue quattro
alla volta, uno per core.

## 9.6 Cosa non facciamo

- iniettiamo solo mentre il programma esegue **il proprio codice**, mai nella
  libreria C (che ASPIS non protegge);
- non tocchiamo i registri **SSE** (`xmm0`...), dove stanno i valori in
  virgola mobile: per `fft` e `pid_control` i guasti nei calcoli in virgola
  mobile sono rappresentati solo quando colpiscono indirizzi, indici o
  interi;
- un solo guasto per esecuzione, niente guasti in memoria.
