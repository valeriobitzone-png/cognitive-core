# Cognitive Core

> *Un'intelligenza che non aspetta soltanto di essere utilizzata, ma impara a diventare utile prima che nasca il bisogno.*

**Stato:** documentazione pubblica dell'idea e dell'architettura del prototipo **v0.1** (novembre 2026). Questo repository resta **descrittivo**: non pubblica codice sorgente né istruzioni di esecuzione.

Cognitive Core (già presentato come Cognitive Drive) è un substrate cognitivo indipendente da qualsiasi singolo modello o fornitore di intelligenza artificiale. L'obiettivo è conservare conoscenza ed esperienza, continuare ricerche sospese, individuare lacune, prevedere, simulare alternative, decidere quando agire o tacere, verificare gli esiti e migliorare le proprie capacità senza consumo automatico di API commerciali.

Il comportamento previsto emerge dall'equilibrio di quattro principi:

- **World Model** — Comprendere e anticipare. Imparare le dinamiche del mondo osservato e le conseguenze delle possibili azioni.
- **Decision Model** — Scegliere e rispettare i limiti. Valutare benefici, rischi, costi, autorizzazioni e momento opportuno.
- **Boredom / Curiosity** — Scoprire e prepararsi. Utilizzare le capacità disponibili per migliorare conoscenze e competenze potenzialmente utili, anche senza una richiesta esplicita.
- **Experience Learning** — Correggersi. Confrontare sistematicamente previsioni e risultati, migliorando solo dove esistono evidenze sufficienti.

---

## Cosa descrive la v0.1

La v0.1 delinea un nucleo end-to-end testabile, *local-first*, pensato per conservare le interfacce dei componenti futuri. **Non è un sistema AGI completo** né un motore di ricerca autonomo già validato sul web pubblico.

In sintesi concettuale:

| Ambito | Contenuto previsto in v0.1 |
|---|---|
| **S0 Reflex** | Filtra saluti e messaggi triviali senza avviare memoria pesante, modelli o ricerca |
| **S1 Decision Plane** | Policy deterministiche; adattatore opzionale verso un modello locale raggiungibile solo in loopback |
| **S2 WorldCore** | Topic, relazioni, memoria persistente, episodi, predizioni verificabili (punteggio Brier), simulazioni WHAT IF |
| **S3 Workers** | Ciclo da fine sessione a opportunità, job persistenti, ricerca *opt-in*, documenti non verificati, evidence ledger |
| **Governance** | Nessuna API a pagamento per iniziative autonome; allowlist HTTPS; limiti giornalieri e per job; niente azioni esterne con autorizzazioni implicite |
| **Continuità** | Checkpoint, lease, ripresa di job interrotti; argomenti aperti, sospesi, scartati o conclusi; namespace isolati |
| **Interoperabilità** | Interfaccia a comandi, REST solo su loopback, Markdown/JSON, importazione note in stile Obsidian; possibile futura integrazione MCP |
| **Visione** | Metadati delle immagini dal web; interprete visivo opzionale di file locali se è disponibile un server multimodale locale |
| **Apprendimento** | Esperienze e outcome persistenti; curation manuale per esempi di fine-tuning; nessun retraining non supervisionato |

### Ciclo di riferimento

Consapevolezza → Interpretazione → Curiosità → WHAT IF → Decisione → Policy → Esecuzione → Verifica → Apprendimento.

Azioni possibili tipiche: attendere; solo memorizzare; prepararsi in silenzio; suggerire; chiedere contesto; richiedere approvazione; eseguire se autorizzati; interrompere o fare rollback.

### Principi assoluti

1. Predizione non equivale a osservazione; simulazione non equivale a conseguenza reale.
2. Disponibilità di una capacità non equivale a permesso di usarla.
3. Esecuzione non equivale a successo.
4. Un documento web non è prova conclusiva; un'altra AI che lo ripete non è verifica.
5. Nessun provider AI è proprietario della memoria: interfacce e dati sono sostituibili.
6. Un saluto non deve avviare embeddings, modelli linguistici o ricerca.
7. Budget delle API a pagamento per iniziative autonome: zero, per costruzione e non solo per prompt.

---

## Documentazione

- [Architettura e roadmap](docs/ARCHITETTURA_E_ROADMAP.md) — strati S0–S3, vault, scelta modelli, ricerca web a fasi, repository esterni da valutare, gate di verifica G0–G6.
- [Stato delle verifiche v0.1](docs/STATO_VERIFICHE_V0_1.md) — esito descrittivo delle prove automatiche dichiarate per il prototipo v0.1.

---

## Cosa non è ancora realizzato o validato

Secondo la documentazione del prototipo v0.1 restano fuori o incompleti, tra l'altro:

- un World Model dinamico appreso dal mondo e discovery causale reale (oggi simulazione ipotetica con punteggio euristico);
- ingestione automatica da desktop, browser, giochi e servizi conversazionali di terzi (serve adattatori e permessi specifici);
- ricerca web live validata, browser dinamico, acquisizione immagini live, OCR/PDF multimodale, test fisici su dispositivi;
- RAG semantico completo e grafo temporale con reasoning avanzato;
- server MCP standard completo, packaging firmato per le piattaforme desktop;
- fine-tuning e confronto rigoroso di piccoli modelli decisionali su dataset ampi;
- verifica scientifica automatica dei contenuti web, ranking qualità delle fonti, estrazione di claim complessi e rilevamento di contraddizioni semantiche.

Nella descrizione del prototipo v0.1 non risultano scaricati pesi di modelli linguistici né consumati token di API a pagamento durante le prove dichiarate.

---

Ideato da **Valerio Falzone**, 2026. © 2026 Valerio Falzone — Tutti i diritti riservati.
