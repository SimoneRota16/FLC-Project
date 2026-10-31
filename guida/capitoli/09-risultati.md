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

| Configurazione | n | masked | rilevati (dati) | rilevati (CFC) | crash | hang | **SDC** | intervallo 95% |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | 1995 | 83,6 | 0,0 | 0,0 | 14,3 | 0,0 | **2,11** | 1,56–2,83 |
| EDDI | 2000 | 83,3 | 2,9 | 0,0 | 13,9 | 0,0 | **0,00** | 0,00–0,19 |
| CFCSS | 1997 | 85,1 | 0,0 | 3,0 | 11,1 | 0,1 | **0,75** | 0,46–1,24 |
| RASM | 1998 | 85,4 | 0,0 | 2,8 | 11,0 | 0,0 | **0,80** | 0,49–1,30 |
| EDDI+CFCSS | 2000 | 83,7 | 1,3 | 2,3 | 12,7 | 0,0 | **0,05** | 0,01–0,28 |
| EDDI+RASM | 1999 | 83,8 | 1,9 | 1,6 | 12,6 | 0,0 | **0,20** | 0,08–0,51 |

(percentuali sugli n guasti di ogni riga: 2000 meno i pochi "non iniettati"
del capitolo 9.3.)

Cosa dire:

- **la maggior parte dei bit-flip non fa nulla** (83,6% *masked*): in un dato
  istante molti registri non contengono valori che verranno usati, o vengono
  sovrascritti prima di essere letti;
- **il 14% fa andare in crash il programma**: un bit cambiato in un indirizzo
  porta a leggere o scrivere fuori dalla memoria valida. Nella `baseline`
  l'89% dei crash viene da un bit-flip in `rsp` (47%) o in `rbp` (42%), i due
  puntatori allo stack: con `-O0` ogni variabile si legge e si scrive
  attraverso di loro;
- **il 2,11% produce un risultato sbagliato in silenzio** (42 casi su 1995):
  sono questi i guasti che contano;
- **con EDDI non ne resta nessuno** su 2000: con il 95% di confidenza la sua
  percentuale di SDC è sotto lo 0,19%, più di dieci volte meno. I suoi
  controlli scattano solo nel 2,9% dei casi, ma sono proprio i casi
  pericolosi: un valore sbagliato viene fermato prima di essere scritto in
  memoria, passato a una funzione o usato in un salto;
- **CFCSS e RASM da soli aiutano poco** (0,75% e 0,80%): una firma vede solo
  i bit-flip che cambiano il percorso del programma, non quelli che cambiano
  un valore;
- **combinando EDDI con una tecnica del flusso restano 1 e 4 SDC su 2000**
  (0,05% con CFCSS, 0,20% con RASM): con così pochi casi queste percentuali
  non si distinguono da quella di EDDI da solo, perché gli intervalli si
  sovrappongono. Non vuol dire che aggiungere RASM peggiori EDDI: è il caso.

## 11.3 Salti condizionali invertiti

| Configurazione | masked | rilevati (dati) | rilevati (CFC) | crash | **SDC** | intervallo 95% |
|---|---:|---:|---:|---:|---:|---|
| baseline | 20,7 | 0,0 | 0,0 | 0,0 | **79,30** | 77,47–81,02 |
| EDDI | 4,1 | 77,2 | 0,0 | 0,0 | **18,75** | 17,10–20,52 |
| CFCSS | 8,5 | 0,0 | 62,5 | 0,1 | **29,05** | 27,10–31,08 |
| RASM | 0,0 | 0,0 | 99,3 | 0,0 | **0,70** | 0,42–1,17 |
| EDDI+CFCSS | 2,5 | 36,3 | 53,5 | 0,0 | **7,70** | 6,61–8,95 |
| EDDI+RASM | 0,0 | 32,9 | 67,1 | 0,0 | **0,00** | 0,00–0,19 |

(2000 guasti per riga; nessun salto invertito ha prodotto un *hang*, per
questo la colonna manca.)

Cosa dire:

- **i salti invertiti sono i guasti peggiori**: nei programmi senza protezione
  il 79,3% produce un risultato sbagliato, perché il risultato dipende da
  quante volte si ripetono i cicli e da quale ramo si prende;
- **EDDI e CFCSS rilevano quasi solo i salti dei loro stessi controlli.**
  Abbiamo misurato dai profili (con `fault_injection/check_jumps.py`) quanti
  dei salti condizionali eseguiti appartengono ai controlli, cioè hanno come
  destinazione il blocco che chiama il gestore d'errore: il **76,3%** con EDDI
  e il **62,4%** con CFCSS. Se si inverte uno di questi salti, il programma va
  nel blocco d'errore e il guasto risulta "rilevato". Infatti le percentuali
  di rilevamento (77,2% e 62,5%) sono molto vicine. Durante la verifica finale
  abbiamo anche classificato uno per uno i salti colpiti: **tutti** i guasti
  rilevati da CFCSS e il 98% di quelli rilevati da EDDI (1517 su 1543) erano
  inversioni di salti dei controlli. Quando invece si inverte un salto **del
  programma**:
  - EDDI non se ne accorge, perché confronta le due copie della condizione
    *prima* del salto, ma poi esegue un solo salto: entrambe le copie dei dati
    vanno dalla parte sbagliata e restano coerenti tra loro;
  - CFCSS non se ne accorge, perché il successore sbagliato è comunque un
    successore lecito (capitolo 4.3);

  e restano il 18,75% e il 29,05% di SDC;
- **RASM rileva il 99,3%**: anche con RASM i salti dei controlli sono la
  maggioranza (67,4%), ma RASM rileva anche le inversioni dei salti del
  programma, perché la firma viene aggiornata con la stessa condizione del
  salto (capitolo 4.4);
- **le 14 SDC rimaste a RASM (0,70%) vengono tutte da un solo salto** di
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
  differiscono e il controllo successivo se ne accorge (sono 11 dei 26 salti
  del programma rilevati da EDDI da solo).

## 11.4 Il bug di RASM nei numeri

| Modello di guasto | SDC prima | SDC dopo | rilevati (CFC) prima | rilevati (CFC) dopo |
|---|---:|---:|---:|---:|
| bit-flip nei registri | 0,15% | 0,20% | 0,4% | 1,6% |
| salti invertiti | **9,70%** | **0,00%** | 36,4% | 67,1% |

Prima della correzione, EDDI+RASM lasciava il 9,7% di SDC sui salti
invertiti: peggio di RASM da solo (0,70%), anche se aveva in più tutti i
controlli di EDDI. È stato questo controsenso a far partire l'indagine
(capitolo 8.3): tutte le 194 SDC erano su salti verso blocchi `VerificationBB`
di EDDI dove RASM reimpostava la firma senza controllarla. Dopo la correzione
i controlli di RASM rilevano il 67,1% dei salti invertiti invece del 36,4%, e
non resta nessuna SDC. Sui bit-flip nei registri la correzione non cambia le
SDC (3 e 4 casi su 2000, una differenza dovuta al caso).

## 11.5 Per applicazione

SDC dei bit-flip nei registri (%, 500 guasti per cella):

| Applicazione | baseline | EDDI | CFCSS | RASM | EDDI+CFCSS | EDDI+RASM |
|---|---:|---:|---:|---:|---:|---:|
| aes128 | 2,0 | 0,0 | 0,8 | 0,8 | 0,2 | 0,4 |
| fft | 2,2 | 0,0 | 0,8 | 0,6 | 0,0 | 0,2 |
| huffman | 2,0 | 0,0 | 0,6 | 1,0 | 0,0 | 0,0 |
| pid_control | 2,2 | 0,0 | 0,8 | 0,8 | 0,0 | 0,2 |

SDC dei salti invertiti (%):

| Applicazione | baseline | EDDI | CFCSS | RASM | EDDI+CFCSS | EDDI+RASM |
|---|---:|---:|---:|---:|---:|---:|
| aes128 | 88,8 | 21,8 | 31,0 | 0,0 | 8,6 | 0,0 |
| fft | 68,4 | 13,6 | 26,2 | 0,0 | 4,6 | 0,0 |
| huffman | 90,0 | 24,6 | 30,0 | 0,0 | 9,4 | 0,0 |
| pid_control | 70,0 | 15,0 | 29,0 | 2,8 | 8,2 | 0,0 |

Con 500 guasti per cella le percentuali delle singole applicazioni sono poco
precise: per i bit-flip nei registri il 2,0% di `aes128` sono 10 casi, con
un intervallo al 95% che va dall'1,1% al 3,6%. Le quattro applicazioni senza
protezione hanno percentuali simili (dal 2,0% al 2,2%) e EDDI le porta tutte
a zero. Per i salti invertiti, invece, le differenze nella `baseline` sono
reali (dal 68,4% di `fft` al 90,0% di `huffman`): dipendono da quanti salti
del programma, se invertiti, cambiano davvero il risultato. Le protezioni
però si comportano allo stesso modo in tutte e quattro le applicazioni;
l'unica eccezione è quella già spiegata, le SDC di RASM in `pid_control`.

## 11.6 Il messaggio in tre frasi

1. La duplicazione dei dati (EDDI) protegge bene dai bit-flip nei registri
   (nessuna SDC su 2000) ma costa molto (3,7 volte le istruzioni) e non vede
   i salti andati dalla parte sbagliata.
2. Il controllo del flusso a firme vede quei salti solo se la firma dipende
   dalla direzione del salto (RASM sì, CFCSS no); nessuna tecnica sull'IR vede
   i salti creati dal back-end.
3. Combinare le due famiglie dà la protezione migliore, a patto che le due
   trasformazioni non si ostacolino: la fault injection ha trovato proprio un
   caso in cui lo facevano (il bug di RASM).
