# Correzioni dell’audit SSD — 10 novembre 2026

Correzioni locali della working tree 1.4.0rc3; non è un rilascio pubblicato.

- `CognitiveCore.memory_search` alterna documenti Vault, memorie WorldCore e knowledge chunks, conservando URL, hash, licenza e scope del risultato.
- `resume(topic)` riutilizza il job bloccato, oppure cancellato dalla pausa del topic. Checkpoint, fonti, tentativi e quote sono preservati. Non sostituisce le fonti di un job incompleto; una modifica richiede un nuovo lavoro esplicito. I lease precedenti restano revocati. I limiti di tentativi/richieste non vengono azzerati dalla ripresa.
- `Vault.add_evidence` richiede un estratto non vuoto, massimo 1500 caratteri, presente letteralmente nel documento. `remember_claim` è atomico: nessun claim orfano se l’evidenza viene rifiutata. L’ancoraggio letterale non prova il supporto semantico né la verità della fonte. Gli archivi storici non vengono riscritti o riclassificati automaticamente.
- `Vault.export_markdown` include tutte le tabelle del namespace, compreso il pool. L’export completo del core aggiunge un `state.json` versionato con entrambi gli archivi e checksum. I dati di altri owner/namespace sono esclusi.

## Export e ripristino

Da un ambiente dove il package è disponibile:

```sh
cognitive-core --home /percorso/dati --owner alice --namespace work export /percorso/export-nuovo
cognitive-core --home /percorso/ripristino-nuovo restore /percorso/export-nuovo
```

Le due cartelle di destinazione devono essere nuove. La pubblicazione della cartella avviene solo dopo il completamento: in caso di errore non viene lasciato un ripristino parziale. Il ripristino usa owner/namespace dell’export; non importa configurazioni di rete, modelli o credenziali. Il runtime deve avere lo stesso schema dello snapshot. Gli indici testuali vengono ricostruiti dai dati originali.

I job running tornano pending, senza lease. Le approvazioni pending/approved diventano denied: il trasferimento conserva lo storico, ma non concede permessi di esecuzione. Quote, tentativi, checkpoint e risultati restano conservati. I job blocked restano blocked e richiedono una ripresa esplicita.

Lo snapshot contiene dati privati locali in chiaro. Il checksum rileva alterazioni accidentali, non autentica l’autore e non verifica le affermazioni contenute. La funzione è un’operazione esplicita dell’operatore; non è esposta al worker/MCP come strumento del modello. `Vault.export_markdown` da solo non esporta WorldCore: usare `core.export_state` o la CLI per il trasferimento completo.

## Verifiche

Le regressioni sono in `tests/test_audit_regressions.py`: tre store, provenienza, isolamento, ripresa blocked/paused, quote e lease, citazioni false/vuote/troppo lunghe, conflitti, export del pool, roundtrip dei record e degli indici, revoca delle approvazioni, checksum, record di scope estraneo, mancata sovrascrittura e CLI.

Queste correzioni non completano la roadmap dell’audit: ciclo cognitivo autonomo generale, sandbox OS, modelli semantici locali e integrazione Moltis restano attività separate.
