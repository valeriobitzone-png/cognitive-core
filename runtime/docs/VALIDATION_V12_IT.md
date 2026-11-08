# WorldCore Cognitive Layer 1.2.0 — rapporto verificabile

Consegna: 31 ottobre 2026. Prove principali eseguite il 30 ottobre 2026, su macOS ARM64, Python 3.12. Il materiale è una Research Alpha; non è una certificazione generale di produzione.

## Provenienza

La versione è una continuazione dello ZIP originale `WorldCore_v1.1_INDEPENDENT_WHATIF_ALPHA.zip`, 188 elementi, SHA-256 `81d7ca1e5fd67bcf484d3e52b2b7330b905bcc76af94e16fdf96f1f84833c5b6`. L'originale è rimasto separato dalla copia modificata. Il rilascio comprende sorgenti, adattatori, dati/benchmark precedenti, nuove prove, wheel e archivio sorgenti Python. Il catalogo storico di repository rimane materiale non ricertificato da questa attività.

Non sono stati introdotti componenti MONO. Il checkout Hermes installato si trova sotto una directory chiamata `mono-1s`, ma è stato usato come host esterno: nessun suo sorgente è copiato nel motore WorldCore.

## Risultati di regressione e watchdog

| Verifica | Esito | Evidenza relativa nella consegna |
|---|---|---|
| Suite completa finale, prima ripetizione | 278 Python passati, 2 saltati; 11 Node passati | `evidence/repeated_final/suite_1.json` |
| Seconda ripetizione | stessi conteggi, 32/32 gruppi passati | `evidence/repeated_final/suite_2.json` |
| Terza ripetizione | stessi conteggi, 32/32 gruppi passati | `evidence/repeated_final/suite_3.json` |
| Durata con supervisore esterno | 22,782 / 22,140 / 22,487 secondi | `evidence/repeated_final/outer_report.json` |
| Stress concorrente | 140/140 casi verificati | `evidence/runner_stress/report.json` |
| Descrittori aperti del supervisore stress | 3 prima, 3 dopo; crescita 0 | stesso rapporto |
| SDK MCP e trasporto stdio reali | handshake, catalogo e invocazioni verificati | log `test_mcp_real_v12.py` nelle tre suite |

I due skip riguardano Chromium via Playwright non installato e il test desktop storico che richiede Xvfb. Un gruppo che contiene skip non equivale a copertura di quelle funzionalità. I test browser e desktop precedenti non sono ricertificati qui.

Ogni ripetizione ha un limite interno per modulo, un limite complessivo e un ulteriore supervisore di processo esterno. Le prove di guasto comprendono processo fermo, thread in attesa con dump stack, SIGTERM ignorato, processi nipoti, output massiccio, comando inesistente, deadline non finite, selezione di suite inesistenti e interruzione del supervisore. Sono presenti prove di concorrenza SQLite, immutabilità, isolamento owner/space, provenienza e proprietà degli intervalli.

## Difetti riprodotti e correzioni

**Runner originale.** Un processo separato eredita stdout e mantiene aperta la pipe dopo l'uscita del leader. `communicate` va in timeout; la pulizia del gruppo genera un'eccezione invece di produrre il rapporto. Il difetto è riprodotto sia nella prima prova sia nella ripetizione con accesso diagnostico ampliato: consultare `original_runner_pipe_reproduction.json` e `original_runner_elevated_reproduction.json`. Questo riproduce un difetto reale; non dimostra che tutte le interruzioni del vecchio ambiente avessero la stessa causa.

Il runner nuovo usa file per stdout/stderr, chiude stdin, legge nel rapporto solo una coda limitata e conserva l'output completo sul disco. Campiona i processi e registra PID, PPID, stato, numero di thread e descrittori. Termina gruppi POSIX e discendenti osservati; registra errori di pulizia; mantiene più processi attivi senza un singolo puntatore globale sovrascrivibile. Scrive il rapporto atomicamente dopo ciascun modulo e non considera riuscita una selezione inesistente o una suite incompleta. Python produce un dump dei thread prima della deadline del modulo.

**Race SQLite.** La regressione ha riprodotto `sqlite3.OperationalError: table intel_index already exists` durante avvii simultanei. Il controllo di esistenza, la creazione dell'indice e il suo backfill ora condividono una transazione. Cinque prove con 12 riaperture concorrenti verificano anche che il backfill non duplichi i record. Il precedente errore è conservato nel log `no_bytecode_full_logs/04_test_engine.py.log`.

**Interprete Node/Python.** Un test OpenClaw richiedeva `python` anche quando quel nome non esisteva. Ora usa l'interprete configurato, come il runner e gli altri adattatori.

**Blocchi di lettura dell'ambiente.** Sono stati osservati anche processi fermi durante letture di file, prima dell'avvio di pytest. Lo stack nativo e i file aperti indicano una lettura di bytecode delle dipendenze (`python_import_sample.txt`). Anche una copia di documentazione si è fermata in lettura. La causa del filesystem non è stata identificata con certezza. Ambiente temporaneo, eliminazione delle sole cache generate, bytecode disattivato e nuova estrazione dallo ZIP hanno consentito le tre esecuzioni complete. I tentativi in timeout rimangono nei log; non sono stati trasformati in successi.

La contenibilità verificata non è una garanzia contro guasti kernel/storage, SIGKILL al supervisore o codice ostile che sfugga prima del campionamento. Per tali scenari serve supervisione del sistema o di un container.

## Integrazioni: host autentici e simulati

| Host/livello | Che cosa è autentico | Limite effettivo |
|---|---|---|
| Hermes installato | `PluginManager._load_plugin`, hook e `tools.registry.dispatch`; invocazione WHAT IF e controllo privacy su database reale | harness diretto sulle API dell'host; non un'intera sessione conversazionale autonoma |
| Hermes LLM | chiamata `ctx.llm.complete` reale; risposta da `nvidia/nemotron-3-ultra-550b-a55b:free`, provider riportato `auto` | singolo prompt sintetico; non benchmark di utilità di lungo periodo |
| MCP Python | SDK 1.30.0, processo server e stdio reali; init/list/call | client SDK, non un LLM |
| OpenCode 2.0.30 | caricamento del default export V2 e connessione del server MCP, con 49 strumenti nel catalogo | ciclo modello→strumento→esito non verificato |
| OpenCode LLM | risposte reali da Groq `openai/gpt-oss-20b`; ulteriore tentativo con `openai/gpt-oss-120b` | testo o proposta JSON senza invocazione non accettati come prova; errori `tool choice is none` nei tentativi successivi |
| Claude Code 2.1.310 | avvio CLI autentico e richiesta reale | `429 usage_limit_reached`, limite settimanale; nessun ciclo LLM completato |
| OpenClaw | bridge Python e database reali nei test Node | host OpenClaw simulato; nessun eseguibile operativo identificato nella ricerca locale limitata |
| OpenCode V1/V2, test Node | contratti hook e bridge reali | contesti host simulati nei test; separati dalla connessione OpenCode autentica sopra |
| Hermes, test Python storici | adapter e SQLite reali | host/LLM simulati nei test che lo dichiarano; separati dalle due prove autentiche Hermes sopra |

Hermes è installato in `<checkout-hermes>`, interprete `<python-hermes>`, checkout HEAD `d923a5eb487a17c0a68801bba9ef0f56c81040a8`. L'assenza iniziale dal PATH non era prova di assenza dell'installazione. Le API del checkout sono state lette e chiamate direttamente, senza simulare il gestore o il registro.

Evidenze: `evidence/hosts/hermes/real_plugin_result.json`, `llm_probe_result.json`; per OpenCode `opencode_isolated/explicit_config.log`, `verified_call.log`, `verified_120b_call.log`; per Claude `roundtrip/claude_mcp_attempt.log`. Il primo tentativo xAI ha restituito `invalid_grant` sul refresh token. La riuscita di Groq non elimina quel problema.

Il testo di un modello ha dichiarato una chiamata con `action_executed=true` senza produrre un evento di tool call. È stato scartato come prova. Il server WHAT IF reale restituisce `action_executed=false`; l'invocazione di uno strumento non equivale all'esecuzione delle azioni simulate.

Una prova successiva che avrebbe abilitato il permesso OpenCode `execute` è stata **rifiutata dalla revisione automatica**: l'estensione del confine dei permessi per un modello esterno è stata giudicata oltre lo scopo della simulazione WorldCore. Il comando non è stato eseguito né aggirato. Questa parte resta soggetta ad approvazione esplicita e non è certificata.

L'adattatore V2 ora ha un default export con `id` e `setup`, più pulizia nel lifecycle; i vecchi soli export nominati non erano sufficienti per il loader autentico. La configurazione e il contratto sono stati confrontati con [migrazione plugin V2](https://dev.opencode.ai/v2/docs/build/plugins/migrate-v1) e [MCP V2](https://dev.opencode.ai/v2/docs/mcp-servers/). La distinzione dei permessi è documentata nella [guida V2](https://dev.opencode.ai/v2/docs/permissions/). I flag e l'esito auth Claude sono stati confrontati con la [documentazione ufficiale CLI](https://code.claude.com/docs/en/cli-reference).

## World model e WHAT IF: valutazione su osservazioni reali

Nuovo percorso `calibrated_world`, indipendente dai modelli storici esplorativi. Ogni osservazione conserva tempi prima/dopo, tempo di disponibilità e provenienza. Il learner esclude dati futuri, rifiuta etichette disponibili troppo tardi per la partizione successiva, separa fit/calibrazione/validazione e non riaddestra sulla validazione. Usa intervalli congiunti split-conformal; il rilascio documenta esplicitamente l'ipotesi di scambiabilità e i suoi limiti in serie temporali.

L'accettazione considera guadagno rispetto alla persistenza, copertura misurata e un intervallo Wilson. La previsione può astenersi per schema sconosciuto, valori fuori distribuzione, confidenza storica insufficiente, ampiezza eccessiva o deriva osservata. Il registro conserva previsione e versione prima dell'esito; la prima risoluzione è immutabile, con controlli di tenant e tempi. Il degrado è valutato per azione sugli ultimi 20 esiti, dopo almeno 10 risoluzioni: astensione se il limite superiore Wilson della copertura è inferiore al target. Questo controllo può produrre falsi allarmi e selezione delle previsioni accettate.

WHAT IF propaga gli intervalli di una singola azione calibrata. Non dichiara calibrati rollout multi-step e non propone automaticamente un candidato sulla sola media. Le risoluzioni che entrano da MCP o dal bridge rimangono `user_reported`; il payload del modello non può promuoverle a `host_verified`.

### Benchmark controllato di filesystem

Sono state effettuate scritture e misurazioni OS reali in directory temporanee. Il carico di lavoro è sintetico e limitato: append di un numero di byte nell'intervallo 56–72, non mostrato al predittore, su file di dimensioni note. Non sono dati di utilizzo di utenti o un modello generale del mondo.

300 osservazioni storiche: 180 fit, 60 calibrazione, 60 validazione; poi 80 episodi con previsione registrata prima della scrittura. Due query esterne al dominio sono valutate prima degli allarmi. Il cambio di regime è valutato su una famiglia/ledger separata inizializzata dagli stessi dati storici, con append di 200 byte.

| Misura finale | Risultato |
|---|---|
| Previsioni accettate sui successivi 80 episodi | 52/80, 65% |
| Esiti inclusi negli intervalli accettati | 40/52, 76,92% |
| Target nominale degli intervalli | 80% |
| Intervallo Wilson 95% della copertura misurata | 63,87%–86,28% |
| Errore assoluto medio accettato | 4,629 byte |
| Baseline persistenza, sugli stessi casi accettati | 63,904 byte |
| Query fuori dominio | 2/2 astensioni |
| Cambio di regime, famiglia separata | primi 10 esiti fuori intervallo, poi 20/20 astensioni |
| Integrità del ledger finale | SQLite `ok` |

La copertura nominale dell'80% non è dimostrata: la misura è 76,92%, il campione è piccolo e condizionato alle accettazioni. Le 28 astensioni sul carico ordinario sono un costo e indicano falsi allarmi/conservatività del controllo sequenziale. Il cambio di regime non è riconosciuto prima dei primi 10 errori. Non c'è autorizzazione ad agire sul mondo reale.

Evidenze: `evidence/temporal/summary.json`, `observations.json`, `forward_outcomes.json`, `forecast_ledger.db`; protocollo finale `benchmarks/v12_protocol.json`, SHA-256 `be246f61307ce721332b1d4ff861793e950625a22172dd5c9186c6204db19a62`.

Sono conservati anche `temporal_development` e `temporal_final_attempt1`. Il primo esperimento ha indotto una revisione del controllo di drift; per la valutazione successiva è stato scelto un nuovo seed prima di generare gli esiti. Una successiva correzione dell'harness ha separato lo shift e anticipato le query OOD, senza cambiare il predittore o i suoi esiti forward. Le ripetizioni non costituiscono nuovi campioni indipendenti. È un benchmark di sviluppo trasparente, non una preregistrazione esterna o una validazione indipendente longitudinale.

## Installabilità, sorgenti e verificabilità

La wheel e il sorgente Python sono prodotti da setuptools. La verifica finale d'installazione usa un ambiente pulito senza dipendenze del motore e senza PYTHONPATH ai sorgenti. I risultati sono in `evidence/install_result.json` e `install.log`. Il pacchetto completo include un manifest di hash per controllare file e prove e lo script `scripts/verify_release.py`; il controllo è di integrità, non una firma d'autore o prova di correttezza.

Il verificatore è stato inoltre provato su log vuoti e file oltre 1 MB: manifest corretto accettato, contenuto alterato e file mancante respinti (3/3 controlli). Legge la dimensione dichiarata e rifiuta variazioni di dimensione durante il controllo. I sette database storici consegnati sono backup SQLite autonomi con integrità verificata, senza dipendere dai sidecar WAL/SHM; lo ZIP originale rimane la fonte immutata.

I log completi delle prove sono inclusi. Le directory runtime degli host, cache di modelli, archivi di sessioni e configurazioni personali non sono incluse. Le configurazioni di test consegnate contengono solo identificativi sintetici e percorsi locali, non credenziali. I vecchi dati macroeconomici e cataloghi rimangono fixture ereditate, non dati correnti ricertificati.

Rimangono aperti il ciclo LLM→strumento di OpenCode, una sessione Claude oltre il limite del provider, OpenClaw autentico, browser/desktop opzionali e benchmark longitudinali su dati personali autorizzati. Nessuno di questi limiti è nascosto dal numero dei test passati.

## Ambito epistemico

Le conseguenze deterministiche valgono solo sotto le regole dichiarate e le relative assunzioni. Il rilascio non contiene una prova formale generale: i controlli di coerenza e le ricerche finite non vanno presentati come tale. Le previsioni nei sistemi aperti restano probabilistiche e fallibili. Le alternative mai realizzate non acquistano esiti osservati; associazioni condizionali e controfattuali non identificano automaticamente causalità.
