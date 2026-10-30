# 4. Le tecniche implementate da ASPIS

## 4.1 EDDI: duplicare le istruzioni

**EDDI** (*Error Detection by Duplicated Instructions*, Oh, Shirvani e
McCluskey, 2002) è la tecnica di base della protezione dei dati. L'idea:
ogni istruzione viene eseguita due volte, su due copie separate dei dati, e
prima dei punti "pericolosi" si controlla che le due copie coincidano.

In pseudo-C, un'istruzione `a = b + c; x[i] = a;` diventa:

```c
a  = b  + c;          // copia originale
a2 = b2 + c2;         // copia duplicata, su variabili separate
if (a != a2 || i != i2) DataCorruption_Handler();   // controllo
x[i]  = a;            // la store originale
x2[i2] = a2;          // e la sua copia, su un array duplicato
```

Ogni variabile ha la sua copia (`b2`, `c2`, `x2`...): locali, globali, e
anche la memoria a cui puntano i puntatori, quando è possibile. Un guasto che
altera un valore di una sola copia viene scoperto al primo controllo che
coinvolge quel valore.

**Dove si controlla.** Controllare dopo ogni istruzione costerebbe troppo.
EDDI controlla nei **punti di sincronizzazione**, cioè dove un valore sbagliato
"esce" dal calcolo duplicato e diventa difficile da recuperare:

- prima di una **store**: un valore sbagliato scritto in memoria verrebbe letto
  da altre parti del programma (si confrontano il valore e l'indirizzo);
- prima di un **salto condizionale**: una condizione sbagliata manderebbe il
  programma sulla strada sbagliata (si confronta la condizione);
- prima di una **chiamata**: gli argomenti sbagliati verrebbero passati alla
  funzione chiamata.

**Costo.** Il programma esegue circa il doppio delle istruzioni, più i
confronti e i salti dei controlli: nei nostri programmi EDDI esegue circa 3,8
volte le istruzioni dell'originale (con `-O0`, dove ogni valore passa dallo
stack, il costo relativo è più alto che con il codice ottimizzato).

**Cosa non vede.** Se un guasto colpisce un valore *prima* che venga
duplicato (per esempio un dato letto da un file) o colpisce entrambe le
copie allo stesso modo, i confronti non lo vedono. Soprattutto, EDDI esegue
**un solo salto** per ogni salto del programma: le due copie della condizione
vengono confrontate, poi si salta usando la prima. Se è il salto stesso a
sbagliare direzione (guasto nei flag o nell'unità di salto), le due copie
dei dati seguono insieme la strada sbagliata e restano coerenti tra loro:
EDDI non se ne accorge.

**Le varianti in ASPIS.** Tutte sono implementate dallo stesso file
(`passes/EDDI.cpp`) con interruttori diversi:

| Opzione | Tecnica | Differenza rispetto a EDDI |
|---|---|---|
| `--eddi` | EDDI | duplica tutto, controlla prima di store, salti e chiamate |
| `--seddi` | sEDDI (*selective EDDI*) | non controlla prima delle store: costa meno, rileva più tardi |
| `--fdsc` | FDSC (*Full Duplication with Selective Checking*) | duplica tutto ma controlla solo in un sottoinsieme dei punti |
| `--reddi` | REDDI | protegge solo le funzioni e le globali annotate con `to_harden` |
| `--multiple-errbb` | | un blocco di errore separato per ogni controllo (utile per capire quale controllo è scattato) |
| `--coarse-grained` | REPAIR | raggruppa le istruzioni duplicate dopo quelle originali, per allontanarle nel tempo |

## 4.2 Il controllo del flusso a firme

Le tecniche di **control-flow checking** proteggono dai guasti che fanno
eseguire i blocchi nell'ordine sbagliato. L'idea comune: ogni basic block ha
una **firma** (un numero scelto dal compilatore), e il programma tiene in una
variabile la **firma di esecuzione**, aggiornata a ogni passaggio da un blocco
all'altro. All'ingresso di ogni blocco si controlla che la firma di
esecuzione sia quella del blocco: se il programma è arrivato lì da un punto
non previsto, la firma non torna e viene chiamato `SigMismatch_Handler`.

Gli errori di flusso si possono classificare così:

1. salto verso un blocco che **non** è un successore del blocco corrente
   (arco inesistente nel grafo);
2. salto nel **mezzo** di un blocco;
3. salto verso il successore **sbagliato** tra quelli ammessi: è il caso del
   salto condizionale invertito, dove l'arco esiste ma non è quello scelto
   dalla condizione.

Le tecniche differiscono in quali di questi errori rilevano.

## 4.3 CFCSS

**CFCSS** (*Control-Flow Checking by Software Signatures*, Oh, Shirvani e
McCluskey, 2002). Ogni blocco `i` ha una firma statica `s_i`, diversa per
ogni blocco. Per ogni blocco con un solo predecessore `p` il compilatore
calcola la differenza `d_i = s_p XOR s_i`. La firma di esecuzione `G` viene
aggiornata all'ingresso di ogni blocco e confrontata:

```c
G = G ^ d_i;                       // all'ingresso del blocco i
if (G != s_i) SigMismatch_Handler();
```

Esempio con firme di 4 bit: il blocco 1 ha due successori, 2 e 3.

```text
s1 = 0001     s2 = 0010     s3 = 0100
d2 = s1 XOR s2 = 0011
d3 = s1 XOR s3 = 0101

esecuzione 1 -> 2:   G = 0001;  all'ingresso di 2: G = 0001 XOR 0011 = 0010 = s2   OK
```

Se un guasto fa saltare dal blocco 1 a un blocco 4 che non è suo successore
(per esempio un blocco il cui predecessore è 2, con `d4 = s2 XOR s4`),
all'ingresso di 4 si ottiene `G = s1 XOR s2 XOR s4`, diverso da `s4`:
**rilevato** (errore di tipo 1).

Ma se il salto condizionale del blocco 1 viene **invertito** e si va in 3
invece che in 2:

```text
esecuzione 1 -> 3 (sbagliata):  G = 0001 XOR 0101 = 0100 = s3   nessun errore!
```

L'arco 1 -> 3 esiste, quindi CFCSS lo considera lecito: **non rilevato**
(errore di tipo 3). CFCSS controlla che il programma segua *un* arco del
grafo, non che segua *quello giusto*.

Per i blocchi con più predecessori serve un accorgimento, la firma di
aggiustamento `D`: il blocco predecessore imposta `D` prima di saltare, e il
blocco di destinazione calcola `G = G XOR d_i XOR D`, in modo che il risultato
sia `s_i` da qualunque predecessore lecito si arrivi.

## 4.4 RASM

**RASM** (*Random Additive Signature Monitoring*, Vankeirsbilck e altri,
2017) usa firme casuali e operazioni di somma e sottrazione, e soprattutto
aggiorna la firma **prima di uscire** da un blocco in base al successore
scelto. Ogni blocco `B` ha due numeri casuali: la firma `sig(B)` e un
correttivo `sub(B)`. Nel codice di ASPIS (`passes/RASM.cpp`):

```c
// all'ingresso del blocco B
S = S - sub(B);
if (S != sig(B)) SigMismatch_Handler();
...  // corpo del blocco
// alla fine di B, prima del salto condizionale "if (c) goto T; else goto F;"
adj_T = sig(B) - (sig(T) + sub(T));      // costanti calcolate dal compilatore
adj_F = sig(B) - (sig(F) + sub(F));
S = S - (c ? adj_T : adj_F);              // una select, non un salto
if (c) goto T; else goto F;
```

Dopo l'aggiornamento `S` vale `sig(T) + sub(T)` se `c` è vero, `sig(F) +
sub(F)` se è falso: proprio il valore che il blocco di destinazione si
aspetta. Esempio numerico:

```text
sig(B) = 100;   sig(T) = 37, sub(T) = 5;   sig(F) = 58, sub(F) = 9
adj_T = 100 - 42 = 58          adj_F = 100 - 67 = 33

c vero, si va in T (corretto):   S = 100 - 58 = 42;  in T: 42 - 5 = 37 = sig(T)   OK
c vero, ma il salto va in F:     S = 42;              in F: 42 - 9 = 33 != 58     RILEVATO
```

Il punto chiave è che la firma viene aggiornata usando **la stessa condizione**
del salto, ma con un'istruzione diversa (una `select`) eseguita **prima** del
salto. Se un guasto fa andare il salto dalla parte opposta alla condizione,
la firma "racconta" un percorso diverso da quello effettivo e il controllo
all'ingresso se ne accorge. È per questo che RASM rileva i salti invertiti e
CFCSS no.

RASM non vede invece un guasto che altera la condizione `c` stessa prima che
venga usata: in quel caso select e salto sono d'accordo tra loro. Ma quello è
un guasto nei dati, ed è il lavoro di EDDI. Per questo le due famiglie si
combinano bene.

In ASPIS ci sono anche due varianti di RASM che non usiamo nella campagna:
**inter-RASM**, che estende il controllo attraverso chiamate e ritorni di
funzione, e **RACFED** (Vankeirsbilck e altri, 2018), che aggiorna la firma
anche dopo ogni istruzione del blocco, per rilevare i salti nel mezzo di un
blocco.

## 4.5 Combinare dati e flusso

ASPIS permette di applicare una tecnica di protezione dei dati e una di
controllo del flusso allo stesso programma (`--eddi --rasm`). La protezione
dei dati viene applicata per prima, quella del flusso dopo, sul codice già
duplicato: quindi anche i blocchi creati da EDDI per i suoi controlli
ricevono firme e controlli di RASM. Proprio in questa interazione si
nascondeva il terzo bug (capitolo 8).
