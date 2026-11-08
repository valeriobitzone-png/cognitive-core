# WorldCore 1.3.0rc2 — apprendimento sui dati, codice stabile

31 ottobre 2026. Candidato tecnico locale, non versione definitivamente esente da manutenzione. Nessuna pubblicazione o modifica di licenza: resta Apache-2.0 in attesa della decisione rinviata.

## Decisione sul requisito

L'utente ha precisato prima «solo memoria, modelli e procedure; codice stabile», poi ha aperto anche al codice «se è meglio». La scelta tecnica di questa versione è mantenere stabile il codice durante il funzionamento e automatizzare l'adattamento dei dati. Non è stato attivato un sistema che riscrive o distribuisce il proprio codice. La bozza iniziale di un supervisore di autoriparazione del codice è stata eliminata senza eseguirla o integrarla.

Le modifiche di sorgente in questa consegna implementano il ciclo di apprendimento: non sono modifiche che il worker farà a sé stesso in produzione. Eventuali future correzioni del codice restano rilasci da verificare separatamente. Il controllo dei permessi non è una procedura appresa.

## Funzionamento verificato

- **Memoria:** rimangono gli aggiornamenti versionati già disponibili; il test completo registra due versioni e conserva la storia. Questa versione non aggiunge un'inferenza autonoma universale delle preferenze.
- **Modelli:** l'host autentica e invia un batch di osservazioni al metodo `refresh_adaptive_world`. Il candidato supera i controlli temporali esistenti; per sostituire un modello deve ridurre l'errore medio assoluto di oltre il 5% sullo stesso holdout fresco e non peggiorarne la copertura. Mantiene azioni validate e schema dello stato.
- **Protezione del test:** gli input del nuovo holdout devono essere successivi al precedente cutoff di selezione. Gli identificatori valutati sono consumati anche dopo un rifiuto di validazione, di schema o del confronto. Non è consentito riprovare sullo stesso test fino a ottenere un esito favorevole. La veridicità di identificatori, tempi e provenienza rimane responsabilità dell'host autenticato.
- **Esiti:** le previsioni conservano la propria versione originale. La risoluzione di esiti `host_verified` controlla automaticamente la copertura e cambia il puntatore al modello nella stessa transazione SQLite: ripristina il precedente o sospende il modello se non esiste un precedente. Le normali astensioni restano applicate anche al modello ripristinato; un rollback non garantisce accuratezza.
- **Procedure:** varianti immutabili di passi testuali, senza codice eseguito. La raccomandazione richiede almeno 20 esiti verificati tra gli ultimi 40 e un limite inferiore Wilson di almeno 0,7. Il peggioramento può ritirare la raccomandazione. Ogni risultato dichiara `execution_authorized=false`.

Le soglie di ammissione sono regole prudenziali, non una dimostrazione statistica generale di superiorità. Gli intervalli sulle procedure non garantiscono prestazioni dopo selezioni multiple o in condizioni mutate.

Le API che modificano modelli e procedure sono riservate all'integrazione Python autenticata. JSONL espone solo stato adattivo e raccomandazioni; il modello non può promuovere a `host_verified` i propri esiti attraverso i trasporti. Sono mantenuti isolamento owner/space, ricevute immutabili e rifiuto delle azioni reali nel worker vincolato.

## Prove

La suite specifica contiene 12 test: promozione su dati nuovi, rifiuto senza miglioramento, consumo degli holdout respinti, blocco di dati futuri/vecchi, cambio schema e validazione parziale, ripristino/sospensione, esiti non verificati, atomicità dopo un errore, due connessioni concorrenti, procedure e integrità dei sorgenti.

Le tre regressioni finali sono tutte complete e verdi nei relativi rapporti: 36 gruppi per esecuzione, 318 test Python e 12 Node, con due skip opzionali browser/desktop. Sono inclusi anche i tre passaggi precedenti allo specifico irrigidimento del consumo del test; non vengono sostituiti o nascosti. Le esecuzioni finali raccolgono diagnostica di processi, thread e file aperti.

La dimostrazione `scripts/validate_adaptive_lifecycle.py` usa il vero motore e un vero database SQLite con osservazioni **sintetiche controllate**. Verifica:

1. Due versioni di memoria conservate.
2. Due promozioni di modello.
3. Esiti negativi verificati che causano un ripristino e poi una sospensione.
4. Una procedura prima raccomandata e poi ritirata dopo feedback negativo.
5. Integrità SQLite e hash invariati di tutti i 35 file del motore durante il ciclo.

Il risultato finale è in `evidence/adaptation/lifecycle_final/report.json`, con le ricevute in `lifecycle.db`. Il primo esperimento è conservato separatamente. Le osservazioni non provengono da utenti, calendario, CRM o sensori live: non si presentano come prova di anticipazione di bisogni reali.

La wheel viene installata e provata in un ambiente pulito; i suoi 35 file del motore sono confrontati byte per byte con i sorgenti. Il pacchetto comprende sorgenti, wheel, documentazione, test, log, database delle prove e manifest. I risultati del precedente stress del runner (140/140, fd 3→3) e dell'audit delle dipendenze rimangono evidenze ereditate rc1; non si afferma di averli rieseguiti per rc2. Questa modifica non aggiunge dipendenze esterne.

## Limiti operativi e stato degli host

L'apprendimento è **sincrono e guidato da eventi dell'host**: una nuova osservazione o risoluzione avvia il percorso previsto, senza chiedere a una persona di scegliere manualmente il modello. Non è stato acceso un servizio di monitoraggio continuo o un task asincrono. L'host deve ancora fornire dati autentici, un ciclo di eventi autorizzato e limiti di risorse. L'autenticazione del sensore non si ottiene scrivendo la stringa `host_verified`.

Il ciclo LLM → strumento → LLM OpenCode era stato verificato 3/3 nella rc1; i log e le ricevute sono conservati e identificano quella versione. Non è stato ripetuto un nuovo ciclo LLM per rc2. La regressione include il trasporto MCP reale. Hermes mantiene le verifiche autentiche di plugin/registro e la chiamata LLM separata già documentate; **il circuito completo Hermes → osservazioni reali → apprendimento → azione autorizzata → esito non è ancora certificato**. Claude rimane limitato dalla precedente quota del provider; OpenClaw è simulato nei test.

Non è corretto definire questa consegna «definitiva» nel senso di completa, valida per qualsiasi workflow o incapace di richiedere manutenzione. Per sostenere l'autonomia utile a persone e aziende occorrono ancora integrazione di eventi reali e pilot rappresentativi che misurino bisogni anticipati correttamente, falsi allarmi, beneficio e latenza rispetto allo stesso agente senza WorldCore. CI remota, scelta licenza e responsabilità del rilascio pubblico restano aperte.
