# Correzioni Cognitive Core — 12 novembre 2026

Gli otto difetti confermati dall’audit sono corretti e installati nel repository canonico `/Volumes/AMBRO/projects/CognitiveCore/cognitive-core`, branch `feature/intelligence-feed-runtime`. Non è stato creato un commit. Le modifiche preesistenti dell’utente sono state conservate.

## Prima e dopo

| Difetto dell’audit | Comportamento dopo la correzione |
|---|---|
| Export con memoria non ripristinabile | Schema memoria inizializzato dal Vault; export/restore comprendono fatti, soppressioni e ordine delle revisioni. Compatibilità con export precedenti senza queste tabelle. |
| Promozione con una semplice stringa, anche autonoma | Autorità interattiva obbligatoria, evidence ID esistente nello stesso namespace, ipotesi esatta, citazione letterale e hash del documento. Risultato `source_backed`, mai verità verificata. |
| Nuova memoria sovrascrive la validità storica | Revisioni aggiuntive senza riscrivere gli intervalli precedenti; validità derivata alla lettura, con tempo del mondo e tempo di conoscenza distinti. |
| Revisioni future mostrate come correnti | Filtri temporali applicati anche a ricerca e contesto operativo. Gestione delle asserzioni retrodatate. |
| Soppressione aggirata da grounded e dream | Visibilità condivisa fra ricerca, grounding, retrieval, curiosità e riflessione. Lettura esplicita e cronologia restano disponibili. |
| Progetto estraneo può sostituire una dipendenza | Nuove dipendenze strutturate con ID, progetto, chiave e hash; rifiuto di sostituzioni e fonti ritirate. |
| Nuova memoria assente dal ciclo | Integrata nel retrieval unificato e nel contesto di curiosità; verifica di integrità prima dell’uso. Prova reale con sola memoria condivisa fino al checkpoint del ciclo. |
| Letture/scritture prive di limiti | Budget disco prima della scrittura, valori entro `max_text_bytes`, 10.000 revisioni per namespace, massimo 128 candidati, 2 MB per lettura, scadenza applicativa di massimo 2 secondi anche durante SQLite. |

Le ipotesi generate internamente sono escluse dal retrieval operativo ordinario e dall’inventario delle fonti. Ripetere la stessa riflessione non crea nuove copie. La memoria condivisa mantiene l’etichetta `INFERRED`, `verified=false`. Nessuna ipotesi viene promossa automaticamente a fatto.

## Verifiche eseguite

- Suite completa finale su copia: **620 test Python superati**, **12 controlli Node superati**, **53/53 gruppi**, nessun fallimento. Baseline audit: 586 Python e 12 Node; aggiunte **34 regressioni**.
- Due esclusioni già presenti: valutazione browser senza Playwright e desktop senza Xvfb.
- Nuove regressioni: export recente/precedente, migrazione additiva legacy, revisioni nello stesso secondo, cronologia e retrodatazione, fonti false/corrotte/estranee, conflitti, autorizzazioni, isolamento owner/namespace, soppressione, query e valori fuori budget, Unicode, duplicati, invalidazione delle prove già raccolte e ciclo operativo.
- Arresto forzato di un processo di test durante una transazione: al riavvio conservato il dato confermato, annullato quello pendente; `integrity_check=ok`, nessun ordine orfano.
- Wheel costruita offline, senza dipendenze esterne: **65 moduli identici ai sorgenti**. Prove isolate Python **3.11.15** e **3.12.13**: memoria temporale, retrieval, soppressione ed export/restore su directory temporanee.
- Dopo l’installazione: **98 test mirati superati** dal repository canonico, usando solo database temporanei. `git diff --check` passa.
- Rollback completo verificato su copia temporanea; verificato anche il rifiuto del rollback se un file è stato modificato successivamente.

I log e gli esiti strutturati sono in `release-tests.json`, `release-tests_logs/`, `test-counts.json`, `wheel-check.json`, `integrity-after.json`. I precedenti log di sviluppo sono diagnostici e non sostituiscono l’esecuzione finale.

## File installati

1. `runtime/src/cognitive_core/memory.py`
2. `runtime/src/cognitive_core/dream.py`
3. `runtime/src/cognitive_core/vault.py`
4. `runtime/src/cognitive_core/portable.py`
5. `runtime/src/cognitive_core/engine.py`
6. `runtime/src/cognitive_core/curiosity.py`
7. `runtime/tests/test_memory_dream.py` — aggiornata l’aspettativa insicura di verifica tramite sola stringa.
8. `runtime/tests/test_memory_audit_regressions.py` — nuovo.
9. `runtime/docs/MEMORY_AUDIT_FIXES_20261112_IT.md` — nuovo.

Prima di scrivere sono stati confrontati gli hash dei **362 file** dell’inventario iniziale: nessuna modifica concorrente. Sette file esistenti aggiornati e due aggiunti; gli altri **355 file** controllati sono invariati. Backup e manifest con hash prima/dopo:

`/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/validation/memory_fixes_20261112/`

Il programma `rollback.py` nella stessa cartella richiede esplicitamente il repository e la cartella di backup. Controlla gli hash prima di ripristinare e conserva i file ritirati. Non è stato eseguito sul repository originale.

## Preservazione e limiti

L’installazione non ha aperto database di produzione. Le prove e le migrazioni sono state eseguite esclusivamente su fixture e copie. La tabella aggiuntiva `mem_order` viene inizializzata alla successiva apertura ordinaria del Vault: non riscrive valori o intervalli delle asserzioni esistenti.

Tutti i **13 file protetti** verificati coincidono con gli hash dell’inventario precedente all’unificazione. Il runner statistico originale **PID 32703** è ancora attivo con `runner.py --loop`; non è stato fermato, modificato o riavviato. Questa verifica riguarda i file inventariati; i risultati che il runner continua a produrre non vengono dichiarati immutabili.

Nessun modello è stato avviato, nessun servizio residente aggiunto, nessuna chiamata a pagamento effettuata. Le impostazioni del modello locale, disattivato per default, non sono state cambiate.

La storia legacy mantiene la precisione originaria al secondo. L’ordine aggiuntivo disambigua revisioni ma non può ricostruire tempi di conoscenza mancanti. Le vecchie ipotesi prive di dipendenze strutturate rimangono conservate, ma non superano il nuovo grounding.

Una citazione prova il contenuto della fonte, non la sua attendibilità indipendente né la verità semantica. I limiti di lettura sono applicativi, non un limite fisico di RAM imposto dal sistema operativo. Al limite di 10.000 revisioni l’ammissione si arresta: non viene cancellata automaticamente la storia. La ricerca fra candidati limitati non garantisce di trovare il migliore risultato nell’intero archivio.

Restano attività distinte, non risultati acquisiti da queste correzioni: valutazione longitudinale reale progresso/costo, scelta sperimentale del decisore neurale rispetto alle regole, visione, voce, Moltis e apprendimento di nuove competenze. Il ciclo resta utilizzabile senza modello residente; eventuali ulteriori modelli vanno confrontati su prove separate e attivati solo su richiesta. Coscienza e neuromodulazione biologica non sono state dimostrate.
