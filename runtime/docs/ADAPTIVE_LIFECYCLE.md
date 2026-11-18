# Adaptive data, stable code

WorldCore updates model data and procedure choices through authenticated host events. It does not modify its source, generate executable code, run a background service or widen permissions. The operator selects which observations the host may supply. Memory already supports versioned updates through `remember`; this release does not infer private preferences from arbitrary text.

## Models

Call the host API when a batch of real observations becomes available:

```python
result = core.refresh_adaptive_world(owner, family, observations, as_of=cutoff, space=space)
```

Use the observation schema documented by `train_temporal`: sample id, environment, action, numeric before/after states, before/observed/available timestamps, `source="observed"`, and provenance. This string is a host assertion, not independent authentication. At least 80 usable observations per action are required; simulated labels do not count.

The initial candidate must pass the existing chronological fit/calibration/test gates. A replacement must preserve validated actions and state schemas, reduce the incumbent's MAE by more than 5% on the same fresh holdout, and have no lower interval coverage on that holdout. These thresholds express an admission rule, not a statistically proven superiority guarantee.

Replacement holdout inputs must occur after the preceding selection cutoff. Evaluation sample ids are consumed even when the comparison rejects a candidate. They may subsequently enter training, but cannot be used again for selection. Reusing a timestamp, renaming an old observation or mislabelling provenance is a data integrity problem for the authenticated host to prevent.

Admission, version allocation, pointer change and audit events are transactional across connections. Concurrent ingestion of the same batch cannot create two active promotions. Rejected candidates leave the incumbent selected; a low-level legacy research training call cannot override an adaptive head.

Forecasts retain their original version forever. After `resolve_calibrated_prediction(..., source="host_verified")`, the same transaction reviews up to 20 verified outcomes per action. With at least ten observations, a Wilson upper bound below target coverage triggers rollback to the previous version, or suspension if none exists. Rollback restores a previous model, not guaranteed accuracy; ordinary confidence/OOD/drift gates still apply. A previously failing fallback may therefore abstain. A suspended head requires fresh validated observations to resume.

User-reported outcomes remain in the forecast ledger but cannot trigger active-head changes. JSONL/MCP prediction resolution retains `user_reported`; models cannot mark their own answers host-verified. The pre-existing prediction abstention gate also considers reported outcome drift; do not treat that gate as authenticated sensor validation.

## Procedures

The authenticated host registers named, immutable variants with `register_adaptive_procedure`. Steps are short text **data**, not Python, shell commands, tool invocations or permission grants. Corrections need a new variant id. Record immutable, scope-bound outcomes with `record_adaptive_procedure_outcome`; replay is idempotent, and changing a receipt or upgrading its provenance is rejected.

`recommend_adaptive_procedure` uses the last 40 host-verified outcomes per variant. It requires at least 20 outcomes and a Wilson lower bound of 0.7 before returning a recommendation; otherwise it abstains. The intervals describe the observed sample, not a guarantee after selecting among variants or under changing conditions. Negative feedback can remove a recommendation. The chosen procedure always has `execution_authorized=false`. The host must interpret steps as untrusted data and enforce action permissions independently.

The JSONL operations `adaptive_status` and `adaptive_procedure` are advisory/read-only. Observation ingestion, procedure registration and provenance upgrades are intentionally absent from model-facing transports. They require an authenticated integration using the Python API.

## Operational scope

This mechanism runs synchronously when the host supplies a batch or verified outcome. It is not a universal sensor, task scheduler, autonomous coding agent, complete Hermes integration or promise that software will never need maintenance. No monitoring or unattended service was enabled by the validation. A production host must provide truthful observations, a permitted event loop, resource budgets and application-specific validation.

Run `scripts/validate_adaptive_lifecycle.py OUTPUT_DIR` for a reproducible synthetic lifecycle over the actual SQLite engine. Its observations and procedure outcomes are controlled fixtures, not evidence of real-user anticipation. The test verifies source digests remain unchanged while memory/model/procedure data evolves.
