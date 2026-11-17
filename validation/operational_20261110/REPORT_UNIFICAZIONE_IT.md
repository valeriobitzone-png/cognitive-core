# COGNITIVE CORE — integrazione operativa bounded

10 novembre 2026. Intervento eseguito sul Mac e sull’SSD AMBRO.

Implementata e verificata una prima integrazione operativa locale: laboratorio sperimentale → recupero unificato → curiosità → Opportunity Pool → ricerca locale → WHAT IF → decisione limitata dalla policy → nota/evidenza → ledger → checkpoint. Il codice è nel repository canonico, sul branch `feature/intelligence-feed-runtime`, senza commit o pubblicazioni. L’archivio dimostrativo è nuovo e isolato: nessuna migrazione dei database di produzione, nessuna sostituzione del runner statistico.

Questo risultato non certifica un agente capace di decidere semanticamente, verificare la verità delle fonti o imparare nuove leggi del mondo senza supervisione. Queste capacità restano esplicitamente nella roadmap.

## Stato prima e dopo

| Area | Prima dell’intervento | Dopo l’intervento |
|---|---|---|
| Dati realtest | Grafo, coda e note separati dal recupero operativo | Bridge `cognitive-lab-v1`, versionato, idempotente, con manifest/hash e isolamento owner/namespace |
| Stato epistemico | Etichette sperimentali, incluse dichiarazioni `tested` | Payload originale preservato; OBSERVED/SIMULATED/INFERRED distinti dalla verità verificata |
| Fonti ritirate o invalide | Dati eterogenei presenti nel laboratorio | Esclusi e quarantena conservati, ma esclusi dal recupero operativo |
| Curiosity/Opportunity Pool | Feed e preparazione soprattutto orientati a URL | Collegamento da topic aperti a opportunità e ricerca locale, senza modello o rete |
| WHAT IF | Backend già esistente e testato | Usato nel ciclo; risultato conservato atomicamente nel checkpoint senza creare una seconda transazione sul ledger WorldCore |
| Azioni autonome | Distinzione interactive/autonomous non obbligatoria nelle nuove operazioni | Autorità configurata dall’host, controlli nei metodi core, CLI e allowlist del worker JSONL |
| Ripresa | Job web con checkpoint e lease già corretti | Anche le sei fasi locali persistono e riprendono dopo arresto forzato; nessuna duplicazione di nota/ledger |
| Apprendimento | Ledger e strumenti distinti | Osservazione persistente del risultato dell’azione locale; nessuna promozione a fatto o modifica automatica dei pesi |
| Portabilità | Snapshot completo e Markdown già corretti | Anche record sperimentali/checkpoint esportati; 242 note originali esportabili come Markdown con provenienza e stato del batch |

Le quattro correzioni del 10 novembre sono conservate: retrieval Vault/WorldCore/knowledge, snapshot/restore, continuità dei job sospesi/bloccati e ancoraggio letterale delle citazioni. Le relative 19 regressioni passano anche direttamente dal codice su AMBRO. I file WorldCore preesistenti, compresi quelli non committati, non sono stati modificati.

## Inventario e preservazione

Il primo accesso è stato in sola lettura. Salvati stato Git, patch delle modifiche già presenti, inventario SHA-256 del repository e dei dati, copia di lavoro del runtime, copie dei tre JSON principali e delle note. Prima dell’applicazione sono stati aggiunti hash dei database `.db` nella radice di realtest e dei file del runner; nessuna connessione SQLite è stata aperta sui database originali. Il loro hash grezzo non è presentato come backup transazionale.

Confronto finale: **726 file protetti controllati**, otto modifiche preesistenti aggiornate intenzionalmente, **zero variazioni inattese**. Hash dei dati sorgente e dei database originali invariati. Anche la wheel precedente delle correzioni è conservata.

Il runner preesistente è stato verificato tramite processo e LaunchAgent: **PID 32703, `runner.py --loop`, stato running**, medesimo processo dell’audit. Non è stato fermato, ricaricato, reinstallato o collegato al nuovo scheduler. Le sue quote restano separate da quelle del core.

Artefatti di preservazione: `inventory-before.json`, `protected-before-deploy.json`, `git-status-before.txt`, `preexisting.patch`, `backup-ssd-originals/`, `source-snapshot/`, `verification-final.json`.

## Importazione dei dati reali

Sorgente inventariata: `/Volumes/AMBRO/projects/CognitiveCore/realtest`. Le prove usano una copia dei file e una home nuova. Il runtime accetta il percorso dall’operatore e non incorpora percorsi AMBRO o dipendenze da questo Mac.

Importati **1.695 record**, da 2.665.537 byte acquisiti:

| Tipo | Record |
|---|---:|
| Nodi | 240 |
| Archi recuperabili | 887 |
| Ipotesi in coda | 262 |
| Note Markdown | 242 |
| Esclusi | 53 |
| Quarantena | 5 |
| Archivi JSON originali come testo | 3 |
| Metadati | 3 |

I 924 archi originari si riconciliano come 887 recuperabili + 32 esclusi dal produttore + 5 con valori numerici non finiti. Gli altri 21 esclusi provengono dalla lista storica delle ipotesi già superate. Nessun record viene cancellato dalla sorgente o perso dall’archivio importato. I JSON originali sono conservati anche come testo esatto, compresi i `NaN`; gli oggetti strutturati usano marcatori per i valori non finiti.

Le note sono osservazioni del testo acquisito, non fatti certificati. Relazioni/ipotesi non vengono addestrate automaticamente nel modello dinamico WorldCore né convertite in memorie fattuali. Il recupero restituisce ID, batch, hash, provenienza e stato epistemico; non segue URL presenti nei payload.

Un’importazione identica non duplica record. Una revisione dello stesso source name supersede la precedente. Il rollback ritira il batch senza cancellarne la storia né riattivare automaticamente revisioni precedenti; reimportare lo stesso snapshot ritirato non lo riabilita. L’importazione è atomica sul Vault: errore, quota o kill non pubblicano un batch parziale. Il manifest documenta i byte acquisiti per ciascun file; non pretende una transazione simultanea sul laboratorio live.

## Prova end-to-end su AMBRO

Home isolata:

`/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/validation/operational_20261110/isolated-home`

Owner `ambrogio`, namespace `realtest-bridge`. È stata ripresa, in questo archivio di prova, la prima ipotesi reale della coda su CLICS4/clima e verificabilità delle fonti. Un evento di sessione sospesa ha creato il topic; la ripresa interactive lo ha riaperto. Il job web è stato bloccato dalla policy perché la rete era disabilitata. Il ciclo locale ha poi attraversato autonomamente sei fasi, chiudendo e riaprendo il runtime tra una fase e l’altra:

`research → whatif → decide → act → learn → done`

Risultato: cinque riferimenti recuperati, una nota locale persistente e un’esperienza nel ledger. Il checkpoint registra hash della nota e conteggio delle fonti, con `truth_updates=0`, `model_weight_updates=0`, `usefulness=unverified`. Lo stato e il checkpoint del job web bloccato restano identici: la nota locale non si spaccia per completamento della ricerca web.

WHAT IF confronta registrare una nota con attendere, senza inventare punteggi o utilità. Mantiene l’astensione del backend sulle scelte semantiche. La policy consente soltanto l’azione reversibile di raccogliere materiale locale; non trasforma la simulazione in autorizzazione ad azioni esterne.

Il percorso completo è stato esportato e ripristinato in una seconda home. Il rollback del bridge è stato verificato su questa copia ripristinata. L’export finale comprende **243 documenti Markdown: 242 note originali e una nota del ciclo**, oltre ai JSON e allo snapshot completo:

`/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/validation/operational_20261110/portable-export-markdown`

## Autorità, arresto e budget

- L’host sceglie `Settings.execution_mode`; i payload e i testi importati non possono elevarlo. CLI `cycle`, `cycle-run` e `daemon` usano autonomous per default. Il worker JSONL autonomo ammette soltanto un elenco esplicito di operazioni.
- Autonomous non può importare/ritirare batch, riaprire topic, esportare stato, creare progetti, registrare claim con evidenze o simulare feedback dell’operatore. Può raccogliere e registrare evidenze locali entro il ciclo ammesso.
- Una pausa esplicita, un discard o la chiusura del topic fermano la prosecuzione. Un’opportunità dismiss non viene riattivata implicitamente. L’assenza di contesto progettuale o evidenze porta ad astensione. Un batch ritirato prima dell’azione impedisce il salvataggio della nuova nota.
- Saluti: zero chiamate a modelli/rete e nessuna creazione del database. API a pagamento: nessun client implementato e permesso rifiutato dalla configurazione.
- Rete disabilitata per default; autonomous richiede anche il distinto opt-in dell’host, oltre ad allowlist e quote del worker preesistente. Verifica web effettuata soltanto con risposte simulate: **zero richieste web reali e zero chiamate a pagamento**.
- Default nuovi: 16 MB/1.000 file/10.000 record per importazione, cinque fonti per fase di ricerca, 100 tick al giorno, controllo cooperativo di dieci secondi, ammissione conservativa di 128 MB per gli archivi del runtime. Restano le quote HTTP per giorno/job e i timeout delle richieste.

Questi controlli sono confini del runtime per un host fidato. Non isolano codice Python ostile, non impongono quote OS ad altri processi e non costituiscono scadenze hard real-time. Le API Python interne e l’accesso diretto a SQLite richiedono fiducia nell’host. Le note completate prima di un ritiro restano documenti storici; il ciclo evita di autocitarle come nuove fonti.

## Verifiche

**510 test Python superati, due saltati; 12 test Node superati. Supervisore: 48/48 gruppi**, incluso self-test del timeout. I due skip riguardano Chromium/Playwright e desktop/Xvfb indisponibili.

**32 nuove regressioni**: import e revisioni, duplicati, scope owner/namespace, payload non fidati e fonti false, dati esclusi e non finiti, quote file/byte/record/disco/tempo, rollback, symlink/leakage, astensione, pause/discard, limiti di autorità, rete opt-in simulata, saluti senza LLM, ciclo e portabilità, compatibilità con snapshot precedenti, Markdown con ritiro esplicito, concorrenza e kill/restart.

Il processo di test è stato ucciso con SIGKILL durante ciascuna delle sei fasi e durante l’importazione: rollback atomico e ripresa senza note o esperienze duplicate. I tick concorrenti non duplicano l’azione. Le 32 regressioni nuove e le 19 precedenti sono state eseguite anche sul codice canonico SSD.

I log conservano anche i fallimenti intermedi: una regressione ha evidenziato una differenza nel messaggio di blocco del daemon; è stata corretta la precedenza della diagnosi senza indebolire il test esistente. Non sono stati modificati o rimossi test preesistenti in questa fase.

Wheel costruita offline, senza installazioni né pubblicazioni. **57 file Python** confrontati con la wheel, nessuna differenza; smoke test con `-I -S -B`, senza dipendenze opzionali, su Python **3.11 e 3.12**: saluto, bridge, ciclo, restart, export/restore e rollback superati.

Wheel finale:

`/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/runtime/dist/operational-20261110-final/worldcore_cognitive_layer-1.4.0rc3-py3-none-any.whl`

SHA-256: `9e1a4c3512e08997c01e7c99e2687656a6ddabb7636720986e432407ccd5f390`.

La versione di metadata resta `1.4.0rc3`: identificare questa build tramite percorso e hash, senza confonderla con le wheel precedenti. Nessun pacchetto è stato installato nel runner.

`git diff --check` superato. La patch inversa è stata applicata a una copia temporanea: ripristino esatto degli otto file originali e rimozione dei quattro file aggiunti, senza intervenire sul repository reale. Non usare un reset globale: distruggerebbe anche le modifiche preesistenti.

Evidenze: `tests-release.json`, `tests-release_logs/`, `ssd-regressions-final.log`, `wheel-verification.json`, `wheel-python311.log`, `rollback-verification.json`, `ssd-cycle-verification.json`, `verification-final.json`.

## File modificati

Otto file esistenti, tutti sotto `runtime/src/cognitive_core/`:

- `config.py`: authority e quote.
- `engine.py`: bridge, retrieval aggiuntivo, tick, controlli interactive e rete autonoma.
- `drive.py`: protezione delle operazioni dell’operatore.
- `research.py`: opt-in separato prima della rete.
- `worker.py`: allowlist autonomous e dispatch del ciclo.
- `cli.py`: comandi bridge/ciclo e scheduler.
- `vault.py`: tre nuove tabelle additive ed export Markdown delle note.
- `portable.py`: ripristino dei precedenti snapshot senza le sole tre nuove tabelle opzionali.

Quattro file nuovi: `experimental.py`, `cycle.py`, `runtime/tests/test_operational_cycle.py`, `runtime/docs/OPERATIONAL_LOOP_IT.md`. Elenco completo con hash prima/dopo in `changes.json`; patch limitata a questa fase in `operational.patch`.

## Limiti e roadmap

1. **Modello decisionale locale.** Sostituire gradualmente il ranking lessicale con un classificatore locale valutato su esempi revisionati. Misurare falsi trigger, astensione e utilità su holdout. Il modello propone; capability, quote e stop restano nel runtime. Nessun addestramento automatico su ipotesi non verificate.
2. **Verifica e learning.** Aggiungere verificatori indipendenti e outcome osservabili per affermazioni, utilità e previsioni; collegarli alla calibrazione WorldCore senza convertire correlazioni/simulazioni in causalità. Il learning attuale riguarda l’esito meccanico della raccolta, non nuove conoscenze certificate.
3. **Web end-to-end.** Certificare separatamente discovery e raccolta opt-in con fonti reali, budget e supervisione OS. Il percorso qui certificato è locale; la parte web è provata con fixture.
4. **Visione.** Introdurre acquisizione opt-in, provenance di immagini/OCR e valutazione di un modello locale. URL/alt o descrizioni generate non sono evidenze visive verificate. Browser/desktop richiedono un ambiente di test adatto.
5. **Moltis.** Adapter sottile sopra protocollo JSONL e API dati, con binding dell’identità e delle capability all’avvio. Il core, gli export e i checkpoint devono restare indipendenti dal runtime e dal modello. Nessun adapter Moltis live è stato installato o certificato.
6. **Protezione dei dati e isolamento.** Autenticazione/cifratura degli snapshot, autenticazione dei processi locali, quote e deadline OS. Gli snapshot attuali sono in chiaro e gli hash non autenticano l’autore. La copertura del governor non si estende al runner statistico separato.

Non è stato attivato un nuovo servizio persistente sul Mac. Il nuovo scheduler è disponibile nel codice; l’archivio isolato e l’export consentono di valutare il risultato prima di una futura migrazione o attivazione di produzione.
