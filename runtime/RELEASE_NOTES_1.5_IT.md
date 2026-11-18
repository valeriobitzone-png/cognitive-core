# Cognitive Core 1.5.0 — note di rilascio (18 novembre 2026)

Unisce il ramo `pa/cuore-v2` a `main`. Parte da 1.4.0rc5. Il ramo nasce per il Personal Agent di Valerio, dove il Core è l'unica fonte di verità per fatti, preferenze, persone, promesse, job, previsioni e approvazioni di azioni.

## Cosa c'è di nuovo

**Memoria e richiamo**
- Richiamo in italiano: parole vuote e interrogative escluse, ricerca per radice («preventivi» trova «preventivo»), peso al soggetto della chiave.
- Richiamo per significato, opzionale: l'embedder lo fornisce l'host (nessuna dipendenza nuova), con vettori dei fatti, recupero dei vettori mancanti e fusione con il lessico.
- `WorldCore.facts(owner, prefisso)`: fatti attivi per prefisso di chiave, per intervallo (nessun carattere jolly). Il prefisso vuoto o oltre 200 caratteri è rifiutato.

**Decisione**
- Riflesso decisionale sui messaggi: segnali dichiarati per impegni e scadenze, problemi, opportunità e azioni esterne (le azioni esterne chiedono sempre approvazione), e compiti dell'assistente.

**Attività programmate**
- `schedule`, `schedules`, `lease_due`, `complete_schedule`, `cancel_schedule`: orario, ricorrenza, lease; il programma vive nel Core, la consegna all'host.

**Previsioni e WHAT IF**
- WHAT IF su uno stato fornito dal chiamante (`simulate` / `compare_futures` con `state=`) ed elenco delle previsioni (`list_forecasts`).

**Affidabilità**
- Versione dello schema in `schema_meta.schema_version` (oggi 1). Un database senza versione la riceve all'apertura, senza toccare i dati; un database scritto da un motore con versione più alta non si apre (`WorldCoreError`).
- Connessione SQLite condivisa tra thread resa sicura (`_LockedDB`): ogni istruzione e la lettura delle sue righe girano sotto il lucchetto rientrante del motore. Prima, letture e scritture in parallelo dall'host davano `sqlite3.InterfaceError: bad parameter or other API misuse`. Il test `test_concurrent_reads.py` fallisce col motore precedente e passa con questo.
- Stato 1.4.0rc5 incluso: curiosità, ciclo operativo, memoria, programma unico, self-model.

**Manutenzione**
- 68 file di `runtime/src` riscritti in forma leggibile (una istruzione per riga, black -l 200 -S), senza cambiare comportamento: la suite è identica prima e dopo.

## Compatibilità

- Non ho confrontato l'API pubblica tra 1.4.0rc5 e 1.5.0 elemento per elemento: non posso dire che non ne sia stata rimossa nessuna. Le aggiunte sono quelle elencate sopra.
- Un database creato prima di 1.5.0 si apre senza interventi e riceve la versione 1.
- Riaprire con un motore precedente un database già aperto con 1.5.0 non è stato provato (la riga `schema_version` in `schema_meta` dovrebbe essere ignorata, ma è un'aspettativa).

## Verifiche

- Suite del Core (`runtime/tests`): 738 passati, 3 falliti (moduli opzionali mancanti, vedi sotto), 4 saltati. Suite del Personal Agent con questo Core: 264 passati.
- Prova di concorrenza con il Personal Agent (server reale + processo notturno + 4 client, 600 richieste dalle app e 1.991 scritture notturne): 0 errori, 0 scritture perse (1.991 trovate nel Core), `integrity_check` ok.
- Backup e ripristino su una copia dei dati reali, anche con il server acceso: integrità ok, conteggi uguali.

## Limiti noti

- 3 test falliscono perché mancano moduli opzionali (benchmark: numpy/scikit-learn/OpenCV): `test_v08::test_macro_artifact_equivalent_to_sklearn`, `test_v09::test_digits_heldout_and_runtime_equal`, `test_v09::test_real_video_decoder_motion`. Non toccano il codice di questo rilascio.
- Il pacchetto non è stato ricostruito né pubblicato (nessuna wheel nuova in `dist/`); la versione cambia nei sorgenti e nel `pyproject.toml`.
- Le migrazioni dello schema sono provate con migrazioni di prova: esiste solo la versione 1.
