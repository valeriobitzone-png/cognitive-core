# WorldCore v0.4 — Model cards

## Online numerical predictor
A binary logistic SGD classifier consumes a fixed schema of normalized [0,1] numeric features, trained on operator-supplied labelled observations and persisted in SQLite. It can continue incremental training. Repeating sample IDs is idempotent; feature schema and values are validated. It is not calibrated to real-world risk and does not learn natural language.

## Nonlinear numerical forest
A 64-tree maximum-depth-7 random forest trained offline on real historical/tabular data is exported to a bounded, validated JSON representation. Python inference uses numeric splits only, no pickle and no code loading. Raw feature bounds and names are persisted so operators can input original units. Inputs beyond training extrema are clamped and flagged as out of training range. Training requires scikit-learn, but inference does not.

## Tabular transition predictor
Counts observed historical state transitions and forecasts the most frequent next state after a named condition/action. On the sunspot dataset `one_year_later` is observational elapsed time, **not a causal intervention**.

## Document retrieval
A durable SQLite FTS5 source catalog indexes operator supplied text with source URLs, declared licenses, document hashes and isolation between logical namespaces. It is a search engine, not a pretrained LLM, and does not execute retrieved text.

## Training data and evaluation
Detailed sample counts, splits, seed variations, model performance and sources: `docs/VALIDATION_V04_IT.md`, `training-artifacts/real/real_data_learning_report.json`.

## Restrictions
No learned natural-language generation, general AI, self-modifying software, unconstrained web crawling, model-level causal reasoning, privacy guarantee across untrusted hosts, verified Hermes/OpenClaw deployment or automatic training daemon. All model predictions require domain calibration and independent validation before deployment.
