# WorldCore 0.7 — Architettura e ambiti cognitivi

## Definizione
WorldCore non è AGI né un LLM. È un **livello di stato e previsione indipendente dall'LLM**, condivisibile con Hermes, OpenClaw, Claude Code, OpenCode e altri framework che possano scambiare JSON o MCP. L'host autentica gli utenti, applica permessi, fornisce osservazioni attendibili e seleziona il modello linguistico. WorldCore non aggira abbonamenti consumer/API key.

## Livelli effettivamente implementati

1. **Stato versionato**: aggiornamenti immutabili per (owner, space, context_id), provenienza, verifica esplicita, isolamento dati, protezione opt-in per chiavi sensibili; memoria ed evidenze v0.1–0.6 restano disponibili.
2. **World model ibrido**: recupero discreto per stati già osservati + apprendimento supervisionato di differenze numeriche, condizionato all'azione. L'host dichiara esplicitamente quando due ambienti appartengono alla medesima famiglia. I modelli numerici vengono accettati solo dopo un test su un **ambiente interamente tenuto fuori dall'addestramento** con guadagno >=10% sulla baseline di persistenza.
3. **Simulazione controfattuale**: rollout senza eseguire azioni; massimo 8 passi; incertezza di previsione e astensione fuori supporto.
4. **Prediction Ledger**: previsione registrata prima dell'esito, versione del modello fissata, esito immutabile, MAE, monitoraggio del peggioramento. Un nuovo modello non riscrive l'errore storico.
5. **Previsioni sullo stato personale**: trend numerico soltanto con osservazioni verificate e test cronologico; scadenze esplicite fornite dall'utente; anomalie statistiche robuste. Nessuna inferenza automatica di condizioni cliniche o tratti psicologici.
6. **Multimodalità non semantica locale**: intestazione PNG (dimensioni), segnale WAV PCM (durata e intensità), struttura HTML già fornito dall'host (link e form), fusione numerica con fonte dichiarata. Sono **feature extractor**, non un modello visivo/audio generale e non effettuano navigazione Internet.
7. **Integrazioni**: funzioni read-only via MCP e bridge JSONL, adattatori Hermes/OpenClaw precedenti. Le nuove funzioni sono registrate in MCP ma **non certificate** su gateway reali.
8. **Ricerca pubblica e argomenti personali**: moduli v0.5–0.6 conservati per cataloghi, notizie, market-event studies, social velocity, intenti; la v0.7 non introduce modelli predittivi di trading o medicina.

## Ambiti predittivi di un personal agent — supporto attuale

| Ambito | Stato | Cosa occorre per attivarlo con affidabilità |
| --- | --- | --- |
| Scadenze, task, obiettivi | **Operativo con dati espliciti** | Calendario/task autenticati dall'host |
| Consumo API e budget | **Trend se supera baseline** | Serie temporali verificate |
| Carico computer / sensoristica locale | **Anomalia numerica** | Misure continue, soglie e controllo cause |
| Browser/UI e workflow software | **Discreto osservato** | Transizioni documentate e modello dedicato |
| Ambiente fisico e robotica | **Solo stati numerici** | Sensori, dinamiche, safety interlock e prove hardware |
| News vs mercato | **Studio retrospettivo v0.6** | Dati timestampati veri, slippage, walk-forward, regimi |
| Crypto e investimenti | **Informazione consultiva** | Fornitore di mercato, backtest robusti, risk review |
| Marketing/social | **Velocità descrittiva v0.6** | Dati di piattaforma e test reali di diffusione |
| Medicina e psicologia | **Evidenze e consigli cauti** | Fonti scientifiche, professionisti, valutazioni di sicurezza |
| Viaggi, mappe, meteo | **Interfacce host** | Routing e feed affidabili, posizione consentita |
| Visione, parlato e conversazione | **Feature e adapter** | Modelli visivi, ASR/TTS e LLM forniti dall'host |
| Architettura, CAD, 3D e stampa | **Catalogo e strumenti host** | Simulatore geometrico/slicer, prove su file, sicurezza fisica |
| Scienza sportiva | **Fonti e analisi non clinica** | Misure e modelli validati, consenso alla raccolta dati |
| Cronologia storica e causalità | **Link di evidenze v0.5** | Dataset strutturati, controfattuali, controllo confondenti |

## Ciò che la v0.7 NON fa

- Non capisce autonomamente qualunque ambiente, non interpreta semantica di immagini, video o voce senza modelli esterni.
- Non simula automaticamente leggi fisiche ignote, né produce AGI, diagnosi, negoziazione o predizioni affidabili di mercati da semplici coincidenze.
- Non insegna a un LLM l'intero contenuto dei 246 repo: l'audit non è addestramento e il catalogo non implica licenze di riutilizzo.
- Non autorizza installazioni di codice GitHub in modo automatico; tutte le candidature restano in quarantena.
- Non continua ad apprendere dopo la chiusura della sandbox; gli scheduler sono eseguibili dall'utente su una macchina propria.

## Requisiti per la maturità

- Pesi e rappresentazioni multimodali apprese su dataset autorizzati, con transfer test su nuovi mondi autentici e baseline competitive.
- Revisione estesa licenze, codice, supply-chain e test dei repository; audit human-in-the-loop prima di qualunque esecuzione o copia.
- Telemetria reale da host Hermes e OpenClaw, con hash di versione, replay, revoca e rollback.
- Convalida di brier, ECE, precision/recall di segnalazioni, falsi allarmi, drift, privacy, latenza e costi per dominio.
- Per medicina/mercati/psicologia: adeguamento normativo, affidabilità delle fonti e revisione da specialisti quando appropriato.
