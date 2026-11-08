# Cognitive Core + WorldCore runtime

Technical release candidate 1.4.0rc3. Python 3.11+, no mandatory runtime
packages. WorldCore APIs are retained; Cognitive Core adds zero-model
admission, persistent research topics, a fenced job queue and an Intelligence
Feed / Opportunity Pool.

```sh
python3 -m pip install .
cognitive-core --home ./data observe '{"text":"ciao"}'
cognitive-worker --home ./data --owner local --namespace demo
```

See [integration and limits](docs/COGNITIVE_INTEGRATION.md) and the repository
[Intelligence Feed example](../docs/INTELLIGENCE_FEED.md). The parent README
retains the original product vision; implemented behavior is covered by tests.

```sh
python3 -m pip install '.[test,mcp,benchmark]' build
python3 scripts/run_bounded_pytests.py --selftest --timeout 60 --total-timeout 240
PYTHONPATH=src python3 scripts/benchmark_intelligence_feed.py --output /tmp/feed.json
python3 -m build
```

Tests use synthetic fixtures unless their report explicitly identifies a real
service. Two optional browser/desktop groups may skip. Source collection does
not independently validate claims. Optional classifiers/vision models are not
bundled. No daemon, private-data collector or automatic code rewriting is
activated by installation. The source distribution omits private workspaces,
historical databases and raw host/provider logs.

WorldCore retains Apache-2.0; Cognitive Core retains its MIT notice in
`src/cognitive_core/LICENSE`. See the parent `LICENSING.md` for documentation.
