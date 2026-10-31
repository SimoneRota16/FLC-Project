# 11. I risultati, spiegati

## 11.1 Il costo delle protezioni

| Configurazione | Dimensione del codice | Istruzioni eseguite | Controlli (EDDI) |
|---|---:|---:|---:|
| baseline | 1,00x | 1,00x | 0 |
| EDDI | 9,27x | 3,74x | 1283 |
| CFCSS | 1,58x | 1,65x | 0 |
| RASM | 1,99x | 2,33x | 0 |
| EDDI+CFCSS | 13,90x | 5,46x | 1283 |
| EDDI+RASM | 14,80x | 5,95x | 1283 |

(medie geometriche sulle quattro applicazioni, rispetto alla `baseline`;
1283 è il totale dei controlli inseriti nelle quattro applicazioni.)

Cosa dire:

- **EDDI costa circa 3,7 volte** le istruzioni (da 3,56x per `huffman` a
  4,12x per `pid_control`): ogni istruzione è eseguita due volte, e ogni
  controllo aggiunge confronti e un salto;
- **il codice cresce molto più dell'esecuzione** (9,3x): ogni funzione esiste
  fino in quattro versioni (`f`, `f_ret`, `f_dup`, `f_ret_dup`), anche quelle
  che alla fine non vengono più chiamate restano nell'eseguibile, ogni
  controllo spezza un blocco in più blocchi, e senza ottimizzazioni ogni
  valore passa dallo stack;
- **le tecniche del flusso costano meno** (1,65x CFCSS, 2,33x RASM): aggiungono
  poche istruzioni per blocco. RASM costa più di CFCSS perché aggiorna la
  firma due volte per blocco (all'ingresso e prima dell'uscita, con la
  `select`);
- **combinate, i costi si sommano**: EDDI+RASM esegue circa 6 volte (5,95x) le
  istruzioni dell'originale.

Il costo è misurato in **istruzioni eseguite** (contate dal profilo), non in
tempo: i programmi durano pochi millisecondi, troppo poco per misure di tempo
affidabili, mentre il numero di istruzioni è esatto e ripetibile.

## 11.2 Bit-flip nei registri

| Configurazione | masked | rilevati (dati) | rilevati (CFC) | crash | hang | **SDC** | intervallo 95% |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline | 86,5 | 0,0 | 0,0 | 12,0 | 0,1 | **1,43** | 1,10–1,84 |
| EDDI | 84,1 | 3,1 | 0,0 | 12,7 | 0,0 | **0,20** | 0,10–0,39 |
| CFCSS | 85,0 | 0,0 | 2,6 | 11,6 | 0,0 | **0,80** | 0,57–1,13 |
| RASM | 86,2 | 0,0 | 2,2 | 11,1 | 0,0 | **0,60** | 0,40–0,89 |
| EDDI+CFCSS | 83,8 | 1,4 | 2,6 | 12,2 | 0,0 | **0,03** | 0,00–0,14 |
| EDDI+RASM | 83,4 | 1,8 | 1,3 | 13,6 | 0,0 | **0,05** | 0,01–0,18 |

(percentuali su 4000 guasti per riga.)

Cosa dire:

- **la maggior parte dei bit-flip non fa nulla** (86,5% *masked*): in un dato
  istante molti registri non contengono valori che verranno usati, o vengono
  sovrascritti prima di essere letti;
- **il 12% fa andare in crash il programma**: un bit cambiato in un indirizzo
  porta a leggere o scrivere fuori dalla memoria valida. Nella `baseline`
  l'88% dei crash viene da un bit-flip in `rsp` (52%) o in `rbp` (36%), i due
  puntatori allo stack: con `-O0` ogni variabile si legge e si scrive
  attraverso di loro;
- **l'1,43% produce un risultato sbagliato in silenzio** (57 casi su 4000):
  sono questi i guasti che contano;
- **EDDI li riduce di 7 volte** (0,20%, 8 casi). I suoi controlli scattano solo
  nel 3,1% dei casi, ma sono proprio i casi pericolosi: un valore sbagliato
  viene fermato prima di essere scritto in memoria, passato a una funzione o
  usato in un salto;
- **CFCSS e RASM da soli aiutano poco** (0,80% e 0,60%): una firma vede solo
  i bit-flip che cambiano il percorso del programma, non quelli che cambiano
  un valore;
- **combinando EDDI con una tecnica del flusso restano una o due SDC su 4000**
  (0,03% con CFCSS, 0,05% con RASM): con così pochi casi le due combinazioni
  non si possono distinguere (gli intervalli si sovrappongono quasi del tutto).

## 11.3 Salti condizionali invertiti

| Configurazione | masked | rilevati (dati) | rilevati (CFC) | crash | **SDC** | intervallo 95% |
|---|---:|---:|---:|---:|---:|---|
| baseline | 19,7 | 0,0 | 0,0 | 0,0 | **80,30** | 79,04–81,50 |
| EDDI | 4,1 | 78,2 | 0,0 | 0,0 | **17,80** | 16,65–19,02 |
| CFCSS | 8,0 | 0,0 | 62,0 | 0,0 | **30,00** | 28,60–31,44 |
| RASM | 0,0 | 0,0 | 99,1 | 0,0 | **0,88** | 0,63–1,21 |
| EDDI+CFCSS | 2,1 | 36,7 | 53,5 | 0,0 | **7,80** | 7,01–8,67 |
| EDDI+RASM | 0,0 | 35,0 | 65,0 | 0,0 | **0,00** | 0,00–0,10 |

(nessun salto invertito ha prodotto un *hang*, per questo la colonna manca.)

Cosa dire:

- **i salti invertiti sono i guasti peggiori**: nei programmi senza protezione
  l'80,3% produce un risultato sbagliato, perché il risultato dipende da
  quante volte si ripetono i cicli e da quale ramo si prende;
- **EDDI e CFCSS rilevano quasi solo i salti dei loro stessi controlli.**
  Abbiamo misurato dai profili (con `fault_injection/check_jumps.py`) quanti
  dei salti condizionali eseguiti appartengono ai controlli, cioè hanno come
  destinazione il blocco che chiama il gestore d'errore: il **76,3%** con EDDI
  e il **62,4%** con CFCSS. Se si inverte uno di questi salti, il programma va
  nel blocco d'errore e il guasto risulta "rilevato". Infatti le percentuali
  di rilevamento (78,2% e 62,0%) sono molto vicine. Durante la verifica finale
  abbiamo anche classificato uno per uno i salti colpiti: **tutti** i guasti
  rilevati da CFCSS e il 98% di quelli rilevati da EDDI (3066 su 3126) erano
  inversioni di salti dei controlli. Quando invece si inverte un salto **del
  programma**:
  - EDDI non se ne accorge, perché confronta le due copie della condizione
    *prima* del salto, ma poi esegue un solo salto: entrambe le copie dei dati
    vanno dalla parte sbagliata e restano coerenti tra loro;
  - CFCSS non se ne accorge, perché il successore sbagliato è comunque un
    successore lecito (capitolo 4.3);

  e restano il 17,8% e il 30,0% di SDC;
- **RASM rileva il 99,1%**: anche con RASM i salti dei controlli sono la
  maggioranza (67,4%), ma RASM rileva anche le inversioni dei salti del
  programma, perché la firma viene aggiornata con la stessa condizione del
  salto (capitolo 4.4);
- **le 35 SDC rimaste a RASM (0,88%) vengono tutte da un solo salto** di
  `pid_control`, nella funzione `load_at`:

  ```c
  static float load_at(int k) {
      return (k >= 1200 && k < 1300) ? 1.5f : 0.0f;
  }
  ```

  Nell'IR questa funzione è un solo blocco: la condizione è calcolata senza
  salti e il `? :` è una `select` tra due `float`. RASM non ha nessun salto da
  proteggere. Ma il back-end x86, senza ottimizzazioni, traduce la `select`
  con un `jne`. Lo si vede con `sdc_sites.py`: i due successori del salto
  caricano due valori diversi in `xmm0` (nel disassemblato la funzione si
  chiama `__unnamed_8`, perché il passo `strip` della pipeline toglie i nomi
  delle funzioni `static`; la si riconosce dai confronti con `0x4b0` = 1200 e
  `0x514` = 1300). Nessuna tecnica che lavora sull'IR può vedere un salto
  creato dopo, dal back-end. È un limite interessante da citare all'orale;
- **EDDI+RASM non lascia nessuna SDC**: le due tecniche si coprono a vicenda.
  RASM vede i salti del programma andati dalla parte sbagliata; EDDI vede il
  caso di `load_at`, perché duplica anche la `select`: il back-end crea due
  salti, uno per copia, e se uno dei due sbaglia le due copie del valore
  differiscono e il controllo successivo se ne accorge (sono 33 dei 60 salti
  del programma rilevati da EDDI da solo).

## 11.4 Il bug di RASM nei numeri

| Modello di guasto | SDC prima | SDC dopo | rilevati (CFC) prima | rilevati (CFC) dopo |
|---|---:|---:|---:|---:|
| bit-flip nei registri | 0,05% | 0,05% | 0,6% | 1,3% |
| salti invertiti | **10,18%** | **0,00%** | 35,1% | 65,0% |

Prima della correzione, EDDI+RASM lasciava il 10,2% di SDC sui salti
invertiti: peggio di RASM da solo (0,88%), anche se aveva in più tutti i
controlli di EDDI. È stato questo controsenso a far partire l'indagine
(capitolo 8.3): tutte le 407 SDC erano su salti verso blocchi `VerificationBB`
di EDDI dove RASM reimpostava la firma senza controllarla. Dopo la correzione
i controlli di RASM rilevano il 65,0% dei salti invertiti invece del 35,1%, e
non resta nessuna SDC. Sui bit-flip nei registri la correzione non cambia le
SDC (2 su 4000 prima e dopo).

## 11.5 Per applicazione

SDC dei bit-flip nei registri (%, 1000 guasti per cella):

| Applicazione | baseline | EDDI | CFCSS | RASM | EDDI+CFCSS | EDDI+RASM |
|---|---:|---:|---:|---:|---:|---:|
| aes128 | 1,9 | 0,1 | 1,0 | 1,0 | 0,1 | 0,1 |
| fft | 1,1 | 0,2 | 1,0 | 0,7 | 0,0 | 0,0 |
| huffman | 1,1 | 0,2 | 0,6 | 0,4 | 0,0 | 0,0 |
| pid_control | 1,6 | 0,3 | 0,6 | 0,3 | 0,0 | 0,1 |

SDC dei salti invertiti (%):

| Applicazione | baseline | EDDI | CFCSS | RASM | EDDI+CFCSS | EDDI+RASM |
|---|---:|---:|---:|---:|---:|---:|
| aes128 | 90,4 | 21,0 | 31,3 | 0,0 | 9,5 | 0,0 |
| fft | 65,8 | 11,7 | 23,6 | 0,0 | 4,7 | 0,0 |
| huffman | 90,3 | 24,4 | 32,2 | 0,0 | 9,4 | 0,0 |
| pid_control | 74,7 | 14,1 | 32,9 | 3,5 | 7,6 | 0,0 |

Con 1000 guasti per cella, le differenze di pochi decimi di punto **non sono
significative**: per i bit-flip nei registri l'1,9% di `aes128` e l'1,1% di
`fft` sono 19 e 11 casi, e i loro intervalli al 95% (1,2–2,9% e 0,6–2,0%) si
sovrappongono. Per i salti invertiti, invece, le differenze nella `baseline`
sono reali (dal 65,8% di `fft` al 90,4% di `aes128`): dipendono da quanti
salti del programma, se invertiti, cambiano davvero il risultato. Le
protezioni però si comportano allo stesso modo in tutte e quattro le
applicazioni; l'unica eccezione è quella già spiegata, le SDC di RASM in
`pid_control`.

## 11.6 Il messaggio in tre frasi

1. La duplicazione dei dati (EDDI) protegge bene dai bit-flip nei registri
   (7 volte meno SDC) ma costa molto (3,7 volte le istruzioni) e non vede i
   salti andati dalla parte sbagliata.
2. Il controllo del flusso a firme vede quei salti solo se la firma dipende
   dalla direzione del salto (RASM sì, CFCSS no); nessuna tecnica sull'IR vede
   i salti creati dal back-end.
3. Combinare le due famiglie dà la protezione migliore, a patto che le due
   trasformazioni non si ostacolino: la fault injection ha trovato proprio un
   caso in cui lo facevano (il bug di RASM).
