"""Explicit CLI probes with synthetic data. Text claiming a call is not evidence.

Uses the interpreter running this script; install the MCP extra there first.
No Code Mode execution permission is granted. Existing host credentials remain
host-owned. Each subprocess has a deadline, full log, and independent receipt.
"""
import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from run_bounded_pytests import bounded

ROOT = Path(__file__).resolve().parents[1]


def receipts(database, table):
    if not database.exists():
        return 0
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
        if not connection.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
            return 0
        # table is selected only by this script, never by model output.
        return connection.execute(f'SELECT COUNT(*) FROM {table} WHERE owner=? AND space=?',('authentic_host','probe')).fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--host', choices=['claude','opencode','both'], default='both')
    parser.add_argument('--model', default='groq/openai/gpt-oss-20b')
    args = parser.parse_args()
    dest = args.output.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    database = dest/'host.db'
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE':'1', 'PYTHONPATH':str(ROOT/'src'),
           'WORLDCORE_PYTHON':python, 'WORLDCORE_DB':str(database),
           'WORLDCORE_OWNER':'authentic_host', 'WORLDCORE_SPACE':'probe',
           'XDG_CONFIG_HOME':str(dest/'config'), 'XDG_CACHE_HOME':str(dest/'cache')}
    server_env = {key:env[key] for key in ('PYTHONPATH','PYTHONDONTWRITEBYTECODE','WORLDCORE_DB','WORLDCORE_OWNER','WORLDCORE_SPACE')}
    server = {'type':'stdio','command':python,'args':['-B','-m','worldcore.mcp_server'],'env':server_env}
    claude_config = dest/'claude_mcp.json'
    claude_config.write_text(json.dumps({'mcpServers':{'worldcore':server}},indent=2))
    prompt = 'Actually call WorldCore whatif_compare with question integration probe, scenarios a and b both actions [], objectives []. Report the real action_executed result; if unavailable say unavailable. Do not use other tools.'
    config = {'$schema':'https://opencode.ai/config.json', 'plugins':[str(ROOT/'adapters/opencode/v2')],
              'snapshots':False, 'permissions':[{'action':'*','resource':'*','effect':'deny'},
              {'action':'worldcore_whatif_compare','resource':'*','effect':'allow'}],
              'mcp':{'servers':{'worldcore':{'type':'local','command':[python,'-B','-m','worldcore.mcp_server'],
                      'environment':server_env,'disabled':False,'codemode':False}}}}
    (dest/'opencode.json').write_text(json.dumps(config,indent=2))
    # The installed V2 host required explicit configuration for a private run.
    env['OPENCODE_CONFIG_CONTENT'] = json.dumps(config)
    commands = {
        'claude':['claude','-p',prompt,'--output-format','json','--tools','',
                  '--allowedTools','mcp__worldcore__whatif_compare','--strict-mcp-config',
                  '--mcp-config',str(claude_config),'--setting-sources','',
                  '--no-session-persistence','--disable-slash-commands','--max-budget-usd','0.20'],
        'opencode':['opencode','--print-logs','--log-level','info','run','--standalone',
                    '--format','json','--model',args.model,prompt]}
    reports = {}
    for host, command in commands.items():
        if args.host not in ('both',host):
            continue
        before = receipts(database,'whatif_runs')
        result = bounded(command,timeout_seconds=35,cwd=dest,env=env,log_path=dest/(host+'.log'))
        result['new_whatif_receipts'] = receipts(database,'whatif_runs')-before
        result['tool_invocation_verified'] = result['new_whatif_receipts']>0
        # A successful text response or catalog connection alone cannot pass.
        result['integration_verified'] = result['outcome']=='passed' and result['tool_invocation_verified']
        reports[host] = result
        (dest/'results.json').write_text(json.dumps(reports,indent=2))
        print(host,result['outcome'],'tool_verified=',result['tool_invocation_verified'],flush=True)
    return 0 if reports and all(r['integration_verified'] for r in reports.values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
