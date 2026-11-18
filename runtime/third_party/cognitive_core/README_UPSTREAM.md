# COGNITIVE CORE — Universal Cognitive Engine v0.1

**Prototipo reale eseguibile**, in Python 3.10+, *local-first*, indipendente da MONO / MONOS / Claude / ChatGPT e da qualsiasi singolo modello. Tutte le dipendenze Python di esecuzione sono nella libreria standard. **Non è un sistema AGI completo né un motore di ricerca autonomo già validato sul web pubblico**: è il primo nucleo end-to-end e testabile che conserva le interfacce dei componenti futuri.

## In breve

- **S0 Reflex:** saluti e messaggi triviali -> nessuna istanza del DB, nessun modello, zero ricerca.
- **S1 Decision Plane:** policy deterministiche + adattatore *opzionale* per modello locale compatibile con le API OpenAI, solo `127.0.0.1`.
- **S2 WorldCore:** topics, grafo relazioni, memoria persistente, episodi, predizioni verificabili con Brier score, WHAT IF ipotetico.
- **S3 Workers:** ciclo di session-end -> opportunità -> job persistente -> worker -> ricerca *opt-in* -> documenti non verificati -> evidence ledger.
- **Governance:** zero API a pagamento; allowlist HTTPS, limiti giornalieri e per job, niente azioni esterne con autorizzazioni implicite.
- **Continuity:** checkpoint, lease, ripresa di job interrotti, argomenti sospesi e scartati, namespace isolati.
- **Interoperabilità:** REST solo su loopback, CLI, Markdown/JSON, importazione note Obsidian-like, possibile futura integrazione MCP.
- **Visione:** lettura dei metadati delle immagini dal web; interprete visivo opzionale di file *locali*, purché un server multimodale locale sia disponibile.
- **Apprendimento:** esperienze e outcome persistenti; curation manuale per esempi di fine-tuning. Nessun retraining non supervisionato.

## Avvio rapido

Da questa directory, su macOS / Linux / Windows con Python >=3.10:

```bash
python3 -m unittest discover -s tests -v
python3 -m cognitive_core --home ./my-vault observe '{"kind":"message", "text":"ciao"}'
python3 -m cognitive_core --home ./my-vault observe @examples/stampa_3d_sessione.json
python3 -m cognitive_core --home ./my-vault status
python3 -m cognitive_core --home ./my-vault topics
python3 -m cognitive_core --home ./my-vault dry-run
python3 -m cognitive_core --home ./my-vault tick
```

Il primo comando `observe` non crea nemmeno il database per un saluto. `tick` sarà **blocked** per default: è corretto, la ricerca non parte per sbaglio.

### Memoria e Obsidian

```bash
python3 -m cognitive_core --home ./my-vault remember 'Testo tecnico' 'Nota utile sulla temperatura degli estrusori'
python3 -m cognitive_core --home ./my-vault search 'temperatura'
python3 -m cognitive_core --home ./my-vault import-markdown ~/Documents/ObsidianVault
python3 -m cognitive_core --home ./my-vault export ./vault-export
```

L'importazione legge le note senza modificarle. L'esportazione genera Markdown per i documenti, JSON per le strutture. Indici FTS5 e dati operativi SQLite sono ricostruibili/migrabili; l'esportazione non implementa ancora un ripristino import bidirezionale completo.

### Ricerca web opt-in: esattamente dove sono i limiti

- Richiede `--web` **e** uno o più `--allow-domain`.
- Per la ricerca per parole chiave serve anche `--searxng-url http://127.0.0.1:8081` (SearXNG avviato separatamente) oppure URL di partenza registrati nell'evento.
- Il fetch è volutamente limitato a pagine HTTPS dentro la allowlist. Usa robots.txt, timeout, limite byte e tetto di richieste.
- Supporta solo HTML, testo e JSON. PDF, browser JS dinamico, immagini scaricate e scraping con login sono adattatori da aggiungere.
- Le pagine recuperate sono **fonti non affidabili**, non affermazioni accettate come vere.

```bash
python3 -m cognitive_core --home ./my-vault observe @examples/web_seed.json
python3 -m cognitive_core --home ./my-vault --web --allow-domain docs.python.org tick
```

**Nota importante:** l'implementazione di rete è sperimentale e non è ancora adeguata a navigare siti sconosciuti senza ulteriori hardening e sandboxing (ad esempio protezione completa contro DNS rebinding e download malevoli). Usare fonti allowlist affidabili.

### Modello locale opzionale

Avviare separatamente un modello con un server OpenAI-compatible locale, per esempio `llama-server` di llama.cpp. La scelta del checkpoint e la compatibilità con il runtime sono responsabilità del test sperimentale.

```bash
python3 -m cognitive_core --home ./my-vault --local-model --local-model-url http://127.0.0.1:8080/v1/chat/completions status
```

`--local-model` abilita il classificatore per i messaggi significativi, ma **non** per i saluti. Errori del modello causano fallback deterministico. L'output del modello non conferisce permessi.

### Visione locale opzionale

```bash
python3 -m cognitive_core --home ./my-vault --local-model vision ./foto-stampa.png
```

Necessita di un server multimodale locale compatibile; in assenza non funzionerà. Le descrizioni visuali sono marcate *unverified*.

### Server JSON per gli agenti collegati

```bash
python3 -m cognitive_core --home ./my-vault serve --port 8731
curl http://127.0.0.1:8731/health
curl http://127.0.0.1:8731/v1/status
curl 'http://127.0.0.1:8731/v1/memory/search?q=filamento'
curl -H 'Content-Type: application/json' -d '{"kind":"session_end","title":"Ricerca","open_questions":["Quali sono gli ultimi dati attendibili sul tema?"]}' http://127.0.0.1:8731/v1/events
```

Il server REST **non ha autenticazione**, è limitato a `127.0.0.1` e non deve essere esposto a internet. Per produzione: autenticazione, autorizzazioni granulari, cifratura e controllo di accesso fra utenti.

### Scheduler locale

```bash
python3 -m cognitive_core --home ./my-vault daemon --interval 30
```

Con web disattivato, i job resteranno bloccati. Per un worker opt-in bisogna passare all'avvio `--web`, le allowlist, eventualmente SearXNG. Arresto con Ctrl+C. Il daemon è un semplice processo, non installa da solo un servizio di sistema; per persistenza oltre logout usare `launchd`, `systemd` o altra configurazione esplicita.

### Benchmark di base prima del fine-tuning

```bash
python3 -m cognitive_core benchmark examples/decision_eval.jsonl
```

Si tratta di **16 esempi inventati e dichiarati** per verificare regressioni, non di una misura attendibile su distribuzioni reali. La baseline deterministica è già sufficiente per molte decisioni di S0: misurare qui prima di spendere risorse con un LLM.

## Non ancora implementato / non validato

- World Model dinamico appreso dal mondo e causal discovery reale (ora solo simulazione ipotetica con punteggio euristico).
- Ingestione automatica da ChatGPT, Claude, desktop, browser e giochi: ciascun provider richiede adattatori e permessi specifici; REST è pronto, non gli adattatori.
- Ricerca web live validata, browser dinamico, acquisizione immagini live, OCR/PDF multimodale, test fisici della stampante.
- RAG semantico completo e grafo temporale con reasoning; esiste FTS5, gli archi, i timestamp, e l'interfaccia pronta per i backend futuri.
- MCP server standard completo, metriche CPU/RAM su Mac M4, packaging macOS con firma/notarizzazione.
- Fine-tuning di un modello, confronto rigoroso hs-decide-1-flash / d3-edge / tiny baselines su dataset ampio.
- Verifica automatica scientifica dei contenuti web, ranking qualità delle fonti, estrazione di claim complessi, rilevamento delle contraddizioni semantiche.

**In questa versione non sono stati scaricati pesi LLM e nessun test ha consumato token API.**

## Directory

```
cognitive_core/
  config.py     Configurazione fail-closed
  vault.py      Memoria, provenance, episodic/prediction ledger, graph, FTS5
  decision.py   Reflex + Decision Plane + modello locale opzionale
  world.py      WHAT IF ipotetico
  engine.py     Ciclo principale e worker web
  research.py   Reader e SearXNG opt-in
  vision.py     VLM locale da file
  learn.py      Dataset supervisionato con revisione
  obsidian.py   Importazione note Markdown
  api.py        JSON REST su loopback
  benchmark.py  Valutazioni per selezione modelli
  cli.py        Interfaccia a comandi
```

Consultare `docs/ARCHITETTURA_E_ROADMAP.md` per le decisioni e le fasi successive.
