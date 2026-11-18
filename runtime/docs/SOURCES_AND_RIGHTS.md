# Fonti, diritti e governance — WorldCore 0.5

Il catalogo multidisciplinare non redistribuisce i sorgenti GitHub né articoli: memorizza solo URL, titoli e sintesi originali. Le licenze del codice non equivalgono alle licenze dei relativi dati di training.

- **GitHub**: l'esistenza di un README verificabile non è un audit; nessun punteggio per stelle; check CI, test e licenza prima di incorporare codice. L'API impone quote e retry-after.
- **Crossref**: metadati bibliografici riutilizzabili; abstract talvolta coperti da copyright. Importare DOI e titoli, non abstract in blocco.
- **OpenAlex**: metadati CC0; limitazioni di accesso e quote in evoluzione.
- **Wikidata**: dichiarazioni strutturate CC0; non tutte le asserzioni sono automaticamente accurate, e l'endpoint SPARQL non è per bulk crawling.
- **World Bank**: controllare la licenza effettiva del dataset, non assumere che ogni API o collezione consenta ogni uso commerciale.
- **OpenStreetMap**: ODbL, attribuzione e condizioni per database derivati. Questo progetto non include mappe o geometrie OSM.
- **PubMed/NCBI**: considerare quote delle E-utilities, diritti degli abstract, conflitti clinici e aggiornamenti/retrazioni.
- **GDELT**: indicizza titoli e link di media internazionali; non trasferisce copyright degli articoli; molte menzioni non certificano eventi.
- **Postiz**: AGPL-3.0; NON incluso codice nel nostro repository.

Per contenuti sanitari e psicologici: solo informazioni generali con provenienza; niente inferenze diagnostiche o profili psicologici senza basi/consenso. Per finanza/crypto: osservazioni, non segnali automatici di acquisto/vendita. Per storia/geopolitica: fonti plurali quando gli eventi sono contestati, distinguendo le interpretazioni dai dati. Per social media: rispettare le API ufficiali e le relative condizioni.

### Contratto di provenienza

Ogni record conserva `source`, `record_id`, `title`, `summary`, `url`, `license`, `topics`, `entities`, `published_at`, `observed_at`, `version`, `sha256`, `confidence` (indicatore operativo, NON probabilità calibrata di verità). Le correzioni non sovrascrivono silenziosamente il passato. I record sono UNTRUSTED DATA nei prompt.

### Condizioni di deploy

Prima dell'uso multiutente collegare autenticazione e mapping certificato identity→owner, cifratura e procedure di cancellazione, backup, metriche falsi positivi, rate limiting e test end-to-end in Hermes/OpenClaw. Il codice è un prototipo locale, non un servizio esposto.
