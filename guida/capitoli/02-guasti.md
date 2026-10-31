# 3. Guasti transitori e tolleranza ai guasti via software

## 3.1 Soft error

Una particella (un neutrone dei raggi cosmici, una particella alfa emessa
dai materiali del chip) che colpisce un transistor può depositare abbastanza
carica da cambiare il valore di un bit: un registro, una cella di memoria, un
latch della pipeline. Il componente non si rompe: al prossimo accesso
funziona di nuovo. Si parla di **guasto transitorio**, *soft error* o *SEU*
(*single event upset*).

Il problema è serio nello spazio e in alta quota (avionica, satelliti) ma
anche a terra nei sistemi critici (automotive, ferroviario, medicale), e
cresce con la miniaturizzazione: transistor più piccoli e tensioni più basse
significano che basta meno carica per invertire un bit.

## 3.2 Guasto, errore, fallimento

La terminologia classica distingue tre livelli:

- **guasto** (*fault*): la causa fisica, per esempio il bit invertito;
- **errore** (*error*): lo stato del sistema diventato sbagliato, per esempio
  un valore errato in un registro che verrà usato;
- **fallimento** (*failure*): il servizio fornito è sbagliato, per esempio il
  programma stampa un risultato errato.

Non tutti i guasti diventano errori (il registro poteva non contenere nulla
di utile) e non tutti gli errori diventano fallimenti.

## 3.3 Gli esiti di un guasto

Quando si inietta un guasto in un programma, l'esecuzione può finire in
cinque modi, che ritroveremo in tutti i risultati:

| Esito | Significato |
|---|---|
| **masked** (mascherato) | il programma termina normalmente con l'output corretto: il guasto non ha avuto effetti (registro non usato, valore sovrascritto, differenza irrilevante) |
| **detected** (rilevato) | un controllo inserito dalla protezione si è accorto del guasto e ha chiamato il gestore d'errore |
| **crash** | il programma è stato ucciso da un segnale, tipicamente `SIGSEGV` (accesso a un indirizzo non valido) |
| **hang** (blocco) | il programma non termina (ciclo infinito) entro un tempo limite |
| **SDC** (*silent data corruption*) | il programma termina "normalmente" ma con un risultato sbagliato |

L'esito peggiore è la **SDC**: nessuno se ne accorge, e un sistema che si fida
del risultato agisce su un dato sbagliato. Crash, hang e rilevamenti sono
invece errori *rilevati* (*DUE, detected unrecoverable errors*): il sistema
sa che qualcosa è andato storto e può reagire (riavviare, ripetere il
calcolo, passare a uno stato sicuro).

Lo scopo delle tecniche che studiamo è quindi **trasformare le SDC in
rilevamenti**. Non correggono l'errore: lo segnalano.

## 3.4 Protezione hardware e protezione software

Ci si può proteggere in hardware: memorie con codici di correzione (ECC),
triplicazione dei circuiti con votazione (TMR), processori che eseguono lo
stesso programma in parallelo e confrontano i risultati (*lockstep*). Funziona
bene, ma costa: chip speciali, più area, più consumo.

L'alternativa è la **SIHFT** (*Software-Implemented Hardware Fault
Tolerance*): si trasforma il programma in modo che si accorga da solo dei
guasti, e lo si esegue su hardware normale ed economico. Il prezzo si paga in
**tempo di esecuzione** (il programma fa più lavoro) e in **dimensione del
codice**.

Le tecniche SIHFT si dividono in due famiglie:

- **protezione del flusso dei dati** (*data-flow*): si duplica il calcolo e si
  confrontano le due copie. Se un guasto altera una sola copia, il confronto
  lo rivela;
- **controllo del flusso di esecuzione** (*control-flow checking*, CFC): a
  ogni basic block si associa una firma e durante l'esecuzione si verifica
  che i blocchi vengano eseguiti in un ordine permesso dal grafo di controllo
  del flusso. Serve contro i guasti che fanno saltare il programma nel posto
  sbagliato.

Le due famiglie sono complementari, e si possono combinare.

## 3.5 Modelli di guasto

Per valutare una tecnica bisogna decidere quali guasti simulare. Un **modello
di guasto** descrive il guasto in modo astratto. I più usati:

- **bit-flip in un registro**: un bit di un registro del processore viene
  invertito in un istante qualsiasi. Rappresenta i guasti nel banco dei
  registri e, approssimativamente, quelli nelle unità di calcolo;
- **salto condizionale invertito**: un salto condizionale va dalla parte
  opposta a quella decisa dalla condizione. Rappresenta un guasto nei flag o
  nell'unità che gestisce i salti. Il programma resta su archi "permessi" del
  grafo, ma sbaglia strada;
- **salto a un indirizzo sbagliato**: il program counter viene alterato e il
  programma continua da un'istruzione qualsiasi;
- **bit-flip in memoria**: un bit di una cella di memoria viene invertito.

Nel progetto usiamo i primi due (capitolo 9).

## 3.6 Fault injection

Per misurare quanto è efficace una protezione si fa **fault injection**: si
esegue il programma molte volte, ogni volta con un guasto artificiale in un
punto scelto a caso, e si contano gli esiti. Il guasto si può iniettare
simulando l'hardware, con apparecchiature fisiche (fasci di particelle,
laser), oppure via software, modificando lo stato del programma mentre è in
esecuzione. Noi usiamo l'ultima strada: un debugger (gdb) ferma il
programma sotto test e ne modifica i registri.

Siccome i guasti sono scelti a caso, ogni percentuale misurata è una **stima**,
e va accompagnata da un **intervallo di confidenza**: con 2000 guasti una
percentuale dello 0,1% significa 2 casi, e la vera probabilità potrebbe
essere un po' più alta o più bassa. Il capitolo 10 spiega come si calcola
l'intervallo.
