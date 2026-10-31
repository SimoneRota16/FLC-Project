# 17. Domande probabili all'orale

Le risposte sono brevi di proposito: sono il nucleo da cui partire, poi si
può approfondire con i capitoli indicati.

**1. Cos'è ASPIS e a cosa serve?**
Un insieme di pass di LLVM che trasforma un programma per renderlo capace di
rilevare i guasti transitori dell'hardware, duplicando i calcoli (EDDI e
varianti) e controllando il flusso di esecuzione con firme (CFCSS, RASM,
RACFED). Funziona sull'IR, quindi vale per qualunque linguaggio e
architettura supportati da LLVM. (Cap. 4-5)

**2. Perché lavorare sull'IR e non sul sorgente o sull'assembly?**
L'IR è indipendente dal linguaggio e dalla macchina, ed è facile da
trasformare con le API di LLVM. Il prezzo è che non si vede quello che fa il
back-end: per esempio i salti con cui traduce una `select` (la SDC residua di
RASM in `pid_control`). (Cap. 2, 11.3)

**3. Perché ASPIS compila a `-O0` e non ottimizza dopo?**
Perché un ottimizzatore riconoscerebbe che le due copie calcolano la stessa
cosa e le fonderebbe, togliendo la protezione. (Cap. 5.4)

**4. Cos'è una SDC e perché è l'esito peggiore?**
Un risultato sbagliato senza nessun segnale d'errore: chi usa il risultato non
sa di non potersi fidare. Crash, hang e rilevamenti sono almeno visibili.
(Cap. 3.3)

**5. Come funziona EDDI? Dove mette i controlli?**
Duplica ogni istruzione su copie separate dei dati e confronta le copie prima
di store, salti condizionali e chiamate, dove un valore sbagliato uscirebbe
dal calcolo. Se differiscono chiama `DataCorruption_Handler`. (Cap. 4.1, 5.6)

**6. Che differenza c'è tra EDDI, sEDDI, FDSC e REDDI?**
sEDDI non controlla prima delle store, FDSC controlla solo in alcuni punti,
REDDI protegge solo il codice annotato `to_harden`. Costano meno di EDDI ma
rilevano meno o più tardi. (Cap. 4.1)

**7. Perché EDDI confronta i valori puntati e non i puntatori?**
Perché le due copie di un puntatore puntano alle due copie del dato, quindi
hanno legittimamente indirizzi diversi. Per sapere che tipo leggere serve la
libreria TypeDeductionAnalysis, perché in LLVM i puntatori sono opachi.
(Cap. 2.6, 5.6)

**8. Come funziona CFCSS e perché non rileva i salti invertiti?**
Ogni blocco ha una firma; all'ingresso si aggiorna la firma di esecuzione con
uno XOR della differenza tra la firma del predecessore e quella del blocco, e
la si confronta. Un salto invertito porta in un successore lecito, e
l'aggiornamento torna giusto: CFCSS controlla che il percorso sia un arco del
grafo, non che sia quello scelto dalla condizione. (Cap. 4.3)

**9. E RASM perché li rileva?**
Prima di uscire da un blocco aggiorna la firma con un valore scelto, con una
`select`, dalla stessa condizione del salto. Se il salto va dalla parte
opposta, la firma corrisponde all'altro successore e il controllo
all'ingresso fallisce. (Cap. 4.4)

**10. Quali bug avete trovato?**
Due. (1) Dopo le chiamate di libreria EDDI copiava sempre 8 byte
dall'originale alla copia di ogni argomento puntatore, anche dentro le
stringhe letterali in memoria di sola lettura: faceva andare in crash la
prima versione di tutte e quattro le applicazioni. (2) RASM non controllava
la firma nei blocchi `VerificationBB` creati da EDDI, quindi EDDI+RASM
perdeva i salti invertiti. Il primo lo abbiamo isolato, segnalato e aggirato;
il secondo lo abbiamo corretto. (Cap. 8)

**11. Come avete trovato il bug di EDDI?**
Con i test di compatibilità, che fallivano in 120 combinazioni su 220. Con
`gdb`: il crash era sempre una scrittura di 8 byte subito dopo un `printf`,
in una stringa letterale (`"kat ct: "`, `"OK"`, `"SUCCESS"`). Poi un programma
di cinque righe che lo riproduce, e la lettura di
`fixFuncValsPassedByReference` in `EDDI.cpp`. (Cap. 8.2)

**12. Perché non avete corretto il bug di EDDI?**
Perché la correzione vera richiede di riscrivere quella funzione: copiare la
dimensione giusta dell'oggetto puntato, saltare la memoria di sola lettura e
gli argomenti che la funzione chiamata non può modificare. È un intervento
complesso nel codice C++ di EDDI, che chi mantiene ASPIS può fare meglio di
noi. Lo abbiamo descritto in `bug_report.md` con il riproduttore e una
proposta di correzione. (Cap. 8.2)

**13. Cambiare le applicazioni per far passare i test non è un trucco?**
No, se lo si dichiara: il bug resta documentato e riproducibile
(`bug_report.md`, `string_literal.c`), la prima versione delle applicazioni è
nella storia di git e il log `harness_master_first_version.log.gz` mostra le
120 combinazioni che fallivano. Le applicazioni modificate stampano lo stesso
identico output. Il report lo dice tra i limiti: quella parte di EDDI non è
provata dalle nostre applicazioni. (Cap. 7.3, 8.2)

**14. Come avete trovato il bug di RASM, visto che nessun test fallisce?**
Dai numeri: EDDI+RASM aveva più SDC di RASM da solo (10,2% contro 0,88%), il
che non ha senso. Con `sdc_sites.py` abbiamo visto che tutte le 407 SDC erano
su salti verso blocchi che cominciavano scrivendo una costante nella firma,
cioè blocchi in cui RASM reimpostava la firma senza controllarla. Erano i
`VerificationBB` di EDDI, esclusi per errore da un controllo sul nome del
blocco. (Cap. 8.3)

**15. Come avete verificato che la correzione non rompa nulla?**
Con il sistema di test ufficiale di ASPIS: sui 48 test esistenti i risultati
con e senza le patch sono identici (2453 superati, 33 falliti, 154
saltati); le nostre applicazioni passano in tutte le 220 combinazioni, sia
su `master` sia con le patch. (Cap. 7.3)

**16. Perché 33 test falliscono anche su `master`?**
Sono tutti di `cpp_complex`: il programma di riferimento non compila con la
libreria C++ della nostra macchina (usa `std::powf`, che libstdc++ 13 non
dichiara). Non dipende da ASPIS. (Cap. 7.3)

**17. Come funziona il vostro iniettore?**
Con `ptrace`: una prima esecuzione passo-passo conta quante volte viene
eseguita ogni istruzione; poi ogni esperimento sceglie a caso un'esecuzione di
un'istruzione (cioè un istante), ferma il programma lì con un breakpoint
`int3`, inverte un bit di un registro o la direzione di un salto, lo lascia
proseguire e classifica l'esito confrontando l'output con quello di
riferimento. (Cap. 9)

**18. Perché disattivate l'ASLR?**
Perché il profilo registra gli indirizzi delle istruzioni: devono essere gli
stessi in tutte le esecuzioni. (Cap. 9.1)

**19. Perché scegliere l'istante uniformemente tra le istruzioni eseguite?**
Perché un guasto transitorio può arrivare in qualunque momento: scegliere
un'esecuzione a caso di un'istruzione a caso (pesata con il numero di
esecuzioni) equivale a scegliere un istante a caso del tempo di esecuzione.
(Cap. 9.4)

**20. Quanti esperimenti e quanto sono affidabili i numeri?**
48.000 (4 applicazioni × 6 configurazioni × 2 modelli × 1000), più 8000 di
EDDI+RASM senza la correzione di RASM. Ogni percentuale ha un intervallo di
confidenza al 95% di Wilson: per esempio la SDC di EDDI con i bit-flip nei
registri è 0,20%, con intervallo 0,10-0,39%. (Cap. 10.3)

**21. Perché l'intervallo di Wilson e non quello classico?**
Perché quello classico funziona male con percentuali vicine a zero (con zero
casi dà un intervallo nullo); Wilson resta corretto. (Cap. 10.3)

**22. Quanto costano le protezioni?**
EDDI esegue 3,74 volte le istruzioni e ha il codice 9,27 volte più grande;
CFCSS 1,65x, RASM 2,33x; EDDI+RASM circa 6x (5,95x). (Cap. 11.1)

**23. Perché il codice cresce più dell'esecuzione?**
Perché ogni funzione esiste in più versioni (`f`, `f_ret`, `f_dup`,
`f_ret_dup`), anche quelle non più usate restano nell'eseguibile, ogni
controllo aggiunge blocchi, e a `-O0` tutto passa dallo stack. (Cap. 11.1)

**24. Perché EDDI "rileva" il 78% dei salti invertiti, se non vede i salti?**
Perché il 76% dei salti condizionali eseguiti da un programma con EDDI sono i
salti dei suoi controlli: invertirne uno manda il programma nel blocco
d'errore. Classificando i salti colpiti, 3066 dei 3126 rilevamenti erano
salti dei controlli; gli altri 60 sono salti del programma nelle funzioni
duplicate, come la `select` di `load_at`, che con EDDI diventa due salti, uno
per copia. Lo stesso per CFCSS (62%), dove tutti i rilevamenti sono salti dei
controlli. (Cap. 11.3)

**25. Qual è la configurazione migliore?**
Dipende da cosa si teme e da quanto si può pagare: contro i guasti nei dati
serve EDDI, contro i salti sbagliati serve RASM; insieme non lasciano quasi
nessuna SDC (2 su 4000 per i registri, 0 su 4000 per i salti), ma costano
circa 6 volte le istruzioni. (Cap. 11.6)

**26. Quali sono i limiti del vostro lavoro?**
Solo registri generali e salti (niente registri in virgola mobile, memoria,
guasti multipli); 1000 guasti per applicazione, quindi intervalli larghi sulla
singola applicazione; costo misurato in istruzioni e non in tempo; le
tecniche sull'IR non vedono i salti creati dal back-end; il bug di EDDI è
aggirato e non corretto. (Report, sezione 7)

**27. Come avete usato l'intelligenza artificiale?**
I supervisori l'hanno permesso a patto di dichiararlo. Abbiamo usato Claude
(Anthropic), tramite Claude Code, per scrivere il codice, eseguire gli
esperimenti, cercare e correggere i bug e scrivere il report; noi abbiamo
definito obiettivi e perimetro, seguito il lavoro e controllato i risultati.
È dichiarato nella sezione 8 del report. Conviene essere pronti a spiegare
ogni parte: è lo scopo di questa guida.

**28. La correzione e i test sono già in ASPIS?**
No: sono pronti come patch (`aspis-integration/patches/`), verificate sul
commit `b66a090`, e il bug di EDDI è descritto in `bug_report.md`, ma non è
stato inviato ancora nulla. Si possono proporre con una pull request e una
issue, dopo averne parlato con i supervisori nella chiamata. (Cap. 12, 16)

**29. Quattro applicazioni bastano?**
È una delle domande da fare ai supervisori (che avevano scritto "once you have
identified them, we can discuss whether they are sufficient"). Gli argomenti a
favore: coprono quattro settori diversi (crittografia, segnali, compressione,
controllo), usano interi, virgola mobile, puntatori, struct e la libreria C,
e ognuna viene provata con 55 combinazioni di tecniche. Se ne chiedono altre,
aggiungerle è facile (cap. 7.2).

# 18. Glossario

| Termine | Significato |
|---|---|
| **ASLR** | *Address Space Layout Randomization*: il sistema operativo carica il programma a indirizzi casuali; l'iniettore la disattiva |
| **basic block** | sequenza di istruzioni senza salti interne, con un solo ingresso e una sola uscita |
| **back-end** | la parte del compilatore che traduce l'IR in codice macchina |
| **CFC** | *control-flow checking*, controllo del flusso di esecuzione |
| **CFCSS** | tecnica CFC a firme con aggiornamento XOR (Oh et al., 2002) |
| **CFG** | *control-flow graph*, grafo dei blocchi e dei salti tra loro |
| **chunk** | blocco di 100 esperimenti eseguiti da un processo `fi` con un seme |
| **DUE** | *detected unrecoverable error*: errore rilevato (crash, hang, controllo) |
| **EDDI** | *Error Detection by Duplicated Instructions* (Oh et al., 2002) |
| **ErrBB** | blocco creato da EDDI (o dalle tecniche CFC) che chiama il gestore d'errore |
| **fault injection** | iniezione artificiale di guasti per misurare l'effetto delle protezioni |
| **FDSC** | *Full Duplication with Selective Checking*, variante di EDDI |
| **front-end** | la parte del compilatore che analizza il sorgente e produce l'IR (per il C: `clang`) |
| **golden run** | esecuzione senza guasti, il cui output fa da riferimento |
| **hang** | il programma non termina entro il tempo limite |
| **harness** | il sistema di test di ASPIS (`testing/test.py`) |
| **int3** | istruzione x86 di breakpoint (byte `0xcc`): genera un `SIGTRAP` |
| **IR** | *intermediate representation*, il linguaggio intermedio di LLVM |
| **jcc** | salto condizionale x86 (`je`, `jne`, `jl`, ...) |
| **masked** | il guasto non ha avuto effetti visibili |
| **opt** | il programma di LLVM che esegue i pass sull'IR |
| **pass** | trasformazione o analisi dell'IR |
| **patch** | file con un commit di git (diff + messaggio), applicabile con `git am` |
| **ptrace** | chiamata di sistema con cui un processo controlla un altro (debugger) |
| **RACFED** | variante di RASM che aggiorna la firma dopo ogni istruzione |
| **RASM** | *Random Additive Signature Monitoring* (Vankeirsbilck et al., 2017) |
| **REDDI** | variante di EDDI che protegge solo il codice annotato `to_harden` |
| **regressione** | una modifica che rompe qualcosa che prima funzionava |
| **riproduttore** | programma minimo che mostra un bug |
| **SDC** | *silent data corruption*: risultato sbagliato senza segnalazione |
| **sEDDI** | *selective EDDI*: non controlla prima delle store |
| **select** | istruzione IR `c ? x : y`, senza salti |
| **SEU** | *single event upset*: inversione di un bit causata da una particella |
| **SIHFT** | *Software-Implemented Hardware Fault Tolerance* |
| **SSA** | *static single assignment*: ogni valore dell'IR è assegnato una volta |
| **TDA** | TypeDeductionAnalysis, la libreria che deduce i tipi puntati |
| **VerificationBB** | blocco creato da EDDI che contiene i confronti tra le copie |
| **Wilson (intervallo di)** | intervallo di confidenza per una proporzione, affidabile anche vicino a 0 |
