# WorldCore 1.3.0rc3 — ciclo Hermes verificato su workspace simulati

31 ottobre 2026. Candidato tecnico installabile. Questa è la verifica più recente; i rapporti rc1/rc2 inclusi descrivono lo stato delle rispettive versioni. Licenza Apache-2.0 invariata, scelta successiva rinviata dall'utente; nessuna pubblicazione eseguita.

## Esito

La serie finale ha superato **3 cicli nativi Hermes su 3**: modello reale, chiamate reali ai due strumenti WorldCore, risposte, hook del plugin e ricevute SQLite indipendenti riconciliate. Inbox, calendario, contatti, cronologia di viaggio e budget sono **interamente simulati**, come richiesto dall'utente. Non si è collegato alcun account mail/calendario né inviato un messaggio o modificata una prenotazione.

| Componente | Natura della prova |
|---|---|
| Hermes | Installazione autentica del computer, `AIAgent.run_conversation`, discovery plugin e dispatch nativi |
| Modello | Groq, modello richiesto `openai/gpt-oss-120b`, chiamate reali; modello servito e route registrati in `host_inventory.json` |
| WorldCore | Motore e plugin reali della rc3, database SQLite reali |
| Calendario | File ICS generati; riunioni sintetiche e conflitto dovuto ai tempi di viaggio dichiarati |
| Inbox | File EML generati; indirizzi `example.invalid`, richiesta di risposta sintetica, metadati importati dal parser reale |
| Contatti e viaggi | Fixture sintetiche, senza rubrica privata, mappe o traffico live; i contatti sono forniti come fixture, non certificati come un connettore operativo |
| Casi aziendali | Separazione personale/azienda, priorità scadenze e risposte testate nel vero motore con dati sintetici; nessun ERP/CRM reale collegato |

## Problemi trovati e risolti

**Rifiuto del provider.** La route compatibile OpenAI emetteva `reasoning_effort="default"`, rifiutato da Groq con HTTP 400. Impostare soltanto `reasoning_config` non bastava. L'override supportato dall'API Hermes `request_overrides={"reasoning_effort":"low"}` risolve la richiesta effettiva. Il percorso riproducibile e la configurazione del profilo temporaneo sono inclusi; non si è alterato il profilo personale dell'utente né patchato l'installazione upstream Hermes.

**Parametri WHAT IF generici.** Il modello autentico aveva inventato campi come `budget_change` e una struttura non valida degli obiettivi. L'adapter ora descrive scenario `id`, azioni numeriche `op/key/value` e obiettivi `key/direction/scale`, con limiti e campi richiesti. Il motore continua a rifiutare dati invalidi; la correzione rende il contratto comprensibile al modello.

**Errori registrati come successi.** La precedente risposta `status="unavailable"` con `error_type` poteva produrre un hook nativo `status=ok`. L'adapter restituisce ora un campo `error`, riconosciuto dal classificatore reale Hermes. La prova negativa separata `hermes_error_contract/` verifica questa classificazione senza chiamate LLM.

**Mail riaperte dal reimport.** È stato riprodotto con un test fallito che rileggere lo stesso EML cancellava risposta e scadenza già note. L'importazione aggiorna ora solo i metadati pertinenti e conserva entrambi. Il test prima fallito e poi passato è incluso; le modifiche esplicite dello stato tramite un connettore più completo restano disponibili.

Le prime due prove hanno inoltre chiarito requisiti di configurazione del profilo: plugin esplicitamente abilitato e catalogo diretto con `tools.tool_search.enabled="off"`. La precedente aspettativa di trovare nomi diretti in una superficie con discovery progressiva era un errore del probe. La configurazione corretta riguarda solo il profilo di test isolato ed è documentata.

## Prove finali

| Verifica | Risultato |
|---|---|
| Hermes nativo, modello → due tool → modello | 3/3, senza errori dei tool nella serie finale |
| Durate complete | 19,236 / 70,588 / 53,559 secondi, entro deadline 120 secondi per caso |
| Ricevute | Una per caso, nonce e run_id distinti, copie dei plugin identiche ai sorgenti consegnati |
| Stato | Budget effettivo invariato a 100; proiezioni WHAT IF 120 e 95; `action_executed=false`; nessuna ricevuta d'azione reale |
| Regressione completa, tre ripetizioni | 38/38 gruppi, **346 Python + 12 Node** per esecuzione, due skip opzionali browser/desktop |
| Workspace sintetici | 16 test: conflitto, inbox, isolamento, dati mancanti, nessun bisogno inventato, scadenze, body injection, duplicati, mail già risposte e otto ordini di inserimento |
| Verificatore del certificato Hermes | 11 test, con rifiuto di prove mancanti/contraffatte, errori del provider/tool, stato mutato e chiamate estranee |
| Ciclo di apprendimento dati | Due promozioni, rollback, sospensione e ritiro di una procedura; hash dei 35 file motore invariati durante l'apprendimento |
| Installazione | Wheel in ambiente pulito, health/isolamento/permessi/SQLite; 35 file motore confrontati con i sorgenti |

Le durate includono l'intero processo Hermes e il provider; non sono una garanzia di latenza in produzione. Non si deduce affidabilità generale da tre casi. Le evidenze dello stress runner 140/140, audit dipendenze, benchmark temporali e OpenCode 3/3 delle versioni precedenti restano incluse e identificate come storiche, non nuovi risultati rc3.

Il verificatore richiede insieme: processo terminato correttamente, conversazione nativa completa, entrambe le chiamate strutturate e i rispettivi risultati, assenza di errori o tool estranei, nonce corretto, ricevuta SQLite, proiezioni attese, hook autentici, stato invariato e risposta finale che riporti run_id e identificatori presenti solo nei risultati. Un processo con exit code 0 o un testo plausibile senza ricevute viene respinto: le prove 3–5 lo mostrano concretamente.

## Artefatti e riproducibilità

Nel pacchetto sono inclusi sorgenti, wheel e sdist, script di certificazione opt-in, test, documentazione del profilo Hermes, fixture ICS/EML/contatti, log stdout/stderr completi, conversazioni sintetiche, ricevute SQLite, inventario host e hash. I profili temporanei e i dump HTTP grezzi non vengono distribuiti: i campi di richiesta necessari alla diagnosi sono estratti in `sanitized_request_diagnostic.json`, senza header o credenziali. Nessun componente MONO è stato copiato; Hermes è utilizzato come installazione esterna autentica.

Percorsi principali, relativi al pacchetto:

- `evidence/personal_agent/hermes_final/summary.json`: risultato completo 3/3.
- `evidence/personal_agent/hermes_final/case_N/`: certificato, verifica, log, SQLite e fixture per caso.
- `evidence/personal_agent/host_inventory.json`: route/modelli e confronto plugin.
- `evidence/personal_agent/hermes_native_1` … `hermes_native_6`: sviluppo, fallimenti e prima riuscita; non sostituiti dalla serie finale.
- `evidence/personal_agent/mail_reimport_before.log` e `mail_reimport_after.log`: regressione prima/dopo.
- `evidence/personal_agent/final_regression/`: tre suite complete con deadline e diagnostica processi/thread/fd.
- `docs/HERMES_SIMULATED_WORKSPACE.md`: comando riproducibile e configurazione funzionante.

## Confini della consegna

Hermes è ora verificato end-to-end **per questi due strumenti consultivi e questi workspace simulati**. Non è corretto definirlo perfetto o completo per ogni workflow. Non sono certificati invio email, scrittura calendario, contatti operativi, ogni provider, calendario ricorrente completo, anticipazione continua senza un ciclo di eventi o impiego reale aziendale. Il modello ha svolto una revisione preventiva richiesta come compito generico; non è stato attivato un servizio che monitora in background.

La scelta rimane codice stabile durante il funzionamento e apprendimento automatico su dati, modelli e procedure, attivato da eventi autenticati dell'host. Le procedure sono dati e non concedono nuovi permessi. Il software può richiedere manutenzione futura; queste prove non giustificano la promessa di una versione «definitiva» che non avrà mai bisogno di interventi.

Restano separati i prerequisiti del lancio pubblico: scelta licenza, responsabilità del manutentore e segnalazioni private, CI remota e valutazioni su workflow rappresentativi. Non sono lasciati processi di test o lavori asincroni attivi dopo questa consegna.
