# WORLDCORE COGNITIVE LAYER v0.6 — Rapporto di validazione

**Data:** 30 ottobre 2026  
**Stato:** research alpha, sperimentazione controllata. Non è un sistema AGI o un agente finanziario/medico autonomo.

## Evidenze di test riproducibili

- **161 test Python raccolti**, tutti superati eseguendo due gruppi isolati (`139` + `22`). La prova di eseguire l'intera raccolta in un solo processo non ha terminato correttamente nella sandbox: per questo il report non ne usa il risultato come prova aggiuntiva.
- **5/5 test Node.js** superati per il plugin OpenClaw con host simulato, incluso bridge persistente e richieste concorrenti.
- **Python wheel 0.6.0** compilata, installata con `--no-deps --target` in ambiente separato, import della libreria e apertura database riusciti.
- **3 database SQLite** nel pacchetto con `PRAGMA integrity_check = ok`: v0.4 modelli numerici, v0.5 evidenze e v0.6 catalogo candidati.
- Nuovo benchmark controllato: **4 ambienti sintetici discreti**, **240 transizioni di training**, **24 previsioni su state-action già noti: 24/24 corrette**; **4 stati fuori distribuzione: 4/4 astensioni**. Questi risultati sono attesi per tabelle di transizione deterministiche: **non provano generalizzazione, intelligenza visiva o apprendimento nel mondo reale**.
- Laboratorio news–mercati testato con **6 eventi e prezzi sintetici** con timestamp e benchmark. Non vi sono in questo rilascio coppie di notizie vere e prezzi storici allineati per un backtest indipendente.
- **246 repository GitHub candidati distinti, di cui 60 con README esaminato**. Candidatura e metadata sono distinti da codice letto, audit qualità/licenze e addestramento del modello. **Zero repository sono stati usati per addestrare pesi linguistici o world model generale.**
- Nuove API MCP registrate con SDK fittizio, non certificazione di host MCP reale. Adapter Hermes/OpenClaw collaudati contro fake host, non contro una loro installazione di produzione.

## Limiti principali

1. **World model**: solo transizioni osservate per stati espliciti JSON e azioni discrete; ignora ambienti mai osservati e dinamiche fisiche/sensoriali continue.
2. **Visione, audio, web, 3D**: contratto per ricevere dati da plugin host; non dispone di propri pesi multimodali o capacità autonoma di web browsing.
3. **Linguaggio naturale**: classificatore leggero di intenti; interpretazione e dialogo rimangono responsabilità del LLM collegato.
4. **Social**: statistiche descrittive di engagement/velocità; non sono state addestrate previsioni di viralità su dataset di piattaforme reali.
5. **Mercati**: correlazioni retrospettive, senza esperimenti causali, sentiment finanziario addestrato su notizie reali, o ordini automatici. Mancano controlli completi di trading calendar, data revisions, multiple testing e costi.
6. **Medicina/psicologia**: suggerimenti condizionali solo con evidenze, non diagnosi certe, prescrizioni o inferenze personali invasive.
7. **Background**: nessun aggiornamento o addestramento continuo attivo nella sandbox dopo la sessione.
8. **Sicurezza**: `owner` e `space` non costituiscono autenticazione; non esporre la libreria/bridge direttamente a Internet.

## Componenti nuovi da verificare su host reali

`worldmodel.py`, `events_lab.py`, `capabilities.py`, `social_lab.py`, `language.py`, `catalog/repository_candidates_v06.json`, `scripts/seed_repo_candidates_v06.py`, `benchmarks/v06_validation.py`.

## Procedure per riprodurre

```bash
python -m pip install ./dist/worldcore_cognitive_layer-0.6.0-py3-none-any.whl
export PYTHONPATH="$PWD/src:$PWD"
pytest -q tests/test_engine.py tests/test_ensemble.py tests/test_hardening.py tests/test_intelligence.py tests/test_knowledge.py tests/test_mcp_mock.py tests/test_hermes.py tests/test_v06.py
pytest -q tests/test_learning.py tests/test_evaluation.py
WORLDCORE_PYTHON="$(command -v python)" node --test tests/openclaw.test.mjs
python benchmarks/v06_validation.py
python scripts/seed_repo_candidates_v06.py --db ./training-artifacts/worldcore_candidates_v06.db
```

## Risultato

**Rilasciabile come codice sperimentale installabile, NON per impiego autonomo in produzione e NON equivalente a un world model generale.** La v0.6 offre uno schema e una pipeline verificabile su cui effettuare in futuro training/benchmark multidominio con dati reali, controllo diritti e valutazioni indipendenti.
