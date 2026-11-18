# Contributing

Use a dedicated virtual environment and install `.[test,benchmark,mcp]`. Run the bounded suite and retain its reports. Test a defect before fixing it and add meaningful regression coverage. Keep changes tied to a concrete behavior.

The fast base worker has no external Python runtime dependency. Keep model/provider calls out of normal tests. Real-host certification is a separate opt-in command and must reconcile independent receipts, not accept claims in generated text.

Never commit `.env` files, API keys, private state databases, host session stores, caches or node_modules. Use only synthetic scopes in integration tests. Record skips and failed attempts honestly.

The existing license remains Apache-2.0 until the project owner decides the final license and verifies provenance. No contribution or distribution should be presented as GPLv2-only on the basis of this candidate.
