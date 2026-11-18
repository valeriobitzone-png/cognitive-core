# Intelligence Feed e Cognitive Drive

Il briefing è una proiezione del lavoro del Core. Web, repository, desktop e
mobile usano lo stesso stimolo strutturato; questo runtime non installa sensori
su quei dispositivi e non avvia una raccolta continua.

Il percorso implementato è:

`stimolo → deduplica/provenienza → contesto del progetto → opportunità → WHAT IF esplicito → preparazione → verifica dell'operatore`

## Esempio eseguibile

```sh
python3 -m pip install ./runtime
cd runtime
PYTHONPATH=src python3 scripts/benchmark_intelligence_feed.py --output /tmp/feed-benchmark.json
```

Il fixture contiene 12 eventi inventati e marcati come tali: cinque candidati
rilevanti, rumore, duplicato, osservazione futura, arrivo tardivo, notizia vecchia
e candidato scartato. Le etichette di valutazione non entrano nell'API del feed.
La prova verifica i cinque risultati attesi, il WHAT IF senza modifica dello
stato, il limite di capacità e la registrazione di un esito. Non è un benchmark
su notizie vere, né dimostra di trovare ciò che un utente giudicherebbe utile.

Per registrare contesto e stimoli reali, usando solo dati autorizzati:

```python
from datetime import datetime, timezone
from cognitive_core import CognitiveCore, Settings

core = CognitiveCore(Settings(home='./dati', owner='local', namespace='progetto'))
try:
    core.drive.upsert_project('core', 'Cognitive Core',
                             ['runner', 'checkpoint', 'recovery'], importance=1)
    result = core.observe({
        'kind': 'stimulus',
        'source_kind': 'github',
        'source_ref': 'https://example.org/candidate',
        'occurred_at': datetime.now(timezone.utc).isoformat(),
        'title': 'Runner checkpoint recovery',
        'summary': 'Esempio inventato: componente da studiare prima di valutarne l’utilità.',
    })
    print(core.drive.briefing(limit=5))
    print(core.drive.prepare(available_capacity=0.8, limit=1))
finally:
    core.close()
```

La preparazione mette in coda **soltanto la lettura di fonti HTTPS**. Non clona
o esegue codice di repository, non manda notifiche, non invia mail. Per leggere
effettivamente le fonti, il chiamante usa `work_once` con web attivato,
allowlist e budget. Riferimenti desktop/mobile richiedono adattatori di lettura
del rispettivo host; una URI locale non diventa un comando.

## Priorità, confidenza e memoria

Il collegamento è lessicale sui termini dei progetti registrati. La priorità
è `rilevanza lessicale × 0,5 × importanza del progetto`, con soglia 0,1 per
proporre un candidato. Il valore 0,5 è un prior fisso non calibrato, uguale
per tutte le fonti: non è una misura verificata della loro attendibilità.
`confidence` resta `null`. La novità vale uno alla prima acquisizione; un
duplicato non genera un'altra opportunità o un aumento della credibilità.

I richiami della memoria conservano i loro identificatori come riferimenti
di contesto. La presenza di un ricordo non verifica la fonte. Le istruzioni
eventualmente contenute in un testo esterno rimangono testo non affidabile;
il payload non può fornire permessi, confidenza o un progetto fidato da usare
in sostituzione del contesto dell'host.

WHAT IF richiede ipotesi esplicite del chiamante:

```python
result = core.drive.compare(opportunity_id, [
    {'id': 'attendi', 'actions': []},
    {'id': 'studia', 'actions': [{'op': 'set', 'key': 'costo_assunto', 'value': 1}]},
], objectives=[])
```

La simulazione è del motore WorldCore, resta distinta da una previsione
empirica e non conferisce autorità di esecuzione. Il valore di un esperimento
non viene inventato per dare automaticamente il via libera a un'opportunità.

## Tempo, capacità e verifica

Il briefing filtra sia l'ora dell'evento sia l'ora in cui il Core lo ha ricevuto.
Le decisioni e i collegamenti WHAT IF hanno una cronologia: una scelta o
simulazione successiva non compare in una proiezione precedente. Le fonti
aggiunte dopo il cutoff sono escluse. Il fixture usa un orologio di replay
controllato; nell'ingresso stdio non è disponibile l'override di quell'orologio.

La capacità viene fornita dall'host in `0..1`, non inferita dal sistema operativo.
Sotto 0,5 non si prepara alcun lavoro. Le iniziative preparate hanno un limite
giornaliero e transazioni atomiche; due worker non preparano due volte la
stessa opportunità. Lo scarto revoca anche l'eventuale lavoro collegato.

`record_outcome(id, useful=True, evidence_ref='...')` registra un feedback
`operator_reported`. Non lo dichiara una verifica indipendente e non aggiorna
automaticamente alcun modello. La raccolta di valutazioni umane indipendenti
resta necessaria prima di misurare precisione reale e calibrazione.

## Interfacce

La CLI aggiunge `project`, `feed`, `opportunities`, `briefing`, `prepare`,
`review`, `opportunity-whatif` e `outcome`; `--help` descrive gli argomenti.
Il worker vincolato all'host espone `cognitive_feed_ingest`,
`cognitive_opportunities` e `cognitive_briefing`. Configurazione dei progetti,
capacità, preparazione e feedback restano nel percorso esplicito Python/CLI
dell'operatore. Nessun orario o servizio di briefing viene attivato dal pacchetto.
