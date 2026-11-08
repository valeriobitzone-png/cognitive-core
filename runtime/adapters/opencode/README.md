# WorldCore / OpenCode adapter

There are **two different OpenCode plugin APIs**, do not mix them.

- **V1 (docs.opencode.ai)**: `worldcore.js` exports `WorldCorePlugin(ctx)` and returns `tool.execute.after` hooks. Copy this file to `.opencode/plugins/worldcore.js`.
- **V2 (opencode.ai/v2)**: `worldcore-v2.js` exports `WorldCoreV2Plugin(ctx)` and registers `ctx.tool.hook('execute.after', ...)`. Copy `worldcore-v2.js` AND the transport module `worldcore.js` to your V2 plugin directory, enabling only the V2 entrypoint according to V2 documentation.

Use the matching `opencode.example.json` to register WorldCore as a local MCP stdio server. `WORLDCORE_OWNER` must be controlled by the trusted host. Plugin event telemetry saves only tool name and observed completion, never commands, credentials or outputs. WHAT IF comparison, backcasting and replay run over MCP, and never authorize actions.

Compatibility is validated with host-shaped mocks and real Python subprocesses. Live OpenCode binaries were not available in the sandbox, and version-specific SDK registration must be tested on the target release.
