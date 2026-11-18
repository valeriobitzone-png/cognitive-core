# Ciclo cognitivo locale bounded — 10 novembre 2026

Il bridge `cognitive-lab-v1` importa uno snapshot logico del laboratorio in tabelle separate del Vault. Non apre né migra i database sorgente. Legge soltanto i tre JSON noti in `data/ensemble` e Markdown in `obsidian-vault`; nessun percorso AMBRO è incorporato nel runtime.

Ogni batch ha hash, manifest, source name portabile, owner/namespace e stato. Le importazioni identiche sono idempotenti; una revisione supersede il batch attivo dello stesso source name. Il rollback ritira il batch senza cancellarlo né riattivare revisioni precedenti. Reimportare lo stesso batch ritirato non lo riattiva. Per ripristinare uno stato operativo precedente usare uno snapshot esportato, in una home nuova.

I payload originali, le voci escluse e i metadati restano conservati. I JSON originali sono archiviati anche come testo UTF-8, compresi i numeri non finiti; questi ultimi sono rappresentati come marcatori e i record interessati vengono messi in quarantena. Record dichiarati blocked/discarded/excluded/dismissed/rejected vengono esclusi dal recupero operativo. Archivi, metadati, esclusi e quarantena non sono cercati come evidenze operative. Le etichette sperimentali `tested` rimangono dichiarazioni del produttore. OBSERVED indica osservazione del testo/record, SIMULATED una simulazione dichiarata, INFERRED un'ipotesi o relazione: nessuna categoria equivale a verità verificata.

## Uso su una home nuova

Comandi esemplificativi; sostituire i percorsi. Non scegliere una home di produzione per la prima prova.

```sh
cognitive-core --home /tmp/core-lab import-lab /percorso/realtest
cognitive-core --home /tmp/core-lab project linguistica Linguistica '["colexification","CLICS4","clima"]' --importance 1
cognitive-core --home /tmp/core-lab observe '{"kind":"session_end","title":"Ricerca CLICS4 sospesa","question":"Come verificare colexification e clima con fonti indipendenti?"}'
cognitive-core --home /tmp/core-lab cycle-run --ticks 12
cognitive-core --home /tmp/core-lab export /tmp/core-export-nuovo
```

`cycle` esegue una fase; `cycle-run` seleziona automaticamente i topic aperti in ordine di importanza, per un numero finito di tick e tempo. Questi comandi e `daemon` scelgono authority autonomous per default. Il daemon preesistente ora visita anche il ciclo locale; non viene installato o avviato automaticamente. CTRL+C arresta il processo. `pause` e `discard` bloccano la prosecuzione del topic, anche tra due fasi. Un progetto semplicemente incompiuto può alimentare un evento `session_end`; una pausa esplicita richiede invece una ripresa interactive.

Il ciclo riusa CognitiveDrive e WHAT IF WorldCore:

1. Gap aperto → stimolo deduplicato → Opportunity Pool, soltanto con un progetto configurato dall'operatore.
2. Ricerca unificata di Vault, memorie WorldCore, knowledge chunks e bridge.
3. Confronto WHAT IF locale fra registrare una nota e attendere. Non inventa punteggi: la scelta semantica resta in astensione.
4. La policy consente esclusivamente la raccolta locale reversibile di evidenze, senza autorizzare azioni esterne.
5. Nota con estratti/provenienza → ledger → checkpoint con osservazione della persistenza e numero di fonti. Non modifica pesi del modello né dichiara utilità o verità.

Ogni fase e i relativi effetti sul Vault condividono una transazione. Il risultato WHAT IF è incorporato nel checkpoint e nello snapshot portabile; non crea una seconda scrittura in `whatif_runs`. I job web preesistenti conservano il proprio stato/checkpoint: completare una nota locale non dichiara completata una ricerca web sospesa. Le fonti bridge ritirate prima dell'azione fanno astenere il ciclo. Le note già completate rimangono documenti storici; non vengono usate dal ciclo per autocitarsi.

## Autorità e limiti

`Settings.execution_mode` appartiene all'host, non ai payload o ai documenti. Autonomous nega import/rollback, ripresa di topic, export, creazione di progetti, claim con evidenze e outcome riferiti dall'operatore. Il worker JSONL applica un allowlist di operazioni autonomous prima del dispatch WorldCore. CLI e API core applicano controlli coerenti; le primitive Python/SQLite restano parte dell'host fidato, non una sandbox per codice ostile.

Web rimane disabilitato per default. In modalità autonomous occorrono separatamente `enable_web=True` e `autonomous_web_opt_in=True` (CLI: `--web --autonomous-web-opt-in`), allowlist HTTPS e quote. La policy è controllata sia dal governor sia da Researcher, prima della rete. La ricerca web opt-in usa il worker già esistente; il ciclo locale non attiva la rete automaticamente quando mancano evidenze. Nessun client API a pagamento è implementato; configurarne il permesso produce errore.

Quote: file, byte, record d'importazione; fonti e tick giornalieri del ciclo; richieste HTTP giornaliere/per-job; controllo cooperativo del tempo e ammissione conservativa dello spazio per Vault, WAL e WorldCore. Le quote del disco non limitano processi esterni e i timeout cooperativi non sono hard real-time. Un host non fidato richiede isolamento OS. La lettura dei file live non è una transazione globale sul laboratorio: il manifest certifica i byte acquisiti di ciascun file, non un istante unico del runner.

Ogni nota importata viene esportata anche come file Markdown autonomo, con testo originale e front matter di provenienza/stato del batch (compreso il ritiro). Export Markdown/JSON e snapshot comprendono batch, record, checkpoint, Opportunity Pool e ledger. I vecchi snapshot state-v1 privi delle sole tre tabelle aggiunte sono ancora accettati; le altre difformità di schema rimangono rifiutate. Il ripristino conserva dati, revoca grant e lease e mantiene rete/modelli disabilitati. Hash non significa autenticazione; gli export sono in chiaro.

Restano aperti: verifica semantica indipendente delle conclusioni; misure di utilità con outcome reali; decision model locale valutato e sostituibile; visione con prove e permessi; adattatore Moltis senza dipendenza del core dal runtime; cifratura/autenticazione degli snapshot; isolamento OS e hard quota. Nessun connettore live o provider a pagamento è certificato da queste prove.
