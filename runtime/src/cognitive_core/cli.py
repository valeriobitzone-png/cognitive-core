"""CLI: zero dependency testable entry point."""
import argparse
import json
import sys
from pathlib import Path
from .config import Settings
from .engine import CognitiveCore


def main(argv=None):
    p=argparse.ArgumentParser(description='Cognitive Core + WorldCore (local-first)')
    p.add_argument('--home',default=str(Path.home()/'.cognitive-core'))
    p.add_argument('--namespace',default='default')
    p.add_argument('--owner',default='local')
    p.add_argument('--web',action='store_true',help='Explicitly enable web fetching')
    p.add_argument('--allow-domain',action='append',default=[],help='Required HTTPS research allowlist; repeatable')
    p.add_argument('--searxng-url',default='',help='Optional SearXNG JSON endpoint')
    p.add_argument('--local-model',action='store_true',help='Enable OPTIONAL locally hosted model')
    p.add_argument('--local-model-url',default='http://127.0.0.1:8080/v1/chat/completions')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('status')
    sub.add_parser('tick',help='Process up to one research job; blocked without web permission')
    sub.add_parser('dry-run')
    x=sub.add_parser('daemon',help='Run low-activity scheduler loop');x.add_argument('--interval',type=float,default=20.0)
    x=sub.add_parser('observe');x.add_argument('event_json',help='JSON inline or @filename')
    x=sub.add_parser('topics');x.add_argument('--status',default=None)
    x=sub.add_parser('pause');x.add_argument('topic_id')
    x=sub.add_parser('discard');x.add_argument('topic_id')
    x=sub.add_parser('resume');x.add_argument('topic_id');x.add_argument('--seed-url',action='append',default=[])
    x=sub.add_parser('remember');x.add_argument('title');x.add_argument('text');x.add_argument('--source',default='')
    x=sub.add_parser('search');x.add_argument('query')
    x=sub.add_parser('export');x.add_argument('folder')
    x=sub.add_parser('benchmark');x.add_argument('cases',default='examples/decision_eval.jsonl')
    x=sub.add_parser('import-markdown');x.add_argument('folder')
    x=sub.add_parser('vision');x.add_argument('image_file');x.add_argument('--question',default='Describe the image and any uncertainty')
    x=sub.add_parser('compare');x.add_argument('scenarios_json',help='JSON list of alternatives')
    x=sub.add_parser('whatif');x.add_argument('payload_json',help='JSON or @file with question, scenarios, objectives')
    x=sub.add_parser('predict');x.add_argument('topic_id');x.add_argument('hypothesis');x.add_argument('probability',type=float);x.add_argument('horizon')
    x=sub.add_parser('resolve');x.add_argument('prediction_id');x.add_argument('happened',choices=['yes','no']);x.add_argument('--observation',default='')
    x=sub.add_parser('serve');x.add_argument('--port',type=int,default=8731)
    x=sub.add_parser('project');x.add_argument('project_id');x.add_argument('title');x.add_argument('keywords_json');x.add_argument('--importance',type=float,default=.5)
    x=sub.add_parser('feed');x.add_argument('event_json')
    x=sub.add_parser('opportunities');x.add_argument('--limit',type=int,default=20)
    x=sub.add_parser('briefing');x.add_argument('--as-of',default=None);x.add_argument('--hours',type=int,default=24);x.add_argument('--limit',type=int,default=5)
    x=sub.add_parser('prepare');x.add_argument('--capacity',type=float,default=0);x.add_argument('--limit',type=int,default=1)
    x=sub.add_parser('review');x.add_argument('opportunity_id');x.add_argument('status',choices=['dismissed','suggested']);x.add_argument('reason')
    x=sub.add_parser('opportunity-whatif');x.add_argument('opportunity_id');x.add_argument('payload_json')
    x=sub.add_parser('outcome');x.add_argument('opportunity_id');x.add_argument('useful',choices=['yes','no']);x.add_argument('evidence_ref')
    args=p.parse_args(argv)
    s=Settings(home=Path(args.home),namespace=args.namespace,owner=args.owner,enable_web=args.web,
               domain_allowlist=tuple(args.allow_domain),searxng_url=args.searxng_url,
               enable_local_model=args.local_model,local_model_url=args.local_model_url)
    core=CognitiveCore(s)
    try:
        if args.command=='status': out=core.status()
        elif args.command=='dry-run':out=core.work_once(dry_run=True)
        elif args.command=='tick':out=core.work_once()
        elif args.command=='daemon':
            import time
            if not 5<=args.interval<=3600:
                raise ValueError('interval must be 5..3600 seconds')
            print('Cognitive Core scheduler active (CTRL+C to stop)',flush=True)
            try:
                while True:
                    pending=core.vault.pending_jobs()
                    if pending:
                        print(json.dumps(core.work_once(),ensure_ascii=False),flush=True)
                    time.sleep(args.interval)
            except KeyboardInterrupt:
                return

        elif args.command=='observe':
            payload=Path(args.event_json[1:]).read_text(encoding='utf-8') if args.event_json.startswith('@') else args.event_json
            out=core.observe(json.loads(payload))
        elif args.command=='topics':out=core.vault.list_topics(args.status)
        elif args.command=='pause':out=core.vault.set_topic_status(args.topic_id,'paused')
        elif args.command=='discard':out=core.vault.set_topic_status(args.topic_id,'discarded')
        elif args.command=='resume':out={'job_id':core.resume(args.topic_id,args.seed_url)}
        elif args.command=='remember':out={'document_id':core.vault.document(args.title,args.text,args.source)}
        elif args.command=='search':out=core.memory_search(args.query)
        elif args.command=='export':out={'exported_documents':core.vault.export_markdown(Path(args.folder)),'path':args.folder}
        elif args.command=='benchmark':
            from .benchmark import evaluate
            out=evaluate(Path(args.cases),s)
        elif args.command=='import-markdown':
            from .obsidian import ingest_markdown_tree
            out=ingest_markdown_tree(core.vault,args.folder)
        elif args.command=='vision':
            from .vision import LocalVision
            out=LocalVision(s).describe_file(args.image_file,args.question)
        elif args.command=='project':out=core.drive.upsert_project(args.project_id,args.title,json.loads(args.keywords_json),args.importance)
        elif args.command=='feed':
            from worldcore.bridge import _decode_request
            raw=Path(args.event_json[1:]).read_bytes() if args.event_json.startswith('@') else args.event_json.encode('utf-8')
            out=core.drive.ingest(_decode_request(raw))
        elif args.command=='opportunities':out=core.drive.opportunities(args.limit)
        elif args.command=='briefing':out=core.drive.briefing(as_of=args.as_of,hours=args.hours,limit=args.limit)
        elif args.command=='prepare':out=core.drive.prepare(args.capacity,args.limit)
        elif args.command=='review':out=core.drive.review(args.opportunity_id,args.status,args.reason)
        elif args.command=='opportunity-whatif':
            from worldcore.bridge import _decode_request
            raw=Path(args.payload_json[1:]).read_bytes() if args.payload_json.startswith('@') else args.payload_json.encode('utf-8')
            data=_decode_request(raw)
            out=core.drive.compare(args.opportunity_id,data['scenarios'],objectives=data.get('objectives',[]))
        elif args.command=='outcome':out=core.drive.record_outcome(args.opportunity_id,args.useful=='yes',args.evidence_ref)
        elif args.command=='compare':
            # Legacy preference ranking uses -inf internally for forbidden options.
            import math
            out=[{**item,'score':item['score'] if math.isfinite(item['score']) else None}
                 for item in core.world.compare({},json.loads(args.scenarios_json))]
        elif args.command=='whatif':
            payload=Path(args.payload_json[1:]).read_text(encoding='utf-8') if args.payload_json.startswith('@') else args.payload_json
            from worldcore.bridge import _decode_request
            data=_decode_request(payload.encode('utf-8'))
            out=core.compare_futures(data['question'],data['scenarios'],objectives=data.get('objectives',[]),
                                     failure_conditions=data.get('failure_conditions'))
        elif args.command=='predict':out={'prediction_id':core.vault.predict(args.topic_id,args.hypothesis,args.probability,args.horizon)}
        elif args.command=='resolve':out={'brier_score':core.vault.resolve_prediction(args.prediction_id,args.happened=='yes',args.observation)}
        elif args.command=='serve':
            from .api import serve
            return serve(core,args.port)
        else: raise ValueError('unknown command')
        print(json.dumps(out,ensure_ascii=False,indent=2,allow_nan=False))
    finally:
        core.close()

if __name__=='__main__':main()
