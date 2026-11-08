# WorldCore worker 1.3.0rc1 — verifica tecnica locale

Data: 31 ottobre 2026. Stato: candidato tecnico installabile, non lancio commerciale e non certificazione esterna. La scelta della licenza è rinviata su richiesta dell'utente: rimane Apache-2.0. Nessuna pubblicazione GitHub eseguita.

## Prodotto e cambiamenti

WorldCore è un worker locale collegabile ad agenti e LLM tramite MCP stdio, JSONL o API Python. Il nuovo comando `worldcore-worker` vincola owner/space all'avvio: il modello non può cambiare identità nelle richieste. Questo ingresso rifiuta proposte ed esecuzioni di azioni reali anche con flag legacy abilitati. Il comando `worldcore-mcp` espone l'ingresso MCP opzionale.

Il protocollo JSONL limita ogni richiesta a 64.000 byte prima del parsing, rifiuta chiavi duplicate, numeri non finiti, Unicode invalido e identificatori di correlazione invalidi. Un messaggio troppo grande termina subito il worker, anche senza newline: non attende lo svuotamento del flusso. Le richieste malformate entro il limite permettono invece di leggere la successiva. Gli adapter misurano i limiti in byte UTF-8. Il client deve applicare deadline e gestire i riavvii senza ripetere ciecamente operazioni che modificano lo stato.

Corretta anche la modifica involontaria dei permessi di directory già esistenti: il worker mantiene i permessi del progetto, crea directory nuove private e limita il file SQLite al proprietario. Le prove prima/dopo e le regressioni sono incluse.

## Runner e robustezza

Il difetto originale e la correzione del runner restano documentati nel rapporto v1.2 incluso: un discendente manteneva aperta la pipe di output; il vecchio cleanup falliva e perdeva il rapporto. Il runner usa log su file, watchdog per processo/gruppo, deadline complessiva, campionamento dei discendenti e rapporti incrementali atomici. I timeout e gli errori di pulizia fanno fallire la prova.

Nuova verifica rc1:

| Prova | Risultato | Evidenza relativa al pacchetto |
|---|---|---|
| Tre regressioni complete | 35/35 gruppi ciascuna; 305 Python + 12 Node per ripetizione | `evidence/market/final_regression/` |
| Regressione con diagnostica estesa | 35/35; processi, thread e fd rilevati | `evidence/market/diagnostic_suite.json` |
| Regressione finale dopo controllo ordine catalogo | 35/35; 306 Python + 12 Node | `evidence/market/release_suite.json` |
| Stress del runner | 140/140; fd iniziali 3, finali 3 | `evidence/market/final_stress/` |
| Verificatore ricevute/certificato | 15 test, inclusi falsi claim, risultati discordanti e catalogo osservato troppo tardi | `tests/test_host_certificate.py` |
| Installazione wheel pulita | versione, health, isolamento, azioni negate, permessi e integrità SQLite passati | `evidence/market/install_verification.json` |
| Wheel rispetto ai sorgenti | 34 file identici byte per byte | `evidence/market/wheel_source_comparison.json` |

Restano due skip opzionali per dipendenze browser/desktop assenti. Le prime tre suite avevano accesso limitato alla diagnostica di sistema; le successive hanno raccolto i dati completi. Non si considera uno skip copertura certificata. Processi ostili, guasti del kernel o blocchi dello storage non sono una garanzia eliminabile con questo supervisore: le protezioni verificate riguardano i guasti riprodotti e i processi ordinari osservabili.

## Ciclo autentico modello–strumento

Il protocollo di prova OpenCode usa stati sintetici differenti e un nonce per ogni caso. Consente Code Mode `execute`, autorizzato esplicitamente dall'utente, e il solo tool applicativo `worldcore_whatif_compare`; shell, file e altri tool applicativi rimangono negati. `execute` ha anche le capacità intrinseche documentate dall'host, quindi questi permessi non costituiscono una separazione di sicurezza a livello di sistema operativo.

Prima della chiamata il modello deve effettuare la ricerca del catalogo con query e namespace fissati, al massimo tre volte in chiamate distinte. Il verificatore richiede un risultato che contenga esattamente `tools.worldcore.whatif_compare` **prima** della chiamata applicativa. Poi riconcilia evento strutturato, nonce, run_id, proiezioni attese, ricevuta SQLite indipendente, hook nativo, risposta finale e stato reale invariato. Un'affermazione del modello da sola non supera la prova.

Le prove iniziali sono conservate: chiamate identiche fallivano una volta con `Unknown tool` e poi riuscivano. L'ipotesi iniziale di una differenza tra notazione punto e parentesi è stata smentita. Si è osservato anche un catalogo inizialmente vuoto seguito da un catalogo disponibile: la procedura di disponibilità evita di chiamare il tool prima di vederlo. Questo è un rimedio verificato nel percorso di integrazione; non dimostra una correzione interna di OpenCode.

Una prova con limite di 55 secondi è stata terminata dal watchdog dopo il risultato del tool ma prima della risposta finale. Rimane fallita. La serie finale usa un limite di 120 secondi per caso e ha superato 3/3 cicli, in 56,331 / 68,870 / 52,455 secondi, senza errori dei tool. Il ricontrollo finale ha verificato anche digest dei log e corrispondenza dei tre database (`final_reconciliation.json`); i risultati e le durate sono nel certificato allegato e vengono ricontrollati con il verificatore finale. Non si nascondono tentativi precedenti e non si deduce un tasso di affidabilità di produzione da tre casi sintetici.

| Host | Natura dell'evidenza |
|---|---|
| OpenCode 2.0.30, Groq `openai/gpt-oss-120b` | Ciclo autentico modello → Code Mode → MCP WorldCore → modello; log e ricevute per caso in `evidence/market/opencode_certification_final/` |
| SDK MCP 1.30.0 | Trasporto stdio reale, inizializzazione, elenco e chiamata tool nei test |
| Hermes locale | Caricamento plugin e dispatch del registro autentici; chiamata LLM autentica separata. Non equivale a una certificazione del ciclo end-to-end Hermes |
| Claude Code 2.1.310 | Tentativo autentico fermato dalla quota del provider; ciclo non certificato |
| OpenClaw | Host simulato nei test degli adapter; nessun ciclo operativo dichiarato |

Hermes è stato trovato nell'installazione esterna già presente sul computer. Nessun componente MONO è stato copiato o incorporato: è mantenuta soltanto l'idea WHAT IF richiesta.

## World model e limiti epistemici

Resta il percorso calibrato introdotto in v1.2: osservazioni con tempi di evento/disponibilità e provenienza, partizione temporale fit/calibrazione/test, embargo sulla disponibilità, intervalli conformali congiunti, valutazione di copertura, confronti con baseline, astensione per dati fuori distribuzione, drift, intervalli larghi o evidenza insufficiente. Le previsioni sono immutabili, associate alla versione del modello e confrontabili con gli esiti successivi; le risoluzioni provenienti dal modello restano `user_reported`.

Il benchmark usa operazioni reali sul filesystem con carico sintetico controllato: 300 osservazioni iniziali e 80 successive; 52 previsioni accettate, 40 coperte (76,92%, contro un obiettivo nominale dell'80%), 28 astensioni. Una famiglia con cambiamento di distribuzione ha prodotto 10 errori prima di 20 astensioni; due query OOD sono state rifiutate. Dati, protocolli e tentativi di sviluppo sono nel pacchetto v1.2 ereditato. Non sono nuovi risultati indipendenti rc1 né una prova di generalizzazione al mercato.

Le trasformazioni deterministiche dichiarate, ad esempio sommare −10 a un budget sintetico, sono verificabili entro le regole implementate. I test non sono una dimostrazione formale universale. Le conseguenze in sistemi aperti restano previsioni probabilistiche; nessuna certezza assoluta, causalità generale o autorità d'esecuzione è dichiarata.

## Dipendenze e consegna

Il worker base non richiede dipendenze Python esterne; alcune funzionalità di ricerca e MCP usano extra opzionali. Gli adapter distribuiti non hanno dipendenze npm di runtime. L'audit PyPI delle 29 dipendenze risolte dell'extra MCP non ha rilevato vulnerabilità note al momento della verifica: non è un audit completo del codice né del runtime nativo. Lock delle versioni, inventario licenze e SBOM CycloneDX sono in `evidence/market/dependencies/`.

Sono forniti ZIP completo, wheel, sorgenti installabili, documentazione del protocollo, SECURITY, CONTRIBUTING, changelog, CI preparata, log integrali delle prove, ricevute sintetiche SQLite, benchmark precedenti e checksum. La CI GitHub Linux/macOS e Python 3.11–3.13 è preparata ma non eseguita remotamente. Il manifest SHA256 e la verifica CRC permettono di controllare l'integrità del pacchetto. I percorsi assoluti nei log indicano l'ambiente originale; la stessa coda di percorso da `evidence/` identifica il file distribuito.

Prima del lancio pubblico rimangono: scelta e verifica della licenza, identità del manutentore e canale privato per segnalazioni, esecuzione della CI sui sistemi supportati, pilot end-to-end negli host da dichiarare supportati e obiettivi di latenza/affidabilità misurati su carichi rappresentativi. Questi punti non sono attestati come completati da una verifica locale.

Documentazione primaria consultata: [OpenCode Tools](https://dev.opencode.ai/v2/docs/tools/), [MCP servers](https://dev.opencode.ai/v2/docs/mcp-servers/), [discovery Code Mode](https://github.com/anomalyco/opencode/issues/45349). Le evidenze locali, non le descrizioni di issue altrui, determinano l'esito delle prove riportate.
