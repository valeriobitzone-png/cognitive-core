# Verifiche runtime 1.4.0rc2 — 8 novembre 2026

La serie locale macOS/Python 3.14 ha superato **432 test Python e 12 Node**,
con 2 test facoltativi browser/desktop saltati. Il supervisore ha completato
42/42 gruppi, incluso un timeout intenzionale per verificare il watchdog.

Il test aggiunge al runtime unificato 23 casi del Cognitive Drive: contesto,
provenienza, duplicati, scarto persistente, isolamento owner/namespace,
concorrenza, rollback, capacità, budget, WHAT IF, proiezione temporale, CLI e
trasporto stdio. Le altre regressioni WorldCore restano presenti.

Il [fixture Intelligence Feed](../runtime/examples/intelligence_feed_fixture.json)
contiene **12 eventi sintetici**. La selezione dei cinque risultati attesi,
il duplicato, l'osservazione futura e la proiezione temporale sono verificati
senza web o modelli. Precision@5 e recall@5 valgono 1 in questo contratto;
non sono stime della rilevanza di notizie reali per l'utente.

Una prova separata usa il commit pubblico reale
[`446b616`](https://github.com/valeriobitzone-png/cognitive-core/commit/446b616dd43e387aa2c2ee333e6ee78dca31e7e2)
come stimolo: il Core lo collega al contesto del progetto e crea un candidato.
Questo verifica l'ingresso di una fonte reale, non la sua utilità indipendente.
Il Core non ha raccolto nuove informazioni personali né chiamato modelli.

I [risultati sintetici](../validation/benchmark.json), la
[prova sul repository](../validation/public_repo_event.json) e il
[riepilogo](../validation/summary.json) sono pubblicati senza database personali
o log grezzi dei provider. La configurazione CI Linux Python 3.11/3.14 è pronta in
[`ci/github-actions.yml.example`](../ci/github-actions.yml.example). La sua
attivazione è bloccata: le credenziali Git locali non hanno scope `workflow` e
il collegamento GitHub dell’app rifiuta la scrittura con HTTP 403. Nessun check
remoto è dichiarato superato. Per attivarla occorre installare quel file come
`.github/workflows/ci.yml` con un accesso autorizzato ai workflow.

La wheel è stata inoltre installata senza dipendenze aggiuntive: 51 file sono
identici tra sorgenti, installazione e archivio sorgente.

Il runtime 1.4.0rc1 di partenza aveva già una prova di raccolta pubblica della
pagina Python JSON, con due richieste HTTP, e un'installazione senza dipendenze
obbligatorie. Le precedenti certificazioni Hermes/OpenCode riguardano le
versioni e i dati indicati nei rispettivi rapporti. La presente PR non dichiara
una nuova certificazione con LLM o del profilo Hermes personale attivo.

I modelli locali, il RAG semantico, i sensori desktop/mobile e la qualità reale
delle opportunità restano da valutare. Il feedback è marcato
`operator_reported`; non diventa automaticamente una verifica indipendente o
un addestramento. Il briefing non viene attivato a un orario prestabilito.
