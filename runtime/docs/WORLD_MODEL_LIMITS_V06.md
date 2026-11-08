# Risultati e lacune tecniche v0.6

## Verificabile oggi

- Stati e azioni in JSON limitato a dimensioni fissate; tabella di transizioni osservate e stima frequenziale.
- Esplorazione controfattuale con ricerca locale limitata (beam), max 8 azioni, fino a 8 rami e astensione su stati non supportati.
- Registro delle previsioni da verificare, scoring top-state, deduplica e scope per proprietario/progetto.
- Event study descrittivo con tassi logaritmici e benchmark, timestamp in UTC, intervalli e filtri sugli overlap.
- Analisi temporale dell'engagement social da screenshot di metriche forniti dall'host come dato tracciato.
- Intent router lessicale incrementale, non LLM generativo.
- 246 nomi candidati GitHub; 0 repository addestrati nel senso di ottimizzazione dei pesi sui sorgenti.

## Non verificato / non implementato

- Generalizzazione fra ambienti mai visti; apprendimento multimodale self-supervised e simulazione fisica realistica.
- Riconoscimento nativo immagini/video/audio o navigazione web completamente autonoma: occorrono strumenti host esterni, consenso e benchmark.
- Inferenza causale scientificamente validata o previsione affidabile dei mercati su notizie in tempo reale.
- Reddit/social scraping continuativo o accesso a feed privati; nessuna attività in background avviata nella sandbox.
- Test end-to-end con gateway Hermes/OpenClaw reali, oltre agli adapter con host fittizi.
- Audit qualità e licenze dei 246 progetti, controllo sicurezza supply-chain, deduplicazione forks e benchmark di ogni repo.
- Calibrazione delle probabilità su casi clinici, finanziari o psicologici reali e analisi fairness/bias.

## Condizioni per uscire dalla alpha

1. Dataset e benchmark indipendenti con licenze e split temporali chiari, incluse serie news + market prices reali.
2. Attacchi avversariali, privacy, isolamento, permessi e accessi autenticati in installazioni reali.
3. Benchmark di qualità di simulazione per almeno tre ambienti complessi mai visti, rispetto a baseline pubblicate.
4. Test end-to-end con Hermes/OpenClaw versioni fissate e completamento delle chiamate MCP reali.
5. Controlli di perdita dei dati, rollback e drift, misure di latenza e utilizzo risorse su macOS M4 16 GB.
6. Percezione visiva e linguistica tramite adapter di provider con dataset separati e tracciamento dei costi.
7. Validazione della robustezza nel tempo (news quotidiane) prima di qualunque invio automatico di raccomandazioni.
