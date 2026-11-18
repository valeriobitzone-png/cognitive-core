# WorldCore v0.4 — Rapporto di addestramento e verifica

**Stato: ALPHA sperimentale. NON AGI, NON produzione, NON confronto indipendente con Hermes/OpenClaw.**

## Dati realmente utilizzati
- **3680** osservazioni reali di addestramento supervisionato, in 6 esperimenti distinti; **1231** osservazioni tenute fuori dal training.
- **230** transizioni storiche per il modello osservazionale e **78** per la verifica cronologica.
- **12** documenti tecnici con link pubblico, licenza e SHA-256; **2** note di progetto ricavate dalle decisioni esplicite di questa conversazione.
- Le serie storiche e i dataset numerici derivano da copie reali già installate con scikit-learn/statsmodels; non è stato possibile scaricare grandi corpus nuovi direttamente nella sandbox. Le pagine pubbliche sono state consultate per fonte e licenza.
- Non sono stati esportati né ottenuti i pesi o il corpus di preaddestramento di ChatGPT.

## Metriche Brier (più basso è meglio; holdout non usato per addestrare)

| Dataset | N train | N holdout | Online SGD | Forest | Costante | Persistenza |
|---|---:|---:|---:|---:|---:|---:|
| iris | 112 | 38 | 0.0647 | 0.0007 | 0.2457 | — |
| wine | 133 | 45 | 0.0907 | 0.0107 | 0.2222 | — |
| digits | 1347 | 450 | 0.1721 | 0.0808 | 0.2500 | — |
| sunspots | 228 | 77 | 0.1482 | 0.0641 | 0.2451 | 0.1491 |
| macrodata | 150 | 50 | 0.1149 | 0.0958 | 0.1204 | 0.1360 |
| co2 | 1710 | 571 | 0.2062 | 0.1940 | 0.2501 | 0.2922 |

Tutti e sei gli esperimenti migliorano la baseline costante per il Brier score; sui tre dataset cronologici il modello Forest supera anche la baseline di persistenza definita nel benchmark. Non è dimostrato che siano migliori di tecniche statistiche competitive o di sistemi agentici esistenti.

## Replica con tre semi casuali

| Seed | SGD meglio della costante | Forest meglio della costante | Forest meglio di SGD |
|---:|---:|---:|---:|
| 20261030 | 6/6 | 6/6 | 6/6 |
| 42 | 6/6 | 6/6 | 6/6 |
| 8008 | 6/6 | 6/6 | 6/6 |

I semi 42 e 8008 riutilizzano le stesse serie cronologiche ma rimescolano l’ordine di aggiornamento, e producono altre partizioni per i dataset non temporali. Non equivalgono a tre raccolte di dati indipendenti.

## Previsione osservazionale delle transizioni solari
- Accuratezza sullo stato successivo: **62.8%** su 78 transizioni future riservate.
- Non implica simulazione fisica, interventi causali né capacità di prevedere eventi mai osservati.

## Memoria documentale verificata
- Ricerca FTS5, hash del documento, licenza, URL e isolamento per namespace. Benchmark interno di recupero: recall@3 **100%** su 12 query pubbliche e **100%** su 2 query di progetto.
- Le query di verifica sono redatte dall’autore dei riassunti: questa prova è un semplice controllo di recupero, NON un benchmark indipendente di comprensione del linguaggio.
- I testi esterni sono trattati come dati non attendibili, non come istruzioni eseguibili.

## Ingegneria e sicurezza
- **99 test Python e 5 test Node** superati (suite del repository, host Hermes/OpenClaw simulati).
- Validazione dei JSON degli alberi, nessun pickle o eval, limiti su nodi e dimensioni, dati isolati per proprietario e progetto.
- Le foreste addestrate con scikit-learn si eseguono in puro Python, con equivalenza numerica verificata rispetto a scikit-learn sugli holdout.
- Il preprocessing raw-to-normalized usa esclusivamente min/max derivati dall’insieme di training; input fuori intervallo segnalati e limitati.
- L’SDK MCP e l’integrazione reale con Hermes/OpenClaw NON sono stati testati end-to-end.
- Non sono presenti training in background, installazione automatica di skill, fetch web autonomo, richieste API a provider o esecuzione autonoma di comandi di sistema.

## Limiti e prossime soglie
1. Verificare la privacy e l’autorizzazione dei dati degli utenti prima di importarli.
2. Eseguire test reali versionati su Hermes e OpenClaw e con un MCP server attivo.
3. Aggiungere benchmark ciechi di recupero semantico e valutare modellazione causale con interventi verificabili.
4. Misurare su nuovi dataset il confronto con modelli forti, non soltanto costante e persistenza.
5. Verificare prestazioni e sicurezza su più hardware e sotto carico reale.

## Riproducibilità
```bash
PYTHONPATH=src python -m pytest -q tests
PYTHONPATH=src node --test tests/openclaw.test.mjs
PYTHONPATH=src python benchmarks/real_data_training.py --out /tmp/worldcore-real --seed 20261030
PYTHONPATH=src python benchmarks/grounded_knowledge.py --db /tmp/worldcore-real/worldcore_real_training.db --output /tmp/worldcore-real/knowledge_report.json
```

Richiede scikit-learn e statsmodels solo per ricreare il training; il core runtime ha zero dipendenze esterne.

## Attribuzioni

Dataset UCI con licenza CC BY 4.0 (attribution richiesta); serie statsmodels contrassegnate public domain. Sorgenti, DOI, impronte, note sui dati e versioni delle librerie sono nei JSON di training. Hermes e OpenClaw hanno repository MIT; l’archivio contiene riassunti originali e collegamenti, non una copia delle loro implementazioni.
