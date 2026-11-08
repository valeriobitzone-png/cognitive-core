"""Operator CLI: deliberately keeps approvals outside agent-accessible MCP."""
from __future__ import annotations
import argparse
import json
import sys
from .engine import WorldCore, WorldCoreError


def main(argv: list[str] | None = None):
    p=argparse.ArgumentParser(prog="worldcore",description="Local-first cognitive layer")
    p.add_argument("--db", help="SQLite path (or WORLDCORE_DB)")
    p.add_argument("--owner",default="local",help="Trusted owner namespace (not authentication)")
    p.add_argument("--space",default="default",help="Workspace namespace")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("doctor")
    a=sub.add_parser("knowledge-add");a.add_argument("doc_id");a.add_argument("file");a.add_argument("--title",required=True);a.add_argument("--source-url",required=True);a.add_argument("--license",required=True)
    a=sub.add_parser("knowledge-search");a.add_argument("query");a.add_argument("--limit",type=int,default=5)
    sub.add_parser("knowledge-stats")
    a=sub.add_parser("ensemble-import");a.add_argument("model_id");a.add_argument("json_file",help="operator-only validated forest model JSON")
    a=sub.add_parser("ensemble-predict");a.add_argument("model_id");a.add_argument("features_json")
    a=sub.add_parser("ensemble-predict-raw");a.add_argument("model_id");a.add_argument("features_json")
    a=sub.add_parser("model-create");a.add_argument("model_id");a.add_argument("features_json");a.add_argument("--provenance",choices=["observed","synthetic","external"],default="observed")
    a=sub.add_parser("model-train");a.add_argument("model_id");a.add_argument("jsonl_file",help="Operator-only local JSONL dataset, max 20000 rows per invocation")
    a=sub.add_parser("model-evaluate");a.add_argument("model_id");a.add_argument("jsonl_file",help="Independent holdout JSONL (read only)")
    a=sub.add_parser("transition-evaluate");a.add_argument("model_id");a.add_argument("jsonl_file",help="Independent transition holdout JSONL")
    a=sub.add_parser("model-predict");a.add_argument("model_id");a.add_argument("features_json");a.add_argument("--min-samples",type=int,default=100)
    a=sub.add_parser("model-stats");a.add_argument("model_id")
    a=sub.add_parser("transition-create");a.add_argument("model_id");a.add_argument("--provenance",choices=["observed","synthetic","external"],default="observed")
    a=sub.add_parser("transition-record");a.add_argument("model_id");a.add_argument("sample_id");a.add_argument("current_state");a.add_argument("action");a.add_argument("next_state")
    a=sub.add_parser("transition-predict");a.add_argument("model_id");a.add_argument("current_state");a.add_argument("action")
    a=sub.add_parser("transition-rollout");a.add_argument("model_id");a.add_argument("initial_state");a.add_argument("actions_json")
    a=sub.add_parser('intel-add');a.add_argument('json_file',help='Trusted operator-supplied normalized metadata JSON')
    a=sub.add_parser('intel-search');a.add_argument('query');a.add_argument('--limit',type=int,default=10)
    a=sub.add_parser('intel-interest');a.add_argument('topic');a.add_argument('weight',type=float)
    a=sub.add_parser('intel-feedback');a.add_argument('source');a.add_argument('record_id');a.add_argument('--positive',action='store_true')
    a=sub.add_parser('intel-digest');a.add_argument('--limit',type=int,default=12)
    sub.add_parser('intel-stats')
    a=sub.add_parser('intel-public-search');a.add_argument('query');a.add_argument('--limit',type=int,default=8)
    a=sub.add_parser('intel-public-news');a.add_argument('--limit',type=int,default=10)
    sub.add_parser('intel-correlate')
    sub.add_parser('intel-timeline')
    a=sub.add_parser('intel-links');a.add_argument('entity');a.add_argument('--limit',type=int,default=20)
    a=sub.add_parser("remember"); a.add_argument("key"); a.add_argument("value"); a.add_argument("--source",default="operator")
    a=sub.add_parser("recall"); a.add_argument("query"); a.add_argument("--limit",type=int,default=8)
    a=sub.add_parser("history");a.add_argument("key")
    a=sub.add_parser("forget");a.add_argument("key")
    a=sub.add_parser("state-set");a.add_argument("key");a.add_argument("json_value")
    sub.add_parser("state-show")
    a=sub.add_parser("simulate");a.add_argument("json_actions")
    a=sub.add_parser("forecast");a.add_argument("claim");a.add_argument("expected",choices=["true","false"]);a.add_argument("probability",type=float);a.add_argument("due_at")
    a=sub.add_parser("resolve");a.add_argument("id");a.add_argument("observed",choices=["true","false"]);a.add_argument("--early",action="store_true")
    sub.add_parser("forecast-stats")
    a=sub.add_parser("observe");a.add_argument("context_key");a.add_argument("outcome",choices=["true","false"])
    a=sub.add_parser("estimate");a.add_argument("context_key")
    a=sub.add_parser("rule-add");a.add_argument("metric");a.add_argument("op",choices=[">",">=","<","<=","==","!="]);a.add_argument("threshold",type=float);a.add_argument("message");a.add_argument("--cooldown",type=int,default=3600)
    sub.add_parser("tick")
    a=sub.add_parser("request-action");a.add_argument("action");a.add_argument("json_args");a.add_argument("purpose")
    a=sub.add_parser("approve");a.add_argument("id");a.add_argument("--yes",action="store_true",help="Explicit operator approval; omit to deny")
    args=p.parse_args(argv)
    try:
        with WorldCore(args.db) as w:
            owner,space=args.owner,args.space
            c=args.command
            if c=="doctor":
                from . import __version__
                out={"db":w.path,"integrity":w.db.execute("PRAGMA integrity_check").fetchone()[0],"version":__version__}
            elif c=="knowledge-add":
                from pathlib import Path
                f=Path(args.file)
                if not f.is_file() or f.stat().st_size>250000:raise WorldCoreError('document missing or too large')
                out=w.ingest_document(owner,args.doc_id,f.read_text(encoding='utf-8'),space=space,
                      title=args.title,source_url=args.source_url,license=args.license)
            elif c=="knowledge-search":out=w.search_evidence(owner,args.query,space=space,limit=args.limit)
            elif c=="knowledge-stats":out=w.knowledge_stats(owner,space=space)
            elif c=="ensemble-import":
                from pathlib import Path
                f=Path(args.json_file)
                if not f.is_file() or f.stat().st_size>5000000:raise WorldCoreError('invalid ensemble file size')
                out=w.import_ensemble(owner,args.model_id,json.loads(f.read_text(encoding='utf-8')),space=space)
            elif c=="ensemble-predict":out=w.predict_ensemble(owner,args.model_id,json.loads(args.features_json),space=space)
            elif c=="ensemble-predict-raw":out=w.predict_raw_ensemble(owner,args.model_id,json.loads(args.features_json),space=space)
            elif c=="model-create":out=w.create_model(owner,args.model_id,json.loads(args.features_json),space=space,provenance=args.provenance)
            elif c=="model-train":
                from pathlib import Path
                file=Path(args.jsonl_file)
                if not file.is_file() or file.stat().st_size>12000000:raise WorldCoreError('dataset not found or >12MB')
                samples=[]
                with file.open('r',encoding='utf-8') as inp:
                    for line in inp:
                        if len(line)>4096 or len(samples)>=20000:raise WorldCoreError('dataset line too long or >20000 rows')
                        if line.strip():samples.append(json.loads(line))
                out=w.train_model(owner,args.model_id,samples,space=space)
            elif c in ("model-evaluate","transition-evaluate"):
                from pathlib import Path
                file=Path(args.jsonl_file)
                if not file.is_file() or file.stat().st_size>12000000:raise WorldCoreError('holdout not found or >12MB')
                holdout=[]
                with file.open('r',encoding='utf-8') as inp:
                    for line in inp:
                        if len(line)>4096 or len(holdout)>=20000:raise WorldCoreError('holdout line too long or >20000 rows')
                        if line.strip():holdout.append(json.loads(line))
                if c=='model-evaluate':out=w.evaluate_model(owner,args.model_id,holdout,space=space)
                else:out=w.evaluate_transitions(owner,args.model_id,holdout,space=space)
            elif c=="model-predict":out=w.predict_model(owner,args.model_id,json.loads(args.features_json),space=space,min_samples=args.min_samples)
            elif c=="model-stats":out=w.model_stats(owner,args.model_id,space=space)
            elif c=="transition-create":out=w.create_transition_model(owner,args.model_id,space=space,provenance=args.provenance)
            elif c=="transition-record":out=w.observe_transition(owner,args.model_id,args.current_state,args.action,args.next_state,sample_id=args.sample_id,space=space)
            elif c=="transition-predict":out=w.predict_transition(owner,args.model_id,args.current_state,args.action,space=space)
            elif c=="transition-rollout":out=w.rollout_transitions(owner,args.model_id,args.initial_state,json.loads(args.actions_json),space=space)
            elif c=='intel-add':
                from pathlib import Path
                f=Path(args.json_file)
                if not f.is_file() or f.stat().st_size>100000:raise WorldCoreError('evidence file too large or missing')
                out=w.learn_evidence(owner,json.loads(f.read_text(encoding='utf-8')),space=space)
            elif c=='intel-search':out=w.query_intelligence(owner,args.query,space=space,limit=args.limit)
            elif c=='intel-interest':
                w.set_interest(owner,args.topic,args.weight,space=space)
                out={'topic':args.topic,'weight':args.weight,'status':'user preference explicitly set'}
            elif c=='intel-feedback':out=w.feedback_on_record(owner,args.source,args.record_id,space=space,positive=args.positive)
            elif c=='intel-digest':out=w.personalized_digest(owner,space=space,limit=args.limit)
            elif c=='intel-stats':out=w.intelligence_stats(owner,space=space)
            elif c=='intel-public-search':out=w.query_public_catalog(args.query,limit=args.limit)
            elif c=='intel-public-news':out=w.personalized_public_digest(owner,space=space,limit=args.limit)
            elif c=='intel-correlate':out=w.find_associations(owner,space=space)
            elif c=='intel-timeline':out=w.temporal_associations(owner,space=space)
            elif c=='intel-links':out=w.query_links(owner,args.entity,space=space,limit=args.limit)
            elif c=="remember":out=w.remember(owner,args.key,args.value,space=space,source=args.source)
            elif c=="recall":out=w.recall(owner,args.query,space=space,limit=args.limit)
            elif c=="history":out=w.history(owner,args.key,space=space)
            elif c=="forget":out={"deleted":w.forget(owner,args.key,space=space)}
            elif c=="state-set":out=w.set_state(owner,args.key,json.loads(args.json_value),space=space)
            elif c=="state-show":out=w.state(owner,space=space)
            elif c=="simulate":out=w.simulate(owner,json.loads(args.json_actions),space=space)
            elif c=="forecast":out=w.forecast(owner,args.claim,args.expected=="true",args.probability,args.due_at,space=space)
            elif c=="resolve":out=w.resolve_forecast(owner,args.id,args.observed=="true",space=space,allow_early=args.early)
            elif c=="forecast-stats":out=w.forecast_stats(owner,space=space)
            elif c=="observe":out=w.observe_binary(owner,args.context_key,args.outcome=="true",space=space)
            elif c=="estimate":out=w.estimate_binary(owner,args.context_key,space=space)
            elif c=="rule-add":out=w.add_rule(owner,args.metric,args.op,args.threshold,args.message,space=space,cooldown_seconds=args.cooldown)
            elif c=="tick":out=w.tick(owner,space=space)
            elif c=="request-action":out=w.request_action(owner,args.action,json.loads(args.json_args),args.purpose,space=space)
            elif c=="approve":out=w.approve_action(owner,args.id,space=space,approve=args.yes)
            else:raise WorldCoreError("unhandled command")
        print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
        return 0
    except (WorldCoreError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print(f"worldcore error: {exc}",file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
