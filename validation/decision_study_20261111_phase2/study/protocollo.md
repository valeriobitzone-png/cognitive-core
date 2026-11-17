# Ricerca estesa, fase 2 — 11 novembre 2026
Soglia utente: almeno25/34 sul test storico, accuratezza raw del modello prima del governor. Nessuna sostituzione automatica del sistema di produzione.
Ricerca: router specializzati e candidati più capaci 1–4B, preferenza pesi ufficiali, nessuna RAM residente e un solo processo di inferenza attivo alla volta.
Il test storico è ormai noto: usarlo soltanto come regressione, non chiamarlo nuova validazione indipendente. Nessuna etichetta del test è inserita nel prompt.
Protocollo V1 identico al precedente (CPU2,2048 contesto,64output,timeout20). Protocollo V2, se necessario, chiarisce priorità della policy ed esempi presi esclusivamente dal train. Scelta del protocollo su dev16, quindi congelamento prima delle nuove misure. I risultati V1/V2 sono separati e non attribuiti solo al cambio di pesi.
Conferma del candidato: nuova batteria sintetica congelata prima della scelta del protocollo, con richieste italiane e inglesi, scope, fonti non fidate, permessi e consenso. Test nuovo mai usato per ottimizzare prompt.
Risorse massime di studio: nuovi download6GB,1500sec ciascuno; CPU2; nessun server; timeout per caso20sec V1/30sec V2; inferenze one-shot; tempo complessivo di prove<=90min. Nessuna chiamata a pagamento o modifica a originali.

Rettifica del parametro registrato: il codice di fase2 ha usato timeout30s anche in V1; il piano iniziale diceva20s. Prompt,CPU2,contesto2048 e64token sono quelli originari, ma non si dichiara parità stretta del tempo massimo con la prima campagna. Nessun output viene riclassificato per nascondere questa differenza.
