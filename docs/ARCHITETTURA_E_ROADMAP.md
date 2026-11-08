# Architettura obiettivo e stato del prototipo

**Data di riferimento del materiale:** 7 novembre 2026  
**Nome del progetto:** Cognitive Core (precedentemente Cognitive Drive)  
**Stato:** architettura e roadmap del prototipo **v0.1**, documentate in forma descrittiva. Questo repository non pubblica codice sorgente.

## Missione

Un substrate indipendente da qualsiasi AI, in grado di conservare conoscenza ed esperienza, continuare ricerche sospese, individuare lacune, prevedere, simulare alternative, decidere quando agire o tacere, verificare gli esiti e migliorare le proprie capacità senza consumo automatico di API commerciali.

Principi assoluti:

1. Predizione ≠ osservazione; simulazione ≠ conseguenza reale.
2. Disponibilità di una capacità ≠ permesso di usarla.
3. Esecuzione ≠ successo.
4. Un documento web ≠ prova conclusiva; un'altra AI che lo ripete ≠ verifica.
5. Nessun provider AI è proprietario della memoria: interfacce e dati sono sostituibili.
6. Un «ciao» non deve avviare embeddings, modelli linguistici o ricerca.
7. Budget paid-API = 0 per iniziative autonome, per costruzione e non solo per prompt.

## Sistema S0 / S1 / S2 / S3

| Strato | Funzioni | Stato v0.1 (secondo il materiale) |
|---|---|---|
| S0 Reflex | Filtra rumore, permessi deterministici, trigger, economic governor | Implementato in versione iniziale |
| S1 Decision Plane | Classificazione, priorità, arresto, scelta strumenti | Implementato con fallback a regole; decision model locale opzionale; da valutare |
| S2 WorldCore | Memoria semantica / episodica / procedurale, temporal graph, world model, WHAT IF, previsioni | Vault e predizioni / WHAT IF basilari; world model appreso assente |
| S3 Worker & Learning | Tool harness, browser, verifiche, evidence, experience, raffinamento decisioni | Web reader opt-in, ledger e dataset supervisionato in forma iniziale |

### Ciclo di riferimento

Consapevolezza → Interpretazione → Curiosità → WHAT IF → Decisione → Policy → Esecuzione → Verifica → Apprendimento.

Stati d'azione di riferimento: attendere; solo memorizzare; prepararsi in silenzio; suggerire; chiedere contesto; richiedere approvazione; eseguire se autorizzati; interrompere o fare rollback.

L'ultima coppia di stati richiede un harness reale con approvazioni e rollback. Nel prototipo descritto non si eseguono azioni esterne diverse da fetch web esplicitamente autorizzati.

## Componenti concettuali previsti

Senza riferirsi a file sorgente, i blocchi funzionali previsti dalla v0.1 sono:

| Componente | Ruolo |
|---|---|
| Configurazione fail-closed | Preferisce il blocco quando mancano permessi o budget |
| Vault | Memoria, provenance, ledger episodico e delle predizioni, grafo, ricerca testuale |
| Decision Plane | Reflex, regole deterministiche, modello locale opzionale |
| World / WHAT IF | Simulazioni ipotetiche senza mutare lo stato del mondo |
| Motore e worker | Ciclo principale, job, ricerca web opt-in |
| Ricerca | Reader e metasearch locale opt-in (es. SearXNG avviato separatamente) |
| Visione | Interprete multimodale locale opzionale su file |
| Apprendimento | Dataset supervisionato con revisione umana |
| Note Markdown | Importazione note senza modificarle; esportazione Markdown / JSON |
| Interfaccia REST | JSON solo su loopback, senza autenticazione in v0.1 (non adatta a esposizione pubblica) |
| Benchmark decisionale | Casi sintetici dichiarati per regressioni, non misura su distribuzioni reali |
| Interfaccia a comandi | Osservazione eventi, stato, topic, tick, memoria, import / export |

## Vault e durabilità

- **Source layer:** documenti originali e provenance (hash, URL, data, metadata), note Markdown esportabili.
- **Semantic layer:** claim espliciti con stati come *unverified*, *source_backed*, *conflicted*. Non è prevista promozione automatica a *tested*.
- **Episodic layer:** eventi e storie azione-osservazione; rischio ed esiti non dedotti in modo autonomo.
- **Intentions:** topic *open*, *paused*, *discarded*, *done*; job con checkpoint e lease.
- **Prediction ledger:** probabilità ex ante, data di risoluzione, outcome osservato, punteggio Brier.
- **Temporal graph:** archi di relazione con timestamp; espansione pianificata con validità temporale dei claim.
- **Retrieval:** ricerca testuale oggi; embeddings e rerank locali opzionali in seguito. Il Vault conserva dati anche senza embedding.
- **Import / export:** Markdown e JSON; documenti ricostruibili; possibilità di migrare lo storage verso altre strutture.

La scelta di uno storage locale leggero come adapter v0.1 è descritta come deliberata e **non definitiva**: si valutano alternative per grafo, vettori e consolidamento episodico, mantenendo schemi e versioni indipendenti.

## Scelta modelli: esperimento previsto

| Candidato | Ruolo | Vincoli da verificare |
|---|---|---|
| Solo regole / piccolo classificatore | S0, gate veloci | Falsi negativi e iniziative perse |
| Hindsight `hs-decide-1-flash` (0.8B) | Novelty, relevance, evidenza sufficiente | Inferenza su Apple Silicon, italiano, formati, licenza Apache 2.0 |
| Hindsight `hs-rerank-1` (114M) | Reranking della memoria | Benchmark reale e compatibilità macOS |
| Hindsight `hs-embed-1` (112M) | Embedding per retrieval semantico | Consistenza multilingue e indicizzazione |
| `vllm-sr/d3-edge` (0.6B) | Decisioni e classificazioni, possibile visione | Runtime con codice custom; controllare supply chain |
| Piccolo Qwen compatibile con runtime locali (es. llama.cpp o MLX) | Generazione query, riassunti, reasoning difficili | RAM, throughput, qualità in italiano |

**Sequenza di valutazione prevista:** baseline a regole → modello locale non fine-tunato → dati etichettati da utenti ed esperti → LoRA se necessario → benchmark su casi non visti → test di regressione → rilascio.

### Dati di training

Nessun feedback da pagine web è automaticamente un'etichetta affidabile. Il motore di dataset richiede revisione esplicita; il training periodico è separato dal worker e avviene solo dopo verifica.

## Ricerca web: percorso a fasi

1. Generazione query controllata da obiettivo e budget.
2. Metasearch opt-in (es. SearXNG o provider compatibile); i risultati sono solo candidati.
3. Fetch su fonti in allowlist, robots, cache, deduplicazione e limiti.
4. Estrattori specializzati (HTML, PDF/documenti, GitHub/API, immagini, tabelle).
5. Provenance per ogni claim; conflitti e validità di versione temporale.
6. Test software isolati quando l'esito è realmente misurabile.
7. Informazioni *verified* solo da evidenze o test opportuni, non dalla fiducia del modello.
8. Motore di curiosità che genera nuove domande con budget e soglia; job figli a profondità limitata.

Nel materiale v0.1 i punti 1 (forma iniziale), 3 (HTML di base) e 5 (relazioni esplicite) risultano parzialmente realizzati. Le altre funzioni richiedono ancora implementazione e prova.

**Limiti dichiarati della ricerca opt-in:** richiede attivazione esplicita e allowlist di domini; il fetch è limitato a HTTPS in allowlist, con robots, timeout, limite di byte e tetto di richieste; supporta HTML, testo e JSON; PDF, browser con JavaScript dinamico, immagini scaricate e scraping autenticato sono adattatori da aggiungere; le pagine recuperate sono fonti non affidabili, non affermazioni accettate come vere. L'implementazione di rete è descritta come sperimentale e non ancora adeguata a navigare siti sconosciuti senza hardening e sandboxing aggiuntivi.

## Repository esterni consultati / integrazioni da valutare

Il materiale v0.1 elenca progetti di riferimento. **Nessun codice di terzi è incluso in questo repository.** Le licenze vanno ricontrollate prima di qualsiasi importazione; le licenze transitive non sono automaticamente identiche a quelle del progetto principale.

| Progetto | Collegamento | Nota dal materiale |
|---|---|---|
| ECC | https://github.com/affaan-m/ECC | Portabilità Markdown, contesti cross-harness, handoff. La sua Memory Vault non è un policy engine o task tracker |
| Hindsight | https://github.com/vectorize-io/hindsight | Retain / recall / reflect; famiglia decision / embedding / reranker |
| EverOS | https://github.com/EverMind-AI/EverOS | Markdown-native, memoria locale persistente |
| Graphiti | https://github.com/getzep/graphiti | Relazioni temporali |
| Cognee | https://github.com/topoteretes/cognee | Ingestione strutturata / grafo |
| LanceDB | https://github.com/lancedb/lancedb | Ricerca semantica embedded |
| SearXNG | https://github.com/searxng/searxng | Metasearch; AGPL, compatibilità di distribuzione da valutare |
| Crawl4AI | https://github.com/unclecode/crawl4ai | Estrazione web |
| Docling | https://github.com/docling-project/docling | PDF e documenti |
| llama.cpp | https://github.com/ggml-org/llama.cpp | Inferenza locale e JSON vincolato |
| MLX-LM | https://github.com/ml-explore/mlx-lm | Inferenza e LoRA su Apple Silicon per famiglie supportate |

## Roadmap in ordini di verifica (non timeline promesse)

**G0 — Sicurezza e costo.** Zero chiamate a provider a pagamento; allowlist; prove contro prompt injection; job con tetto; rate limiter; controllo accessi.

**G1 — Integrità WorldCore.** Snapshot / export / import; prove di cifratura; namespace; provenance delle fonti; versionamento dello schema; nessuna perdita in migrazione.

**G2 — Autonomia completa.** Dopo fine sessione: opportunità → WHAT IF → selezione → ricerca → evidence → ledger → ripresa dopo interruzione del processo.

**G3 — Ricerca reale.** Ingestione da browser o fonti pubbliche permesse; robustezza a robot e rete; misura di qualità e falsi claim; visione multimodale.

**G4 — Modello decisionale.** Confronto sull'hardware reale; costo zero; accuratezza anche in italiano; criterio di stop; LoRA solo se migliora l'holdout.

**G5 — Interfacce universali.** MCP standard; SDK; connettori per framework supportati; autenticazione e permessi separati.

**G6 — Crescita autonoma disciplinata.** Lacune di conoscenza dedotte; competenze future; esperimenti causali; world model appreso verificato in ambienti sconosciuti; anti-loop dei job figli.
