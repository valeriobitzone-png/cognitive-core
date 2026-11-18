# WorldCore per Claude Code e OpenCode — v1.1

## Claude Code

Installare la wheel Python e la dipendenza opzionale MCP (`pip install 'worldcore-cognitive-layer[mcp]'`). Copiare `adapters/claude-code/mcp.example.json` in `.mcp.json` nel progetto, e *unire* i contenuti di `settings.example.json` con le proprie impostazioni Claude Code sotto `.claude/settings.json`. Non sovrascrivere altri hook o permessi già presenti. Verificare i comandi disponibili nella versione installata di Claude Code.

Gli hook sono **osservativi**: `UserPromptSubmit` fornisce contesto letto dalla memoria, `PostToolUse` e `PostToolUseFailure` registrano solo nome e stato dello strumento. Non vengono salvati comandi, argomenti, prompt, file, chiavi o output.

Gli strumenti `whatif_compare`, `whatif_backcast`, `whatif_stress_test`, `whatif_history`, `whatif_verify`, `whatif_replay` sono forniti dal server MCP stdio. Nessuno di questi permette di approvare o eseguire le azioni ipotizzate. MCP deve restare accessibile solo a host autenticati e fidati.

## OpenCode V1

Usare `adapters/opencode/opencode.example.json` e copiare **solo** `adapters/opencode/worldcore.js` in `.opencode/plugins/`. Il plugin osserva eventi `tool.execute.after`, ma le funzioni WHAT IF sono veicolate tramite MCP. La comunicazione con il motore usa un subprocess Python persistente, non un lancio Python per ogni evento.

## OpenCode V2

La V2 usa **un'API plugin e uno schema MCP differenti**. Usare `adapters/opencode/opencode-v2.example.json` e copiare **entrambi** `worldcore-v2.js` e `worldcore.js` nella directory dei plugin V2, abilitando soltanto l'entrypoint V2. Il secondo file è una dipendenza di trasporto. Non copiare la configurazione `mcp` della V1 nella V2.

## Sicurezza e test effettivi

- L'identità `WORLDCORE_OWNER` è impostata dall'host fidato, non dall'LLM; non esporre i bridge locali come servizi di rete non autenticati.
- Ogni esecuzione o modifica esterna richiede le autorizzazioni dell'host. La simulazione è sempre read-only.
- Sono stati eseguiti hook Claude Code via stdin con subprocess Python reale; plugin OpenCode V1 e V2 con hook mock e IPC reale; MCP con server mock e runtime Python reale.
- **Non sono stati eseguiti Claude Code/OpenCode installati e autenticati**: esistono ancora incompatibilità possibili con versioni concrete, specialmente l'API V2 in evoluzione.

Riferimenti ufficiali: https://claude.com/blog/how-to-configure-hooks ; https://docs.opencode.ai/docs/plugins/ ; https://opencode.ai/v2/docs/build/plugins/ ; https://opencode.ai/v2/docs/mcp-servers/ .
