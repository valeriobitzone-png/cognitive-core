# Rapporto — Assistente Personale 0.3 / box di allineamento

14 novembre 2026. Installazione locale su AMBRO, Core 1.4.0rc5. Nessun commit o cambio di branch.

## Esito e limite principale

Le box sono operative: generazione di geometria e composizione, controlli del codice, prova nel browser, revisione limitata, verifica su casi separati, anteprima, giudizio visivo e conservazione della versione. Il corpo e la composizione sono nuovo HTML/CSS/SVG, non soltanto parametri dentro forme predefinite. La schermata iniziale Vela è stata scritta dall’assistente di sviluppo ed è attribuita esplicitamente. Non è una scelta autonoma del piccolo modello locale.

Le generazioni locali hanno prodotto anche codice utilizzabile, ma la qualità artistica osservata resta insufficiente: curve disconnesse, simboli o composizioni povere. Questi esiti non sono presentati come un’autorepresentazione riuscita. Una prova tecnica riuscita resta una proposta da guardare e confermare o scartare; il feedback viene conservato per il ciclo successivo. Nessun addestramento dei pesi, coscienza o introspezione delle attivazioni è stato dimostrato.

## Prima e dopo

| Prima (0.2) | Dopo (0.3) |
|---|---|
| Corpo parametrico e composizioni limitate | Codice HTML/CSS/SVG generabile liberamente entro una grammatica sicura |
| Generazione e uso diretto della scelta | Box separate per geometria/composizione, revisione e casi finali separati |
| Nessuna misura reale di resa del nuovo codice | Chrome temporaneo: viewport, testo effettivo, geometria visibile, movimento ridotto, richieste esterne ed errori |
| Esito del modello assimilabile a forma scelta | Proposta visibile, conferma/scarto, feedback, storico e ripristino |
| Inferenza sempre sulle impostazioni CPU precedenti | Opzione host esplicita per GPU/thread; default Core invariato |
| Una sola istruzione generica per i modelli | Ruoli configurabili dall’host, senza nuove autorità o strumenti al modello |

## Prove locali dei modelli

| Modello/prova | Risultato osservato |
|---|---|
| LFM2.5 1.2B | 8,63 s; markup non valido, nessun corpo SVG utilizzabile |
| Rizzo 4B, compito completo | Timeout di 60 s; scartato |
| Qwen 3.5 0.8B presente | Errore del motore locale (ValueError); nessuna compatibilità dichiarata |
| Qwen2.5-Coder 1.5B Q4_K_M | Echo/copia del riferimento; copie respinte |
| Qwen2.5-Coder 7B Q3_K_M, compito completo | Vari tentativi incompleti o timeout; un risultato tecnicamente valido era una scheda/logo ed è stato respinto nella revisione visiva |
| 7B, due compiti separati | Geometria 29,45 s + composizione 18,55 s; controlli desktop/telefono superati, ma risultato visivo frammentario |
| Rizzo 4B, sola geometria | 43,71 s, testo troncato/ripetitivo; non adottato |
| 7B, percorso integrato con revisione | Proposta e prove finali prodotte; esito funzionale positivo, qualità visiva ancora insufficiente |

Il 7B è installato soltanto come autore **sperimentale**, non come modello decisionale né come vincitore di una classifica generale. È distinto dal Rizzo già configurato per il dialogo. I confronti sono osservazioni su questi compiti e questo Mac, non benchmark scientifici omogenei o prove di superiorità. Nessuna API a pagamento. Nessun modello residente. Le prove attivavano esplicitamente il modello soltanto nei propri archivi temporanei.

Provenienza dei pesi: [repository ufficiale Qwen](https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF), revisione `13fb94bfda8c8cf22497dc57b78f391a9acb426a`, licenza dichiarata Apache-2.0. Quantizzazione Q3_K_M, 3.808.391.104 byte. SHA-256 `ff5c64615cf8a44651d208e9d8da1f753feefc21605e6c1ee67957aa77257c3c`. Profilo in `/Volumes/AMBRO/models/assistant-authoring/PROVENANCE.json`. Nessun peso preesistente sovrascritto. Il 1.5B provato resta nell’area temporanea e non viene configurato sull’installazione.

## Verifiche

- Python: **773 passati, 2 saltati**, suite completa sulle copie; i due skip preesistenti richiedono Playwright/Xvfb. Le nuove prove browser sono state eseguite con Chrome reale.
- Interfaccia reale: **11 controlli** (anche sull’installazione), saluto del Core senza LLM, isolamento fra pagine, injection trattata come testo, token assente nella scena, messaggi da mittente falso ignorati, pausa effettiva, desktop/telefono, avvio e annullamento delle box, stop/ripresa e modello spento al reload, nessuna richiesta esterna o eccezione JavaScript.
- Proposta e feedback: **4 controlli browser aggiuntivi** con fixture dichiarata, nessuna falsa attribuzione neurale; prova tecnica → anteprima → conservazione → persistenza.
- 24 verifiche Node storiche mantenute: 5 sulla geometria parametrica, 7 sul bridge grafico e 12 sugli adattatori Core. I processi figli usano la copia del Core tramite configurazione esplicita del test.
- Arresto forzato del processo padre e riavvio: fixture in processo reale, modello spento, annullamento riconosciuto, nessuna adozione tardiva, lease rilasciata. La fixture non misura qualità neurale.
- Regressioni per codice attivo/rete/CSS, binding falsi e quote, copia e sola ricolorazione, doppia serializzazione, campi sconosciuti, scope/permessi, quota concorrente, esiti falsi senza prova separata, approvazione/scarto, duplicati, export/restore e rollback.
- Wheel separate installate e provate con Python **3.11.15** e **3.12.13**; risorse del renderer e riferimento incluse; saluto senza modello e default spento verificati. Corrispondenza byte per byte fra wheel e sorgenti testati.
- Ripristino provato su copie nello stesso filesystem; modifica successiva intenzionale correttamente protetta dal rollback.

Le prime esecuzioni della copia completa hanno segnalato fixture mancanti (cataloghi/adattatori/benchmark) e una differenza di versione fra processo figlio canonico e copia. Le fixture sono state copiate e la suite finale è stata eseguita tutta nella copia coerente: nessun errore residuo. Questi fallimenti preliminari non sono conteggiati come regressioni risolte del prodotto.

## Preservazione e separazione

- Confrontati gli hash iniziali dei sorgenti: nessuna modifica concorrente prima dell’installazione. Conservate le modifiche preesistenti, comprese retrieval unificato, snapshot/restore, continuità dei job e citazioni letterali.
- **13 hash protetti invariati**: sei database originali e sette file del runner. Archivio dell’assistente e archivio del programma Core invariati durante installazione e verifiche; nessuna prova sull’archivio personale. Il runner statistico originale è stato lasciato attivo.
- Test e generazioni su copie e archivi temporanei. Nessun avvio del runner, nessun suo arresto o sovrascrittura.
- Codice grafico, feedback e box restano nell’Assistente Personale. Il Core riceve soltanto supporto generico di host per ruolo e hardware del modello. Nessun import dall’assistente nel Core.
- Otto metadati generati dalla compilazione sono stati ritirati/ripristinati: non sono lasciati come modifiche aggiuntive ai sorgenti canonici.

## File installati

### Assistente Personale

- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/teaching_reference.json`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/atelier.py`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/artifact.py`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/webserver.py`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/assistant.py`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/atelier_worker.py`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/box_eval.cjs`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/web/index.html`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/web/app.css`
- `/Volumes/AMBRO/projects/AssistentePersonale/src/personal_assistant/web/app.js`
- `/Volumes/AMBRO/projects/AssistentePersonale/tests/test_atelier.py`
- `/Volumes/AMBRO/projects/AssistentePersonale/tests/test_web.py`
- `/Volumes/AMBRO/projects/AssistentePersonale/pyproject.toml`
- `/Volumes/AMBRO/projects/AssistentePersonale/host-modello.json`
- `/Volumes/AMBRO/projects/AssistentePersonale/LEGGIMI_IT.md`
- `/Volumes/AMBRO/projects/AssistentePersonale/ALLENAMENTO_BOX_V03_IT.md`

- `/Volumes/AMBRO/projects/AssistentePersonale/pacchetti/STATO_VERSIONI_IT.md`

### Cognitive Core

- `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/runtime/src/cognitive_core/config.py`
- `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/runtime/src/cognitive_core/models.py`
- `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/runtime/src/cognitive_core/__init__.py`
- `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/runtime/src/cognitive_core/ondemand.py`
- `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/runtime/src/worldcore/__init__.py`
- `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/runtime/tests/test_model_host_tasks.py`
- `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/runtime/pyproject.toml`

## Backup e ripristino

Backup app: `/Volumes/AMBRO/projects/AssistentePersonale/validation/alignment_boxes_20261114`. Backup Core: `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/validation/model_host_tasks_20261114`. Ciascuno contiene `deployment.json`, `before/`, `rollback.py` e la prova del ripristino. Lo script rifiuta di sovrascrivere modifiche successive all’installazione. Ripristina i due componenti insieme, con le rispettive radici indicate nei manifest. Il modello aggiuntivo resta come file inutilizzato dopo il rollback; nessun archivio dati viene ripristinato o cancellato.

## Limiti aperti e roadmap

1. Qualità artistica locale: serve un benchmark su compiti di autorappresentazione, con confronti visivi e costo/tempo misurati. Il piccolo modello non è ancora autonomamente all’altezza dello studio iniziale. Un controllo geometrico non sostituisce un giudizio visivo.
2. Dialogo: la precedente chiamata di risposta è ancora sincrona. Lo stop durante una risposta viene servito alla sua conclusione, entro 60 s; le box invece sono annullabili durante l’inferenza. Va reso asincrono anche quel percorso prima di chiamarlo arresto immediato generale.
3. Giudizio di qualità: oggi il modello sceglie/genera la proposta, mentre la conservazione richiede feedback visivo. Non è completata una crescita estetica autonoma longitudinale. Il riesame neurale disponibile legge codice, non immagini.
4. Modello decisionale locale: mantenere distinto dall’autore grafico e rivalutarlo con compiti decisionali reali, astensione e costo longitudinale; non promuovere il Coder 7B a decisore. La matrice fattoriale completa e D longitudinale restano lavoro separato, non dichiarati conclusi qui.
5. Visione e voce: futuri connettori espliciti, con consenso per singola fonte, budget e prove dedicate. Nessun sensore è stato attivato da questa fase.
6. Moltis: adapter verso il contratto pubblico del Core, con contesti e permessi separati; nessuna fusione dei database o dipendenza obbligatoria dal suo runtime.
7. Risorse: dopo molti allenamenti il laboratorio può raggiungere il tetto di disco; manca ancora un’interfaccia guidata per esportare/archiviare le vecchie prove. Nessuna pulizia distruttiva automatica.

Il pacchetto di prova è utilizzabile offline per la scena e il dialogo senza modello; non include i pesi o i dati personali. Per allenare su un altro computer occorre configurare un modello e gli strumenti locali di verifica.

## Consegna e controllo finale

Pacchetto: `/Volumes/AMBRO/projects/AssistentePersonale/pacchetti/Assistente_Personale_Atelier_0.3_2026-11-14.zip`, 862.958 byte; SHA-256 `fd9cff17db41f500c98ef52a79fcfab5b702244729dfa5bd5bcf9027052b2f9b`. ZIP estratto e provato nel browser: 11 controlli, nessun download o inferenza senza modello configurato. Il pacchetto non include pesi, dati o percorsi del proprietario nella configurazione. Il lanciatore canonico è stato avviato con un home temporaneo: modello spento, nessun archivio creato dal semplice avvio.

Rapporto salvato in `AssistentePersonale/docs/REPORT_BOX_V03_20261114_IT.md`. Evidenze, screenshot, log e manifest sono nella cartella di validazione `alignment_boxes_20261114`; prova finale in `post-install-check.json`. Oltre ai 23 file funzionali/di guida installati sono stati aggiornati il registro del pacchetto e creati ZIP, rapporto ed evidenze. Nessun dato originale è incluso in questi prodotti.

Il controllo finale conferma: hash dei file installati, tutti gli altri file della baseline invariati, entrambi gli archivi applicativi invariati, 13 hash protetti invariati, runner originale PID 32703 attivo, branch conservato e `git diff --check` pulito.
