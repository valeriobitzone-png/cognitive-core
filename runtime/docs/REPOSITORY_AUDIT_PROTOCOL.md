# WorldCore — Quality & license audit gate

**Discovery is never authorization.** A GitHub search result is untrusted metadata.

## Current evidence

`catalog/candidate_quarantine_v07.json`: 246 repository candidates, all `can_install=false` and `may_be_used_as_verified_skill=false`.

`catalog/reviewed_evidence_v07.json`: **16 repositories** with some directly retrieved GitHub file evidence, **12 with source file excerpts**, **15 with license files**. Only one (Pydantic AI) has license, source, tests and CI evidenced in this partial sample under a permissive license. **None is authorized for automatic execution.** A few file excerpts do not constitute a complete code review, source-quality rating, security scan or license clearance.

Examples:
- `polakowo/vectorbt`: the source file header references Apache 2.0 with Commons Clause; `LICENSE.md` adds restriction on selling. Status: **restricted, manual legal review**; do not assume OSS compatibility.
- `freqtrade/freqtrade`: GPL-3.0. CI/tests and source present, but redistribution/integration requires careful copyleft assessment.
- `gitroomhq/postiz-app`: AGPL-3.0; similarly requires manual review.
- `pydantic/pydantic-ai`: MIT + source/test/CI files observed, yet not fully security-audited or installed/tested from the repository.

## Automated read-only audit on an Internet-enabled system

1. Install WorldCore and set `GITHUB_TOKEN` in the environment if needed.
2. Execute `python scripts/audit_github_catalog.py --output audits/github_review.json --limit 246`.
3. Each audit pins a commit hash and retrieves GitHub's tree. If truncated, it refuses the audit. It checks a declared SPDX license **and** the actual license text for additional restrictions; retrieves representative source/test/CI blobs and emits evidence SHA.
4. The maximum automatic status is `source_screened_needs_human_review`. It NEVER executes code, installs packages, downloads datasets for model training or declares a repository secure.
5. A human or separate CI pipeline must then inspect code, scan dependencies and secrets, test from a pinned checkout in a sandbox, read every relevant third-party license, reproduce benchmarks, inspect maintainer activity and sign the approval.
6. Only after explicit approval may a distinct trusted importer consider installing anything. `authorized_for_capability()` returns false for all the machine-screened results.

## Quality checklist per repository

- License file plus effective SPDX and exceptions; dependencies and data/model licenses separately.
- Pinned commit, authenticated source provenance, test coverage and actual test runs.
- CI workflow and last green commit; release discipline, supported Python/Node/runtime versions.
- Design boundaries, public API, reproducible examples, error handling and type validation.
- Security policy, dependency/supply-chain issues, package vulnerabilities, secrets/credentials handling, unsafe external effects.
- Hardware/resource footprint; compatibility with Mac M4 16GB, licensing on commercial distribution.
- Benchmarks versus simple baselines, split integrity, uncertainty, known failure modes.

**Always track unknown separately from false and true.** Stars, forks, README marketing text and repository size never substitute for code quality.
