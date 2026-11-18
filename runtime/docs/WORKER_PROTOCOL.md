# WorldCore JSONL worker protocol v1

Launch `worldcore-worker --db PATH --owner OWNER --space SPACE`. Flags override environment defaults `WORLDCORE_DB`, `WORLDCORE_OWNER` and `WORLDCORE_SPACE`. Without explicit identity, the local defaults are `local/default`; use distinct scopes for projects that must not share state.

The operator is trusted. Owner/space binding isolates requests; it does not authenticate a user on a public network. This worker has no HTTP listener.

## Frames and responses

Each request is one UTF-8 JSON object followed by newline. Limit: 64,000 bytes **including newline**, measured before decoding. `_req` is optional; when present it must be a string of 1–128 characters. Duplicate keys, nonfinite numbers, invalid UTF-8 and escaped lone surrogates are rejected.

```json
{"op":"health","_req":"startup"}
{"ok":true,"result":{"status":"ready","version":"1.3.0rc3","protocol":"worldcore-jsonl-v1"},"_req":"startup"}
```

An operation error has `ok:false`, a diagnostic `error` string and the request id when it was valid. Error wording is diagnostic, not a stable machine-readable classification. An invalid request id is never echoed. The protocol writes only JSON responses to stdout.

Owner and space may be omitted. If supplied, they must match the operator-bound scope. Scope changes are rejected before dispatch. `action_propose` and `action_execute_approved` are always rejected by this bound entry point; approvals cannot be manufactured by simulations.

A bounded malformed frame returns an error and processing continues with the next frame. An oversized frame returns `request too large` and exits nonzero immediately, without draining the stream or waiting for its newline. The host must restart the child and must not automatically replay state-changing requests without checking their outcome. EOF closes the worker normally.

Use deadlines in the host. A worker waiting for a complete, in-limit frame is an idle stream reader; the host must supply the newline or close stdin. `--help` and `--version` do not initialize a database. A storage initialization failure returns a generic unavailable error without disclosing paths.

## Host example with an external deadline

```python
import json, subprocess
p = subprocess.Popen(
    ["worldcore-worker", "--db", "./local-state/worker.db", "--owner", "agent", "--space", "demo"],
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
)
try:
    stdout, stderr = p.communicate(json.dumps({"op": "health", "_req": "probe"}) + "\n", timeout=5)
except subprocess.TimeoutExpired:
    p.kill()
    p.communicate(timeout=1)
    raise
result = json.loads(stdout)
assert p.returncode == 0 and result["ok"]
```

For persistent use, the OpenCode/OpenClaw adapters contain pending-request correlation and per-request deadlines. Their observable telemetry excludes prompts, arguments and tool-output contents. MCP provides model-visible typed schemas for the same engine; its SDK transport has its own framing and is not governed by this JSONL byte limit.

## Compatibility

`python -m worldcore.bridge` and `--lines` remain legacy host transports: the authenticated host supplies owner/space in requests. They now share strict bounded decoding but do not provide the bound entry point's tenant binding. Use `worldcore-worker` or operator-bound MCP when connecting untrusted model payloads.

Python API users remain responsible for authentication, truthful observation provenance, lifecycle and external execution permissions. API immutability is enforced by engine transactions; a person with direct write access to SQLite can alter the files.
