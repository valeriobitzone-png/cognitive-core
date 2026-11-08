# WHAT IF — Specifica indipendente per WorldCore 1.1

**Nessuna dipendenza da orchestratori, divisioni o prodotti di terzi.** WHAT IF è soltanto il metodo di ragionamento controfattuale: osservare lo stato, formulare alternative, simulare, cercare punti di fallimento, presentare incertezza, ottenere autorizzazioni dall'host e verificare l'esito osservato.

## Confini epistemici

1. **Stato osservato:** dati versionati realmente registrati da un host autenticato.
2. **Ipotesi:** modifiche `set/add/delete` sono effetti *assunti* e non conoscenza causale, anche quando producono risultati numerici esatti.
3. **Dinamica stimata:** un modello `world` può simulare soltanto se sono disponibili osservazioni sufficienti e un modello compatibile; altrimenti si astiene.
4. **Alternative non realizzate:** non possono essere osservate contemporaneamente; il replay misura soltanto lo scarto fra previsione ed esito della scelta effettuata.
5. **Consenso:** simulare non autorizza alcuna modifica reale. Ogni esecuzione resta compito del framework ospitante e del suo gestore di permessi.

## Le cinque funzioni

- `compare_futures`: **Multiverse / Failure Futures**. Scenari da uno stesso snapshot, obiettivi dichiarati, soglie di fallimento, ranking *relativo* con copertura dei dati. Non esegue azioni.
- `whatif_backcast`: **Future Backcasting**. Ricerca in ampiezza limitata a 1–5 passaggi entro un budget di 2.000 stati. Obiettivo numerico e azioni dichiarate, cross-check con il simulatore di produzione. Restituisce un *piano ipotetico*, non l'esecuzione.
- `whatif_stress_test`: **Robustness / Unknown-Unknown reminder**. Applica perturbazioni dichiarate a piani identici, confronta lo scenario peggiore. Le perturbazioni non sono probabilità stimate.
- `verify_whatif`: **Outcome Verification**. Associa una sola osservazione al ramo effettivamente scelto; è immutabile. `host_verified` richiede fiducia nella chiamata dell'host; i tool MCP pubblici marcano `user_reported`.
- `whatif_replay`: **Decision Replay**. Conserva gli errori osservati e marca gli altri rami come non osservabili. Nessuna deduzione causale automatica.

`Shadow Evolution` e `Discovery Frontier` sono ancora temi di ricerca, non moduli con prestazioni dimostrate.

## Esempio concreto (Python)

```python
from worldcore import WorldCore

with WorldCore('example.db') as core:
    core.set_state('user-1', 'available_hours', 5)
    core.set_state('user-1', 'remaining_tasks', 4)
    result = core.whatif_backcast('user-1', 'Finire tutte le attività entro sera',
        {'remaining_tasks': {'op':'<=','value':0}},
        [{'op':'add','key':'remaining_tasks','value':-1}],
        max_depth=4)
    assert result['action_executed'] is False
    print(result['status'], result['plan'])
```

**Scenari da non automatizzare senza altre evidenze:** diagnosi mediche, decisioni finanziarie, psicologia individuale, spostamenti basati su ETA non verificati, operazioni irreversibili, installazioni di codice sconosciuto. WHAT IF può aiutare a esplorare opzioni e domande, non a creare autorità o certezza.

## Connessione con gli LLM

L'LLM ospitante traduce domande naturali in `question`, `objectives`, `scenarios`, `failure_conditions`, `target` e `candidate_actions` JSON. WorldCore controlla formato, isolamento e limiti, esegue simulazione locale, conserva l'esito e restituisce evidenze. L'LLM valuta e spiega la risposta, senza che WorldCore sia legato ai suoi pesi.

La disponibilità di uno strumento MCP non prova che la versione corrente dell'LLM sappia formulare scenari coerenti; servono benchmark end-to-end con modelli autenticati sui client reali.
