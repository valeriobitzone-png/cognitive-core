# WorldCore 0.1 — sandbox validation record

**Status:** Developer alpha; functional core validated locally. **Not production certified. Not AGI.**

**Date:** 2026-10-29. Test host: sandbox Python 3.13, Node 22, SQLite 3.46.1. All local tests use temp SQLite databases, no LLM API or network access.

## Acceptance requirements and evidence

| Requirement | What was verified | Status |
|---|---|---|
| Independent Python installation | Wheel build, isolated wheel import + CLI | PASS |
| Durable memory | DB re-open, version timeline, deletion, expiry and source | PASS |
| Scope isolation | distinct owner/workspace, cross-owner ID and forecast isolation | PASS for local API; no authentication |
| Recall | FTS5 exact-token retrieval, >1,000 memories, migration/backfill | PASS, **not semantic recall** |
| Event ledger | metadata-only tool observations via bridge and mocked hosts | PASS |
| Counterfactuals | deterministic state transition simulation, rejects unsafe operations, no real action | PASS |
| Predictions | explicit binary hypotheses, due dates, Brier error verification | PASS; no autonomous general forecasting |
| Frequency estimation | Beta-smoothed observed frequencies, insufficient-sample gating | PASS; association, not causality |
| Proactivity | numeric threshold rules, cooldown, no actions executed | PASS for on-demand `tick`; no background clock |
| Permission record | exact action + args binding, operator-only approval, one-time consumption, cross-process race and expiry | PASS; host must independently enforce |
| Concurrent database access | multi-process writes, trigger race, approval consumption; repeated test runs | PASS in sandbox |
| Hermes adapter | Register/use hooks against a fake `ctx`, metadata-only observation | PASS mock, NOT live host |
| OpenClaw adapter | Native plugin manifest, hook registration, persistent IPC, 24 concurrent queries, restart, failure fallback, child shutdown in Node mock | PASS mock, NOT live host |
| MCP tool surface | Tool registration and permission exclusion with a fake `FastMCP` SDK | PASS mock, NOT actual SDK transport |
| Secrets | Basic regex redaction, no raw tool args/results in adapters | LIMITED; regex cannot guarantee detection of all secrets |
| CI | CI workflow supplied for two OSes and two Python releases | NOT executed in GitHub Actions |

## Synthetic performance results

`python benchmarks/performance.py`: 1,000 SQLite memories; write total ~661 ms; FTS exact-term recall median 0.05 ms, p95 0.16 ms; deterministic simulate median 0.01 ms. `node benchmarks/bridge.mjs`: OpenClaw adapter persistent Python cold start ~765 ms, warm median 0.22 ms and p95 0.45 ms across 100 requests. These values vary by hardware and database size. Do NOT claim they demonstrate superiority over OpenClaw or Hermes.

## Blockers before claiming a production-ready cognitive engine

1. Live version-pinned smoke tests on actual Hermes and OpenClaw installs, including dynamic plugin activation, permissions and update compatibility.
2. Real MCP SDK v2 stdio integration test. SDK not present in sandbox and network installation unavailable; mock validates only our registrations.
3. Authorization and encryption hardening for remote/multi-user deployments; secure deletion/retention rules; identity-bound scopes and adversarial prompt-injection evaluation.
4. Measured recall quality on realistic temporal, contradictory and multilingual information, including exact and semantic comparisons against existing agent memory solutions.
5. Automatic evidence extraction, source trust, safe consolidation and semantic embeddings with clear versioning; current `remember` requires explicit call.
6. Calibrated predictive world models and evaluated multi-step planning; the existing state simulator is deterministic and the probabilities are observation frequencies.
7. More extensive fuzzing, failure injection, backup/restore and durability tests on macOS M4, Windows and different filesystems.
8. Host-validated action authorization; WorldCore cannot block all external actions taken by a host.

## Operational safety defaults

- No network listener, no model credential access, no automated external tool execution.
- MCP cannot approve or consume an action. Operator CLI approval requires direct trusted machine access.
- Hermes and OpenClaw adapters record only tool metadata, never raw conversation text; explicit memory-saving tools can store data after simple redaction.
- No heartbeat process starts by itself. `tick` is invoked by operator or host scheduling.
- API key and subscription handling remain under the host framework's official integrations.

## Validation commands

```sh
python -m pip install -e .
python -m pytest -q tests
node --test tests/openclaw.test.mjs
python -m compileall -q src adapters/hermes
python -m pip wheel . --no-deps --no-build-isolation -w dist
python benchmarks/performance.py
node benchmarks/bridge.mjs
```
