# Stato delle verifiche — Cognitive Core v0.1

**Data di riferimento del materiale:** 7 novembre 2026  
**Fonte:** rapporto di prova allegato al pacchetto descrittivo del prototipo v0.1.

Questo documento riassume in forma narrativa gli esiti dichiarati. Non pubblica codice di test né istruzioni di esecuzione.

## Esito complessivo

Il materiale riporta **22 prove automatiche** eseguite con esito positivo complessivo (OK), in circa 0,16 secondi sul sistema usato per la prova.

È inoltre dichiarato un **benchmark decisionale** su **16 casi sintetici redatti a mano**, con accuratezza 1,0 sulla baseline deterministica, latenza mediana dell'ordine del millisecondo e **zero chiamate a modelli**. Il materiale stesso precisa che si tratta di esempi inventati e dichiarati per regressioni, non di una misura attendibile su distribuzioni reali.

## Aree coperte dalle prove dichiarate

Le prove elencate nel rapporto riguardano, tra l'altro:

| Area | Cosa risulta verificato nel rapporto |
|---|---|
| Budget e costi | Budget atomico rispettato; impossibilità di abilitare chiamate a pagamento |
| Reflex e saluti | Saluto senza database né modello; saluti triviali multilingue |
| Azioni esterne | Azione esterna che richiede approvazione; accesso web negato senza permesso esplicito |
| Ricerca web | Ricerca bloccata di default; rifiuto di IP locali e di HTTP non sicuro |
| Worker e continuità | Worker limitato con ricerca simulata e checkpoint; job in lease dopo crash riprendibile; topic in pausa non in lease; scarto che annulla |
| Memoria e claim | Importazione Markdown; ricerca ed export; claim che non diventano *tested* solo perché collegati a una fonte |
| World / predizioni | Rami ipotetici che non mutano il mondo; predizioni confrontate con gli outcome (punteggio) |
| Sessione e job | Passaggio da fine sessione a job |
| Visione e parsing | Modello di visione che richiede loopback; parser web che restituisce metadati immagine senza inventare una visione |
| Apprendimento | Esempi di apprendimento solo dopo revisione |
| Isolamento | Namespace di workspace isolati |

## Lettura cauta

Queste verifiche descrivono il comportamento dichiarato del prototipo v0.1 in ambiente di prova controllato. Non sostituiscono prove su telefono reale, su rete pubblica senza allowlist, né validazioni scientifiche dei contenuti recuperati dal web.
