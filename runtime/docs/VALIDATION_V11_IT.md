# WorldCore v1.1 — Rapporto di validazione indipendente

**Data:** 30 ottobre 2026. **Classificazione:** research alpha, non certificata su host di produzione.

## Che cosa è stato realizzato

- WHAT IF non legato ad alcun orchestratore: `compare_futures`, `whatif_backcast`, `whatif_stress_test`, `verify_whatif`, `whatif_replay`, `whatif_history`.
- Ogni simulazione è limitata a effetti dichiarati e non concede autorizzazioni. La ricerca a ritroso usa BFS e ricontrolla l'esito con il simulatore principale.
- Le informazioni salvate distinguono effetti simulati, proiezioni apprese e conseguenze realmente osservate. Il replay non attribuisce risultati alle alternative mai realizzate.
- MCP: le nuove funzioni sono registrate come strumenti; prova di registrazione e chiamata effettuata con SDK simulato, non trasporto MCP reale.
- Claude Code: esempi di `.mcp.json` e hook, test del subprocess Python vero alimentato da JSON su stdin, con esclusione di argomenti e segreti dal registro.
- OpenCode V1 e V2: plugin adattati alle rispettive API. Le osservazioni viaggiano via un processo Python persistente; i test hanno richiamato davvero il bridge SQLite, ma con un mock dell'host OpenCode.
- OpenClaw e Hermes mantengono le integrazioni precedenti. OpenClaw espone anche WHAT IF e backcasting come strumenti nativi.

## Test riproducibili

| Livello | Risultato | Limite |
|---|---|---|
| Test Python completi (`pytest -q tests`) | **248 superati**, 82,32 s | Esecuzione diretta, non runner isolato |
| Test Node.js completi (`node --test tests/*.test.mjs`) | **10 superati**, 0 falliti | Hook host simulati, bridge Python reale |
| Benchmark WHAT IF sintetico | **4 controlli superati** | Non misura accuratezza predittiva su eventi reali |
| Wheel 1.1.0 | **Compilata** | Nessuna prova di compatibilità cross-platform |
| Installazione wheel isolata | **Superata** | Solo Python 3.13 dell'ambiente |
| Controllo SQLite | **Superato** | Per il database nuovo di installazione isolata |
| Runner a processi separati | **Non ricertificato in questa esecuzione** | Comandi esterni si sono interrotti prima della conclusione; test diretti superati |

## Limiti ancora aperti

1. Claude Code e OpenCode non erano installati né autenticati nel container. Nessuna chiamata a modelli Claude/OpenCode reali: i test verificano contratti hook e bridge, non l'intero ciclo con LLM.
2. Il componente WHAT IF **non apprende automaticamente leggi causali** e **non è un world model generale**. Può simulare transizioni esplicite o chiamare modelli compatibili, astenendosi quando non ci sono prove.
3. La ricerca a ritroso non conosce i veri effetti delle azioni: un piano trovato è una conseguenza ipotetica delle operazioni dichiarate.
4. Stress test senza probabilità calibrate; perturbazioni dichiarate dall'utente. Le condizioni sconosciute rimangono sconosciute.
5. Il catalogo storico di repository rimane in quarantena secondo gli audit precedenti: questo rilascio non amplia né certifica quell'audit.
6. Rimangono da collaudare SDK MCP reale, host CLI reali, credenziali e permessi reali, errori di rete, compatibilità software e benchmark con situazioni personali autorizzate.

## Riproduzione

```bash
python -m pip install ./dist/worldcore_cognitive_layer-1.1.0-py3-none-any.whl
python -m pytest -q tests
node --test tests/*.test.mjs
PYTHONPATH=src python benchmarks/v11_whatif_cases.py
python scripts/verify_release.py
```

## Pratiche di sicurezza

- Tenant e spazio isolati per tutte le simulazioni persistenti.
- Nessun comando shell, invio email, acquisto, trading o browsing esterno eseguito da WHAT IF.
- Non salvare output di modello, segreti, contenuti di file o comandi nei plugin osservativi.
- La verifica `user_reported` non equivale a verifica indipendente dell'host.
- L'host resta responsabile di identità, permessi, privacy e approvazioni prima di qualsiasi azione reale.
