# Cognitive Core + WorldCore 1.4.0rc3

This distribution combines the supplied Cognitive Core 0.1 (MIT) with the
existing WorldCore 1.3.0rc3 engine (Apache-2.0). Both notices are retained.
The previously deferred licensing choice remains deferred. No MONO components,
model weights or credentials are included.

## One install, distinct responsibilities

- S0: `CognitiveCore.observe` filters trivial messages before opening either DB.
- S1: deterministic admission plus an optional loopback classifier. Network and
  model calls default to off; a classifier cannot authorize external actions.
- S2: `CognitiveCore.worldcore` lazily opens the existing WorldCore engine.
  `compare_futures` delegates to its persisted WHAT IF implementation, including
  uncertainty/abstention behavior for empirical model scenarios. The original
  `world.compare` remains a compatibility heuristic over declared preferences;
  its weights are not calibrated probabilities or a physical prediction model.
- S3: the Cognitive Vault holds topics, evidence, source documents and fenced
  resumable jobs. It does not execute arbitrary tools. WorldCore keeps its own
  versioned memories, forecasts, models and simulation receipts.

The two SQLite databases deliberately keep their existing schemas: joining
their unrelated `events` tables or treating retrieved prose as verified model
training data would destroy provenance. `memory_search` federates both stores.
Owner and namespace bind each API instance. Existing 0.1 vaults migrate on open;
default owner `local` retains their namespace. Existing WorldCore databases can
still be opened directly with `WorldCore(path)`. They are not imported silently.

## Installation and use

Python 3.11+; no mandatory runtime dependencies:

```sh
python3 -m pip install worldcore_cognitive_layer-1.4.0rc3-py3-none-any.whl
cognitive-core --home ./local-data observe '{"text":"ciao"}'
cognitive-worker --home ./local-data --owner local --namespace demo
```

Send one JSON object per line to the worker. `_req` is echoed:

```json
{"_req":"a","op":"cognitive_observe","event":{"kind":"session_end","question":"Which material should we investigate?"}}
{"_req":"b","op":"cognitive_topics"}
{"_req":"c","op":"whatif_compare","question":"Compare declared effects","scenarios":[{"id":"a","actions":[]},{"id":"b","actions":[{"op":"set","key":"cost","value":5}]}],"objectives":[]}
```

The worker reuses WorldCore's bounded strict JSON parser, rejects identity
changes and denies action authorization/execution. No cognitive web tick or
model call is exposed by this transport. The CLI/Python research path needs
explicit network settings and an allowlist. An idle worker is a long-lived
stdio process owned by its host; a test supervisor should impose deadlines.
No scheduler or daemon is installed or started automatically.

```python
from cognitive_core import CognitiveCore, Settings

c = CognitiveCore(Settings(home='./local-data', owner='local', namespace='demo'))
try:
    c.worldcore.set_state('local', 'budget', 100, space='demo')
    result = c.compare_futures('Compare preparation costs', [
        {'id': 'wait', 'actions': []},
        {'id': 'prepare', 'actions': [{'op': 'add', 'key': 'budget', 'value': -5}]},
    ], objectives=[{'key': 'budget', 'direction': 'minimize', 'scale': 1}])
finally:
    c.close()
```

## Corrections to the supplied prototype

Running checkpoints renew rather than clear the lease. Each lease has a
rotating token; stale/revoked workers cannot finish or overwrite a replacement.
Pause/discard cancels pending/running jobs atomically. Repeated normalized
questions reuse their topic, including discarded topics, and active jobs are
deduplicated. Reservations reject negative, fractional and boolean amounts.
Input event lists are copied before processing. The DB file is private on POSIX.

The research budget reserves robots.txt and page requests separately, also
counting discovery. Reservations survive checkpoints. HTTPS connects to the
validated public IP and verifies TLS for the original hostname; environment
proxies and redirects are disabled. Reads enforce byte bounds and elapsed-time
checks in addition to socket timeouts. The subprocess supervisor remains the
outer limit against a stalled worker. No hard real-time guarantees are claimed.

The optional legacy loopback REST adapter rejects browser origins, foreign
Host headers and non-JSON POSTs. It remains unauthenticated and is unsuitable
for a shared machine or reverse proxy; prefer the host-bound stdio worker.

## What is not supplied

No local decision/embedding/reranking/vision weights have been installed or
benchmarked. Memory search is lexical FTS/SQLite, not semantic RAG. The supplied
16-case decision benchmark is synthetic and measures admission rules only.
Source retrieval does not validate source claims; image metadata is not vision.
The WorldCore uncertainty tests concern the measured fixture distributions,
not all real-world consequences. No automatic code rewriting is enabled.
Existing Hermes/OpenCode certificates refer to their recorded earlier code
and fixtures; the unified release requires its own host deployment validation.

## Reproduce

```sh
python3 -m pip install '.[test,mcp,benchmark]'
python3 scripts/run_bounded_pytests.py --selftest --timeout 40 --total-timeout 240
PYTHONPATH=src python3 scripts/validate_unified.py --output demo.json
# Opt-in public research, no private data or model:
PYTHONPATH=src python3 scripts/validate_unified.py --allow-public-web --output web-demo.json
```
