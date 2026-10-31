# 10. La campagna e la statistica

## 10.1 Il file di configurazione

`fault_injection/campaign.toml` descrive la campagna:

```toml
[campaign]
root = ".."                               # i sorgenti sono relativi a ASPIS-Project/
work = "~/aspis-project/campaign"         # eseguibili, profili, risultati di ogni gruppo
results = "../results/fault_injection"    # metrics.csv, outcomes.csv, raw.csv.gz
aspis = "~/aspis-project/ASPIS"           # ASPIS con le nostre patch
llvm_bin = "~/aspis-project/toolchain/LLVM-21.1.8-Linux-X64/bin"
tmp = "/dev/shm/aspis-fi"                 # file di output degli esperimenti
models = ["reg", "branch"]
injections = 500                          # per applicazione x configurazione x modello
seed = 2026
timeout_factor = 20                       # dopo il guasto: hang = 20 volte il tempo normale...
timeout_min_ms = 1000                     # ...e almeno 1 secondo

[[config]]                                # la prima è il riferimento
name = "baseline"
flags = "--no-dup --no-cfc"
...                                       # EDDI, CFCSS, RASM, EDDI+CFCSS, EDDI+RASM

[[application]]
name = "fft"
source = "benchmarks/fft.c"
flags = "-lm"
...
```

I percorsi in `[campaign]` vanno adattati alla propria macchina.

## 10.2 Cosa fa `campaign.py`

```bash
python3 fault_injection/campaign.py fault_injection/campaign.toml --jobs 4
```

1. **Compila** ogni applicazione con ogni configurazione (`aspis.sh` con le
   opzioni della configurazione), ognuna nella sua cartella
   `build/<applicazione>/<configurazione>/`. `aspis.sh` viene eseguito *dentro*
   quella cartella perché EDDI scrive un file di lavoro
   (`compiled_eddi_functions.csv`) nella cartella corrente: due compilazioni
   in parallelo nella stessa cartella si sovrascriverebbero il file a vicenda.
2. **Misura** la dimensione del codice (sezione `.text`, con `llvm-size`) e il
   numero di controlli inseriti da EDDI (la riga `Comparison Counter` stampata
   da `aspis.sh`).
3. **Fa le golden run** (capitolo 9.1) e controlla che tutte le
   configurazioni stampino esattamente lo stesso output della `baseline`:
   una protezione non deve cambiare il risultato.
4. Scrive `metrics.csv`: per ogni applicazione e configurazione, dimensione
   del codice, controlli, istruzioni eseguite (contate da valgrind).
5. **Prepara gli esperimenti** di ogni gruppo (applicazione, configurazione,
   modello): 500 istanti scelti come nel capitolo 9.2, con un generatore di
   numeri casuali il cui seme è calcolato con SHA-256 dai nomi
   (`"2026/aes128/EDDI/reg"` → i primi 15 caratteri esadecimali dell'hash). Il
   seme è sempre lo stesso, quindi la campagna è **riproducibile**.
6. **Lancia gli esperimenti** con gdb (capitolo 9.3), quattro alla volta, e li
   classifica (9.4). Il tempo limite per gli *hang* è 20 volte il tempo
   normale del programma, e almeno 1 secondo: per i nostri programmi, che
   durano pochi millisecondi, vale sempre 1 secondo.
7. **Aggrega**: scrive `raw.csv.gz` (una riga per esperimento) e
   `outcomes.csv` (gli esiti per applicazione, configurazione e modello, con la
   percentuale di SDC e il suo intervallo di confidenza).

Ogni gruppo salva i suoi risultati su file appena finito (scrivendo prima un
file `.part` e rinominandolo alla fine): se la campagna si interrompe,
rilanciandola rifà solo quello che manca.

I numeri della nostra campagna: 4 applicazioni × 6 configurazioni × 2 modelli
× 500 = **24.000 esperimenti**, più **4000** di EDDI+RASM con ASPIS senza la
correzione di RASM (4 applicazioni × 2 modelli × 500). Su una macchina
virtuale con 4 core la campagna principale ha richiesto circa 38 minuti
(compilazioni e golden run pochi secondi, il resto esperimenti), quella senza
correzione circa 6. Undici bit-flip su 12.000 sono risultati "non iniettati"
(capitolo 9.3) e non vengono contati: per questo alcune configurazioni hanno
1995-1999 esperimenti invece di 2000.

## 10.3 Percentuali e intervalli di confidenza

Ogni percentuale della campagna è una **stima**: abbiamo scelto 2000 guasti a
caso (500 per applicazione) tra tutti quelli possibili, e la percentuale
osservata `p = k / n` (`k` SDC su `n` esperimenti) è vicina, ma non uguale,
alla vera probabilità. L'**intervallo di confidenza al 95%** è un intervallo
costruito in modo che, se si ripetesse la campagna molte volte, conterrebbe
la vera probabilità nel 95% dei casi.

La formula più nota (intervallo "di Wald") è `p ± 1,96 · sqrt(p(1-p)/n)`, ma
funziona male quando `p` è vicina a 0, proprio il nostro caso: con `k = 0`
dà l'intervallo `[0, 0]`, come se fossimo sicuri che la probabilità sia
esattamente zero. Usiamo quindi l'**intervallo di Wilson**, che si comporta
bene anche agli estremi:

```text
            p + z²/(2n)  ±  z · sqrt( p(1-p)/n + z²/(4n²) )
intervallo = ----------------------------------------------      con z = 1,96
                            1 + z²/n
```

Esempi dalla nostra campagna:

| | k / n | p | intervallo di Wilson al 95% |
|---|---:|---:|---|
| EDDI, bit-flip nei registri | 0 / 2000 | 0% | 0,00% – 0,19% |
| EDDI+RASM, salti invertiti | 0 / 2000 | 0% | 0,00% – 0,19% |
| baseline, bit-flip nei registri | 42 / 1995 | 2,11% | 1,56% – 2,83% |

Il primo esempio si legge: "non abbiamo visto nessuna SDC su 2000 bit-flip;
la vera probabilità è, con il 95% di confidenza, sotto lo 0,19%". Quando due
intervalli non si sovrappongono (1,56-2,83% contro 0,00-0,19%), la differenza
non è dovuta al caso.

## 10.4 La media geometrica

Per riassumere il costo su quattro applicazioni usiamo la **media
geometrica** dei rapporti, `(r1 · r2 · r3 · r4)^(1/4)`, non quella aritmetica.
Il motivo: i rapporti si moltiplicano, non si sommano. Se un programma
raddoppia (2x) e un altro dimezza (0,5x), la media aritmetica dice 1,25x,
quella geometrica 1x, che è la risposta giusta ("in media non cambia
nulla"). Per EDDI i rapporti delle istruzioni eseguite sono 3,68 (`aes128`),
3,63 (`fft`), 3,56 (`huffman`) e 4,12 (`pid_control`): la media geometrica è
3,74.

## 10.5 Gli script di analisi

- `analyze.py` legge i risultati della campagna e i log del sistema di test e
  scrive le tabelle (`report/tables/*.md`, in formato Markdown) e le figure
  (`report/figures/*.svg` e `.png`, con matplotlib) che `report/build.py`
  inserisce nel report;
- `sdc_sites.py` (capitolo 8.3) mostra dove sono avvenute le SDC di una
  configurazione: le istruzioni colpite, quante volte, e i successori dei
  salti;
- `check_jumps.py` (capitolo 11.3) conta, dai profili delle golden run, quanti
  dei salti condizionali eseguiti appartengono ai controlli di ASPIS.
