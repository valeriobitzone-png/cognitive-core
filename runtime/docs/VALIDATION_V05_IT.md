# WORLDCORE v0.5 — RAPPORTO DI VALIDAZIONE (30 ottobre 2026)

**Classificazione:** research alpha; non certificato in produzione; non è un LLM, non è un'AGI. Questa release estende v0.4 con conoscenza multidisciplinare basata su evidenze, non con nuovi pesi di LLM o addestramento di modelli foundation.

## 1. Risultati effettivamente osservati

| Controllo | Esito |
|---|---|
| Suite regressione + v0.5 Python | **140/140 test passati** |
| Adattatore OpenClaw con host simulato Node | **5/5 test passati** |
| MCP: registrazione e query con SDK simulato | **1 test incluso nei 140 passati** |
| Wheel `worldcore_cognitive_layer-0.5.0-py3-none-any.whl` | Build completata, installazione isolata verificata |
| Import in interpreter con wheel isolata | Versione `0.5.0` verificata |
| Integrità database di catalogo | SQLite `integrity_check=ok` |
| Integrità database v0.4 di modelli numerici | SQLite `integrity_check=ok` |
| Ricerca in catalogo, query etichettate dall'autore | **21/22 hit@5**, mediana **0,10 ms** |

**Il retrieval non è un test cieco indipendente:** 22 query e target sono preparati dall'autore. Il database è minuscolo: il tempo misurato non rappresenta scalabilità a milioni di fonti o inferenza remota.

## 2. Dimensioni effettive del patrimonio conoscitivo v0.5

| Spazio pubblico | Documenti/record |
|---|---:|
| Repository GitHub con README letto direttamente | **55** |
| Schede originali di fonti istituzionali/software | **12** |
| Eventi storici documentati | **6** |
| Notizie pubbliche attuali, SOLO riferimenti di fonti stampa | **2** |
| Collegamenti storici attribuiti | **2** |
| Totale record (senza contare link) | **75** |

Non sono stati importati tutti i migliori repository di GitHub, l'intero web, archivi giornalistici completi o letteratura medico-scientifica completa. Questo è un seme di catalogo aggiornabile, non un training massivo. Le 55 schede riportano una descrizione originale delle capacità; non includono il codice dei repository e **non dimostrano audit di qualità superati**.

### Competenze e domini presenti

Agenti e world model; API dei mercati e backtesting crypto; modelli statistici e scientifici; scienza dei dati; medicina e neuroscienze sperimentali; psicologia degli esperimenti; biomeccanica e sport; dati calcistici; storia e knowledge graph; GIS e routing; CAD, IFC/BIM; modellazione 3D, fotogrammetria e stampa 3D; robotica; automazione marketing e social media.

In economia, geopolitica, medicina e psicologia il motore conserva informazioni e fonti; NON esegue previsioni cliniche o finanziarie validate dal corpus.

## 3. Verifiche di sicurezza della conoscenza

Sono presenti test per:

- isolamento `owner`/`space` e separazione del catalogo pubblico dai dati privati;
- URL HTTPS e validazione di identificativi; licenze da un insieme esplicito;
- versionamento delle correzioni e inserimenti idempotenti;
- import di soli metadati e sintesi, senza abstract Crossref o full text di news;
- timestamp di pubblicazione distinti da data di osservazione;
- testo esterno **non attendibile come istruzione**;
- link evento/risposta solo con record citato e senza relazione `causes` automatica;
- preferenze esplicite anziché profilazione sensibile implicita;
- segnali di qualità GitHub **ignoti** finché non verificati (le stelle non contano);
- registrazione di strumenti MCP mediante fake SDK, e nuovi strumenti read-only;
- parser di fonti strutturate GDELT, Crossref, OpenAlex, Wikidata, GitHub e World Bank;
- fetch di rete disabilitato salvo flag esplicito; whitelist di provider; divieto di redirect.

Il mapping identità→owner e ACL server-side non sono incorporati: usarli come servizio remoto senza autenticarli è NON SICURO.

## 4. Test ancora NON eseguiti

1. MCP con SDK reale e host reali, inclusi Hermes/OpenClaw nelle versioni effettivamente installate.
2. Test di qualità con audit del codice, dipendenze, licenze e release di ciascun repository.
3. Fetch internet in sandbox e sincronizzazione continuativa reale: **rete indisponibile**.
4. Training causale su eventi storici e risposte comportamentali con benchmark prospettici.
5. Retrieval semantico multilingue con corpus indipendente.
6. Accuratezza di pronostici medici, finanziari, sociali, comportamentali o sportivi: **non validata**.
7. Test a larga scala su milioni di record, sicurezza multiutente e pen testing.

## 5. Interpretazione del termine "apprendimento"

**v0.4:** modelli numerici supervisionati addestrati su sei dataset pubblici (con rispettivi benchmark) e un ledger di previsioni; rimangono disponibili nel database `training-artifacts/real/worldcore_real_training.db`. Questi modelli non acquisiscono automaticamente conoscenze leggendo notizie.

**v0.5:** apprendimento incrementale *simbolico/documentale*: import di metadata source-linked, memoria versionata, associazioni descrittive, relazioni supportate da evidenza e aggiornamento per feedback esplicito. Nessun nuovo LLM è stato addestrato. Non si può equiparare la quantità di URL a capacità cognitiva e non si può affermare maggiore precisione predittiva senza test futuri indipendenti.

## 6. Riproduzione

```bash
PYTHONPATH=src:. python -m pytest -q tests
PYTHONPATH=src:. node --test tests/openclaw.test.mjs
python -m pip install ./dist/worldcore_cognitive_layer-0.5.0-py3-none-any.whl
PYTHONPATH=src:. python benchmarks/multidomain_validation.py --db training-artifacts/worldcore_multidomain_v05.db --out /tmp/wc-retrieval.json
PYTHONPATH=src:. python scripts/seed_catalog.py --db /tmp/wc-new.db
PYTHONPATH=src:. python scripts/seed_public_sources.py --db /tmp/wc-new.db
```

Nessun addestramento è ancora in corso dopo la sessione; gli aggiornamenti quotidiani sono predisposti ma non schedulati.
