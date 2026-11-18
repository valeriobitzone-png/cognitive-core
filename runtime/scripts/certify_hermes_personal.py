"""Native Hermes/LLM certification against synthetic offline workspaces.

Model text is insufficient: reconcile structured calls, tool results, independent
SQLite receipts, native hooks, unchanged state and unknown fixture identifiers.
"""
from pathlib import Path
import argparse
import json
import mmap
import os
import sqlite3
import sys
from run_bounded_pytests import bounded

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    if not path.stat().st_size:return b''
    with path.open('rb') as stream:
        with mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as view:return view[:]


def verify_certificate(c):
    result=c.get('result',{});calls={};outputs={};errors=[]
    for message in result.get('messages',[]):
        if message.get('role')=='assistant':
            for call in message.get('tool_calls',[]):
                if isinstance(call,dict):calls[call.get('id')]=call.get('function',{})
        elif message.get('role')=='tool':
            try:output=json.loads(message.get('content',''))
            except (ValueError,TypeError):output=None
            outputs[message.get('tool_call_id')]=output
            if not isinstance(output,dict) or output.get('error') or output.get('status')=='unavailable':errors.append('tool_error')
    names=[f.get('name') for f in calls.values()]
    receipts=c.get('receipts',[]);ack=str(result.get('final_response',''))
    actual={calls[i].get('name'):output for i,output in outputs.items() if i in calls}
    whatif=actual.get('worldcore_whatif',{});advice=actual.get('worldcore_personal_advice',{})
    if not isinstance(whatif,dict):whatif={}
    if not isinstance(advice,dict):advice={}
    checks={'process_passed':c.get('process_outcome')=='passed','native_completed':result.get('completed') is True and not result.get('failed'),
        'two_expected_calls':sorted(names)==['worldcore_personal_advice','worldcore_whatif'],
        'all_calls_have_results':set(calls)==set(outputs),'no_tool_errors':not errors,
        'one_scoped_receipt':len(receipts)==1 and receipts[0].get('question')==c.get('nonce'),
        'state_unchanged':c.get('state_after')=={'budget':100},
        'grounded_conflict':any(isinstance(e,dict) and e.get('event_id')==c.get('conflict_id') and e.get('conflict') is True for e in advice.get('events',[])),
        'grounded_mail':any(c.get('mail_token','MISSING') in str(m.get('subject','')) for m in advice.get('unanswered_mail',[]) if isinstance(m,dict)),
        'model_acknowledges_grounding':bool(c.get('conflict_id')) and c['conflict_id'] in ack and c.get('mail_token','MISSING') in ack,
        'native_hooks':all(any(e.get('source')=='hermes' and ('tool='+name+' status=ok ') in e.get('summary','') for e in c.get('plugin_events',[])) for name in ('worldcore_personal_advice','worldcore_whatif'))}
    try:checks['call_nonce_matches']=any(f.get('name')=='worldcore_whatif' and json.loads(f.get('arguments',''))['question']==c.get('nonce') for f in calls.values())
    except (ValueError,TypeError,KeyError):checks['call_nonce_matches']=False
    try:
        receipt=receipts[0];stored=json.loads(receipt['result_json'])
        projected={s['id']:s['projected_state']['budget'] for s in whatif['scenarios']}
        stored_projected={s['id']:s['projected_state']['budget'] for s in stored['scenarios']}
        checks.update(receipt_matches=whatif.get('run_id')==receipt['id'],
                      projections_match=projected==stored_projected=={'keep':120,'prepare':95},
                      no_action=whatif.get('action_executed') is False and stored.get('action_executed') is False,
                      model_acknowledges_receipt=receipt['id'] in ack and 'false' in ack.lower())
    except (KeyError,IndexError,TypeError,ValueError):
        checks.update(receipt_matches=False,projections_match=False,no_action=False,model_acknowledges_receipt=False)
    return {'verified':all(checks.values()),'checks':checks}


def verify_case(directory):
    c=json.loads(read(directory/'certificate.json'));process=json.loads(read(directory/'process.json'))
    c['process_outcome']=process['outcome'];result=verify_certificate(c)
    with sqlite3.connect(f'file:{directory / "worldcore.db"}?mode=ro',uri=True) as con:
        rows=con.execute('SELECT id,question,result_json FROM whatif_runs WHERE owner=? AND space=?',(c['owner'],c['space'])).fetchall()
        checks=result['checks']
        checks['sqlite_integrity']=con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        checks['database_matches']=len(rows)==1 and [{'id':r[0],'question':r[1],'result_json':r[2]} for r in rows]==c['receipts']
        checks['no_action_receipts']=con.execute('SELECT COUNT(*) FROM action_receipts').fetchone()[0]==0
    result['verified']=all(result['checks'].values())
    result['duration_seconds']=process['duration_seconds'];result['worldcore_version']=c.get('worldcore_version')
    (directory/'verification.json').write_text(json.dumps(result,indent=2))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path);parser.add_argument('--hermes-root',required=True,type=Path)
    parser.add_argument('--hermes-python',required=True,type=Path)
    parser.add_argument('--repeats',type=int,default=3,choices=range(1,6))
    parser.add_argument('--allow-model-calls',action='store_true')
    args=parser.parse_args()
    if not args.allow_model_calls:parser.error('explicit --allow-model-calls required')
    if not os.getenv('GROQ_API_KEY'):parser.error('host GROQ_API_KEY is required; never place credentials in fixtures')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True);reports=[]
    for index in range(args.repeats):
        dest=output/f'case_{index+1}';dest.mkdir()
        env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1',
             'PYTHONPATH':str(ROOT/'src')+os.pathsep+str(args.hermes_root.resolve()),
             'WORLDCORE_SOURCE':str(ROOT),'LAB_OUTPUT':str(dest),'HERMES_HOME':str(dest/'home'),
             'HERMES_ENABLE_PROJECT_PLUGINS':'0'}
        process=bounded([str(args.hermes_python.absolute()),'-B',str(ROOT/'scripts/hermes_personal_cycle.py')],
            cwd=dest,env=env,timeout_seconds=120,log_path=dest/'host.log')
        (dest/'process.json').write_text(json.dumps(process,indent=2))
        result=verify_case(dest) if (dest/'certificate.json').exists() else {'verified':False,'reason':'no_certificate'}
        reports.append(result)
        (output/'summary.json').write_text(json.dumps({'results':reports,'requested_repeats':args.repeats,
            'completed_repeats':len(reports),'complete':len(reports)==args.repeats,
            'all_verified':len(reports)==args.repeats and all(r['verified'] for r in reports)},indent=2))
        print(json.dumps({'case':index+1,**result}),flush=True)
        if not result['verified']:return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
