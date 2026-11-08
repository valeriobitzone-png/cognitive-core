# 1.4.0rc3 — Durable research recovery

Preserves checkpoints when policy blocks recovery, freezes discovered source
URLs across attempts, rolls back interrupted lease acquisition, finalizes
already-collected jobs without new network quota, and atomically commits final
status with its experience entry. Adds a real-process kill/recovery regression
and an opt-in public-source end-to-end verifier.

# 1.4.0rc2 — Intelligence Feed

Adds unified structured stimuli, trusted project context, provenance-preserving
deduplication, persistent opportunities, explicit WHAT IF linkage, capacity and
budget gated source jobs, temporal briefing projections and operator feedback.
Adds nested transaction savepoints for atomic preparation. No new collector,
model weights, notification scheduler or arbitrary-code executor is installed.

# 1.4.0rc1 — Cognitive Core integration

One install includes Cognitive Core and WorldCore, lazy canonical WHAT IF, federated memory, bound JSONL transport and original MIT notice. Fixes prototype lease/checkpoint races, stale workers, topic/job duplication, negative quotas, input mutation, proxy routing and HTTP budget accounting. Original data formats remain separate and migrate without implicit ingestion.

# Changelog

## 1.3.0rc1 — local worker candidate, 2026-10-31

- Add installed `worldcore-worker` and `worldcore-mcp` entry points and a readiness operation.
- Bind the JSONL worker's owner/space to operator configuration. Reject cross-scope requests and real-action execution/proposals in that entry point.
- Read bounded UTF-8 frames before parsing; reject oversized unterminated streams, duplicate keys, nonfinite values, invalid correlation ids and malformed Unicode.
- Preserve existing project-directory permissions while restricting newly created private database directories.
- Measure Node bridge request/response budgets in UTF-8 bytes.
- Distinguish wrapped Code Mode errors from successful telemetry in the OpenCode V2 hook.
- Add an opt-in real OpenCode cycle verifier with structured events, matching SQLite receipts, native hooks, expected projections and model acknowledgement.
- Correct CI dependency installation, retain reports on failure and add a worker readiness check.
- Preserve the existing Apache-2.0 license pending the owner's decision; no public repository or production release is created by this candidate.

## 1.2.0 — research alpha baseline

Bounded runner, process/thread/fd diagnostics, SQLite initialization race fix, temporal calibrated predictions, observed-outcome tracking, WHAT IF confidence gates, real SDK/Hermes probes and archived validation evidence.

## 1.3.0rc2

- Add data-only model refresh with prospective comparison and consumed holdouts.
- Roll back or suspend adaptive heads atomically on verified outcome drift.
- Rank immutable procedure variants from verified outcomes; recommendations grant no permissions.
- Keep existing research training and historical forecast versions; expose adaptive status read-only through JSONL.

## 1.3.0rc3

- Type Hermes numeric WHAT IF schemas to prevent invented argument shapes.
- Return native-recognizable error fields instead of successful unavailable telemetry.
- Preserve reply state and deadlines when reimporting offline EML metadata.
- Add reproducible native Hermes/model probes with simulated workspaces and independent receipt checks.
