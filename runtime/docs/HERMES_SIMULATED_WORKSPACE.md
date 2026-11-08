# Native Hermes with simulated workspaces

This integration profile uses the installed Hermes `AIAgent.run_conversation`, a real Groq model and the real WorldCore plugin/SQLite engine. Calendar ICS, inbox EML, contacts, travel histories and budgets are synthetic fixtures. No mail/calendar account is connected; no message is sent and no booking is changed.

## Reproduce the verified path

Install WorldCore's test dependencies in the supervising Python environment. Hermes and its dependencies must already exist in their own environment. Provide the provider key through the host environment, never fixture files:

```sh
python -B scripts/certify_hermes_personal.py ./validation/hermes \
  --hermes-root /path/to/hermes-agent \
  --hermes-python /path/to/hermes-venv/bin/python \
  --repeats 3 --allow-model-calls
```

The probe requires `GROQ_API_KEY` in the environment and makes real billed/provider-limited calls. Each case gets its own new, disposable `HERMES_HOME`; it enables only the WorldCore plugin and uses:

```yaml
plugins:
  enabled:
    - worldcore
tools:
  tool_search:
    enabled: "off"
```

This is the tested direct-tool profile. It is not a claim that other discovery profiles fail; the initial probe incorrectly expected eager tool names while progressive discovery was active.

The native constructor uses the installed host's supported request override:

```python
AIAgent(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
    provider="custom",
    api_mode="chat_completions",
    model="openai/gpt-oss-120b",
    reasoning_config={"enabled": True, "effort": "low"},
    request_overrides={"reasoning_effort": "low"},
    # The reproducible probe also restricts tools, iterations and runtime.
)
```

The request override is necessary in this installed route: `reasoning_config` alone still emitted `reasoning_effort="default"`, which Groq rejected with HTTP 400. The effective top-level override fixed that refusal. This does not rewrite the user's existing Hermes profile or patch upstream Hermes. The script is a working, explicit integration entry point; an operator embedding WorldCore should preserve the same provider-compatible request contract.

The probe limits the advertised tools to `worldcore_personal_advice` and `worldcore_whatif`, disables background review, skips personal context/memory files and caps iterations and execution time. Agent tools cannot send emails or edit appointments in this profile.

## Corrections discovered by native execution

The WHAT IF schema now specifies numeric actions (`op`, `key`, `value`), scenario ids and objective fields (`key`, `direction`, `scale`). Previously generic objects caused a real model to invent `budget_change` and nested objectives, which the engine correctly rejected. The typed schema was then verified through native model tool calls, not only a manual registry invocation.

Adapter failures now return an `error` field. The installed native Hermes classifier recognizes this as an error; previously `status="unavailable"` plus `error_type` could be recorded as `status=ok`. Error class names are returned without raw exception contents or credentials.

The offline mail importer also preserves already known reply status and deadlines when the same EML file is imported again. Explicit `put_mail_signal` state updates remain available to a richer, authenticated inbox connector.

## Evidence and limits

Certification reconciles native assistant tool calls, matching tool responses, unique fixture identifiers absent from the prompt, a scoped SQLite WHAT IF receipt, expected budget projections (120 and 95), unchanged real state, native observation hooks and final acknowledgement. It rejects a successful process exit or fluent text without these receipts. Eleven unit tests exercise forged/missing evidence.

The synthetic workspace tests cover personal/company separation, missing travel evidence, empty workspaces, reply/deadline prioritization, body prompt injection, duplicate imports, preserving answered mail and eight calendar insertion orders. Calendar parsing remains a documented limited ICS subset; these tests do not certify every calendar standard or provider.

The final native cases demonstrate a model identifying an existing travel conflict and pending reply, comparing declared assumptions and proposing a plan in response to a generic preventive-review request. They do not prove continuous background anticipation, calibrated commute uncertainty, production delivery reliability, autonomous email sending or enterprise-grade authorization. No background monitor is enabled by this probe.
