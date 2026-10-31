# 16. La chiamata con i supervisori

I supervisori hanno scritto: *"Quando siete pronti facciamo una call dove ci
spiegate quel che avete fatto. In più, dovete redarre un report che ci serve
come reference per la valutazione"*. Per la chiamata c'è una presentazione di
17 slide, in inglese come il report:
<https://claude.ai/artifact/R4PFNt1VCATSuovbDMCFzV>. Si può proiettare dal
browser o scaricare in PDF o PowerPoint.

Ogni slide ha delle **note per chi parla**, in italiano, con quello che c'è da
dire: si vedono nella modalità presentatore. Attenzione: le note sono visibili
a chiunque apra la presentazione, quindi se la condividete con i supervisori
le leggeranno anche loro.

**Durata e divisione.** Circa 15 minuti, poi le domande. Una divisione
naturale: uno presenta la prima metà (slide 1-6: progetto, ASPIS,
applicazioni, test di compatibilità, bug di EDDI), l'altro la seconda (slide
7-13: iniettore, campagna, risultati, bug di RASM), e le ultime quattro
(integrazione, limiti, intelligenza artificiale, domande) le fate insieme.

**Il consiglio più importante.** I supervisori sono gli sviluppatori di ASPIS:
conoscono le tecniche molto meglio di noi. Non serve spiegare loro EDDI o
RASM; serve mostrare che sapete cosa avete fatto, perché, e cosa avete
trovato. Le parti su cui saranno più curiosi sono i due bug (slide 6, 12 e
13) e la domanda finale su come ricevere le patch.

Di seguito, slide per slide, il messaggio da far passare e i numeri da
ricordare. Tutti i numeri sono gli stessi del report e dei capitoli 7-11.

## 16.1 Parte 1: il progetto (slide 1-2)

**1. Copertina.** Presentarsi e dare la scaletta: le applicazioni, i due bug,
la fault injection, cosa portiamo in ASPIS, i limiti, l'uso dell'IA, tre
domande per loro.

**2. Tre obiettivi.** La proposta chiedeva di proteggere applicazioni C con
ASPIS, di verificare la protezione con la fault injection e di integrare le
applicazioni in ASPIS come test di regressione. Per ognuno, una riga di
risultato: 55 combinazioni su 55 per ogni applicazione; 24.000 esperimenti
più 4000, con i guasti iniettati da gdb; due patch e un bug report, non
ancora inviati.

## 16.2 Parte 2: le applicazioni e i test (slide 3-6)

**3. ASPIS.** Un richiamo veloce, solo per mostrare che sapete come funziona:
pass sull'IR, duplicazione dei dati (EDDI e varianti), firme sul flusso
(CFCSS, RASM, RACFED), compilazione a `-O0` senza ottimizzazioni dopo i pass
(capitoli 4-5).

**4. Le applicazioni.** Avevano lasciato a noi la scelta e chiesto di poterne
discutere: quattro applicazioni scritte da noi, che si controllano da sole
(stampano `SUCCESS` o `FAIL`), deterministiche, brevi (meno di un milione di
istruzioni), valide in C e in C++, con licenza MIT perché possano entrare nel
repository di ASPIS (capitolo 6). Sono anche la base della domanda finale "ne
bastano quattro?".

**5. Compatibilità.** Il sistema di test ufficiale, 55 combinazioni per
programma. Con la prima versione delle applicazioni passavano 100 combinazioni
su 220: EDDI, sEDDI e FDSC andavano in crash su tutte e quattro. Con la
versione finale passano tutte e 220, sia su `master` sia con le patch. I 48
test esistenti danno gli stessi risultati con e senza patch (2453 superati, 33
falliti, 154 saltati). Se chiedono dei 33 falliti: sono tutti di
`cpp_complex`, che non compila nemmeno con `clang++` sulla nostra macchina
(capitolo 7).

**6. Bug di EDDI.** Il riproduttore di cinque righe, la causa (dopo una
chiamata di libreria EDDI copia sempre 8 byte dall'originale alla copia di
ogni argomento puntatore, e con una stringa letterale scrive in memoria di
sola lettura), cosa abbiamo fatto (aggirato nelle applicazioni, documentato
nel bug report, non corretto dentro ASPIS). Se chiedono perché non l'abbiamo
corretto: la correzione vera richiede di riscrivere
`fixFuncValsPassedByReference`, e preferiamo proporla a loro con il bug report
piuttosto che toccare EDDI da soli (capitolo 8.2).

## 16.3 Parte 3: la fault injection (slide 7-13)

**7. L'iniezione con gdb.** Non abbiamo scritto un iniettore: valgrind
(`callgrind`) conta le esecuzioni di ogni istruzione nella golden run, poi in
ogni esperimento gdb ferma il programma in un istante a caso (un breakpoint
con *ignore count*), lo script inietta il guasto (un bit di un registro con
`set`, o il salto mandato dall'altra parte cambiando `$pc`) e la campagna
classifica l'esito confrontando l'output con quello di riferimento. Ricordare
la definizione di SDC: un risultato sbagliato senza nessun segnale d'errore
(capitolo 9). Se chiedono perché non un iniettore nostro: gdb fa già tutto,
ed è più facile da verificare; il prezzo è il tempo.

**8. La campagna.** 4 applicazioni × 6 configurazioni × 2 modelli × 500 =
24.000 esperimenti, più 4000 di EDDI+RASM senza la correzione. Semi fissi,
ASLR disattivato, intervalli di Wilson al 95%, ⟦campaign_time_short⟧ su 4 core
(capitolo 10).

**9. Il costo.** EDDI esegue 3,74 volte le istruzioni e ha il codice 9,27
volte più grande; CFCSS 1,65x e RASM 2,33x; EDDI+RASM 5,95x. Il costo è
misurato in istruzioni eseguite, non in tempo, perché i programmi durano
pochi millisecondi (capitolo 11.1).

**10. Bit-flip nei registri.** Senza protezione l'1,43% dei guasti produce una
SDC; EDDI la porta allo 0,20%, circa 7 volte meno; CFCSS e RASM da soli poco
(0,80% e 0,60%); EDDI con una tecnica del flusso 0,03-0,05%, cioè 1 o 2 casi
su 4000 (capitolo 11.2).

**11. Salti invertiti.** Senza protezione l'80,3% è una SDC. EDDI e CFCSS
rilevano quasi solo i salti dei loro controlli (76,3% e 62,4% dei salti
eseguiti) e lasciano il 17,8% e il 30,0%; RASM rileva il 99,1%, e le sue 35
SDC vengono tutte dal salto che il back-end crea per la `select` di
`load_at`; EDDI+RASM non ne lascia nessuna (capitolo 11.3). È la slide in cui
è più facile ricevere domande tecniche: rileggete bene il capitolo 11.3.

**12. Bug di RASM: il sintomo.** La slide più importante. EDDI+RASM lasciava il
10,2% di SDC, contro lo 0,88% di RASM da solo: un controsenso. Con
`sdc_sites.py` si vede che tutte le 407 SDC erano salti verso blocchi che
cominciano scrivendo una costante nella firma: i `VerificationBB` di EDDI,
dove RASM reimpostava la firma invece di controllarla (capitolo 8.3).

**13. Bug di RASM: la correzione.** Una riga: l'eccezione vale solo per i
blocchi il cui nome comincia con `RASM_`; lo stesso in RACFED. Dopo la
correzione: da 407 a 0 SDC, i controlli di RASM rilevano il 65,0% dei salti
invertiti invece del 35,1%, e i test di ASPIS danno gli stessi risultati.

## 16.4 Parte 4: integrazione, limiti, IA (slide 14-17)

**14. Integrazione.** Due patch (la correzione e i test) e un bug report,
pronti ma non inviati. Qui fate le **tre domande**:

1. preferite una sola pull request con le due patch, o la correzione di RASM
   da sola?
2. apriamo una issue per il bug di EDDI?
3. quattro applicazioni bastano come test di regressione?

Prendete nota delle risposte: decidono cosa fare dopo la chiamata (capitolo
12).

**15. Limiti.** Gli stessi della sezione 7 del report: solo registri generali e
salti, intervalli larghi per la singola applicazione, costo in istruzioni e
non in tempo, salti del back-end invisibili alle tecniche sull'IR, bug di EDDI
aggirato e non corretto. Dirli voi prima che ve li chiedano fa buona
impressione.

**16. Intelligenza artificiale.** Le regole le hanno date loro: si può usare
l'IA anche per tutto il progetto, purché lo si dichiari nel report. Ditelo in
modo diretto: abbiamo usato Claude tramite Claude Code per il codice, gli
esperimenti, il debugging e il report; noi abbiamo definito obiettivi e
perimetro, seguito il lavoro e controllato i risultati. Poi mostrate, nelle
risposte, di conoscere ogni parte: è lo scopo di questa guida.

**17. Domande.** Chiudere chiedendo se vogliono altro nel report prima della
consegna.

## 16.5 Dopo la chiamata

- Aggiornare il report con quello che chiedono (il sorgente è
  `ASPIS-Project/report/report.md`, poi `python3 report/build.py`, capitolo
  13).
- Se vogliono le patch: fork di `HEAPLab/ASPIS`, `git am` delle patch su un
  branch, pull request (capitolo 12). Se vogliono la issue: aprirla con il
  testo di `aspis-integration/bug_report.md`.
- Se chiedono altre applicazioni, la procedura è quella del capitolo 7.2:
  aggiungerle in `testing/tests/c/applications/` e in `tests.toml`, e
  rilanciare i test.
