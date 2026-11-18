# WorldCore v1.0 — Protocollo di validazione, risultati e limiti

## Obiettivo

Correggere il rischio di blocco del runner; mantenere tutte le capacità v0.9; iniziare l'apprendimento dall'uso di interfacce reali tramite esperienze verificabili; migliorare previsioni personali su calendario, email, spostamenti e orari con dati espliciti.

## Runner

- La vecchia suite v0.9, lanciata direttamente, ha **completato 212 test in ~40 secondi** nel file `worldcore_runner_repro.log`. Il precedente timeout dell'involucro esterno NON dimostrava un deadlock funzionale interno.
- Il nuovo `scripts/run_bounded_pytests.py` è sequenziale e usa un processo separato per ciascun modulo: `Popen(..., start_new_session=True)`, `communicate(timeout=...)`, `killpg(SIGKILL)` al timeout e un risultato globale non-zero quando una prova fallisce.
- Il suo `--selftest` termina intenzionalmente un processo bloccato. Le prove `test_v10_runner.py` verificano il timeout, codice non-zero e normale successo.
- I test possono fallire o andare in timeout, e questo sarà visibile nel file JSON, anziché bloccare indefinitamente il rilascio.

## Browser e desktop

- Playwright ha controllato **Chromium reale** su pagine di test HTML isolate senza navigazione pubblica. Tre UI sono state usate per la raccolta di esempi, con test su un layout non incontrato.
- Benchmark aggiuntivo `v10_browser_holdout.json`: sei UI generate non utilizzate durante l'apprendimento, più quattro casi di azione mai vista; il comportamento di astensione è parte dell'esito, non un errore.
- Il test desktop avvia una reale GUI Tk su Xvfb, usa testo/accessibilità dei widget e applica una capacità precedentemente acquisita dalle UI browser. Non testa applicazioni desktop arbitrarie.
- Il motore non esegue mai automaticamente il comando suggerito fuori dalla sandbox di valutazione.

## Personal agent

- Archiviazione versionata di appuntamenti, isolamento proprietario/spazio, cancellazioni, collisioni temporali, segnali email con scadenze.
- Tempi di viaggio appresi da dati forniti dal programma host. Ritorno di stima solo sopra la soglia di osservazioni, uso dell'80° percentile come margine. Benchmark cronologico su dati **sintetici** (`v10_personal_backtest.json`); NON dati GPS reali o dati privati utente.
- Ottimizzazione orari basata su intervalli liberi, eventi e tempi di viaggio; se una tratta richiesta non è misurata, astensione. Nessun accesso diretto a Google Calendar, Gmail, mappe o GPS.
- Import ICS: solo VEVENT con DTSTART/DTEND e fuso IANA o UTC; segnala le ricorrenze non espanse. EML: solo header essenziali, con consenso esplicito, nessun corpo.

## Adattatori

- Hermes: test con host simulato di `register_hook` e `register_tool`, inclusi risultati di consultazione reali da database SQLite. Nessuna chiamata reale al LLM Hermes né con account remoto.
- OpenClaw: test Node.js di `api.on` e `api.registerTool`, IPC JSONL persistente che richiama Python, e test di restart. Non è verificato in un Gateway effettivo.
- MCP: nuove API di lettura registrate nel server; la disponibilità del server in un host MCP reale resta da provare.

## Cosa manca per produzione

1. Prove su account/calendar/email/itinerari **reali, con consenso** e holdout temporale, oltre a false-positive rate e calibrazione.
2. Modelli visivi/audio generali usati da una piattaforma con permessi. La v0.9 riconosce cifre/toni/movimento, non contenuti semantici arbitrari.
3. Policy, rollback e approvazioni reali in Hermes/OpenClaw su app e siti autentici; test di browser isolato senza dati sensibili.
4. Benchmark esterni, audit completo delle dipendenze e validazione di licenze dei 246 repository già catalogati.
5. Servizio di aggiornamento continuo, monitoraggio dei modelli e gestione privacy con host installato: nessuna attività rimane in esecuzione dopo la chat.

**Verdetto:** research alpha installabile, non engine predittivo generale certificato.

## Certificazione eseguita nella sandbox (build 1.0.0)

- Runner: **24/24 gruppi** passati, inclusi 1 watchdog con timeout deliberato; nessun gruppo fallito.
- Pytest: **231 test passati** nei moduli isolati. Node.js: **6 test passati** su 2 moduli.
- Browser Chromium reale su HTML offline: **6/6** azioni corrette su layout sintetici non presenti nel training; **4/4** astensioni su affordance sconosciute.
- Desktop: Tk su Xvfb, **1 test passato** di trasferimento di un comando da browser a finestra desktop. Non equivale ad automazione di app generiche.
- Benchmark viaggio con dati sintetici separati cronologicamente: 20 dati di training e 10 di verifica, copertura osservata 70% con una stima all'80° percentile; errore mediano assoluto riportato dal benchmark = 4.5 minuti. Non sono tempi reali.
- Wheel `worldcore_cognitive_layer-1.0.0-py3-none-any.whl`: costruita, installata in una cartella estranea ai sorgenti, importata e `doctor` eseguito con SQLite integro.
- Integrità dei 7 database di training inclusi: **7/7 ok**.

**Caveat importante:** i test funzionali e la compatibilità del plugin con host simulati non certificano un'installazione reale Hermes o OpenClaw. L'engine non gestisce account personali senza importazione consensuale, non controlla un browser remoto, non ha live traffic né un modello generale del mondo.
