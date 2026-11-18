# Memoria e riflessione: contratto dopo l’audit del 12 novembre 2026

La memoria contiene asserzioni attribuite a una fonte, non fatti automaticamente verificati. Il retrieval operativo etichetta queste asserzioni `INFERRED`, `verified=false`. Esclude revisioni future, ritirate, soppresse e ipotesi generate internamente. Le ricerche esplicite di cronologia e le letture dirette restano disponibili all’operatore.

Le nuove revisioni non riscrivono la validità delle precedenti. La lettura distingue tempo del mondo (`valid_at`) e tempo di conoscenza (`known_at`). La tabella aggiuntiva `mem_order` conserva l’ordine delle revisioni anche durante export/restore. I dati legacy sono conservati: si aggiunge solo l’ordine mancante. La precisione storica dei timestamp resta al secondo; l’ordine disambigua le revisioni ma non ricrea tempi che non erano stati registrati.

Ricerca, grounding, contesto di curiosità e riflessione condividono i filtri di visibilità. Una prova già raccolta viene respinta se la memoria viene ritirata, soppressa, sostituita o alterata. Le dipendenze delle nuove ipotesi comprendono ID, progetto e hash. Le vecchie ipotesi senza dipendenze strutturate rimangono leggibili, ma non possono superare il controllo di grounding.

`dream.promote(..., evidence_id=...)` richiede autorità interattiva, una evidenza esistente nello stesso namespace, la corrispondenza esatta dell’ipotesi e una citazione letterale da un documento integro. Una semplice etichetta di verificatore viene respinta. Il risultato è `source_backed`, con `semantic_truth_verified=false`: l’attendibilità indipendente della fonte non è dimostrata da questa operazione. Non viene eseguito alcun verificatore esterno.

I limiti sono: 10.000 revisioni per namespace, valore entro `max_text_bytes`, ammissione vincolata al budget disco, 128 candidati per ricerca, 2 MB di contenuti per lettura e massimo 2 secondi (o `max_cycle_seconds`, se inferiore), incluso il controllo durante le istruzioni SQLite. Il superamento produce astensione tramite errore esplicito. Sono limiti applicativi, non un limite fisico di RAM imposto dal sistema operativo. I dati più vecchi non vengono cancellati automaticamente.

Export e restore comprendono le tabelle di memoria e accettano anche gli export precedenti che ne sono privi. Il restore richiede sempre una nuova destinazione e non ripristina i permessi di esecuzione.

Queste correzioni non attivano modelli, rete, servizi residenti o chiamate a pagamento. Il modello locale resta opzionale e disattivato per impostazione predefinita.
