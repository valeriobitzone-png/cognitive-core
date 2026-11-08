"""JSON stdin/stdout bridge for host plugins; no network listener.

Security: host supplies a trusted owner id. Do not expose this bridge as a
network API without authenticating and binding that identity server-side.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
import os
import sys
from .engine import WorldCore, WorldCoreError, _check_id

MAX_REQUEST_BYTES = 64_000
MAX_REQUEST_ID_CHARS = 128


def dispatch(payload: dict, core: WorldCore) -> dict:
    if not isinstance(payload, dict): raise WorldCoreError("payload must be object")
    owner = payload.get("owner")
    space = payload.get("space", "default")
    op = payload.get("op")
    if op == "health":
        from . import __version__
        with core.lock:
            core.db.execute('SELECT 1').fetchone()
        return {'status':'ready','version':__version__,'protocol':'worldcore-jsonl-v1'}
    if op == "calibrated_predict":
        return core.predict_calibrated_world(owner,payload['family'],payload['before'],payload['action'],space=space,
            min_confidence=payload.get('min_confidence',.5),max_width=payload.get('max_width'),persist=payload.get('persist',False))
    if op == "calibrated_resolve":
        return core.resolve_calibrated_prediction(owner,payload['prediction_id'],payload['actual'],space=space,
            observed_at=payload.get('observed_at'),source='user_reported')
    if op == "adaptive_status":
        return core.adaptive_status(owner,payload["family"],space=space)
    if op == "adaptive_procedure":
        return core.recommend_adaptive_procedure(owner,payload["procedure"],space=space)
    if op == "calibrated_metrics":
        return core.calibrated_prediction_metrics(owner,payload['family'],space=space)
    if op == "whatif_compare":
        return core.compare_futures(owner,payload["question"],payload["scenarios"],space=space,objectives=payload.get("objectives",[]),failure_conditions=payload.get("failure_conditions",[]))
    if op == "whatif_stress_test":
        return core.whatif_stress_test(owner,payload["question"],payload["plans"],payload["shocks"],
             space=space,objectives=payload["objectives"])
    if op == "whatif_backcast":
        return core.whatif_backcast(owner,payload["question"],payload["target"],payload["candidate_actions"],
              space=space,max_depth=payload.get("max_depth",4),max_states=payload.get("max_states",1500),
              persist=payload.get("persist",False))
    if op == "whatif_replay":
        return core.whatif_replay(owner,payload["run_id"],space=space)
    if op == "whatif_history":
        return core.whatif_history(owner,space=space,limit=payload.get("limit",20))
    if op == "whatif_verify":
        return core.verify_whatif(owner,payload["run_id"],payload["selected"],payload["observed"],space=space,source="user_reported")
    if op == "context":
        return {"context":core.context_for(owner, payload.get("query", ""), space=space, limit=payload.get("limit", 5))}
    if op == "recall":
        return {"memories":core.recall(owner,payload.get("query", ""),space=space,limit=payload.get("limit",8))}
    if op == "remember":
        return {"memory":core.remember(owner,payload["key"],payload["value"],space=space,source="explicit_agent_request",kind=payload.get("kind","fact"))}
    if op == "event":
        return {"event":core.record_event(owner,payload["event_type"],payload["summary"],space=space,source=payload.get("source","host"),outcome=payload.get("outcome","observed"))}
    if op == "tick":
        return {"alerts":core.tick(owner,space=space)}
    if op == "alerts":
        return {"alerts":core.alerts(owner,space=space)}
    if op == "simulate":
        return core.simulate(owner,payload["actions"],space=space)
    if op == "estimate":
        return core.estimate_binary(owner,payload["context_key"],space=space)
    if op == "predict_model":
        return core.predict_model(owner,payload["model_id"],payload["features"],space=space)
    if op == "predict_transition":
        return core.predict_transition(owner,payload["model_id"],payload["current_state"],payload["action"],space=space)
    if op == "rollout_transitions":
        return core.rollout_transitions(owner,payload["model_id"],payload["initial_state"],payload["actions"],space=space)
    if op == "world_imagine":
        return core.imagine_world(owner,payload["environment"],payload["before"],payload["actions"],space=space)
    if op == "world_reliability":
        return core.world_model_metrics(owner,payload["environment"],space=space)
    if op == "news_market_study":
        return core.news_market_study(owner,payload["topic"],payload["symbol"],payload["benchmark"],space=space)
    if op == "social_velocity":
        return core.social_velocity(owner,payload["platform"],payload["post"],space=space)
    if op == "language_intent":
        return core.classify_intent(owner,payload["text"],space=space)
    if op == "repo_candidates":
        return core.search_repo_candidates(payload["query"],limit=payload.get('limit',8))
    if op == "world_predict_next":
        return core.predict_world_state(owner,payload['environment'],payload['before'],payload['action'],
                                        space=space,family=payload.get('family'))
    if op == "world_simulate_hybrid":
        return core.simulate_hybrid_world(owner,payload['environment'],payload['before'],payload['actions'],
                                          space=space,family=payload.get('family'))
    if op == "learned_world_dynamics":
        return core.predict_shared_dynamics(owner,payload["family"],payload["state"],payload["action"],space=space)
    if op == "verified_context_forecast":
        return core.forecast_verified_state(owner,payload["context_id"],payload["signal"],space=space,horizon_hours=payload.get("horizon_hours",1))
    if op == "personal_attention":
        return core.anticipate_needs(owner,space=space,horizon_hours=payload.get("horizon_hours",72))
    if op == "context_anomaly":
        return core.flag_state_anomaly(owner,payload["context_id"],payload["signal"],space=space)
    if op == "semantic_observe":
        return core.record_semantic_observation(owner,payload['context'],payload['claims'],space=space,
            modality=payload['modality'],source=payload['source'],verified_by_host=False)
    if op == "semantic_scene":
        return core.semantic_scene(owner,payload['context'],space=space)
    if op == "action_propose":
        return core.propose_real_action(owner,payload['action'],payload['args'],payload['purpose'],space=space)
    if op == "action_execute_approved":
        if os.getenv('WORLDCORE_HOST_REAL_ACTIONS')!='1':
            return {'status':'disabled','reason':'trusted host has not enabled local actions'}
        return core.execute_approved_action(owner,payload['request_id'],payload['action'],payload['args'],space=space)
    if op == "action_receipt":
        return core.action_receipt(owner,payload['request_id'],space=space) or {'status':'not_found'}
    if op == "ui_learn_transition":
        return core.record_ui_transition(owner,payload['app'],payload['goal'],payload['element'],payload['before'],payload['after'],
                                         payload['successful'],space=space)
    if op == "ui_predict_effect":
        return core.predict_ui_effect(owner,payload['goal'],payload['element'],space=space)
    if op == "ui_suggest_action":
        return core.suggest_ui_action(owner,payload['goal'],payload['elements'],space=space)
    if op == "calendar_upsert":
        return core.put_calendar_event(owner,payload['event_id'],payload['title'],payload['start_at'],payload['end_at'],space=space,place=payload.get('place','remote'))
    if op == "mail_signal_upsert":
        return core.put_mail_signal(owner,payload['signal_id'],payload['received_at'],payload['subject'],space=space,
          requires_reply=payload.get('requires_reply',True),replied=payload.get('replied',False),deadline=payload.get('deadline'))
    if op == "travel_observe":
        return core.observe_travel(owner,payload['origin'],payload['destination'],payload['observed_at'],payload['minutes'],space=space)
    if op == "travel_forecast":
        return core.travel_forecast(owner,payload['origin'],payload['destination'],space=space)
    if op == "day_advice":
        return core.day_advice(owner,payload['start_at'],payload['end_at'],space=space,from_place=payload.get('from_place'),now=payload.get('now'))
    if op == "optimize_stop_order":
        return core.optimize_stop_order(owner,payload['origin'],payload['stops'],space=space,end_at=payload.get('end_at'))
    if op == "recommend_slot":
        return core.recommend_slot(owner,payload['start_at'],payload['end_at'],payload['duration_minutes'],space=space,
                                   place=payload.get('place','remote'),from_place=payload.get('from_place'))
    if op == "forecast_stats":
        return core.forecast_stats(owner,space=space)
    raise WorldCoreError("unsupported bridge operation")


def _reject_constant(_value):
    raise WorldCoreError('nonfinite JSON numbers are not permitted')


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorldCoreError('duplicate JSON key')
        result[key] = value
    return result


def _decode_request(raw):
    if len(raw) > MAX_REQUEST_BYTES:
        raise WorldCoreError('request too large')
    try:
        payload = json.loads(raw.decode('utf-8'), parse_constant=_reject_constant,
                             object_pairs_hook=_unique_object)
        # Reject escaped lone surrogates as well as malformed UTF-8 bytes.
        json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except UnicodeError as exc:
        raise WorldCoreError('request must contain valid UTF-8 Unicode') from exc
    except RecursionError as exc:
        raise WorldCoreError('request nesting too deep') from exc
    if not isinstance(payload, dict):
        raise WorldCoreError('payload must be object')
    request_id = payload.get('_req')
    if request_id is not None and (not isinstance(request_id, str) or not 1 <= len(request_id) <= MAX_REQUEST_ID_CHARS):
        raise WorldCoreError('invalid request id')
    return payload


def _bind_scope(payload, owner, space):
    if owner is None:
        return payload  # Legacy transport: authenticated host supplies identity.
    if payload.get('op') in ('action_propose', 'action_execute_approved'):
        raise WorldCoreError('the bound worker does not execute or authorize real actions')
    if payload.get('owner', owner) != owner or payload.get('space', space) != space:
        raise WorldCoreError('request identity differs from worker scope')
    return {**payload, 'owner': owner, 'space': space}


def serve_lines(*, path=None, bound_owner=None, bound_space=None):
    """Bounded UTF-8 JSONL; an oversized frame closes the worker immediately.

    Read at most limit+1 bytes BEFORE parsing, so an oversized request without a
    newline or EOF cannot make the worker wait indefinitely or grow unbounded.
    Malformed bounded frames return an error and leave the next frame usable.
    """
    with WorldCore(path) as core:
        while True:
            raw = sys.stdin.buffer.readline(MAX_REQUEST_BYTES + 1)
            if not raw:
                return 0
            request_id = None
            try:
                payload = _decode_request(raw)
                request_id = payload.get('_req')
                payload = _bind_scope(payload, bound_owner, bound_space)
                result = {'ok': True, 'result': dispatch(payload, core)}
            except (WorldCoreError, ValueError, KeyError, TypeError, RecursionError) as exc:
                result = {'ok': False, 'error': str(exc)}
            result['_req'] = request_id
            print(json.dumps(result, ensure_ascii=False, allow_nan=False), flush=True)
            if len(raw) > MAX_REQUEST_BYTES:
                return 1  # Never drain an untrusted unterminated stream.


def worker_main():
    """Operator-bound worker entry point; model payloads cannot switch tenants."""
    from . import __version__
    parser = argparse.ArgumentParser(description='WorldCore local JSONL worker; no network listener')
    parser.add_argument('--db', default=os.getenv('WORLDCORE_DB'))
    parser.add_argument('--owner', default=os.getenv('WORLDCORE_OWNER', 'local'))
    parser.add_argument('--space', default=os.getenv('WORLDCORE_SPACE', 'default'))
    parser.add_argument('--version', action='version', version=__version__)
    args = parser.parse_args()
    try:
        owner = _check_id(args.owner, 'owner')
        space = _check_id(args.space, 'space')
    except WorldCoreError as exc:
        parser.error(str(exc))
    try:
        code = serve_lines(path=args.db, bound_owner=owner, bound_space=space)
    except (OSError, sqlite3.Error):
        print(json.dumps({'ok':False,'error':'worker storage unavailable','_req':None}), flush=True)
        code = 1
    raise SystemExit(code)


def main():
    if '--lines' in sys.argv[1:]:
        raise SystemExit(serve_lines())
    try:
        payload = _decode_request(sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1))
        with WorldCore() as core:
            result = dispatch(payload, core)
        print(json.dumps({'ok':True,'result':result},ensure_ascii=False,allow_nan=False))
    except (WorldCoreError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
