# WorldCore Cognitive Layer 1.2.0 — Research Alpha

Continuazione dei sorgenti originali 1.1.0. Nessun componente MONO incluso.

## Installazione

Richiede Python >=3.11. Dalla directory di rilascio:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install dist/worldcore_cognitive_layer-1.2.0-py3-none-any.whl
.venv/bin/python -m worldcore --help
```

Per MCP installare l'extra testato con SDK 1.30:

```sh
.venv/bin/python -m pip install '.[mcp]'
```

Le dipendenze del motore di base sono soltanto la libreria standard. Gli extra `test` e `benchmark` servono per riprodurre tutte le verifiche. I test browser/desktop storici richiedono inoltre strumenti opzionali, specificati nei loro messaggi di skip.

## Verifiche riproducibili

```sh
.venv/bin/python -m pip install '.[test,benchmark,mcp]'
.venv/bin/python -B scripts/run_bounded_pytests.py --selftest --timeout 40 --total-timeout 150
.venv/bin/python -B scripts/repeat_validation_v12.py /tmp/worldcore-validation
.venv/bin/python -B scripts/stress_runner_v12.py /tmp/worldcore-stress
.venv/bin/python -B benchmarks/v12_real_temporal.py
.venv/bin/python scripts/verify_release.py
```

Il runner disattiva il bytecode nei processi di test e l'autocaricamento di plugin pytest esterni. Ogni modulo ha un limite di tempo, output completo su disco, diagnostica di processi/thread/fd quando psutil è disponibile, pulizia del gruppo e dei discendenti osservati. I rapporti vengono aggiornati atomicamente. Il supervisore delle ripetizioni impone un ulteriore limite esterno.

Su questo Mac sono stati osservati blocchi durante letture di file, inclusi bytecode delle dipendenze. Ambiente temporaneo, estrazione fresca e rimozione delle sole cache generate hanno consentito tre esecuzioni complete. Questi risultati non identificano definitivamente la causa del filesystem o del sistema operativo.

## Previsioni temporali con intervalli

`train_calibrated_dynamics(owner, family, samples, as_of=...)` richiede almeno 80 osservazioni per azione utilizzabile. Ogni campione include identificativo, ambiente, azione, stati numerici prima/dopo, `before_at`, `observed_at`, `available_at`, `source='observed'` e provenienza. L'host deve attestare l'origine: una stringa non costituisce autenticazione del sensore.

Il percorso separa cronologicamente fit, calibrazione e validazione 60/20/20. Un'etichetta di una partizione precedente deve essere disponibile prima delle previsioni della successiva. I dati non ancora disponibili al cutoff sono esclusi. Il modello non viene riaddestrato sulla validazione. Gli intervalli congiunti usano residui split-conformal e la copertura viene misurata separatamente, con intervallo Wilson.

`predict_calibrated_world(..., min_confidence=.5, max_width=None, persist=True)` può astenersi per schema ignoto, valori fuori dal range di addestramento, scarsa evidenza, intervallo troppo largo o degrado osservato. Il parametro confidence è una soglia sulla copertura storica validata, non una probabilità individuale di correttezza. Le proprietà conformal richiedono scambiabilità dei residui; non valgono automaticamente nel tempo o in sistemi aperti.

`resolve_calibrated_prediction` confronta una previsione registrata prima dell'osservazione con l'esito. Modello/versione e intervalli restano fissati; tenant, ordine temporale e prima risoluzione sono protetti da transazioni. La risoluzione non riaddestra automaticamente il modello. `calibrated_prediction_metrics` distingue invii, risoluzioni e copertura condizionata alle previsioni accettate.

MCP espone `calibrated_world_predict`, `calibrated_world_resolve`, `calibrated_world_metrics`. Il bridge JSON espone `calibrated_predict`, `calibrated_resolve`, `calibrated_metrics`. Le risoluzioni da questi trasporti rimangono `user_reported`; solo il codice host autenticato può attribuire `host_verified`.

WHAT IF accetta `kind='calibrated_world'`, con `family`, `before` e una sola azione. Propaga l'intervallo e si astiene dove manca un modello. Non inventa coperture multi-step: più azioni sono rifiutate per questo tipo. Le classifiche restano confronti di obiettivi dichiarati; non viene nominato automaticamente un candidato sulla sola media prevista.

I precedenti modelli e le simulazioni `state`/`world` rimangono disponibili come percorsi esplorativi con i loro limiti; non acquisiscono automaticamente la calibrazione del nuovo percorso.

## Host

Claude Code usa gli esempi in `adapters/claude-code`. OpenCode V1 usa il proprio adattatore; V2 richiede il default export con id/setup in `adapters/opencode/v2` e l'esempio `opencode-v2.example.json`. Mantenere tutta la directory `adapters/opencode` perché il punto d'ingresso V2 usa i moduli fratelli. Non installare soltanto la sottocartella V2 come pacchetto autonomo.

Hermes: installare il motore nel suo ambiente Python e caricare `adapters/hermes/worldcore` tramite il gestore plugin. Il manifest descrive hook e strumenti. Le prove su un checkout Hermes esistente devono passare il suo percorso nel PYTHONPATH e usare una home temporanea per i test dei registri; la chiamata LLM usa il provider dell'host e il suo normale controllo dei permessi.

Il rilascio comprende i risultati effettivi, inclusi errori dei provider e host simulati. Consultare `docs/VALIDATION_V12_IT.md` prima di interpretare la compatibilità.

## Garanzie e limiti

Le operazioni deterministiche descrivono conseguenze delle sole regole esplicite, entro uno stato e uno spazio d'azioni finito. I test e i controlli esaustivi di piccoli casi non sono una prova formale universale. Un file realmente scritto in una cartella controllata non dimostra comprensione di qualsiasi browser, città o persona.

In sistemi aperti il modello produce previsioni fallibili. Controfattuali osservazionali non identificano automaticamente cause; alternative mai realizzate non diventano esiti osservati. Simulazioni, intervalli e classifiche non concedono autorizzazioni né eseguono azioni reali.

Il runner contiene i guasti verificati, ma non è una barriera contro codice ostile: processi che sfuggono prima del campionamento, SIGKILL al supervisore, guasti kernel o storage richiedono supervisione a livello di sistema/container. La certificazione riguarda questo ambiente e le prove consegnate, non ogni possibile host.
