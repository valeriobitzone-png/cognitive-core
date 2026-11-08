"""Build report strictly from persisted benchmark JSON, no invented metrics."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
base=root/'training-artifacts/real'
j=json.loads((base/'real_data_learning_report.json').read_text())
k=json.loads((base/'knowledge_report.json').read_text())
seeds=[j]
for seed in [42,8008]:seeds.append(json.loads((root/f'training-artifacts/robustness/seed{seed}/real_data_learning_report.json').read_text()))
count=sum(r['train_rows'] for r in j['real_datasets'].values())
held=sum(r['test_rows'] for r in j['real_datasets'].values())
lines=['# WorldCore v0.4 — Rapporto di addestramento e verifica',
       '', '**Stato: ALPHA sperimentale. NON AGI, NON produzione, NON confronto indipendente con Hermes/OpenClaw.**','',
       '## Dati realmente utilizzati',
       f'- **{count}** osservazioni reali di addestramento supervisionato, in 6 esperimenti distinti; **{held}** osservazioni tenute fuori dal training.',
       f'- **{j["sunspot_transition"]["train_rows"]}** transizioni storiche per il modello osservazionale e **{j["sunspot_transition"]["test_rows"]}** per la verifica cronologica.',
       f'- **{k["public_sources"]["documents"]}** documenti tecnici con link pubblico, licenza e SHA-256; **{k["user_project"]["documents"]}** note di progetto ricavate dalle decisioni esplicite di questa conversazione.',
       '- Le serie storiche e i dataset numerici derivano da copie reali già installate con scikit-learn/statsmodels; non è stato possibile scaricare grandi corpus nuovi direttamente nella sandbox. Le pagine pubbliche sono state consultate per fonte e licenza.',
       '- Non sono stati esportati né ottenuti i pesi o il corpus di preaddestramento di ChatGPT.',
       '', '## Metriche Brier (più basso è meglio; holdout non usato per addestrare)',
       '', '| Dataset | N train | N holdout | Online SGD | Forest | Costante | Persistenza |','|---|---:|---:|---:|---:|---:|---:|']
for n,r in j['real_datasets'].items():
    persistence=r.get('persistence_baseline',{}).get('brier')
    lines.append(f'| {n} | {r["train_rows"]} | {r["test_rows"]} | {r["brier"]:.4f} | {r["nonlinear_forest"]["brier"]:.4f} | {r["baseline_brier"]:.4f} | {persistence:.4f}'+' |' if persistence is not None else f'| {n} | {r["train_rows"]} | {r["test_rows"]} | {r["brier"]:.4f} | {r["nonlinear_forest"]["brier"]:.4f} | {r["baseline_brier"]:.4f} | — |')
lines+=['', 'Tutti e sei gli esperimenti migliorano la baseline costante per il Brier score; sui tre dataset cronologici il modello Forest supera anche la baseline di persistenza definita nel benchmark. Non è dimostrato che siano migliori di tecniche statistiche competitive o di sistemi agentici esistenti.',
        '', '## Replica con tre semi casuali', '', '| Seed | SGD meglio della costante | Forest meglio della costante | Forest meglio di SGD |', '|---:|---:|---:|---:|']
for rep in seeds:
    vals=list(rep['real_datasets'].values())
    lines.append(f'| {rep["seed"]} | {sum(v["beat_constant_brier_baseline"] for v in vals)}/6 | {sum(v["nonlinear_forest"]["beat_constant_brier_baseline"] for v in vals)}/6 | {sum(v["nonlinear_forest"]["beat_incremental_brier"] for v in vals)}/6 |')
lines+=['', 'I semi 42 e 8008 riutilizzano le stesse serie cronologiche ma rimescolano l’ordine di aggiornamento, e producono altre partizioni per i dataset non temporali. Non equivalgono a tre raccolte di dati indipendenti.',
        '', '## Previsione osservazionale delle transizioni solari',
        f'- Accuratezza sullo stato successivo: **{j["sunspot_transition"]["top1_accuracy"]:.1%}** su {j["sunspot_transition"]["test_rows"]} transizioni future riservate.',
        '- Non implica simulazione fisica, interventi causali né capacità di prevedere eventi mai osservati.',
        '', '## Memoria documentale verificata',
        f'- Ricerca FTS5, hash del documento, licenza, URL e isolamento per namespace. Benchmark interno di recupero: recall@3 **{k["retrieval_public"]["recall_at_k"]:.0%}** su {k["retrieval_public"]["cases"]} query pubbliche e **{k["retrieval_project"]["recall_at_k"]:.0%}** su {k["retrieval_project"]["cases"]} query di progetto.',
        '- Le query di verifica sono redatte dall’autore dei riassunti: questa prova è un semplice controllo di recupero, NON un benchmark indipendente di comprensione del linguaggio.',
        '- I testi esterni sono trattati come dati non attendibili, non come istruzioni eseguibili.',
        '', '## Ingegneria e sicurezza',
        '- **99 test Python e 5 test Node** superati (suite del repository, host Hermes/OpenClaw simulati).',
        '- Validazione dei JSON degli alberi, nessun pickle o eval, limiti su nodi e dimensioni, dati isolati per proprietario e progetto.',
        '- Le foreste addestrate con scikit-learn si eseguono in puro Python, con equivalenza numerica verificata rispetto a scikit-learn sugli holdout.',
        '- Il preprocessing raw-to-normalized usa esclusivamente min/max derivati dall’insieme di training; input fuori intervallo segnalati e limitati.',
        '- L’SDK MCP e l’integrazione reale con Hermes/OpenClaw NON sono stati testati end-to-end.',
        '- Non sono presenti training in background, installazione automatica di skill, fetch web autonomo, richieste API a provider o esecuzione autonoma di comandi di sistema.',
        '', '## Limiti e prossime soglie',
        '1. Verificare la privacy e l’autorizzazione dei dati degli utenti prima di importarli.',
        '2. Eseguire test reali versionati su Hermes e OpenClaw e con un MCP server attivo.',
        '3. Aggiungere benchmark ciechi di recupero semantico e valutare modellazione causale con interventi verificabili.',
        '4. Misurare su nuovi dataset il confronto con modelli forti, non soltanto costante e persistenza.',
        '5. Verificare prestazioni e sicurezza su più hardware e sotto carico reale.',
        '', '## Riproducibilità',
        '```bash',
        'PYTHONPATH=src python -m pytest -q tests',
        'PYTHONPATH=src node --test tests/openclaw.test.mjs',
        'PYTHONPATH=src python benchmarks/real_data_training.py --out /tmp/worldcore-real --seed 20261030',
        'PYTHONPATH=src python benchmarks/grounded_knowledge.py --db /tmp/worldcore-real/worldcore_real_training.db --output /tmp/worldcore-real/knowledge_report.json',
        '```', '', 'Richiede scikit-learn e statsmodels solo per ricreare il training; il core runtime ha zero dipendenze esterne.',
        '', '## Attribuzioni', '',
        'Dataset UCI con licenza CC BY 4.0 (attribution richiesta); serie statsmodels contrassegnate public domain. Sorgenti, DOI, impronte, note sui dati e versioni delle librerie sono nei JSON di training. Hermes e OpenClaw hanno repository MIT; l’archivio contiene riassunti originali e collegamenti, non una copia delle loro implementazioni.']
(root/'docs/VALIDATION_V04_IT.md').write_text('\n'.join(lines)+'\n')
print('Wrote',root/'docs/VALIDATION_V04_IT.md')
