# Ripresa durevole — 1.4.0rc3

Sono stati riprodotti cinque difetti del runtime precedente e aggiunte prove
che fallivano prima della correzione:

1. Un blocco di policy durante la ripresa sostituiva il checkpoint con il solo
   motivo del blocco, perdendo documenti, completamenti e budget per job.
2. KeyboardInterrupt durante l'acquisizione poteva lasciare aperta la transazione.
3. Dopo un crash finale, una ricerca già interamente raccolta poteva restare
   bloccata dal budget, pur non richiedendo più alcun accesso alla rete.
4. Gli URL scoperti non erano conservati: una ripresa ripeteva la ricerca.
5. Stato finale e registro dell'esperienza erano salvati separatamente.

I test verificano conservazione del progresso, rollback, ripresa sugli URL
originali, finalizzazione senza nuove richieste e atomicità del registro.
Una sesta prova avvia un processo worker, aspetta il checkpoint durevole,
lo termina forzatamente e verifica la riacquisizione dopo la scadenza del lease.
La terminazione è reale; il lavoro e il tempo di lease sono controllati dal test.

`runtime/scripts/validate_feed_live.py --allow-public-web --output risultato.json`
verifica anche il ciclo reale su una sola pagina pubblica Python: evento,
opportunità, WHAT IF esplicito, preparazione, due richieste, documento con hash,
registro dell'esperienza e confronto con l'esito osservato. Non usa account
personali o modelli e non inferisce l'utilità soggettiva per un utente.

La prima esecuzione dell'harness aveva un nome di provenienza non supportato
ed è stata rifiutata dal motore; la raccolta era già riuscita. È stato corretto
il chiamante usando l'enumerazione esistente `host_verified`, senza allargare
le autorizzazioni del motore. Le prove fallite sono conservate nel rapporto
locale insieme a quelle finali.
