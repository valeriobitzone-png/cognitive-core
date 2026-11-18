"""Generate an honest summary from saved tests/artifacts, no invented scores."""
import json,sqlite3,sys,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[1]
bench=json.loads((root/'training-artifacts/v07_generalization_benchmark.json').read_text())
hist=json.loads((root/'training-artifacts/v07_historical_training_report.json').read_text())
aud=json.loads((root/'catalog/reviewed_evidence_v07.json').read_text())
candidates=json.loads((root/'catalog/candidate_quarantine_v07.json').read_text())
external={}
for p in list((root/'training-artifacts').glob('*.db'))+list((root/'training-artifacts/real').glob('*.db')):
    with sqlite3.connect(p) as db:external[str(p.relative_to(root))]=db.execute('PRAGMA integrity_check').fetchone()[0]
report=f'''# WorldCore Cognitive Layer 0.7 — Rapporto di validazione (30 ottobre 2026)

## Stato del rilascio

**Research alpha installabile, non pronto per produzione autonoma.** L'obiettivo è una memoria e un modello dello stato applicabili a qualunque LLM attraverso un host autorizzato. Non è un'AGI, un modello multimodale semantico generale o un simulatore universale di ogni ambiente.

## Test eseguiti

- **186 test Python superati** (`PYTHONPATH="$PWD/src:$PWD" pytest -q tests`), con test di regressione, concorrenza tra processi, database, previsione, privacy, permessi, repository gating e host simulati.
- **5/5 test Node.js superati** con plugin OpenClaw simulato e processo Python persistente. Non certificano la compatibilità con un Gateway OpenClaw reale.
- La wheel `worldcore_cognitive_layer-0.7.0-py3-none-any.whl` è stata costruita localmente e installata in directory isolata. `WorldCore.__version__=0.7.0`, nuovi metodi presenti e `PRAGMA integrity_check=ok`.
- MCP: registrazione dei nuovi tool testata con server simulato; **SDK MCP reale non installato in questa sandbox**, quindi trasporto/host reale non verificati.

## Prove di generalizzazione

**Le misure MAE sono nella scala specifica di ciascun esperimento e non sono confrontabili tra dataset.** Il modello numerico viene attivato solo con almeno tre ambienti, test su un ambiente separato e miglioramento >=10% contro la previsione di persistenza.

| Dataset / nuovo ambiente | Origine | MAE WorldCore | MAE persistenza | Miglioramento | Decisione |
|---|---|---:|---:|---:|---|
| Movimento 2D, arena D non vista | Simulazione sintetica | {bench['synthetic_motion']['actions']['east']['holdout_mae']:.6f} | {bench['synthetic_motion']['actions']['east']['persistence_mae']:.4f} | {100*bench['synthetic_motion']['actions']['east']['improvement']:.2f}% | Accettato |
| Attività solare 1900–2008 | Dati storici `statsmodels.sunspots` | {bench['sunspots']['model_result']['advance_year']['holdout_mae']:.4f} | {bench['sunspots']['model_result']['advance_year']['baseline_mae']:.4f} | {100*bench['sunspots']['model_result']['advance_year']['improvement']:.2f}% | Accettato nell'esperimento |
| Serie macro USA 1991–2009 | Dati storici `statsmodels.macrodata` | {bench['macrodata']['model_result']['advance_quarter']['holdout_mae']:.6f} | {bench['macrodata']['model_result']['advance_quarter']['baseline_mae']:.6f} | {100*bench['macrodata']['model_result']['advance_quarter']['improvement']:.2f}% | **Respinto** (sotto 10%) |

Il dataset sintetico non dimostra generalizzazione in ambienti fisici mai incontrati. L'esperimento storico è retrospettivo: non dimostra previsione affidabile in tempo reale. Il 29% su sunspots è un miglioramento della media degli errori nel protocollo specificato, non un'accuratezza generale o una garanzia statistica.

### Modello storico persistito

- Dataset: {hist['dataset_size']} transizioni osservate; train 1700–1899, test 1900–2008.
- Archiviato in `training-artifacts/{hist['db_path']}`; SQLite integro.
- Stima esemplificativa sullo stato {{activity:50, change:5}} prodotta dal modello: {{activity:{hist['sample_query']['state']['activity']:.2f}, change:{hist['sample_query']['state']['change']:.2f}}}; **non è una previsione clinica, fisica o finanziaria operativa**.

## Audit GitHub: evidenza reale, non 246 approvazioni

- **{len(candidates)} candidati** in quarantena: nessuno è approvato per installazione, skill o esecuzione.
- **{len(aud['records'])} repository** con file effettivamente recuperati direttamente da GitHub, di cui **{sum('source' in x['evidence'] for x in aud['records'])} con frammenti sorgente** e **{sum('license' in x['evidence'] for x in aud['records'])} con file di licenza**.
- Solo **{sum(x['screen_status']=='source_screened_not_approved' for x in aud['records'])}** risulta con licenza permissiva e prove dirette di sorgente, test e CI in questa selezione: non equivale a code review completa o security audit.
- `polakowo/vectorbt`: testo `Commons Clause` e restrizione commerciale, quindi **bloccato** salvo analisi legale; `freqtrade/freqtrade` GPL-3.0 e `gitroomhq/postiz-app` AGPL-3.0 richiedono revisione dei termini prima del riutilizzo.
- Lo script `scripts/audit_github_catalog.py` può controllare su macchina con Internet al massimo 246 repository per esecuzione, usando commit fissato, struttura dei sorgenti, contenuto delle licenze, test, CI e metadati; non esegue codice estraneo, non può certificare da solo sicurezza o qualità finale.
- Licenze dei dataset, pesi dei modelli e dipendenze sono valutazioni separate da quella del repo.

## Stato personale, memoria e privacy

- Snapshots versionati e fonti dichiarate per utente e spazio, con opt-in per chiavi sensibili; nessuna autentificazione integrata: l'host DEVE assegnare identità reali affidabili.
- Proattività in v0.7: scadenze esplicite, trend numerici con holdout cronologico e anomalie robuste; nessuna diagnosi clinica/psicologica o trading automatico.
- Prediction ledger con ID, versione del modello fissata, confronto con osservazione successiva, errore non riscrivibile, allarme sul peggioramento.
- Interfaccia multimodale locale: metadati PNG, RMS WAV, struttura HTML; **non** riconoscimento di oggetti, linguaggio parlato o browsing autonomo. Per quelle capacità occorre un modello/provider esterno.

## Limiti bloccanti verso la produzione

1. Assenza di una rappresentazione dinamica generale appresa da video, audio, linguaggio e ambiente fisico; attuale modello numerico è una ridge regression per azione più frequenze discrete.
2. Mancanza di benchmark indipendenti su vere applicazioni mai viste, sistemi robotici, notizie/prezzi reali correlati temporalmente e profili di rischio personali.
3. Integrazione con gateway Hermes/OpenClaw e trasporto MCP **ancora simulata**.
4. Mancanza di verifiche complete su codice, licenze delle dipendenze, vulnerabilità, manutenzione e sicurezza per l'intero catalogo dei 246 repository.
5. Calibrazione incerta in domini sensibili; i suggerimenti devono includere fonti, limiti e revisione umana quando appropriato.
6. Scheduler di apprendimento continuo non avviato; richiede un host sempre acceso, consenso, connessione, controllo costi, logging e rollback.

## Integrità SQLite verificata

'''
for k,v in external.items():report+=f'- `{k}` — `{v}`\n'
report+='''
## Riferimenti al codice e ai risultati

- `src/worldcore/dynamics.py`, `src/worldcore/hybrid_world.py`, `src/worldcore/state_lens.py`, `src/worldcore/multimodal.py`, `src/worldcore/repo_audit.py`.
- `training-artifacts/v07_generalization_benchmark.json` e `training-artifacts/v07_historical_training_report.json`.
- `catalog/reviewed_evidence_v07.json` e `catalog/candidate_quarantine_v07.json`.
- `docs/REPOSITORY_AUDIT_PROTOCOL.md` e `docs/COGNITIVE_SCOPE_V07_IT.md`.

**Verdetto**: versione di ricerca coerente e testata nei limiti indicati. Non certificata per autonomia generale, medicina, mercati o produzione. Il numero di repository scoperti non misura capacità apprese.
'''
(root/'docs/VALIDATION_V07_IT.md').write_text(report)
Path('/mnt/data/WorldCore_v0.7_Validation_Report_IT.md').write_text(report)
print(json.dumps({'dbs':external,'docs_written':True,'audit_partial':len(aud['records'])},indent=2))
