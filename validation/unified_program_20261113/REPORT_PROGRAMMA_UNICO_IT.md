# Cognitive Core: programma unificato installato

13 novembre 2026. Repository canonico su AMBRO, branch `feature/intelligence-feed-runtime`. Nessun commit o cambio di branch; modifiche precedenti preservate.

## Risultato

Un solo `CognitiveCore`, con ingresso `core.run(...)` condiviso da console, worker JSONL e API locale `POST /v1/run`. Collega memoria, WorldCore, Boredom/Curiosity, Opportunity Pool, ricerca locale, WHAT IF, decisione con permessi, evidenze e checkpoint. Aggiunge contesto World/User/Cognitive, regole di attenzione e ricette di trasformazioni ristrette ricavate dalle proposte cognitive dell’ultimo allegato. Nessuna grafica viene avviata; il prototipo SIS non diventa un secondo archivio operativo.

Aprire [Avvia_Cognitive_Core.command](../../cognitive-core/Avvia_Cognitive_Core.command). Richiede Python >=3.11 già installato. È una console in primo piano, senza servizi permanenti. Comandi: `/status`, domande, `/json {...}`, `/stop`, `/start`, `/exit`. [Guida completa e contratto dei collegamenti](../../cognitive-core/runtime/docs/PROGRAMMA_UNICO_IT.md).

## Prima e dopo

| Prima | Dopo |
|---|---|
| Componenti e comandi separati; proposte cognitive dell’allegato come riferimento | Ingresso operativo unico, mantenendo compatibilità dei vecchi comandi |
| Laboratorio e bridge consultabili/importabili separatamente | Archivio nuovo `dati-programma`, owner `local`, namespace `unified`, con 1800 record e provenance |
| Advisor locale opzionale già presente | Gateway sostituibile: GGUF su richiesta o server HTTP loopback dell’host; nessun modello attivato di default |
| Nessuna sessione contestuale comune | Osservazioni bounded con scope, fonte, TTL, revoca e regole di attenzione |
| Proposte di apprendimento non equivalenti a competenze implementate | Ricette pure a massimo tre passi, selezione su sviluppo e verifica held-out; adozione interattiva temporanea |

L’import include 1695 record da `realtest` e 105 dal bridge cognitivo dell’ultimo pacchetto. Ripetere lo stesso import restituisce duplicato senza duplicare i record. Cinque archi con numeri non finiti sono messi in quarantena, con motivo e percorso; non vengono utilizzati come evidenza. I dati conservano gli stati OBSERVED/SIMULATED/INFERRED; zero nuovi fatti verificati. Sono conservate anche tracce dei dati esclusi. I database originali non sono stati aperti dal programma per questa installazione.

## Modelli e limiti di autonomia

Modelli disattivati per impostazione predefinita. Nessun download, client cloud a pagamento o chiave API. Abilitare un profilo non lo rende residente: il backend GGUF avvia un processo solo alla richiesta e lo chiude al termine. Il Core non gestisce invece la residenza o eventuali costi upstream di un server locale esterno.

Sono necessari abilitazione dell’host e richiesta esplicita. L’autonomia richiede inoltre un opt-in distinto; includere memoria nel prompt richiede autorità interattiva. I saluti non caricano modelli né aprono l’archivio. Il turno unificato non chiama advisor o classificatori LLM nascosti. Output generativo INFERRED/non verificato, mai eseguito come tool call o promosso a fatto.

Quote giornaliere prenotate prima della chiamata, lease esclusivo con scadenza, limiti di tempo/output/token e massimo 12 tick per turno. Queste quote riguardano il nuovo ingresso; i comandi legacy mantengono i propri limiti esistenti. Non sono quote di RAM imposte dal sistema operativo.

Le sessioni contestuali e le adozioni di ricette non sopravvivono a riavvio, revoca o stop. Non concedono permessi OS. Contesto personale non incluso automaticamente nel retrieval o nei prompt. Il filtro di dati sensibili copre forme riconosciute, non è una protezione universale: i connettori devono minimizzare i segnali inviati.

La console è sequenziale: durante una generazione usare Ctrl+C per interromperla subito; `/stop` digitato viene letto dopo il ritorno. Uno stop da un altro ingresso sullo stesso archivio viene controllato durante l’attesa GGUF. Se lo stop non può essere scritto per budget disco, vale nel processo corrente e restituisce `persisted=false`.

## Verifica

- Suite finale sulla copia di rilascio: **675 test Python e 12 Node passati, 54/54 gruppi**, due skip per dipendenze browser/Xvfb assenti.
- **55 nuove regressioni**, ripetute con successo sul codice installato.
- Casi coperti: ciclo locale reale, permessi/scope, duplicati e rollback import, falsi riferimenti, dati esclusi/quarantena, stop/restart e perdita dei consensi, TTL e leakage fra contesti, quote e lease, cancellazione/timeout, rifiuto di tool call generative, ricette con held-out ed export senza autorità.
- Wheel: 68 moduli confrontati byte per byte con il sorgente; avvio isolato, saluto senza modello, ciclo reale e stop su Python 3.11.15 e 3.12.13. SHA256 `f035f8bdcdd5c0737c1841df1ef725a45f2e90699762403c0b49b94e124dfbc1`.
- Una chiamata reale locale Rizzo Flow 4B su archivio temporaneo: 6,134 secondi, picco processo 5.532.844.032 byte (~5,15 GiB), nessuna residenza dopo la chiamata. Risposta grezza `PRONTO</think>PRONTO`: prova del collegamento e del ciclo di vita, non benchmark di qualità né certificazione come decisore. Nessuna riparazione automatica del testo.
- Launcher installato provato su copia temporanea dell’archivio nuovo.
- Hash dei 15 file installati verificati; **342 altri file runtime preesistenti invariati**. Tutti i **13 hash protetti** coincidono; runner PID 32703 ancora attivo. `git diff --check` superato.
- Zero chiamate API a pagamento e nessun sensore avviato.

## File installati

Modificati, con backup integrale precedente:

- `runtime/src/cognitive_core/api.py`, `cli.py`, `config.py`
- `runtime/src/cognitive_core/cycle.py`, `engine.py`, `ondemand.py`
- `runtime/src/cognitive_core/portable.py`, `vault.py`, `worker.py`

Nuovi:

- `runtime/src/cognitive_core/program.py`, `models.py`, `skills.py`
- `runtime/tests/test_unified_program.py`
- `runtime/docs/PROGRAMMA_UNICO_IT.md`
- `Avvia_Cognitive_Core.command`

Nessun nuovo schema SIS duplicato: riuso del ledger eventi esistente e indice aggiuntivo. Export degli eventi in ordine di inserimento per preservare revisioni e controllo. Conservati retrieval unificato, export/restore, continuità dei job e citazioni letterali preesistenti.

## Recupero e tracce

[Manifest, backup, risultati e wheel](../../cognitive-core/validation/unified_program_20261113/) sono il riferimento verificabile. `deployment.json` elenca hash prima/dopo; `before/` contiene i nove file precedenti; `rollback.py` ripristina i sorgenti solo se nessuno li ha modificati successivamente. Ripristino e rifiuto in presenza di modifiche successive provati su checkout temporaneo. Il rollback conserva i nuovi file ritirati e non cancella `dati-programma`.

L’archivio applicativo nuovo è `../../dati-programma`; gli originali restano in `../../realtest` e nell’archivio dell’allegato. Nessuna cancellazione automatica. Non eseguire il rollback su codice successivamente modificato senza prima conservarne le variazioni.

## Limiti e prossime integrazioni

Il programma collega le funzioni implementate; non rende automaticamente operative tutte le 69 proposte del catalogo. Restano aperti visione/voce e sensori reali, adattatori specifici Moltis, valutazione longitudinale reale delle nuove competenze e una scelta neurale decisionale sostenuta da benchmark migliori delle regole. Il modello locale rimane un supporto opzionale, non il controllore autonomo generale. Le sperimentazioni precedenti su personalità e quantum-inspired restano studi con i rispettivi risultati, non facoltà dimostrate.

Ordine consigliato: valutare i profili neurali sullo stesso protocollo senza cambiare dati; aggiungere un adattatore di visione con consenso e fixture; collegare Moltis tramite il contratto unificato e gli stessi vincoli di scope e budget. Il formato dei dati e l’export restano indipendenti da modello e runtime.
