# WorldCore v0.3 — sandbox validation (29 October 2026)

**Status: DEV ALPHA — not production-certified; not AGI.**

## Tests and software verification

- 87 Python tests pass with `PYTHONPATH=src`, including 6 evaluation/drift tests, legacy persistence/scoping/permission tests and concurrent database tests.
- 5 Node.js tests pass using an OpenClaw **mock host**; not tested with an actual OpenClaw gateway.
- Hermes integration is tested with a mocked environment only.
- Installed the built 0.3.0 wheel in an isolated target and imported it separately from repository sources; performed a model train/predict/evaluate smoke test.
- `compileall` verifies Python syntax. The MCP tool registry has mock coverage in earlier tests, not a real transport exercise.
- Running `pytest` without a suitable `PYTHONPATH` can load the already-installed v0.1 when multiple development versions exist. The documentation now prescribes explicitly selecting the source path.

## Reproducible synthetic learning (seed 20261029)

Exactly 12,000 train rows per learned model and 4,000 separately generated holdout rows per evaluation case. Synthetic only; known-generating rules. No LLM weights trained.

| Case | Held-out Brier | Held-out accuracy | Other findings |
|---|---:|---:|---|
| Stationary probabilistic 2-feature binary outcome | 0.155851 | 77.00% | +35.49% Brier skill vs best holdout constant |
| Same trained model after unannounced rule reversal | 0.508256 | 28.40% | Brier deterioration +0.352405; drift alarm |
| No interaction features on XOR | 0.255705 | 49.68% | FAILS nonlinear pattern as expected |
| Supplied `x*y` feature for XOR | 0.039904 | 95.85% | Task-specific engineered interaction required |
| Three-state action-conditioned transition model | N/A | 92.65% top-1 | 100% test coverage, mean log loss 0.315180 |

Additional deterministic seed runs 42, 2027 and 8008 each pass benchmark gates (including deliberate drift and nonlinear control). Repeatable benchmark script: `benchmarks/learn_eval.py`. Raw main run: `training-artifacts/learning_report.json`.

**Interpretation**: These measure learning a *known small synthetic process*. The drift failure is serious and documented, not hidden. Statistical accuracy in these tasks is not evidence of AGI, transferable world reasoning, memory superiority over Hermes/OpenClaw, or future predictive capacity. The training-ID overlap check cannot detect all duplicate data under new IDs.

## Conditions before live deployment

1. Real version-pinned Hermes and OpenClaw integration and lifecycle tests, including policies and permissions.
2. Actual MCP SDK transport testing and host sandboxing.
3. Domain-specific time-separated data with leakage controls, uncertainty bounds, drift monitoring, and human oversight; benchmark against host-native solutions.
4. Authentication and storage encryption if used outside a trusted single-user machine; comprehensive privacy reviews.
5. Restore/backup testing, adversarial testing, cross-platform smoke tests and true performance measurements under host load.

Do not place the current DB on a network. Do not promote predictions automatically into external actions. No asynchronous background training is running after these tests finish.
