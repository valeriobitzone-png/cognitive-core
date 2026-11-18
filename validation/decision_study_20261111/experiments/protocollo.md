# Protocollo congelato prima del confronto locale
11 novembre 2026. Origine dei dati: SIMULATED / fixture manuali; nessun dato personale o database originale viene modificato.

## Selezione del modello
Nessun modello è selezionato prima dei risultati. Qwen3.5-0.8B è un controllo generico. Candidati locali: LiquidAI LFM2.5-350M (strutture/tool use), IBM Granite4.0-350M (tool use), FunctionGemma270M (specialista function calling). Quest'ultimo richiede protocollo nativo e viene valutato separatamente anche in tale protocollo; un risultato in JSON comune non è una misura sufficiente della sua capacità nativa. I benchmark pubblici di autori diversi non sono direttamente una graduatoria unica. Italiano, astensione, permessi e cambio degli strumenti vanno verificati qui.

Compito principale: scegliere la prossima azione fra WAIT, REMEMBER, LOCAL_RESEARCH, WEB_RESEARCH, ASK_CLARIFICATION, REQUIRE_APPROVAL, osservando richiesta, fonti disponibili, capacità, consensi e budget. Non basta giudicare la pertinenza. Nessuna azione proposta viene eseguita; i test delle conseguenze usano un simulatore chiuso. Baseline: policy a regole, classificatore statistico TF-IDF/logistico, e nessun modello. Si riportano macro-F1/accuratezza, proposte non consentite prima del governor, astensione, latenza a freddo e memoria. I risultati dopo il governor sono separati: la sicurezza non viene attribuita al modello se è garantita dal codice.

Prompt/API e casi di verifica sono congelati prima di valutarli. Train, sviluppo e verifica sono separati per famiglia/formulazione, con casi IT/EN e distrattori. Non si aggiustano prompt o pesi sui risultati del test. Le differenze tra formati nativi sono dichiarate; gli errori di parsing/runtime contano come fallimenti, non vengono esclusi. Il test piccolo serve come screening, non certifica affidabilità generale. Se nessuno supera le condizioni minime, nessun modello riceve autonomia di produzione.

## Modello di sé
Previsione precedente distinta da esito osservato. Confronti B memoria, C stato proprio, ablazione dello stato utile e perturbazione irrilevante comparabile; osservatore esterno con le stesse informazioni. Non attribuire vantaggio introspettivo se l'osservatore ottiene lo stesso risultato. Gli esiti SIMULATED non contaminano gli stimatori OBSERVED. Brier, attribuzione sé/altro e ripresa si misurano su episodi non usati nel fit.

## Personalità
Preferenze funzionali nelle scelte fra costo, evidenza e progresso. Manipolare il profilo e l'ordine delle alternative; misurare stabilità, compromessi e violazioni, non frasi in prima persona. Regole di autorizzazione identiche per ogni profilo. Separare test di una policy costruita da osservazioni del comportamento dei modelli.

## LoRA
Vera ottimizzazione di matrici a rango ridotto su un modello compatto, se supportata dal runtime presente. Pesi di base immutabili; adapter separati. Dataset sintetico di routing/attribuzione, nessuna ricompensa per dichiarazioni di coscienza. Confronto stesso modello+prompt, stesso modello+contesto e stesso modello+LoRA; test non visto, due o più semi se possibile, budget di passi esplicito. Risultato negativo o mancanza di generalizzazione viene conservato. Nessun adapter sperimentale sostituisce automaticamente il modello operativo.

## Quantum-inspired
Piccolo modello proiettivo 2D, dati sintetici con ordine A/B. Confronti: classico statico, classico dinamico con memoria e versione classica equivalente a pari numero di parametri. Almeno tre generatori (quantum-inspired, dinamico classico, indipendente), dieci semi, train/valid/test distinti. Log-loss su holdout e complessità; intervalli sulle differenze fra semi. L'equivalenza con un modello classico è un risultato valido. Nessun vantaggio quantistico fisico o coscienza è inferito.

## Budget e preservazione
Download nuovi sotto2GB aggiuntivi per i checkpoint principali, hash/revisioni verificati. Esperimenti finiti, un modello attivo alla volta, timeout per inferenza e per run. Nessuna API a pagamento, nessun servizio residente, nessuna esecuzione di strumenti reali, nessun arresto del runner statistico AMBRO. Artefatti in questa cartella, con log anche dei fallimenti.
