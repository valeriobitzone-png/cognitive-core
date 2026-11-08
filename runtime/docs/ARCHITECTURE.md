# WorldCore Cognitive Layer v0.1

## What is actually implemented

- SQLite WAL event and memory ledger scoped by trusted `owner` and `space`.
- Memory upsert with explicit source, versioning, expiry, provenance, manual deletion and no auto-claim extraction.
- Deterministic non-executing simulation of state set / add / delete + guards.
- Binary forecast ledger and Brier error scoring, with explicit observed outcomes.
- Frequency estimates from labelled observations with beta(1,1) smoothing and uncertainty indication; no causal learning.
- Proactive numeric-threshold monitoring via explicitly invoked `tick()` and cooldown, generating alerts only.
- One-time, exact-argument approval records, with approvals kept away from MCP and agent plugins; **not an authorization replacement for host policy**.
- Hermes general plugin hooks and OpenClaw native plugin hooks that recall text and record *metadata-only* tool outcomes by default.
- Official-SDK MCP stdio server (optional extra), with operator-bound owner and no approval/consumption tools.
- Host model/auth remains in the host framework; WorldCore uses **no API key and no subscription credentials**.

## Trust boundaries

This is a local **developer prototype**, not a hardened multi-tenant online service.
`owner` and `space` are namespace selectors, NOT authentication. Treat CLI, MCP, plugin configuration and local files as privileged. Protect physical storage and backups; no encryption at rest provided. The plugin relies on host permissions; WorldCore does not intercept all tool calls or prevent execution by the host. Do not insert untrusted text without instruction delimiters. Only memory deliberately written via CLI, MCP `memory_save`, or bridge `remember` becomes persistent factual context. The adapters do not persist raw prompts or raw tool results.

Do not expose MCP, bridge or SQLite to a network without authentication/authorization. Never give untrusted agents the operator-only `approve` CLI or DB file access. No model-owned action may execute solely on the basis of an approval record.

## Design limits

There is **no AGI**, no trained world model, no independent predictive model across arbitrary environments, no automatic skills training and no guarantee of improved agent performance. Simulations are rule-based, and predictions require manual hypotheses and observed outcomes. The example uses an early forecast resolution only for demonstration.

## Phased path to meaningful improvements

1. Benchmark host baselines on fact recall after revisions, controlled privacy probes and actual measurable prediction tasks.
2. Replace linear memory recall with bounded FTS and semantic retrieval; evaluate exact and temporal memory correctness.
3. Add calibrated domain-specific transition models, evidence linking, multi-step search and certified simulation vs real-state outcomes.
4. Add host-enforced action policy interceptors with integration tests on version-pinned Hermes and OpenClaw builds.
5. Run supervised shadow-mode trials with alert precision/recall, costs and human review before proactive production.

## v0.3 learned models and evaluation

V0.2 adds two scoped and persisted model families to the stdlib-only engine: online logistic regression on explicit normalized numeric features and tabular action-conditioned next-state frequencies with smoothing. Results are associations unless the evidence comes from controlled interventions. Rollouts never execute an action. The training methods are not present on the agent-callable bridge or MCP surface; only trusted/operator code invokes them.

V0.3 adds read-only out-of-sample evaluation, a consistent SQLite read snapshot, training/holdout sample-ID overlap rejection, Brier score/log loss/ECE metrics, a constant oracle reference (computed from holdout prevalence and therefore an optimistic baseline), and a conservative Hoeffding-style bounded-loss alarm. Drift comparison requires an identical model fingerprint (weights, bias, schema and training sample count). These checks require IID-like evidence for their interpretation and do not protect against adversarial or mislabeled data, concept drift with delayed outcomes, or leakage via duplicated examples with new IDs.
