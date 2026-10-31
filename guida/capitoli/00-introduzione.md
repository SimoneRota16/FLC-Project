---
title: "Guida al progetto «Harden a C application with ASPIS»"
subtitle: "Tutto quello che c'è da sapere per capire, rifare e presentare il progetto"
author:
  - "Per Alberto Rotolo e Simone Rota"
date: "Linguaggi Formali e Compilatori, A.A. 2026/27, Politecnico di Milano"
lang: it
---

# Come leggere questa guida

Questa guida spiega **tutto** il progetto, partendo da zero. Si assume solo
quello che uno studente di ingegneria informatica conosce già: il linguaggio
C, le basi di architettura dei calcolatori (registri, istruzioni, memoria) e
di sistemi operativi (processi, segnali, `fork`/`exec`). Non si assume
nessuna conoscenza del corso di Linguaggi Formali e Compilatori, di LLVM o di
tolleranza ai guasti.

La guida è divisa in tre parti:

- **Parte I, i concetti** (capitoli 1-4): cosa chiede il progetto, cos'è un
  compilatore e com'è fatto LLVM, cosa sono i guasti transitori e come si
  proteggono i programmi via software, quali tecniche implementa ASPIS.
- **Parte II, il lavoro fatto** (capitoli 5-11): come si usa ASPIS, le
  quattro applicazioni, i test, i due bug trovati in ASPIS, l'iniettore di
  guasti, la campagna di fault injection e i suoi risultati.
- **Parte III, pratica ed esame** (capitoli 12-18): come integrare il lavoro
  in ASPIS, come rifare tutti gli esperimenti, la mappa dei file, cosa è
  stato tolto dalle versioni precedenti, cosa dire slide per slide nella
  chiamata con i supervisori, le domande probabili all'orale con le risposte
  e un glossario.

Il consiglio è leggere i capitoli nell'ordine, con il repository aperto
accanto: ogni volta che si parla di un file, il percorso è scritto in
`questo formato`, relativo alla cartella `ASPIS-Project/` del repository
(salvo dove indicato diversamente).

Il report ufficiale del progetto, quello che leggeranno i supervisori, è
`ASPIS-Project/report/report.pdf` ed è in inglese. Questa guida ne segue la
struttura, ma spiega molto di più: il perché delle scelte, i meccanismi
interni e i dettagli del codice. Dove serve, riporta i termini inglesi usati
nel report.

# Parte I. I concetti

# 1. Il progetto in cinque minuti

## 1.1 Cosa chiede la proposta

Il progetto «Harden a C application with ASPIS» (supervisori Davide Baroffio
ed Emilio Corigliano, del gruppo HEAPLab) ha tre obiettivi:

1. **proteggere applicazioni C con ASPIS**, un insieme di trasformazioni del
   compilatore LLVM che rendono un programma capace di accorgersi dei guasti
   hardware;
2. **verificare la protezione con la fault injection**, cioè iniettando
   guasti artificiali nel programma in esecuzione e osservando cosa succede;
3. **integrare le applicazioni nel branch principale di ASPIS** come test di
   regressione, così che ogni modifica futura di ASPIS venga provata anche
   su di esse.

I supervisori hanno anche scritto (file `Buongiorno,.txt` nella radice del
repository) che si può usare l'intelligenza artificiale, anche per tutto il
progetto, a patto di dichiarare nel report se e per cosa la si è usata, che
il numero di programmi da proteggere dipende dalla loro complessità (e se ne
può discutere con loro), e che quando saremo pronti ci sarà una chiamata in
cui spiegare loro il lavoro; il report servirà come riferimento per la
valutazione.

## 1.2 Cosa è stato fatto

- **Quattro applicazioni** scritte apposta, piccole e capaci di controllare
  da sole il proprio risultato: cifratura AES-128, trasformata di Fourier
  (FFT), compressione di Huffman, controllo PID della velocità di un motore.
- **Test di compatibilità** con il sistema di test ufficiale di ASPIS, che
  compila ogni programma con 55 combinazioni di tecniche. Sul branch
  principale di ASPIS la prima versione delle applicazioni funzionava solo in
  100 delle 220 combinazioni: con EDDI, sEDDI e FDSC (le tecniche che
  duplicano tutto il programma) le quattro applicazioni andavano in crash.
- **Due bug di ASPIS trovati.** Il primo, in EDDI, causava i crash: lo
  abbiamo isolato in un programma di cinque righe, descritto in un *bug
  report* ed evitato nelle applicazioni, che ora funzionano in tutte le 220
  combinazioni. Il secondo, in RASM, è stato scoperto grazie alla fault
  injection e lo abbiamo corretto cambiando una riga; con la correzione i 48
  test che ASPIS aveva già danno gli stessi risultati di prima.
- **Un iniettore di guasti** scritto in C (`fault_injection/injector/fi.c`)
  che, usando la chiamata di sistema `ptrace` (quella dei debugger), ferma il
  programma in un istante casuale e inverte un bit di un registro oppure fa
  andare un salto condizionale dalla parte sbagliata.
- **Una campagna di fault injection** di 56.000 esperimenti: 4 applicazioni,
  6 configurazioni di protezione, 2 modelli di guasto, 1000 guasti per
  combinazione, più 8000 esperimenti per misurare l'effetto del bug di RASM.
- **Due patch** pronte per il repository ufficiale di ASPIS (la correzione di
  RASM e l'aggiunta dei test) e il bug report di EDDI, non ancora inviati.
- **Il report** in inglese, con la dichiarazione sull'uso dell'AI.

## 1.3 Il messaggio principale dei risultati

- **EDDI** (duplicazione dei dati) riduce drasticamente i risultati sbagliati
  non rilevati causati da bit-flip nei registri, ma quasi quadruplica il
  costo: il programma esegue circa 3,7 volte le istruzioni.
- EDDI **non vede** un salto condizionale andato dalla parte sbagliata,
  perché le due copie del calcolo seguono lo stesso salto. Lo vedono invece
  le tecniche di **controllo del flusso a firme**, ma non tutte: **RASM**
  rileva quasi tutti i salti invertiti, **CFCSS** no, perché verifica solo
  che il salto vada in un blocco "ammesso", non in quello giusto.
- Combinare EDDI con RASM avrebbe dovuto dare il meglio dei due mondi, ma la
  fault injection ha mostrato che la combinazione rilevava i salti invertiti
  **peggio** di RASM da solo: era il bug di RASM, ora corretto.

I numeri precisi sono nel capitolo 11.

## 1.4 Il repository

| Cartella o file | Contenuto |
|---|---|
| `ASPIS-Project/benchmarks/` | le quattro applicazioni |
| `ASPIS-Project/aspis-integration/` | le due patch per ASPIS, le voci dei test, il bug report di EDDI e il suo riproduttore |
| `ASPIS-Project/fault_injection/` | l'iniettore (`injector/fi.c`), la campagna (`campaign.py`, `campaign.toml`), l'analisi (`analyze.py`, `export.py`, `sdc_sites.py`, `check_jumps.py`) |
| `ASPIS-Project/results/` | i log dei test e i risultati della campagna |
| `ASPIS-Project/report/` | il report (`report.md`, `report.pdf`) e lo script che lo genera |
| `guida/` | questa guida (fuori dalla cartella del progetto) |

## 1.5 Una nota sulla dimensione del progetto

La prima versione del progetto era molto più grande: 22 programmi di test,
23 bug corretti in ASPIS, un iniettore più sofisticato e una campagna di
240.900 esperimenti. Era troppo per un progetto che vale il 30% di un esame
da 5 CFU. Una seconda versione aveva già le quattro applicazioni attuali, ma
correggeva ancora due bug dentro EDDI, con modifiche al codice C++ di LLVM
difficili da studiare e da difendere all'orale. La versione attuale tiene
solo la correzione di RASM, che è una riga, ed evita il bug di EDDI nelle
applicazioni. Le versioni precedenti non sono andate perse: sono nella
storia di git, ai commit `e1d7e8b` e `7074cd6`. Il capitolo 15 riassume cosa
contenevano.
