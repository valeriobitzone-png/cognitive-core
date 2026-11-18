"""Host-bound JSONL entry point sharing the hardened WorldCore wire protocol.

No web tick or model dispatch is exposed. The embedding host explicitly runs
research through the CLI/Python API after configuring its network policy.
"""

import argparse
import json
import sqlite3
import sys
from .config import Settings
from .engine import CognitiveCore
from worldcore.bridge import MAX_REQUEST_BYTES, _decode_request, _bind_scope
from worldcore.bridge import dispatch as world_dispatch


def dispatch(payload, core):
    autonomous_ops = {
        'cognitive_run',
        'health',
        'cognitive_cycle',
        'cognitive_observe',
        'cognitive_status',
        'cognitive_topics',
        'cognitive_search',
        'cognitive_dry_run',
        'cognitive_feed_ingest',
        'cognitive_opportunities',
        'cognitive_briefing',
        'recall',
        'context',
        'alerts',
        'whatif_history',
        'whatif_replay',
        'forecast_stats',
    }
    if core.s.execution_mode == 'autonomous' and payload.get('op') not in autonomous_ops:
        raise PermissionError('operation requires interactive authority')
    payload = _bind_scope(payload, core.s.owner, core.s.namespace)
    op = payload.get('op')
    if not isinstance(op, str):
        raise ValueError('operation must be text')
    if op == 'health':
        from . import __version__

        return {'status': 'ready', 'version': __version__, 'protocol': 'worldcore-jsonl-v1', 'components': ['cognitive_core', 'worldcore'], 'network_enabled': False}
    if op == 'cognitive_run':
        return core.run(payload['request'])
    if op == 'cognitive_cycle':
        return core.cycle_once(payload.get('topic_id'))
    if op == 'cognitive_observe':
        return core.observe(payload['event'])
    if op == 'cognitive_status':
        return core.status()
    if op == 'cognitive_topics':
        return {'topics': core.vault.list_topics(payload.get('status'))}
    if op == 'cognitive_search':
        return {'memories': core.memory_search(payload.get('query', ''), payload.get('limit', 10))}
    if op == 'cognitive_dry_run':
        return core.work_once(dry_run=True)
    if op == 'cognitive_feed_ingest':
        return core.drive.ingest(payload['event'])
    if op == 'cognitive_opportunities':
        return {'opportunities': core.drive.opportunities(payload.get('limit', 20))}
    if op == 'cognitive_briefing':
        return core.drive.briefing(hours=payload.get('hours', 24), limit=payload.get('limit', 5))
    if op.startswith('cognitive_'):
        raise ValueError('unsupported cognitive operation')
    return world_dispatch(payload, core.worldcore)


def main():
    parser = argparse.ArgumentParser(description='Cognitive Core + WorldCore host-bound local worker')
    parser.add_argument('--home', default=None)
    parser.add_argument('--owner', default='local')
    parser.add_argument('--namespace', default='default')
    parser.add_argument('--authority', choices=['interactive', 'autonomous'], default='interactive')
    args = parser.parse_args()
    settings = {'owner': args.owner, 'namespace': args.namespace, 'execution_mode': args.authority}
    if args.home is not None:
        settings['home'] = args.home
    core = CognitiveCore(Settings(**settings))
    try:
        while True:
            raw = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
            if not raw:
                return
            ident = None
            try:
                payload = _decode_request(raw)
                ident = payload.get('_req')
                response = {'ok': True, 'result': dispatch(payload, core)}
            except (ValueError, KeyError, TypeError, RecursionError, sqlite3.Error, OSError) as exc:
                response = {'ok': False, 'error': str(exc)[:500]}
            print(json.dumps({**response, '_req': ident}, ensure_ascii=False, allow_nan=False), flush=True)
            if len(raw) > MAX_REQUEST_BYTES:
                raise SystemExit(1)
    finally:
        core.close()


if __name__ == '__main__':
    main()
