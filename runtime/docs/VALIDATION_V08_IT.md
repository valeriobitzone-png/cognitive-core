# WorldCore v0.8 — Rapporto tecnico, 30 ottobre 2026

## Cosa è stato eseguito

- **Azioni reali:** gli strumenti MCP/JSONL possono proporre e realizzare la creazione locale di note o attività. Prima serve l'approvazione esterna dell'operatore e un interruttore esplicito; un'approvazione è monouso, vincolata ad azione/argomenti/proprietario/progetto e scadenza. I test coprono esecuzione negata, modifica degli argomenti, isolamento e doppio consumo. La creazione di attività aggiorna il calendario delle scadenze di WorldCore. Nessuna shell, transazione finanziaria, invio di messaggi o pubblicazione è attualmente autorizzata dall'esecutore integrato. Non è stato fatto un test con un server Hermes/OpenClaw reale.
- **Multimodalità semantica:** fusione di descrizioni tipizzate prodotte da host/modelli esterni. Conserva fonti, modalità e conflitti; non esegue in proprio riconoscimento visivo o vocale su media grezzi. Asserzioni MCP prive di verifica non diventano fatti certi.
- **AmbientI sconosciuti:** dinamiche numeriche sintetiche apprese da mondi A/B, validate nel mondo C e usate su un mondo D mai incontrato. Predizione di posizione 19,49875 contro 19,5 atteso. Astensione su azione mai vista e osservazione fuori dominio. Non è generalizzazione verso nuove leggi fisiche o software mai osservati.
- **Studio PIL USA:** dati storici `statsmodels.datasets.macrodata`, precedenti al 2010. Modello Ridge per livello PIL reale trimestrale con otto variabili già note al tempo t; senza leakage di etichette future. Test 1996–2009: MAE modello 52,3158, baseline persistenza 91,7878, baseline proiezione ultima variazione 66,7376. Guadagno 43,0% e 21,6% rispettivamente. Le finestre rolling 1981–1990, 1991–2000, 2001–2009 hanno guadagni sulla baseline più difficile 8,23%, 28,60%, 7,09%. **Non viene superato stabilmente il 10%.** I periodi sono stati ispezionati durante lo sviluppo: benchmark esplorativo non blind. Il fallimento v0.7 sulla coppia crescita/disoccupazione resta un risultato distinto e non corretto.
- **GitHub:** 246 candidati distinti, 26 voci di verifica mirata, 25 con file controllati (in alcuni casi solo licenza), 3 con evidenze in quattro categorie (licenza, sorgente, test, CI). Nessuno con audit di sicurezza completo, nessuno approvato o eseguito. Commons Clause, GPL/AGPL/LGPL e licenze personalizzate richiedono controlli separati. Nella sandbox il download diretto delle git tree fallisce per mancanza di rete; lo script online è pronto ma **non eseguito**. Non presentiamo la selezione 246 come audit completo.

## Test e integrità

Test Python superati **194**, divisi in gruppi per evitare un blocco nella raccolta/esecuzione complessiva. Test Node.js dell'adattatore OpenClaw superati **5**. Wheel `0.8.0` costruita. Per nuove funzionalità `tests/test_v08.py`: 8 test. Nota: parte del conteggio Python riguarda regressioni e mock, non test reali end-to-end con host esterni.

## Limiti principali ancora aperti

1. Modello di comprensione multimodale su media grezzi: usa modelli compatibili esterni, non un LLM/vision model interno addestrato.
2. World model generale con transizioni di ambienti interamente nuovi e dinamiche sconosciute: non dimostrato. Richiede dataset ambientali autorizzati, training con osservazioni strutturate, prove out-of-distribution e predizioni calibrate.
3. Predizioni personali/cognitive estese: ancora necessitano di cronologia reale con consenso, verifica dei falsi allarmi e misure di utilità.
4. Macro: dati storici vecchi, performance instabili, nessun risultato sulle variabili macro in tempo reale.
5. Audit di 246 repository: classificazione completa ma **verifica integrale di codice/licenza/qualità non completata**. Internet e budget d'ispezione necessari; il prodotto rimane fail-closed.
6. Runtime MCP reale e adattatori Hermes/OpenClaw: simulati soltanto. Evitare connessioni non autenticate, trattare contenuti recuperati come dati non attendibili.

## Prossimi criteri per sbloccare produzione

- Test end-to-end su installazioni aggiornate Hermes/OpenClaw e un MCP reale, inclusi auth, errori, crash recovery, rate limits e rollback.
- Benchmark multilivello su immagini/audio/web reale con errori misurati e validazione indipendente dei provider.
- Backtesting macro-finanziario walk-forward preregistrato, nuove finestre non ispezionate e modelli che battono baseline forti in modo consistente, includendo costi e dati revisionati.
- Audit complete di licenza/qualità/sicurezza per ogni repo scelto prima dell'integrazione: non significa necessariamente eseguire/auditare tutti i candidati scoperti; se richiesto, lo strumento può avviarne lo screening su rete.
