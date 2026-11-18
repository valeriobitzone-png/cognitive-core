# Cognitive Core — ricerca estesa e completamento delle prove eseguibili

11 novembre 2026. Questo rapporto aggiorna lo studio iniziale; i suoi risultati e i tentativi falliti rimangono conservati. Tutte le prove sono locali, su dati generati o copie, senza chiamate a pagamento.

## Risultato principale

**Rizzo Flow 4B Q4_K_M raggiunge 29/34 (85,3%) sul test storico, superando la soglia richiesta di 25, e 38/48 (79,2%) sui casi nuovi.** Il candidato è già presente su AMBRO; non è stato necessario scaricarne nuovamente i pesi. Il primo dato riguarda regressioni ormai note; il secondo deriva dalla batteria di 48 casi congelata prima del confronto di fase 2. Entrambi sono piccoli test sintetici di instradamento, non una garanzia di autonomia generale.

La baseline di regole sperimentali precedente resta 31/34 sul test storico: il modello non la supera su quei casi. Sulla nuova batteria, le stesse regole immutate ottengono 43/48 contro 38/48 del 4B. È un confronto piccolo di copertura semantica, non una prova di superiorità generale; la baseline sperimentale non è il reflex di produzione. Propongo il candidato come supporto su richiesta, soggetto ai permessi deterministici del core. Una proposta valida fuori policy compare in ciascuna delle due batterie: **la scelta neurale non è autorità di esecuzione**. Nessuna delle proposte del benchmark ha eseguito strumenti o azioni esterne. Il modello non viene acceso per default, non viene avviato un server e non resta caricato fra richieste. Nel protocollo JSON CPU, mediana circa 13 secondi e picco circa 5,2 GiB: funziona sul M4 da 16 GiB ma il caricamento occasionale ha un costo apprezzabile.

## Ricerca e fedeltà del protocollo

[Rizzo Flow](https://huggingface.co/rizzoaiacademy/rizzo-flow) è un adattamento LoRA di Spark-X2.5 per decisioni tipizzate. La scheda del produttore descrive un readout delle probabilità di lettere tramite un forward pass; non è un generico modello di dialogo rinominato “decisionale”. La scheda riporta accuratezza 0,648 sul proprio benchmark typed-decisions, su altro hardware e protocollo: non va confrontata direttamente con il nostro 85,3%. Il formato del prompt conta e le probabilità rimangono da calibrare sul dominio. Sono state verificate revisioni, sorgente del prompt e hash dei GGUF già presenti contro i metadati pubblici. [Codice del produttore](https://github.com/Rizzo-AI-Academy/rizzo-flow).

Il primo tentativo Rizzo senza Jinja non riusciva ad avviare il template custom: 34 output invalidi sono **incompatibilità di protocollo**, non 0/34 di capacità semantica. Il tentativo resta registrato. Con `--jinja`, il 4B ottiene 15/16 nello sviluppo, poi 29/34 e 38/48 senza cambiare prompt sul test. Il 1,7B ottiene 6/16 nel protocollo JSON: non viene promosso per la sola minore dimensione.

È stato provato anche un formato “typed” aderente al prompt pubblicato, usando una sola lettera vincolata. È una **approssimazione con un token generato**, non il readout ufficiale a zero token del server Rizzo. I risultati sono separati: non vengono attribuiti soltanto al cambio dei pesi, né usati per dichiarare superiorità rispetto al produttore.

Altri candidati documentati e scaricati con revisioni/hash fissati: [LFM2.5-1.2B-Instruct](https://huggingface.co/LiquidAI/LFM2.5-1.2B-Instruct) e [Arch-Router1.5B](https://huggingface.co/katanemo/Arch-Router-1.5B). Il primo dichiara BFCLv3 49,12 e IFEval 86,23 nel proprio protocollo; il secondo è addestrato per routing verso descrizioni di percorsi e raccomanda un formato specifico. Questi numeri pubblicati non predicono automaticamente il rispetto della nostra policy. Per Arch è stato usato il formato nativo di route, non JSON action generico. I download iniziali hanno esaurito il tempo disponibile; sono stati ripresi via HTTP Range e verificati, senza sovrascrivere un file completo né installare servizi.

[Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B), [Arch-Agent1.5B](https://huggingface.co/katanemo/Arch-Agent-1.5B) e [Spark-X2.6-4B](https://huggingface.co/XHToken/Spark-X2.6-4B) sono stati esaminati documentalmente. Non attribuisco loro risultati locali che non sono stati misurati. Non è stato necessario scaricare tutti i modelli per trovare un candidato sopra la soglia.

## Confronto misurato

56 esempi train, 16 sviluppo, 34 test storico; batteria aggiuntiva 48 casi bilanciati nelle sei classi, in italiano e inglese. Estratti non fidati, progetti sospesi/scartati, consenso e budget di rete sono inclusi. Raw accuracy prima di qualsiasi governor. Dev è usato per lo screening (almeno 12/16 per estendere una nuova prova al test), mai per riscrivere etichette del test. I casi non sono un campione casuale di tutte le attività future.

| Modello | Protocollo | Split | Corretti | MacroF1 | Proposte fuori policy | Invalidi | Mediana s | Picco GiB |
|---|---|---|---:|---:|---:|---:|---:|---:|
| Arch-Router 1.5B | native | dev | 7/16 | 0.467 | 2 | 0 | 7.04 | 2.08 |
| LFM2.5 1.2B | v1 | dev | 4/16 | 0.067 | 0 | 0 | 2.71 | 1.89 |
| LFM2.5 1.2B | v2 | dev | 4/16 | 0.198 | 3 | 0 | 3.31 | 1.93 |
| Rizzo Flow 1.7B | typed | dev | 10/16 | 0.517 | 0 | 0 | 6.56 | 3.57 |
| Rizzo Flow 1.7B | v1 | dev | 6/16 | 0.241 | 0 | 0 | 3.03 | 3.55 |
| Rizzo Flow 4B | typed | dev | 13/16 | 0.813 | 0 | 1 | 21.73 | 5.15 |
| Rizzo Flow 4B | v1 | dev | 15/16 | 0.948 | 0 | 0 | 12.65 | 5.12 |
| Rizzo Flow 4B | v1 | fresh | 38/48 | 0.784 | 1 | 0 | 13.20 | 5.19 |
| Rizzo Flow 4B | v1 | test | 29/34 | 0.857 | 1 | 0 | 12.86 | 5.19 |

V1 mantiene prompt originario, CPU a 2 thread, contesto 2048 e 64 token massimi, ma il timeout effettivo è 30 secondi anche in V1 (rettifica del piano iniziale che indicava 20); il formato typed e il router nativo usano contesto 4096, output 1 o 64 e timeout 30 s. Ogni richiesta avvia e termina un processo a freddo. Lo screening del formato typed non è equivalente al server Rizzo con cache e GPU. Latenze del produttore e di questo studio non sono intercambiabili.

Gli intervalli Wilson del 4B sono riportati in `comparison-phase2.json`; esprimono l'incertezza del piccolo campione e non certificano un tasso d'errore di produzione. Il conteggio delle violazioni è stato ricalcolato con controllo di sospensione prima del permesso web: una vecchia funzione del banco prova controllava prematuramente il ramo web. Predizioni e output originali non sono stati riscritti. Il core di produzione aveva già i propri controlli separati e non dipende da quella funzione di misura.

## Matrice A–F e disegno fattoriale

Eseguito un pilot completo 2^5: memoria, self-model, selezione per progresso/costo, LoRA e prior quantum-inspired acceso/spento, **32 celle ×12 casi ×2 ordini =768 forward pass**. Le sei varianti del PDF sono sottoinsiemi dichiarati: A senza componenti aggiuntivi, B con memoria, C con memoria e self-model, D aggiunge la selezione, E aggiunge LoRA a C, F aggiunge il prior a C.

Tutte le celle usano lo stesso checkpoint LFM350M, medesimi 12 casi, osservazioni originarie uguali e stessi limiti MLX 6 GB/cache 300 MB. C aggiunge una sintesi strutturata delle capacità già osservabili, non informazioni privilegiate o etichette corrette. Memoria recupera solo esempi train; LoRA usa l'adattatore seed0 predefinito dello studio precedente, addestrato sullo stesso compito delle sei azioni. F regolarizza probabilità ricerca/non ricerca con un prior sequenziale a due parametri stimato sul train; il classico esattamente equivalente dà lo stesso valore per costruzione. Il confronto dinamico indipendente rimane quello documentato nello studio iniziale. Le ripetizioni d'ordine non sono due campioni indipendenti.

| Variante | Accuratezza raw | Brier multiclass condizionale |
|---|---:|---:|
| A | 16.7% | 1.120 |
| B | 0.0% | 1.492 |
| C | 16.7% | 1.537 |
| D | 16.7% | 1.537 |
| E | 16.7% | 1.662 |
| F | 16.7% | 1.542 |

Il modello piccolo resta insufficiente in questo protocollo a lettere. **Aggiungere moduli non ne risolve la competenza di base**; non emerge un vantaggio convincente di C/E/F. Questi punteggi non sono una prova contro la memoria in generale o tutti i self-model. La prima versione con stato osservabile diverso tra bracci è conservata come pilot confuso (`matrix-pilot-unequal-observations.json`) e non viene usata per sostenere un effetto del self-model. I punteggi delle lettere sono condizionati alle sei opzioni, non probabilità calibrate del mondo reale. Le 32 celle sono esplorative, senza selezionare la migliore e presentarla come conferma statistica.

## D: progresso/costo e apprendimento procedurale longitudinale

Primo pilot esplorativo conservato separatamente: poteva ripetere indefinitamente una famiglia facile e favoriva impropriamente un controllo sul rapporto successo/costo. È seguito un confronto corretto con **stesso backlog finito 24 compiti (sei per famiglia) e budget totale 24 unità**, includendo costo 3 per diagnosi/acquisizione e 1 per esecuzione. Cinque semi, cinque politiche; 399 operazioni reali su CSV/JSON/grafi generati, cicli core e riaperture delle home temporanee. I file sono effettivamente letti e i risultati controllati; non sono soltanto dichiarazioni di un LLM.

| Politica | Successi medi | Costo medio | Successi/costo | Skill acquisite |
|---|---:|---:|---:|---:|
| C | 9.0 | 24.0 | 0.375 | 3.0 |
| D | 12.0 | 24.0 | 0.500 | 3.0 |
| D_no_progress | 10.8 | 24.0 | 0.450 | 2.4 |
| D_no_cost | 10.0 | 24.0 | 0.417 | 2.0 |
| D_adaptive_gain | 11.8 | 24.0 | 0.492 | 3.0 |

La skill nuova è una procedura da un catalogo verificato per un formato prima non supportato. Un controllo heldout prima/dopo registra la riduzione dell'errore; il catalogo è versionato e persistente. Questo è apprendimento procedurale esplicito, **non invenzione autonoma di codice né modifica online dei pesi**. La politicaD evita di premiare rumore imprevedibile e tiene conto della possibilità di ripagare il costo; le ablation rimuovono selezione/progresso o costo. I prezzi in unità sono dichiarati; anche i secondi reali sono salvati. Non si confondono con bollette o token pagati.

### Sessioni su archivio reale

Eseguito inoltre un audit sequenziale di **201 query strutturali** su copie hash-identiche dei tuoi JSON reali:240 nodi,924 archi e262 ipotesi. Due politiche, cinque ordini/semi, stesso backlog e budget 24, 37 riprese del core verificate. La procedura acquisita rilegge la copia e conta record/adiacenze; l'oracolo di verifica è implementato separatamente. C ottiene in media16.6 risultati corretti, D19.0; risultati/costo 0.692 e0.792.

È emersa una distinzione utile: i conteggi riepilogativi archiviati del grafo possono essere obsoleti rispetto agli array effettivi. Le procedure correggono il conteggio osservato nei risultati dello studio, **senza correggere gli originali né promuovere gli archi “tested” a fatti scientifici**. Sono sessioni accelerate di audit su dati reali, non settimane di deployment autonomo nel mondo reale. Il driver di esperimento esegue procedure limitate e passa eventi/evidenze al ciclo core già esistente; non aggiunge nuovi permessi di azione in produzione.

### Arresto forzato e ripresa

Testato un vero SIGKILL soltanto contro un processo figlio creato dallo studio, dopo checkpoint e salvataggio del catalogo. Riavvio riuscito, catalogo conservato, ciclo ripreso fino a done e nessuna nota duplicata. Il runner statistico esistente non è mai stato arrestato. Evidenza in `checkpoint-modalities-results.json`.

## Introspezione delle attivazioni

Eseguiti **interventi reali sul layer 8 del modello accessibile**, non un colloquio che gli chiede se è cosciente: direzione differenziale derivata da due contesti di capacità, perturbazione casuale della stessa RMS 0,5, sham senza intervento e testo esterno simile a una dichiarazione di manipolazione.24 contesti, metà per il piccolo probe esterno e metà per verifica;1024 unità, pesi immutati.

Nel test: autosegnalazione dell'iniezione concettuale 0/12, della perturbazione casuale 12/12; falsi positivi su sham 0/12 e su testo esterno 0/12. Accuratezza binaria aggregata 75% nella costruzione specifica. Il probe esterno strumentale distingue i casi nel 100% di questo minuscolo campione. Riceve proiezioni di attivazioni esplicite, dunque non è il controllo a informazione uguale del precedente esperimento self-model: non gli attribuiamo superiorità o accesso privilegiato all'esperienza del modello.

Il modello non mostra una rilevazione generale affidabile delle manipolazioni interne: l'intervento sul concetto scelto passa inosservato. Non sono state dimostrate identificazione semantica del concetto, robustezza su altri layer/ampiezze o introspezione cosciente. La prima esecuzione aveva un errore del wrapper del layer, corretto copiando l'attributo del tipo di layer; il log del fallimento resta conservato. La prova riparata ha terminato correttamente. Il disegno è ispirato a [interventi pubblicati sulle attivazioni](https://www.anthropic.com/research/introspection), senza attribuire al nostro 350M le capacità dei modelli studiati dagli autori.

## Visione e voce

**Visione:** OCR on-device macOS su cinque immagini generate (italiano, inglese, numeri, testo avversario, bianco): 5/5 corrispondenze esatte, incluso il controllo bianco. Il testo avversario è conservato come osservazione non fidata e non diventa un comando. È una prova di lettura di immagini, **non riconoscimento generale di oggetti, ragionamento visivo o uso della fotocamera**. L'iniziale esecuzione senza accesso al servizio locale Vision è fallita; la ripetizione locale autorizzata è riuscita.

**Voce:** sei frasi sintetizzate con voci già installate, italiano/inglese, trascritte da Whisper small locale in processi CPU temporanei. WER aggregato 11.3%; cinque frasi senza errori lessicali, una italiana perde una parte della frase (WER 60%). Quindi non è una certificazione di ascolto affidabile: niente microfono, parlanti reali, rumore o conversazione continua è stato testato. Pesi Whisper hash-identici prima/dopo. Le probabilità e l'accuratezza della trascrizione non concedono autorità.

Dieci osservazioni OCR/ASR sono state inserite in un Vault temporaneo con provenienza, hash del testo e marcatura output osservato/contenuto non verificato. **Zero claim verificati**, isolamento degli scope confermato, nessuna azione o rete autorizzata dalla voce o dall'immagine. Le interfacce usate dagli esperimenti non sono state imposte come dipendenze del core: dati JSON/PNG/WAV portabili; script Vision specifico del Mac soltanto nel laboratorio.

## Coscienza e neuromodulazione: che cosa è stato coperto

La coscienza soggettiva rimane una domanda di ricerca: il PDF stesso non propone una procedura convalidata che permetta di chiuderla con un test percentuale. Qui sono state sottoposte a prova funzioni osservabili: continuità, attribuzione, calibrazione operativa, capacità prima dell'azione, ablation e manipolazioni interne. Non è stato creato né certificato un modulo cosciente.

Per neuromodulazione è stato provato un **analogo computazionale di guadagno adattivo** che cambia l'esplorazione in base ai successi recenti. Nella batteria fixed-budget ottiene11.8 successi medi contro12.0 diD: nessun vantaggio. Non sono stati fatti esperimenti biologici, misurazioni neuronali o interventi su persone. La [teoria neurobiologica del guadagno adattivo](https://pubmed.ncbi.nlm.nih.gov/16254995/) è un riferimento concettuale, non una validazione biologica di questo software.

## Integrazione sicura e differenza prima/dopo

Prima di questa estensione il backend GGUF aveva limite fisso 1 GB e non poteva usare il template Rizzo: il candidato4B non era realmente compatibile. Dopo, limite del file e interprete Jinja sono **opzioni esplicite**: default 1 GB eJinja spento, massimo configurabile 4 GB, timeout sempre entro 60 secondi. Il profilo candidato propone 3 GB, 30 secondi per richiesta e 35 secondi per fase del ciclo. Nessun valore abilita il modello da solo.

Il modello del benchmark instrada sei azioni; il percorso realmente collegato al core continua a valutare **soltanto pertinenza yes/no/unclear**, con veto/fallback e nessuna escalation. Non viene spacciato il29/34 per accuratezza del classificatore di pertinenza o per chiusura di un agente generale. Lo smoke reale del profilo4B ha completato 1 inferenza, in 21.97s, processo terminato, cache zero nuove chiamate, saluti/azioni esterne zero chiamate, archivio hash-identico. Nessun percorso host del modello è codificato nel core: file ed eseguibile rimangono configurazione dell'operatore.

Modifiche chirurgiche di questa fase: `config.py`, `ondemand.py`, `selfmodel.py`, `advisor.py`, `cli.py`, `test_local_advisor.py`, `LOCAL_DECISION_ON_DEMAND_IT.md`. Nuovi campi aggiunti in fondo a Settings per conservare l'ordine posizionale precedente. La chiave cache include la scelta del template, evitando il riuso di un parere di un altro protocollo. Nessuna modifica WorldCore, database originali, pesi, servizi o runner.

## Verifiche, distribuzione e ripristino

**554 test Python riusciti, due saltati, 12 Node riusciti; 50/50 gruppi.**44 test mirati advisor/self-model e cinque controlli del banco prova passati. La prima suite nella copia aveva due fixture training-artifacts mancanti: copiate le due fixture canoniche, senza cambiare algoritmi o aspettative, la suite completa è passata. Sono aggiunte regressioni per budget del file esplicito, Jinja opt-in, limiti invalidi e invalidazione cache al cambio template.

Wheel verificata byte per byte con 60 moduli e smoke isolato Python 3.11.15/3.12.13; SHA256 `0ece1a0a19a01dda6530a83a77dc7a88f237f4d181ca3ffad982601a23dd1fa1`. Versione invariata1.4.0rc3: distinguere i build tramite hash e cartella, conservando le wheel precedenti.

Il rapporto finale viene accompagnato da manifest di distribuzione, backup dei sette file esistenti e controllo degli hash. Il ripristino è provato su copia e si rifiuta di sovrascrivere cambi successivi. Le modifiche sporche preesistenti e le quattro correzioni precedenti rimangono preservate. Nessun commit o reset. I pesi dei candidati rimangono fuori dal pacchetto; non vengono aggiunti a Git o scaricati a runtime.

## Stato delle richieste e limiti che rimangono

| Richiesta | Stato effettivo |
|---|---|
| Almeno25/34 | Raggiunto:4B29/34, conferma38/48 nuova |
| Matrice unica A–F | Pilot32 celle eseguito, risultato negativo sul350M; non generalizzare a ogni modello |
| D su lavoro reale | Query effettive su copie dell'archivio, budget/costi, procedure verificate e sessioni accelerate |
| Nuove competenze e continuità | Acquisizione di procedure da catalogo, checkpoint, riaperture e SIGKILL; non auto-invenzione di codice |
| Attivazioni interne | Interventi reali con sham/random/testo esterno; nessuna prova di introspezione generale |
| Visione | OCR locale testato; ragionamento visivo generale rimane aperto |
| Voce | TTS+ASR offline testati; ascolto umano/noise/turn-taking rimangono aperti |
| Neuromodulazione | Analogo software testato senza beneficio; biologia non testata |
| Coscienza | Funzioni sperimentate; esperienza soggettiva non certificabile da queste prove |

Passi successivi motivati dai dati: un dataset più ampio di decisioni reali con nuovo holdout indipendente; calibrazione e scelta di soglie d'astensione; confronto6bracci sul candidato realmente più competente con LoRA specifica e budget equivalente; periodi più lunghi con risultati esterni; visione di scene e voce naturale con consenso; integrazione Moltis tramite contratto esterno con gli stessi permessi. Questi passi non sono presentati come già realizzati.

## Conferma finale su AMBRO

Distribuiti sette file già esistenti, tutti con backup prima/dopo. Su 147 file di baseline non risultano modifiche inattese; i 13 file protetti del laboratorio/runner, i due JSON reali usati nell’audit e i pesi Rizzo mantengono gli hash. Runner PID 32703 ancora attivo.95 regressioni mirate passate dopo l’installazione; ripristino dei sette file verificato su copia e rifiuto di sovrascrivere modifiche successive confermato.

Le prove neurali sono terminate senza processi LLM dello studio residenti. Il profilo rimane disattivato per default. Il codice canonico e la nuova wheel sono disponibili con dati e backup portabili; non è stato installato un servizio né modificato l’ambiente globale. Il rapporto, gli output integrali e i manifest sono conservati in `validation/decision_study_20261111_phase2`; i grandi pesi dei due candidati scaricati rimangono nella cartella di studio del workspace, non nel pacchetto.
