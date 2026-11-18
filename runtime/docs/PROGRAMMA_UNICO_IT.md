# Cognitive Core: un unico programma operativo

Il programma rimane **Cognitive Core**. Il nuovo ingresso `core.run(...)` collega i componenti già presenti e integra contesto, attenzione e piccole ricette di strumenti dall’apporto del 13 novembre. Non installa il prototipo SIS come secondo assistente.

```mermaid
flowchart LR
 H[Persona o connettore] --> P[Unico ingresso Cognitive Core]
 P --> C[Contesto e attenzione]
 C --> B[Boredom / Curiosità]
 B --> O[Opportunity Pool e ricerca]
 O --> W[WorldCore / WHAT IF]
 W --> D[Decisione e permessi]
 D --> E[Evidenze, ledger e checkpoint]
 E --> B
 P --> M[LLM opzionali su richiesta]
 M --> P
```

## Avvio

Sul Mac, aprire `Avvia_Cognitive_Core.command` nella cartella del repository. Richiede Python 3.11 o successivo, individuato nel PATH; non scarica nulla. Il launcher usa la cartella sorella `dati-programma`, namespace `unified`. `COGNITIVE_CORE_HOME` e `COGNITIVE_CORE_PYTHON` consentono al proprietario di scegliere un altro archivio o interprete.

L’interfaccia è testuale. Nessuna grafica dell’allegato viene avviata.

- `/status`: componenti, backend e stato del programma.
- Scrivere una domanda: ricerca locale, ciclo cognitivo bounded e fonti. Senza modello non viene inventata una risposta discorsiva.
- `/json {"op":"..."}`: una richiesta strutturata nella stessa sessione.
- `/stop`, `/start`, `/exit`: arresto, ripartenza esplicita e chiusura.

Il launcher parte **senza LLM**, rete di ricerca o cattura schermo. La console resta in primo piano; non crea un servizio in background. Ogni turno compie al massimo dodici tick e rispetta il limite temporale configurato.

## Un solo ingresso per applicazioni e connettori

```python
from cognitive_core import CognitiveCore, Settings
core = CognitiveCore(Settings(home="archivio", owner="local", namespace="unified"))
try:
    result = core.run({"op": "turn", "text": "Come riprendere il progetto runner?"})
finally:
    core.close()
```

Lo stesso contratto passa da:

- CLI: `cognitive-core ... run '{"op":"status"}'` oppure `run @richiesta.json`.
- Worker JSONL: `{"op":"cognitive_run","request":{"op":"status"}}`.
- API locale già esistente: `POST /v1/run`, avviata solo su richiesta.

Il worker è legato a owner/namespace del processo host. L’API HTTP resta solo loopback, con i limiti preesistenti su Host e Origin: non è autenticazione per accesso remoto e non va pubblicata come servizio Internet.

L’operazione `worldcore` inoltra le operazioni esistenti allo stesso backend, conservando scope, autorità e blocco delle azioni reali del worker. Esempio: `{"op":"worldcore","request":{"op":"recall","query":"runner"}}`. Sono vietati annidamenti ricorsivi `cognitive_*`.

## Componenti collegati

| Parte | Operazioni del programma |
|---|---|
| Memoria e conoscenza | `remember`, `search`, `import`, `rollback_import` |
| Boredom / Curiosità / ricerca locale | `observe`, `turn`, `tick`, `project` |
| Opportunity Pool, modelli del mondo e WHAT IF | `whatif` e ingresso `worldcore` con i comandi esistenti |
| Riflessione | `dream`; resta INFERRED e non può confermare da sola le ipotesi |
| World × User × Cognitive | `session_open`, `assist`, `context`, `session_close` |
| Attenzione | Sessione/scope/TTL, silenzio esplicito, capacità dichiarata indisponibile, cooldown |
| Piccoli strumenti | `skill_propose`, `skill_adopt`, `skill_use` |
| Feedback ed esperienza | `feedback`, ledger e checkpoint del ciclo; apprendimento soltanto nel significato dichiarato |
| Modelli sostituibili | `model` oppure `turn` con richiesta esplicita `use_model` |

Il programma utilizza Vault e WorldCore esistenti. Le nuove osservazioni e le ricette sono registrate nel ledger degli eventi del Vault, senza un database SIS duplicato. I comandi e le API precedenti rimangono compatibili. Le loro procedure legacy conservano i propri contratti e limiti; la quota `program_model_calls` riguarda le chiamate del nuovo ingresso unificato, non altri programmi o processi esterni.

## LLM: abilitato, residente e chiamato sono cose diverse

Il gateway ammette due famiglie di backend:

1. **GGUF one-shot**, con binario locale già installato: avvia il processo alla richiesta, impone timeout/output/token, poi chiude il processo. Nessun server e nessun peso residente gestito dal Core fra richieste.
2. **Server HTTP locale compatibile**, già gestito dal proprietario: il Core si collega soltanto a loopback, senza credenziali o redirect. La residenza del modello e gli eventuali upstream di quel server sono responsabilità dell’host; il Core non lo avvia né lo scarica.

L’host può registrare fino a otto profili aggiuntivi, senza cambiare memoria o ciclo:

```python
from cognitive_core.models import ModelProfile
core.program.models.register(ModelProfile(
    id="scrittura", backend="gguf", weights="/percorso/modello.gguf",
    binary="llama-completion", enabled=True))
```

La registrazione è configurazione Python dell’host interattivo: non è una funzione concessa a messaggi LLM o documenti importati. Per usare un profilo occorrono anche `Settings.enable_local_model=True` e una richiesta esplicita al modello. I profili non sono permessi esportati con i dati.

Per la console, le opzioni già esistenti `--local-model`, `--model-gguf`, `--model-binary`, `--model-max-bytes`, `--model-jinja` e `--model-timeout` selezionano il backend. `--generation-tokens` limita l’output generativo (default 256; massimo 2048). La quota giornaliera configurata è prenotata prima della chiamata; fallimenti e timeout consumano la prenotazione. Un lease con scadenza impedisce due generazioni simultanee nello stesso home/namespace.

I saluti non caricano modelli né aprono l’archivio. Il nuovo `turn` non esegue classificazioni o consigli LLM nascosti: attiva solo la generazione richiesta, senza tentativi di riparazione o fallback verso altri modelli. L’output è dato **INFERRED, verified=false** e non viene trasformato in tool call o memoria vera.

L’inclusione di estratti di memoria nel prompt richiede `use_memory=true` e autorità interattiva. Il contesto personale delle osservazioni non entra automaticamente nel retrieval o nei prompt.

In autonomia la generazione è bloccata, salvo il distinto opt-in dell’host `autonomous_model_opt_in`/`--autonomous-model-opt-in`. Non esiste un client per provider cloud a pagamento; nessuna chiave API viene accettata dal contratto. Un proxy locale rimane un componente fidato dell’host, non una garanzia del Core su eventuali costi upstream.

## Osservazioni dell’ultimo pacchetto

I connettori possono inviare dati normalizzati; non vengono avviati sensori.

Prima l’host interattivo apre una sessione per una sola fonte, dominio e contesto, con TTL fino a un’ora. `assist` ammette solo osservazioni dello stesso scope, non future né scadute, con origine `OBSERVED`, `SIMULATED` o `INFERRED`, confidenza e segnali scalari bounded. Le sessioni non sono autenticazione OS e non concedono Screen Recording, accessibilità o azioni sul dispositivo.

Il livello User richiede autorità interattiva; non vengono dedotte emozioni o caratteristiche sensibili. Osservazioni private e chiavi sensibili riconosciute sono rifiutate. Questo filtro non è un redattore universale di segreti: l’host deve fornire segnali minimizzati, non screenshot o testo privato grezzo.

La fusione applica solo regole esplicite: quiet/allow_advice dell’utente, indisponibilità dichiarata del livello Cognitive, sufficienza della fonte e cooldown. Non è causalità generale. Una domanda ammessa passa allo stesso ciclo Boredom/WHAT IF; resta una proposta senza attuazione esterna. Il programma non controlla giochi, telefono, applicazioni o dispositivi fisici.

Revoca, scadenza, stop o riavvio rendono inutilizzabili le sessioni precedenti. Il contesto resta esportabile come dato; i consensi non vengono ripristinati.

## Piccole competenze verificabili

`skill_propose` ricerca una ricetta composta da operazioni predefinite su testo, liste o numeri: massimo tre passi e 2500 candidati, con deadline. Servono almeno due esempi di sviluppo e due di valutazione, con input separati. Una ricetta viene selezionata sullo sviluppo e valutata una sola volta sul set escluso: se fallisce non viene riparata sul test.

Si conserva ricetta, digest degli esempi ed esito; non il testo degli esempi nel ledger. Questo è apprendimento di trasformazioni ristrette, non programmazione arbitraria o addestramento dei pesi.

L’adozione richiede autorità interattiva e vale soltanto nel processo corrente. Dopo stop o riavvio deve essere confermata di nuovo. `skill_use` restituisce solo dati, con una quota di 24 usi al giorno: nessuna shell, eval, chiamata di rete o azione OS. Le ricette persistono nell’export, i permessi no.

## Dati, stop e compatibilità

Il nuovo launcher usa `dati-programma` come archivio dell’applicazione. La preparazione iniziale può importare in questo archivio nuovo il laboratorio `realtest` e il bridge cognitivo selezionato dal pacchetto del 13 novembre. I sorgenti restano in sola lettura e nessuna ipotesi diventa un fatto verificato. La cartella esiste solo se predisposta esplicitamente; non viene sovrascritta.

`/stop` viene controllato anche durante l’attesa di un processo GGUF quando registrato da un altro ingresso sullo stesso archivio. La console e il worker elaborano richieste in sequenza: per interrompere subito una chiamata dalla console usare Ctrl+C; una riga `/stop` digitata durante la chiamata viene letta dopo il suo ritorno. Se il budget disco impedisce di registrarlo, ferma comunque il processo corrente e restituisce `persisted=false`: in quel caso non può promettere persistenza al riavvio. Un server HTTP esterno può continuare il proprio lavoro fino al timeout; il Core scarta la risposta dopo stop.

I limiti sono applicativi, non quote OS di RAM. Il modello locale resta opzionale. Cambiare modello o runtime non cambia eventi, conoscenza, ricette o checkpoint esportabili.

Visione/voce complete, ScreenCaptureKit, connettori Moltis specifici, strumenti arbitrari e tutte le 69 proposte del catalogo non diventano implementati per il solo fatto di collegare il programma. La piattaforma espone il punto di innesto; gli adapter reali richiedono implementazione e prove dedicate.
