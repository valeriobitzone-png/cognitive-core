# WorldCore learned-model card (v0.3)

**Type**: (1) small online logistic binary classifier over 1–24 user-supplied numerical features normalized to [0,1]; (2) smoothed tabular conditional next-state estimator on discrete actions/states.

**Data**: user/operator-supplied numeric observations and explicit labels. Included demo dataset: pseudorandom synthetic trajectories produced from fixed equations and simple 3-state transitions. No private OpenAI training data, no model weights, no scraping or external APIs.

**Training procedure**: incremental SGD for the logistic estimator, with bounded rate, shrinkage and coefficients; counts for the transition estimator; SQLite storage, idempotent sample IDs and conflicting replay rejection. No self-generated truth labels. No unbounded/recurrent autonomous training loop. No hosted-service authentication.

**Evaluation**: holdout samples with disjoint IDs, 4,000 per task; Brier/log loss/accuracy/ECE for binary classification, coverage/top-1/log loss for discrete transitions. Separate drift experiment intentionally reverses the risk relationship. Cross-seed checks are reproducible via `benchmarks/learn_eval.py`. The constant reference is computed using the holdout outcome frequency and is an optimistic comparator, not a deployed baseline.

**Expected failures**: nonlinear XOR without an explicit cross feature, novel environment states/actions, time-varying dynamics, poorly normalized input, limited-label regimes, domain shift. Do not use for safety-critical or financial decisions without substantial domain-specific calibration, validation and human oversight.

**Privacy**: local SQLite storage not encrypted. `owner` / `space` are not authentication; no remote service built in. The operator must manage dataset rights and retention.

**Interpretability**: numerical metrics and model provenance are exposed, but no causal attribution guaranteed. A drift alarm can be investigated; it never grants an action.

**Deployment status**: verified developer alpha. Real Hermes/OpenClaw lifecycle, production authorization, real MCP SDK transport, continuous real-world training and semantic memory have not been certified.
