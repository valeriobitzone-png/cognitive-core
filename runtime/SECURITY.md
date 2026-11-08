# Security boundaries

WorldCore's initial supported deployment is a local worker owned by one trusted operator, connected through stdio. It does not provide public-network authentication or a multi-user SaaS boundary.

- Launch a dedicated database and explicit owner/space for each required scope. New database directories are private on POSIX; existing project-directory permissions are preserved. Database files are restricted to their owner. SQLite content is not encrypted by WorldCore.
- Treat memory, imported evidence, model output and scenario descriptions as untrusted data. Their content never grants execution authority. Hosts must enforce their own permissions before acting.
- `worldcore-worker` binds tenant identity and rejects real-action execution/proposals. The legacy bridge is for authenticated host code. MCP binds identity from operator configuration; do not expose it as an unauthenticated remote service.
- Bound frames and host deadlines contain ordinary IPC faults. Process groups, observed descendant cleanup and watchdogs are not a hostile-code sandbox or protection against every kernel/storage failure.
- Observation labels are host assertions. A `host_verified` string is not independent sensor authentication. Model-facing resolution transports retain `user_reported` provenance.
- Do not include credentials, personal databases, raw model sessions or host caches in source releases. The distributed adapters have no npm runtime dependency; optional MCP dependencies need their own version/security review.

## Reporting a vulnerability

Do not post credentials or exploitable private deployment details in a public issue. Before a public GitHub launch, the maintainer must configure a private reporting channel, supported-version policy and maintainer identity. Those governance fields are not yet assigned in this release candidate; no fictional contact address is provided.

## Release status

The candidate carries tested technical changes and local evidence. Licensing is explicitly pending user selection, and the prepared CI matrix has not been executed on GitHub from this local task. Do not describe those pending steps as completed certifications.
