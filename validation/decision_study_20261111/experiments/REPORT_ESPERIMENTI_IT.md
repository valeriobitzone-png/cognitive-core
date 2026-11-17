# Cognitive Core — studio locale e integrazione opzionale, 11 novembre 2026

## Esito e decisione

Non confermo la precedente scelta preliminare di Qwen3.5: era basata su un controllo di pertinenza troppo limitato. Nessuno dei quattro candidati neurali testati viene scelto o abilitato per le decisioni autonome. Nel piccolo test locale le regole sperimentali superano tutti i candidati; queste regole del banco prova non sono identiche al reflex già presente nel prodotto e non vengono sostituite al core in questa modifica.

Il collegamento opzionale al modello locale e un self-model funzionale vengono aggiunti con default spento, senza un percorso pesi preconfigurato. Il modello può soltanto esprimere pertinenza o astensione; non concede permessi. I risultati su instradamento di sei azioni sono uno studio separato, non le prestazioni certificate di questo adattatore di pertinenza.

## Ricerca prima della scelta

Sono state consultate fonti primarie, distinguendo modelli generativi generici, specialisti per chiamate di funzione, encoder e politiche apprese da traiettorie. I numeri pubblicati non costituiscono una graduatoria normalizzata: cambiano versione del benchmark, formato, lingua, prompt e addestramento.

- [FunctionGemma270M, Google](https://ai.google.dev/gemma/docs/functiongemma): specialista per chiamate di funzione; Google raccomanda fine-tuning sul compito. La [scheda originale](https://huggingface.co/google/functiongemma-270m-it) riporta BFCL Simple 61,6, Live Simple 36,2, Relevance 61,1 e Irrelevance 73,7: sottocompiti diversi, non un unico punteggio aggregato. Va usato il [formato nativo](https://ai.google.dev/gemma/docs/functiongemma/formatting-and-best-practices).
- [LFM2.5-350M, Liquid](https://www.liquid.ai/blog/lfm2-5-350m-no-size-left-behind): autore riporta BFCLv3 44,11, BFCLv4 21,86 e IFBench 40,69. La lista ufficiale delle lingue non include italiano; questo rende necessario un test locale, non un'assunzione di supporto.
- [Granite4.0-350M, IBM](https://huggingface.co/ibm-granite/granite-4.0-350m): candidato piccolo con uso di strumenti, licenza Apache2; non si assume una competenza decisionale generale dal nome.
- [Qwen3.5-0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B): baseline generativa generica, non uno specifico modello decisionale.
- [LFM encoder](https://www.liquid.ai/blog/lfm2-5-encoders) e [MiniLM multilingue](https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2): candidati per un classificatore leggero, da completare e addestrare sul compito; similarità non equivale a rispetto dei permessi. Non scaricati né misurati in questa sessione.
- [Decision Transformer](https://huggingface.co/docs/transformers/model_doc/decision_transformer): richiede stati, azioni, ricompense e traiettorie pertinenti all'ambiente; non è un controllore conversazionale pronto da collegare all'archivio.
- Valutati soltanto documentalmente: [Hammer2.1-0.5B](https://huggingface.co/MadeAgents/Hammer2.1-0.5b), [xLAM-1b-fc-r](https://huggingface.co/Salesforce/xLAM-1b-fc-r) (circa 1,35B effettivi), [Tiny Recursive Models](https://github.com/SamsungSAILMontreal/TinyRecursiveModels). Nessun risultato locale è attribuito a questi modelli; la competenza su puzzle dei piccoli modelli ricorsivi non li rende controllori linguistici pronti.

## Protocollo e confronto locale

Apple M4, 16 GiB di memoria unificata. Dataset sintetico congelato: 56 train, 16 sviluppo, 34 test, sei classi (attesa, memoria, ricerca locale, ricerca web, chiarimento, approvazione). SHA dataset: `5b400cd1673f0423a48ed36b755649aee740287abd286c20bada7c97a3f1b5b8`. Nuove formulazioni e domini nel test; non è un campione rappresentativo della vita reale. Permessi, consenso e budget sono dati strutturati; estratti sono dati non fidati. Le azioni sono solo etichette: nessuna chiamata a strumenti o rete è stata eseguita dai modelli.

Per i GGUF: processo a freddo per caso, CPU due thread, contesto 2048, massimo 64 token, temperatura zero, timeout 20 secondi. Per modello: 16 sviluppo + 34 test + 6 ripetizioni di controllo. I generici usano JSON vincolato; FunctionGemma il protocollo nativo. TF-IDF è addestrato sui soli 56 casi train. Risultati sul test:

| Sistema | Corretti | Macro F1 | Proposte valide fuori policy | Output invalidi | Mediana secondi | Picco processo GiB |
|---|---:|---:|---:|---:|---:|---:|
| Regole sperimentali | 31/34 | 0.909 | 0 | 0 | 0.0000 | 0.00 |
| TF-IDF + regressione logistica | 20/34 | 0.603 | 6 | 0 | 0.0004 | 0.00 |
| Qwen3.5-0.8B Q8 | 10/34 | 0.236 | 2 | 0 | 2.2661 | 1.71 |
| LFM2.5-350M Q8 | 15/34 | 0.313 | 4 | 0 | 0.8259 | 0.80 |
| Granite4.0-350M Q8 | 11/34 | 0.312 | 4 | 0 | 1.0669 | 0.84 |
| FunctionGemma270M Q8 (primo call) | 7/34 | 0.134 | 4 | 1 | 1.9888 | 0.64 |

Le proposte fuori policy non sono azioni eseguite. Output invalidi e violazioni vengono contati separatamente. La RAM riportata è RSS di processo, non il limite rigido della macchina; zero per le baseline significa non misurata nel processo separato, non memoria nulla.

FunctionGemma: il primo parser contava anche continuazioni inventate dopo la prima funzione, ottenendo 5/34 con sette output invalidi. Applicando il confine documentato della prima chiamata completa, senza cambiare prompt, pesi o generazione, si ottengono 7/34, un output invalido e quattro proposte fuori policy. Restano 27 risposte senza chiamata nativa. Entrambi i conteggi e i raw output sono conservati. I tempi sono quelli della generazione completa, dunque un limite superiore rispetto all'arresto alla prima chiamata. Un controllo nativo separato sulla funzione meteo ha prodotto correttamente nome e argomento: la prova debole sul nostro instradamento non è una misura universale del modello.

Non vengono ottimizzati prompt o pesi sul test dopo questi risultati. Un unico piccolo dataset e prompt non permettono di distinguere definitivamente limiti del modello, del protocollo e della quantizzazione. Non si convertono i risultati del produttore in stime locali.

## Esperimenti richiesti dall'allegato

### A/B/C: memoria e self-model funzionale

Implementati episodi persistenti con previsione antecedente all'esito, attribuzione self/other, separazione OBSERVED/SIMULATED, identificazione del runtime e controllo delle capacità prima dell'azione. Esito immutabile e riavvio/esportazione JSON sono verificati. La stima concerne processo completato con schema valido; la verità semantica resta non misurata. Il core non dichiara coscienza e non impara dai propri racconti come se fossero osservazioni.

Esperimento sintetico: dieci semi, 80 episodi train e 80 holdout per seme, runtime stabile/degradato; tutte le previsioni holdout sono congelate prima degli esiti. Brier medio (minore è meglio): memoria aggregata 0,24657; stato del runtime 0,14815; osservatore esterno con la stessa informazione 0,14815; rimozione dello stato 0,25000. La perturbazione di un tema irrilevante non cambia il risultato. Differenza stato meno memoria −0,09842, bootstrap 95% sui dieci semi [−0,11316; −0,08233]. L'uguaglianza con l'osservatore esterno smentisce qualsiasi pretesa di accesso privilegiato; questo è un compito costruito, non una certificazione di calibrazione reale. Un tool rimosso provoca astensione prima dell'inferenza; episodi simulati non aggiornano le stime osservate.

### Personalità nelle scelte

Politiche esplicite prudente/esplorativa: 2.000 decisioni sintetiche, dieci semi; stabilità al riordino 100%, scelte non autorizzate zero, differenza tra profili 21,5%. È una preferenza costruita nella funzione di scelta, non una personalità emergente.

Controllo neurale molto piccolo: 12 casi per modello (due profili, tre scenari, due ordini). Qwen: accordo con il trade-off atteso 50%, stabilità all'ordine 33,3%. LFM: 66,7% e 66,7%. Nessuna scelta proibita in questi pochi casi. La fragilità all'ordine impedisce di adottare una personalità appresa dal solo prompt; nessuna conclusione psicologica.

### E: LoRA reale, non simulata

Eseguito vero addestramento locale MLX su LFM2.5-350M, secondo [mlx-lm](https://github.com/ml-explore/mlx-lm/blob/main/mlx_lm/LORA.md), con checkpoint base immutato e adattatori separati. Tre semi, rank8, quattro layer finali, batch1, 24 passi, learning rate 0,0002, 0,754 milioni di parametri addestrabili (0,213%). Soltanto 96 token supervisionati per run: esperimento pilota volutamente limitato. Nessun dataset personale usato. Memoria MLX limitata a 6GB, cache 300MB; picco train circa 1,18GB, adattatore circa 2,9MB per seme.

Protocollo separato: scelta del prossimo token A–F fra sei azioni, checkpoint base non quantizzato; non confrontare direttamente queste latenze o percentuali con la generazione JSON su CPU. Holdout 34: base prompt 8/34, base con due esempi recuperati dal train 9/34; LoRA semi 0/1/2 rispettivamente 6/34, 6/34, 5/34. La loss di validazione del primo run peggiora. Nessun adattatore viene adottato. Questa prova non dimostra che LoRA sia inefficace in generale; occorrono più dati e un addestramento adeguato prima di un nuovo test indipendente.

### F: quantum-inspired contro classici dinamici

Eseguito calcolo classico, nessun hardware quantistico: probabilità sequenziali di uno stato puro 2D con due parametri. Tre generatori, dieci semi ciascuno, per run 160 train / 80 validazione / 400 test. Confronti: modello classico esattamente equivalente a due parametri, modello dinamico indipendente a tre parametri, modello statico a due.

NLL media holdout: sul generatore proiettivo 1,10398 quantum e classico equivalente, 1,10460 dinamico, 1,33375 statico; CI 95% quantum meno dinamico [−0,00222; 0,00080]. Sul generatore classico dinamico: 1,03085 / 1,02809 / 1,36453. Su dati indipendenti il modello puro ristretto è peggiore: 1,66599 contro 1,39713 dinamico e 1,39272 statico. Il confronto equivalente è identico per costruzione matematica, non una scoperta empirica indipendente. Il dinamico è stimato separatamente. Nessun vantaggio riscontrato sul classico dinamico comparabile; il risultato negativo riguarda questa parametrizzazione, non tutti i modelli quantum-inspired. Modulo non integrato nel core.

### Parti dell'allegato ancora aperte

La matrice A/B/C/E/F è coperta solo nelle componenti descritte; non è stata realizzata una singola prova fattoriale completa. D, progresso contro costo su compiti longitudinali reali, resta da sviluppare. Non sono stati testati introspezione delle attivazioni, coscienza, neuromodulazione biologica, visione, voce o un ciclo autonomo longitudinale con nuove competenze. Le formulazioni del documento sono trattate come proposte da verificare, non risultati già acquisiti.

## Prima e dopo nel software

Prima: ciclo operativo unificato esistente, reflex e backend HTTP opzionale; mancavano inferenza GGUF a chiamata singola su archivio senza migrazione e ledger delle previsioni sulle proprie capacità.

Dopo: adapter GGUF opzionale senza servizio residente, retrieval riusato su copie temporanee DB/WAL, cache per contesto/modello/scope, quota persistita prima dell'inferenza, timeout/output/token/disk bounded, saluti gestiti senza modello, astensione e fallback deterministico. Il modello può veto sulla registrazione locale; non può estendere autorità o promuovere ipotesi a fatti. Self-model portabile in sidecar separato, previsioni prima degli esiti. Default disabilitato; nessun modello selezionato o inserito nel percorso autonomo.

Modificati soltanto questi file rispetto alla baseline di questa fase:

- `runtime/src/cognitive_core/{config,decision,engine,cycle,cli}.py`
- nuovi `runtime/src/cognitive_core/{advisor,ondemand,selfmodel}.py`
- nuovi `runtime/tests/{test_local_advisor,test_functional_self}.py`
- nuovo `runtime/docs/LOCAL_DECISION_ON_DEMAND_IT.md`

Le correzioni preesistenti, i moduli WorldCore e i database originali vengono preservati. Nessun commit, nessun reset, nessun servizio o configurazione globale cambiati. L'eseguibile llama.cpp resta una dipendenza opzionale indicata dall'operatore, non un requisito del core portabile. Nessuna dipendenza MLX aggiunta alla wheel.

## Verifica e limiti operativi

Suite finale: 548 test Python riusciti, due saltati, 12 test Node riusciti, 50/50 gruppi inclusa la prova del watchdog. La riga testuale del runner dice erroneamente “50 / 50 failed []”: significa 50 gruppi passati, lista fallimenti vuota; il JSON strutturato ha complete=true. Un primo avvio manuale di pytest senza PYTHONPATH ha fallito la raccolta; rieseguito correttamente e poi verificato con il runner completo. Nuova regressione: se il ledger delle previsioni non può scrivere, nessuna inferenza parte e il lease viene rilasciato, conservando la quota già impegnata.

Verificati cache/restart, crash dopo ammissione, timeout e raccolta figli, quota, lettura WAL, hash archivi immutati, namespace/owner, fonti non fidate e schemi malformati, nessuna escalation permessi, esportazione self-model e riavvio su copia, esclusione storia simulata e altrui. I test precedenti su duplicati, rollback, fonti false/scartate, scope e citazioni restano passanti.

Wheel confrontata byte per byte con 60 moduli Python; smoke isolato senza dipendenze esterne con Python 3.11.15 e 3.12.13. SHA256 nuova wheel: `ef5c0b705b253c84f95ebfa00a10211faa154087cb6271ebb8137c51eb924735`. Versione pacchetto invariata 1.4.0rc3: distinguere i build tramite percorso e hash, non sovrascrivere la wheel precedente.

Smoke finale reale dell'adapter con Qwen candidato: tre inferenze terminate, zero figli residui, cache zero nuove chiamate (0,005s), saluto e azione esterna zero inferenze, archivio originale identico negli hash. Tempi 3,250 / 2,638 / 2,427s, picco RSS figlio circa 1,74GiB. È verifica del collegamento, non prova di correttezza decisionale. Zero chiamate a pagamento; rete usata soltanto per ricerca e download espliciti dei candidati, mai durante l'inferenza o dai modelli. Pesi base verificati negli hash dopo LoRA.

La quota massima 1GB dei pesi non è un limite rigido RAM. Il processo termina fra richieste; cache del sistema operativo reclamabile può rimanere. La morte forzata dell'host può lasciare il figlio fino al termine della generazione bounded: l'arresto immediato in quel caso richiede supervisione OS. Limite lettura archivio 32MB/2s: archivi più grandi o cambiati durante la copia causano astensione/errore esplicito. Le quote disco sono soglie di ammissione, non un filesystem con quota rigida. Gli esiti di schema valido non alimentano una presunta misura di verità.

## Artefatti e ripristino

Report, protocollo, dataset congelato, script, raw output, metriche, adattatori, log test e manifest sono raccolti in `validation/decision_study_20261111` su AMBRO. I grandi pesi dei candidati rimangono nella cartella di studio del workspace, con revisioni/hash in `download-plan.json` e `weights-integrity-final.json`; nessun modello sperimentale è configurato come default. La cartella contiene backup dei cinque file modificati e un manifest con hash prima/dopo per gli undici file del runtime. Il ripristino verifica prima che i file correnti corrispondano a quelli distribuiti: se sono cambiati successivamente si arresta, evitando di cancellare lavoro altrui. I file nuovi vengono conservati in una cartella di ritiro, non eliminati. Non è stato eseguito rollback sul repository attivo; il ripristino viene testato su una copia temporanea.

## Roadmap motivata dai risultati

1. Raccogliere con consenso decisioni reali etichettate, budget e risultati verificati; separare progetti e periodi fra train/test, includere italiano e casi ambigui, misurare astensione, calibrazione e costo per decisione corretta. Conservare un nuovo test intatto.
2. Provare prima un piccolo classificatore/encoder locale sul compito, con regole inderogabili per i permessi. Rivalutare FunctionGemma/LFM con quantità di dati adeguata e formato nativo; eventualmente un modello 1–3B se il beneficio misurato giustifica la memoria. Nessuna scelta per sola taglia o leaderboard pubblica.
3. Ampliare self-model e progresso/costo con esiti esterni, deriva del runtime e skill specifiche; confrontare sempre con osservatore esterno a informazione uguale. Personalità come preferenze stabili verificabili, senza modificare autorità.
4. Visione come ingresso opzionale di osservazioni con provenienza, mai promozione automatica a fatti. Moltis come adapter esterno sostituibile con permessi e budget del core, dopo verifica del contratto di integrazione. Nessuna installazione invasiva o dipendenza dall'host.

## Conferma finale dell'installazione

Installazione completata nel repository canonico sul branch `feature/intelligence-feed-runtime`: cinque file preesistenti aggiornati e sei nuovi, hash di distribuzione corrispondenti. Su 173 file di baseline non risultano modifiche inattese; i 13 file protetti di database/laboratorio e codice runner conservano gli hash. Runner PID 32703 ancora attivo; nessun processo di inferenza o addestramento residuo al controllo finale.

Dopo l'installazione: 89 regressioni mirate passate sul codice canonico; unica segnalazione innocua, la cache di pytest non è scrivibile con i permessi della verifica. `git diff --check` riuscito. Ripristino provato sugli undici file in una copia temporanea: ricostruisce gli hash precedenti e ritira i file nuovi; rifiuta file modificati dopo l'installazione. Il repository attivo non è stato ripristinato. Evidenze: `deployment.json`, `integrity-after.json`, `rollback-verification.json`.
