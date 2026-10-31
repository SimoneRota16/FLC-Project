# 6. Le quattro applicazioni

## 6.1 Perché queste e con quali regole

La proposta lascia libera la scelta del codice da proteggere. Abbiamo scritto
quattro programmi piccoli ma realistici, scelti per coprire tipi di calcolo
diversi e tipici dei sistemi embedded, dove si usa la SIHFT: crittografia
(operazioni su byte e tabelle), elaborazione del segnale (virgola mobile a
doppia precisione), compressione (strutture dati e salti che dipendono dai
dati), controllo automatico (virgola mobile a singola precisione, stato
globale).

Tutti seguono le stesse regole, ciascuna con un motivo preciso:

| Regola | Perché |
|---|---|
| **deterministici**: nessun input esterno, nessun numero casuale vero | ogni esecuzione senza guasti deve stampare esattamente lo stesso output, altrimenti non si potrebbe confrontare l'output con quello di riferimento |
| **autoverificanti**: confrontano i risultati con valori attesi e stampano `SUCCESS` o `FAIL` (codice d'uscita 0 o 1) | un risultato sbagliato si vede sia nell'output sia nel codice d'uscita |
| definiscono i due **gestori d'errore**, che stampano `FAULT_DETECTED: ...` su stderr ed escono con codice 2 o 3 | un rilevamento si riconosce subito, sia nei test sia nella fault injection |
| sono validi sia in **C sia in C++** | il sistema di test di ASPIS compila il programma di riferimento con `clang++` |
| sono **brevi**: meno di un milione di istruzioni eseguite | migliaia di esperimenti di fault injection devono durare minuti, non giorni |
| usano solo la **libreria standard** e sono rilasciati con **licenza MIT** | possono entrare nel repository di ASPIS |

Ogni file inizia con un commento che spiega cosa fa il programma e quali
caratteristiche del C mette alla prova.

## 6.2 `aes128.c`: cifratura AES-128

329 righe, 645.668 istruzioni eseguite. Implementa l'algoritmo di
cifratura a blocchi AES con chiave di 128 bit (standard FIPS-197):

- calcola all'avvio le tabelle `sbox` e `inv_sbox` (la sostituzione di byte
  di AES) con l'aritmetica nel campo finito GF(2^8), e le salva in array
  globali **non costanti**, così ASPIS deve duplicarli;
- esegue il *known-answer test* dell'appendice C.1 dello standard: cifra un
  blocco noto con una chiave nota e confronta il risultato con quello
  pubblicato (`69c4e0d86a7b0430d8cdb78070b4c55a`), poi lo decifra;
- cifra e decifra in modalità CBC un messaggio di 64 byte e verifica che il
  testo decifrato sia uguale all'originale; stampa anche un hash (FNV-1a)
  del testo cifrato.

Stampa le tabelle e i risultati intermedi e finisce con `SUCCESS` se tutti i
confronti tornano. Nella prima versione la funzione `print_hex` riceveva
un'etichetta come parametro e la stampava con `printf("%s", label)`: era
proprio il caso che faceva andare in crash EDDI (capitolo 8). Ora
l'etichetta viene stampata da chi chiama `print_hex`, con una stringa
letterale.

## 6.3 `fft.c`: trasformata di Fourier

186 righe, 367.759 istruzioni. Calcola la FFT radix-2 (algoritmo di
Cooley-Tukey iterativo) di un segnale di 256 campioni complessi in doppia
precisione:

- il segnale è la somma di tre sinusoidi (frequenze 5, 12 e 40) più un
  rumore deterministico;
- trova le tre frequenze dominanti e controlla che siano 5, 12 e 40;
- verifica il **teorema di Parseval** (l'energia del segnale nel tempo è
  uguale a quella in frequenza, divisa per N);
- calcola la trasformata inversa e controlla che ricostruisca il segnale
  con un errore inferiore a 10^-9.

Usa la libreria matematica (`sin`, `cos`, `sqrt`), e infatti va compilato con
`-lm`.

## 6.4 `huffman.c`: compressione di Huffman

225 righe, 170.974 istruzioni. Comprime e decomprime un testo fisso con la
codifica di Huffman:

- conta le frequenze dei caratteri;
- costruisce l'albero di Huffman con un **min-heap** binario (con un criterio
  deterministico per i casi di parità);
- assegna i codici con una visita ricorsiva dell'albero;
- scrive il testo compresso in un buffer di bit globale e poi lo decodifica
  percorrendo l'albero;
- controlla che il testo decodificato sia uguale all'originale e stampa
  statistiche e un checksum (Adler-32) dei dati compressi.

L'albero è un array di struct con indici interi al posto dei puntatori, e i
cicli del heap hanno uscite che dipendono dai dati: tanti salti condizionali
"interessanti" per il controllo del flusso.

## 6.5 `pid_control.c`: controllore PID

159 righe, 477.391 istruzioni. Simula per 2000 passi di 10 ms un motore in
corrente continua (modello del primo ordine) controllato da un **PID**:

- il riferimento di velocità cambia a gradini (10, 25, 5, 15 rad/s);
- tra il passo 1200 e il 1300 si applica un disturbo di coppia;
- il sensore di velocità è quantizzato come un encoder;
- il PID ha la derivata filtrata, la saturazione dell'uscita a ±24 V e un
  meccanismo *anti-windup* (l'integrale viene aggiornato solo se aiuta a
  uscire dalla saturazione).

Stampa ogni 250 passi lo stato del sistema e alla fine l'errore integrale
assoluto (IAE), la sovraelongazione e i passi in saturazione; il controllo
finale verifica che la velocità abbia raggiunto il riferimento. Usa `float`
(singola precisione), tipico dei microcontrollori, e tiene lo stato del
controllore in una struct globale aggiornata tramite puntatore.

# 7. I test di compatibilità

## 7.1 Il sistema di test di ASPIS

ASPIS ha un sistema di test basato su **pytest** (cartella `testing/`). I
programmi di test sono elencati in `testing/config/tests.toml`, uno per voce:

```toml
[[tests]]
test_name = "c_fft"
source_file = "c/applications/fft.c"     # relativo a testing/tests/
add_compiler_flags = "-lm"               # opzioni in più per aspis.sh
# black_list = ["--inter-rasm"]          # tecniche da non provare
```

Il file `testing/test.py` prende ogni test e lo compila con **55
combinazioni**: le 11 opzioni dei dati (`--no-dup`, `--eddi`, `--eddi
--multiple-errbb`, `--eddi --coarse-grained`, `--eddi --multiple-errbb
--coarse-grained`, le stesse quattro per `--reddi`, `--seddi`, `--fdsc`) per le
5 del flusso (`--no-cfc`, `--cfcss`, `--rasm`, `--racfed`, `--inter-rasm`). Per
ogni combinazione:

1. compila il programma con `clang++` senza ASPIS (una volta sola) e lo
   esegue: è l'output di riferimento;
2. compila il programma con `aspis.sh` e le opzioni della combinazione;
3. lo esegue; il test **passa** se l'esecuzione termina con codice 0 e
   l'output è uguale a quello di riferimento.

Ogni combinazione ha un limite di 60 secondi. Le combinazioni nella
`black_list` di un test vengono saltate (*skipped*).

Si lancia così, dalla cartella `testing/` di ASPIS (dopo aver scritto il
percorso di LLVM in `testing/config/llvm.toml`):

```bash
pytest test.py -v > harness.log
```

Ogni riga del log è una combinazione, per esempio
`test.py::test_aspis[c_fft---rasm---eddi] PASSED`: nome del test, tecnica del
flusso, tecnica dei dati, esito.

## 7.2 Cosa abbiamo fatto

Abbiamo aggiunto le quattro applicazioni in `testing/tests/c/applications/` e
le loro voci in fondo a `tests.toml` (sono nel file
`aspis-integration/flc_tests.toml`), poi abbiamo eseguito l'intera suite tre
volte (log in `results/compatibility/`):

- con la **prima versione** delle applicazioni, sul branch principale di
  ASPIS (`b66a090`): `harness_master_first_version.log.gz`;
- con la **versione finale** delle applicazioni (quella che evita il bug di
  EDDI), sul branch principale: `harness_master.log.gz`;
- con la versione finale e le **nostre due patch** (la correzione di RASM e
  le voci dei test): `harness_fixed.log.gz`.

Ognuna delle esecuzioni compila e prova 52 test × 55 combinazioni = 2860
programmi e dura circa 9 minuti. Lo script `fault_injection/analyze.py` legge
i log e produce le tabelle del report.

## 7.3 I risultati

Le nostre applicazioni (4 applicazioni × 5 tecniche del flusso per ogni riga):

| Protezione dei dati | prima versione, `master` | versione finale, `master` | versione finale, con le patch |
|---|---:|---:|---:|
| nessuna (`--no-dup`) | 20 / 20 | 20 / 20 | 20 / 20 |
| EDDI, 4 varianti | 0 / 80 | 80 / 80 | 80 / 80 |
| sEDDI | 0 / 20 | 20 / 20 | 20 / 20 |
| FDSC | 0 / 20 | 20 / 20 | 20 / 20 |
| REDDI, 4 varianti | 80 / 80 | 80 / 80 | 80 / 80 |
| **totale** | **100 / 220** | **220 / 220** | **220 / 220** |

Come si legge:

- **le tecniche del flusso da sole funzionano** su tutte le applicazioni
  (riga `--no-dup`);
- **REDDI passa**, ma per un motivo banale: REDDI protegge solo ciò che è
  annotato con `to_harden` (e quello che usa), e le nostre applicazioni non
  hanno annotazioni, quindi REDDI non protegge nulla;
- con la prima versione **EDDI, sEDDI e FDSC andavano in crash su tutte e
  quattro le applicazioni** (*segmentation fault*), con qualunque tecnica del
  flusso: è il bug di EDDI del capitolo 8;
- con la versione finale, che evita quel bug, passano tutte le 220
  combinazioni, sia su `master` sia con le nostre patch.

I 48 test che ASPIS aveva già:

| Esito | `master` | con le patch |
|---|---:|---:|
| passati | 2453 | 2453 |
| falliti | 33 | 33 |
| saltati | 154 | 154 |

I risultati sono **identici**: la correzione di RASM non rompe nulla
(nessuna *regressione*). I 154 saltati sono le combinazioni nelle
`black_list`. I 33 falliti sono tutte le combinazioni non escluse di un solo
test, `cpp_complex`, e falliscono anche su `master` già nel primo passo: il
programma di riferimento non compila, perché il sorgente usa `std::powf`, che
la libreria C++ della nostra macchina (libstdc++ 13) non dichiara. È un
problema del test e dell'ambiente, non di ASPIS né delle nostre modifiche.
