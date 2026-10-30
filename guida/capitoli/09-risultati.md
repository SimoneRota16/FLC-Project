# 11. I risultati, spiegati

## 11.1 Il costo delle protezioni

| Configurazione | Dimensione del codice | Istruzioni eseguite | Controlli (EDDI) |
|---|---:|---:|---:|
| baseline | 1,00x | 1,00x | 0 |
| EDDI | 9,18x | 3,78x | 1259 |
| CFCSS | 1,54x | 1,65x | 0 |
| RASM | 1,93x | 2,33x | 0 |
| EDDI+CFCSS | 13,56x | 5,51x | 1259 |
| EDDI+RASM | 14,40x | 5,99x | 1259 |

(medie geometriche sulle quattro applicazioni, rispetto alla `baseline`;
1259 è il totale dei controlli inseriti nelle quattro applicazioni.)

Cosa dire:

- **EDDI costa circa 3,8 volte** le istruzioni: ogni istruzione è eseguita due
  volte, e ogni controllo aggiunge confronti e un salto;
- **il codice cresce molto più dell'esecuzione** (9,2x): ogni funzione esiste
  fino in quattro versioni (`f`, `f_ret`, `f_dup`, `f_ret_dup`), anche quelle
  che alla fine non vengono più chiamate restano nell'eseguibile, ogni
  controllo spezza un blocco in più blocchi, e senza ottimizzazioni ogni
  valore passa dallo stack;
- **le tecniche del flusso costano meno** (1,7x CFCSS, 2,3x RASM): aggiungono
  poche istruzioni per blocco. RASM costa più di CFCSS perché aggiorna la
  firma due volte per blocco (all'ingresso e prima dell'uscita, con la
  `select`);
- **combinate, i costi si sommano**: EDDI+RASM esegue 6 volte le istruzioni
  dell'originale.

Il costo è misurato in **istruzioni eseguite** (contate dal profilo), non in
tempo: i programmi durano pochi millisecondi, troppo poco per misure di tempo
affidabili, mentre il numero di istruzioni è esatto e ripetibile.

## 11.2 Bit-flip nei registri

| Configurazione | masked | rilevati (dati) | rilevati (CFC) | crash | hang | **SDC** | intervallo 95% |
|---|---:|---:|---:|---:|---:|---:|---|
| baseline | 86,2 | 0,0 | 0,0 | 12,0 | 0,1 | **1,70** | 1,34–2,15 |
| EDDI | 84,0 | 2,9 | 0,0 | 13,0 | 0,0 | **0,15** | 0,07–0,33 |
| CFCSS | 85,5 | 0,0 | 2,1 | 11,5 | 0,0 | **0,88** | 0,63–1,21 |
| RASM | 85,8 | 0,0 | 2,2 | 11,3 | 0,0 | **0,65** | 0,44–0,95 |
| EDDI+CFCSS | 83,4 | 1,3 | 2,5 | 12,8 | 0,0 | **0,03** | 0,00–0,14 |
| EDDI+RASM | 83,3 | 2,0 | 1,6 | 13,1 | 0,0 | **0,03** | 0,00–0,14 |

(percentuali su 4000 guasti per riga.)

Cosa dire:

- **la maggior parte dei bit-flip non fa nulla** (86% *masked*): in un dato
  istante molti registri non contengono valori che verranno usati, o vengono
  sovrascritti prima di essere letti;
- **il 12% fa andare in crash il programma**: un bit cambiato in un indirizzo
  porta a leggere o scrivere fuori dalla memoria valida. Nella `baseline`
  l'87% dei crash viene da un bit-flip in `rsp` (52%) o in `rbp` (35%), i due
  puntatori allo stack: con `-O0` ogni variabile si legge e si scrive
  attraverso di loro;
- **l'1,70% produce un risultato sbagliato in silenzio**: sono questi i guasti
  che contano;
- **EDDI li riduce di 11 volte** (0,15%). I suoi controlli scattano solo nel
  2,9% dei casi, ma sono proprio i casi pericolosi: un valore sbagliato viene
  fermato prima di essere scritto in memoria, passato a una funzione o usato
  in un salto;
- **CFCSS e RASM da soli aiutano poco** (0,88% e 0,65%): una firma vede solo
  i bit-flip che cambiano il percorso del programma, non quelli che cambiano
  un valore;
- **combinando EDDI con una tecnica del flusso resta una sola SDC su 4000**
  (0,03%).

## 11.3 Salti condizionali invertiti

| Configurazione | masked | rilevati (dati) | rilevati (CFC) | crash | **SDC** | intervallo 95% |
|---|---:|---:|---:|---:|---:|---|
| baseline | 21,2 | 0,0 | 0,0 | 0,0 | **78,80** | 77,51–80,04 |
| EDDI | 4,6 | 76,8 | 0,0 | 0,0 | **18,57** | 17,40–19,81 |
| CFCSS | 7,5 | 0,0 | 62,6 | 0,1 | **29,75** | 28,35–31,19 |
| RASM | 0,0 | 0,0 | 99,3 | 0,0 | **0,73** | 0,51–1,04 |
| EDDI+CFCSS | 2,1 | 35,5 | 54,2 | 0,0 | **8,18** | 7,37–9,06 |
| EDDI+RASM | 0,0 | 34,0 | 66,0 | 0,0 | **0,00** | 0,00–0,10 |

Cosa dire:

- **i salti invertiti sono i guasti peggiori**: nei programmi senza protezione
  il 78,8% produce un risultato sbagliato, perché il risultato dipende da
  quante volte si ripetono i cicli e da quale ramo si prende;
- **EDDI e CFCSS rilevano solo i salti dei loro stessi controlli.** Abbiamo
  misurato dai profili quanti dei salti condizionali eseguiti appartengono ai
  controlli (cioè hanno come destinazione il blocco che chiama il gestore
  d'errore): il **76,3%** con EDDI e il **62,4%** con CFCSS. Se si inverte uno
  di questi salti, il programma va nel blocco d'errore e il guasto risulta
  "rilevato". Infatti le percentuali di rilevamento (76,8% e 62,6%) sono
  quasi identiche. Quando invece si inverte un salto **del programma**:
  - EDDI non se ne accorge, perché confronta le due copie della condizione
    *prima* del salto, ma poi esegue un solo salto: entrambe le copie dei dati
    vanno dalla parte sbagliata e restano coerenti tra loro;
  - CFCSS non se ne accorge, perché il successore sbagliato è comunque un
    successore lecito (capitolo 4.3);

  e restano il 18,6% e il 29,8% di SDC;
- **RASM rileva il 99,3%**: anche con RASM i salti dei controlli sono la
  maggioranza (67,4%), ma RASM rileva anche le inversioni dei salti del
  programma, perché la firma viene aggiornata con la stessa condizione del
  salto (capitolo 4.4);
- **le 29 SDC rimaste a RASM (0,73%) vengono tutte da un solo salto** di
  `pid_control`, nella funzione `load_at`:

  ```c
  static float load_at(int k) {
      return (k >= 1200 && k < 1300) ? 1.5f : 0.0f;
  }
  ```

  Nell'IR questa è una `select` tra due `float`, senza salti: RASM non ha
  nessun salto da proteggere. Ma il back-end x86, senza ottimizzazioni,
  traduce la `select` con un `jne` (lo si vede con `sdc_sites.py`: i due
  successori del salto caricano due valori diversi in `xmm0`). Nessuna
  tecnica che lavora sull'IR può vedere un salto creato dopo, dal back-end.
  È un limite interessante da citare all'orale;
- **EDDI+RASM non lascia nessuna SDC**: le due tecniche si coprono a vicenda.
  RASM vede i salti del programma andati dalla parte sbagliata; EDDI vede il
  caso di `load_at`, perché duplica anche la `select`: il back-end crea due
  salti, uno per copia, e se uno dei due sbaglia le due copie del valore
  differiscono e il controllo successivo se ne accorge.

## 11.4 Il bug 3 nei numeri

| Modello di guasto | SDC prima | SDC dopo | rilevati (CFC) prima | rilevati (CFC) dopo |
|---|---:|---:|---:|---:|
| bit-flip nei registri | 0,10% | 0,03% | 0,5% | 1,6% |
| salti invertiti | **10,53%** | **0,00%** | 34,6% | 66,0% |

Prima della correzione, EDDI+RASM lasciava il 10,5% di SDC sui salti
invertiti: peggio di RASM da solo (0,73%), anche se aveva in più tutti i
controlli di EDDI. È stato questo controsenso a far partire l'indagine
(capitolo 8.4): tutte le 421 SDC erano su salti verso blocchi `VerificationBB`
di EDDI dove RASM reimpostava la firma senza controllarla. Dopo la correzione
i controlli di RASM rilevano il 66% dei salti invertiti invece del 34,6%, e
non resta nessuna SDC.

## 11.5 Per applicazione

SDC dei bit-flip nei registri (%, 1000 guasti per cella):

| Applicazione | baseline | EDDI | CFCSS | RASM | EDDI+CFCSS | EDDI+RASM |
|---|---:|---:|---:|---:|---:|---:|
| aes128 | 2,2 | 0,2 | 0,8 | 0,5 | 0,0 | 0,0 |
| fft | 1,3 | 0,0 | 0,8 | 0,9 | 0,0 | 0,0 |
| huffman | 1,6 | 0,0 | 0,4 | 0,9 | 0,1 | 0,1 |
| pid_control | 1,7 | 0,4 | 1,5 | 0,3 | 0,0 | 0,0 |

SDC dei salti invertiti (%):

| Applicazione | baseline | EDDI | CFCSS | RASM | EDDI+CFCSS | EDDI+RASM |
|---|---:|---:|---:|---:|---:|---:|
| aes128 | 88,8 | 22,9 | 31,8 | 0,0 | 10,0 | 0,0 |
| fft | 66,8 | 13,6 | 23,7 | 0,0 | 5,6 | 0,0 |
| huffman | 89,7 | 24,9 | 30,0 | 0,0 | 10,7 | 0,0 |
| pid_control | 69,9 | 12,9 | 33,5 | 2,9 | 6,4 | 0,0 |

Le applicazioni si comportano in modo simile. Con 1000 guasti per cella le
differenze di pochi decimi di punto (per esempio 0,2% contro 0,4%) **non sono
significative**: corrispondono a 2 o 4 casi. Le uniche differenze nette sono
quelle già spiegate (le SDC di RASM in `pid_control`).

## 11.6 Il messaggio in tre frasi

1. La duplicazione dei dati (EDDI) protegge bene dai bit-flip nei registri
   (11 volte meno SDC) ma costa molto (3,8 volte le istruzioni) e non vede i
   salti andati dalla parte sbagliata.
2. Il controllo del flusso a firme vede quei salti solo se la firma dipende
   dalla direzione del salto (RASM sì, CFCSS no); nessuna tecnica sull'IR vede
   i salti creati dal back-end.
3. Combinare le due famiglie dà la protezione migliore, a patto che le due
   trasformazioni non si ostacolino: la fault injection ha trovato proprio un
   caso in cui lo facevano (il bug 3).
