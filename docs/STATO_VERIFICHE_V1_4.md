# Verifiche runtime 1.4.0rc3 — 8 novembre 2026

La serie locale macOS/Python 3.14 ha superato **439 test Python e 12 Node**,
con 2 test facoltativi browser/desktop saltati. Il supervisore ha completato
43/43 gruppi, incluso un timeout intenzionale per verificare il watchdog.

Il test aggiunge al runtime unificato 24 casi del Cognitive Drive: contesto,
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
o log grezzi dei provider. La CI Linux Python 3.11/3.14 è installata in
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml). Il primo accesso era
privo dello scope `workflow`; il titolare ha completato l'autorizzazione
GitHub e il file è stato poi pubblicato con il collegamento locale.
Lo stato effettivo dei check va letto nella PR, senza dedurlo dai test locali.

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

La revisione rc3 aggiunge sei [prove di ripresa durevole](RECOVERY_V1_4_RC3.md): cinque difetti riprodotti prima della correzione, più un processo worker realmente terminato. Il ciclo completo Feed → raccolta pubblica → registro → riconciliazione WHAT IF ha inoltre superato la prova reale senza LLM.
