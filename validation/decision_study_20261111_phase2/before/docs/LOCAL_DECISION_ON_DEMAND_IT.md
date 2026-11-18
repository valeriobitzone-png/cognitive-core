# Modello decisionale locale a chiamata singola

Il backend GGUF avvia `llama-completion` soltanto per una richiesta ammessa e chiude il processo al termine, anche per timeout o output eccessivo. Non avvia server, listener o servizi persistenti; non scarica modelli a runtime. Non è configurato un modello predefinito. Il confronto dell’11 novembre su 34 casi sintetici non giustifica la promozione di nessuno dei quattro candidati neurali. Qwen3.5-0.8B è stato soltanto un candidato sperimentale; questo backend è un classificatore di pertinenza, non un decisore completo né un verificatore della verità.

Il modello valuta la pertinenza tematica, senza pretendere che gli estratti bastino a rispondere. Non usa le note generate dal ciclo come nuove fonti. Legge tre estratti dal retrieval unificato già esistente (Vault, WorldCore, knowledge e laboratorio). Per non aprire o migrare i database originali, il lettore copia temporaneamente DB e WAL entro 32 MB e due secondi, verifica che inode/dimensioni/date non siano cambiati durante la lettura, poi usa il core sulle copie. Una modifica concorrente provoca errore e richiede una successiva richiesta; non viene consultato un insieme parziale. Le copie sono eliminate dopo il recupero. Anche una connessione SQLite `mode=ro` può creare file WAL/SHM: per questo non viene usata sui file originali.

Il modello restituisce soltanto una classe di pertinenza (yes/no/unclear) in JSON, tradotta deterministicamente in PREPARE_SILENTLY/WAIT/ASK_FOR_CONTEXT, senza spiegazioni libere o punteggi inventati. La priorità resta quella del reflex deterministico e non è una probabilità calibrata. Ogni parere è INFERRED. Le fonti non diventano fatti e il modello non può concedere permessi. Nel ciclo locale il parere viene chiesto soltanto nella fase `decide`, se il backend è esplicitamente abilitato; WAIT/ASK_FOR_CONTEXT fanno astenere il ciclo. Un parere favorevole non estende l'azione già ammessa: resta soltanto la registrazione di una nota locale. In `observe` la classificazione GGUF viene differita a questa fase, senza tentare di contattare il vecchio endpoint HTTP. Il backend HTTP preesistente rimane disponibile se non si configura un file GGUF.

Default della modalità GGUF:

- CPU, due thread, contesto di 4.096 token, nessun reasoning esteso;
- prompt massimo 3.000 byte, output massimo 64 token (configurabile fra 32 e 128);
- massimo dieci ammissioni al giorno per owner/namespace nel sidecar configurato (impostabile anche a zero);
- un'inferenza alla volta per sidecar, timeout del processo di 12 secondi (nel ciclo: al massimo budget della fase meno due secondi);
- output catturato massimo 32 KB, nessun log o prompt-cache permanente;
- pesi locali fino a 1 GB; nessun downloader o API a pagamento nel backend.

Il sidecar è una cartella diversa dall'archivio. Memorizza soltanto cache, ammissioni e lease, con limite di ammissione di circa 4 MB. La quota viene impegnata prima dell'inferenza e non rimborsata dopo timeout o crash. Eventi e contesti uguali, con medesima identità del modello e policy, usano il parere già salvato anche dopo il riavvio: zero nuovi token. Cambi di contesto o file modello invalidano la chiave; l'identità a runtime usa percorso, dimensione e data del file, mentre l'hash completo dei pesi viene verificato durante il provisioning.

Assenza del modello, errore o output malformato non autorizzano azioni aggiuntive: torna il comportamento deterministico del core. Un errore già valutato è conservato in cache, evitando tentativi ripetuti in background. Un crash dopo l'ammissione può lasciare un lease fino alla sua scadenza; non si azzera la quota. La terminazione forzata del processo host richiede supervisione OS per garantire l'arresto immediato di un figlio già avviato; il backend limita comunque generazione e contesto.

I saluti e le richieste di azioni esterne vengono risolti dal reflex prima di leggere archivi, creare il sidecar o caricare il modello. Il backend è spento per default. Non viene schedulata alcuna chiamata periodica.

## Chiamata esplicita

Usare una cartella nuova per lo stato e indicare owner/namespace dell'archivio:

```sh
cognitive-core --home /tmp/decision-state --owner ambrogio --namespace realtest-bridge \
  --local-model --model-gguf /percorso/candidato-validato.gguf \
  decide-local '{"kind":"question_open","question":"Quali verifiche servono per CLICS4 e clima?"}' \
  --archive /percorso/isolated-home
```

Per il ciclo locale configurare anche `--decision-state` fuori dalla home del core, insieme a `--local-model --model-gguf`. Il modello non risiede nella RAM dopo il comando; il sistema operativo può conservare pagine del file nella propria cache, che rimane reclamabile. Il caricamento a freddo paga di nuovo la lettura dei pesi per ogni nuova richiesta non in cache: è il compromesso scelto per evitare consumo residente.

Le quote di token e contesto non equivalgono a un limite rigido sulla RAM: il picco dipende dal runtime e viene misurato separatamente. Non viene imposto un limite di memoria OS né modificato il runner statistico.

## Applicazione dello studio interdisciplinare dell’11 novembre

Il self-model funzionale salva nel sidecar `self-model.sqlite3` una previsione prima dell’inferenza e un esito immutabile dopo. Le capacità vengono controllate prima dell’azione: se pesi, eseguibile o archivio non sono disponibili, la strategia cambia e non viene caricato alcun modello. L’esaurimento del budget di registrazione impedisce l’inferenza. La quota già riservata non viene rimborsata.

Le stime distinguono owner/namespace, identità del runtime, contesto, attore proprio/altrui ed episodi OBSERVED/SIMULATED. Prima di cinque esiti non viene esposta una probabilità empirica. Anche dopo, la stima resta non calibrata: misura il completamento del processo con schema valido, non l’accuratezza semantica. `SelfModel.export()` esporta episodi e provenienza in JSON `cognitive-self-v1`; la lettura rimane disponibile a budget esaurito. Nessuna modifica dei pesi avviene nel core.

Gli esperimenti separati su personalità, LoRA e probabilità quantum-inspired non sono attivati nel runtime. Il loro risultato è documentato in `validation/decision_study_20261111/REPORT_ESPERIMENTI_IT.md` del repository canonico. Sono prove sintetiche limitate, senza conclusioni su coscienza o vantaggio quantistico.
