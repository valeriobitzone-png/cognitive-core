"""Verify real model -> Code Mode -> WorldCore -> model, with independent DB receipts.

No model response alone can pass. This script is opt-in, uses synthetic states
and operator-bound scopes, and denies shell, files and unrelated tools.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import mmap
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]


def verify_cycle(certificate):
    """Reconcile structured invocation, output, model acknowledgement and SQLite."""
    nonce=certificate['nonce'];receipts=certificate['receipts'];events=certificate['events']
    matched=[];unexpected=[];errors=0;acknowledgement='';catalog_ready=False;invoked_before_ready=False
    for event in events:
        part=event.get('part',{})
        if event.get('type')=='text':acknowledgement+='\n'+part.get('text','')
        if event.get('type')!='tool_use':continue
        state=part.get('state',{})
        metadata=state.get('metadata',{}).get('metadata',{})
        if state.get('status')!='completed' or metadata.get('error'):errors+=1
        for call in metadata.get('toolCalls',[]):
            discovery=(call.get('tool')=='search' and call.get('status')=='completed'
                       and call.get('input')=={'query':'whatif_compare','namespace':'worldcore','limit':5})
            if discovery:
                try:catalog=json.loads(state.get('output',''))
                except (ValueError,TypeError):catalog={}
                catalog_ready=catalog_ready or (isinstance(catalog,dict) and isinstance(catalog.get('items'),list) and any(isinstance(item,dict) and item.get('path')=='tools.worldcore.whatif_compare' for item in catalog['items']))
            elif call.get('tool')!='worldcore.whatif_compare':unexpected.append(call.get('tool'))
            if call.get('tool')=='worldcore.whatif_compare' and call.get('status')=='completed' and call.get('input',{}).get('question')==nonce:
                if not catalog_ready:invoked_before_ready=True
                try:output=json.loads(state.get('output',''))
                except (ValueError,TypeError):continue
                if isinstance(output,dict):matched.append(output)
    expected=certificate['expected_budgets']
    checks={'process_passed':certificate['process_outcome']=='passed',
            'one_scoped_receipt':len(receipts)==1 and receipts[0]['question']==nonce,
            'structured_tool_result':len(matched)==1,
            'no_unrelated_nested_tool':not unexpected,
            'no_tool_errors':errors==0,
            'catalog_ready':(catalog_ready and not invoked_before_ready) if certificate.get('require_discovery') else True,
            'real_state_unchanged':certificate['state_after']==certificate['state_before'],
            'native_plugin_hook':any(e.get('source')=='opencode-v2' and e.get('summary')=='tool=worldcore_whatif_compare completed=true' for e in certificate['plugin_events'])}
    if len(receipts)==1 and len(matched)==1:
        receipt=receipts[0];result=matched[0]
        try:
            actual={s['id']:s['projected_state']['budget'] for s in receipt['result']['scenarios']}
            returned={s['id']:s['projected_state']['budget'] for s in result.get('scenarios',[])}
        except (KeyError,TypeError):
            actual=returned=None
        checks.update(receipt_matches_tool_id=result.get('run_id')==receipt['id'],
                      scenarios_match_expected=actual==expected and returned==expected,
                      simulation_only=result.get('action_executed') is False and receipt['result'].get('action_executed') is False,
                      model_acknowledges_result=receipt['id'] in acknowledgement and 'false' in acknowledgement.lower())
    else:
        checks.update(receipt_matches_tool_id=False,scenarios_match_expected=False,simulation_only=False,model_acknowledges_result=False)
    return {'verified':all(checks.values()),'checks':checks,'tool_errors':errors,'unexpected_nested_tools':unexpected}


def run_case(output, *, python, model, case):
    sys.path.insert(0,str(ROOT/'src'))
    from worldcore import WorldCore
    from run_bounded_pytests import bounded
    dest=output/f'case_{case}';dest.mkdir(parents=True,exist_ok=True)
    nonce='cert_'+uuid.uuid4().hex;owner='certification';space=nonce
    database=dest/'worldcore.db';initial=100+case
    with WorldCore(database) as core:core.set_state(owner,'budget',initial,space=space)
    server_env={'PYTHONPATH':str(ROOT/'src'),'PYTHONDONTWRITEBYTECODE':'1','WORLDCORE_DB':str(database),'WORLDCORE_OWNER':owner,'WORLDCORE_SPACE':space}
    config={'$schema':'https://opencode.ai/config.json','snapshots':False,'plugins':[str(ROOT/'adapters/opencode/v2')],
            'permissions':[{'action':'*','resource':'*','effect':'deny'},
                           {'action':'execute','resource':'*','effect':'allow'},
                           {'action':'worldcore_whatif_compare','resource':'*','effect':'allow'}],
            'mcp':{'servers':{'worldcore':{'type':'local','command':[python,'-B','-m','worldcore.mcp_server'],
                    'environment':server_env,'codemode':True,'disabled':False}}}}
    (dest/'config.json').write_text(json.dumps(config,indent=2))
    env={**os.environ,**server_env,'WORLDCORE_PYTHON':python,'PWD':str(dest),
         'XDG_CONFIG_HOME':str(dest/'config'),'XDG_DATA_HOME':str(dest/'data'),'XDG_CACHE_HOME':str(dest/'cache'),
         'OPENCODE_CONFIG_CONTENT':json.dumps(config)}
    params={'question':nonce,'scenarios':[{'id':'save','actions':[{'op':'add','key':'budget','value':-10}]},
                                        {'id':'spend','actions':[{'op':'add','key':'budget','value':10}]}],
            'objectives':[{'key':'budget','direction':'minimize','scale':1}]}
    code='const result = await tools["worldcore"].whatif_compare('+json.dumps(params)+'); return result;'
    prompt=('First invoke execute with code: return await search({query:"whatif_compare",namespace:"worldcore",limit:5}); '
            'If items is empty repeat that discovery in a NEW execute call, at most three discovery calls total. '
            'Proceed only when a nonempty discovery result lists whatif_compare; otherwise stop and report unavailable. '
            'Then invoke execute with this exact JavaScript: '+code+
            ' Await the actual result, then answer with its run_id and action_executed=false. '
            'Do not print proposed code instead of invoking execute, and do not fabricate the result.')
    process=bounded(['opencode','--print-logs','--log-level','info','run','--standalone','--format','json','--model',model,prompt],
                    cwd=dest,env=env,timeout_seconds=120,log_path=dest/'host.log')
    log_path=dest/'host.log'
    with log_path.open('rb',buffering=0) as stream:
        if log_path.stat().st_size:
            with mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as view:raw=view[:].decode(errors='replace')
        else:raw=''
    events=[]
    for line in raw.splitlines():
        if line.startswith('{'):
            try:events.append(json.loads(line))
            except ValueError:pass
    with WorldCore(database) as core:
        rows=core.db.execute('SELECT id,question,result_json FROM whatif_runs WHERE owner=? AND space=?',(owner,space)).fetchall()
        state_after=core.state(owner,space=space);plugin_events=core.events(owner,space=space)
    certificate={'nonce':nonce,'require_discovery':True,'model':model,'process_outcome':process['outcome'],'events':events,
                 'receipts':[{'id':r['id'],'question':r['question'],'result':json.loads(r['result_json'])} for r in rows],
                 'state_before':{'budget':initial},'state_after':state_after,'expected_budgets':{'save':initial-10,'spend':initial+10},
                 'plugin_events':plugin_events,'permissions':config['permissions'],'user_authorized_code_mode':True,
                 'log_sha256':hashlib.sha256(raw.encode()).hexdigest(),
                 'reported_cost_usd':sum(e.get('part',{}).get('cost',0) for e in events if e.get('type')=='step_finish')}
    certificate['verification']=verify_cycle(certificate)
    (dest/'certificate.json').write_text(json.dumps(certificate,indent=2))
    (dest/'process.json').write_text(json.dumps(process,indent=2))
    return {'case':case,**certificate['verification'],'model':model,'duration_seconds':process['duration_seconds'],
            'reported_cost_usd':certificate['reported_cost_usd'],'certificate':str(dest/'certificate.json')}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--model',required=True)
    parser.add_argument('--repeats',type=int,default=3,choices=range(1,6))
    parser.add_argument('--allow-code-mode',action='store_true',help='Explicitly authorize execute for this isolated synthetic probe')
    args=parser.parse_args()
    if not args.allow_code_mode:parser.error('Explicit --allow-code-mode authorization is required')
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    reports=[]
    for case in range(1,args.repeats+1):
        result=run_case(output,python=sys.executable,model=args.model,case=case)
        reports.append(result)
        (output/'summary.json').write_text(json.dumps({'results':reports,'requested_repeats':args.repeats,'completed_repeats':len(reports),
            'complete':len(reports)==args.repeats,'all_verified':len(reports)==args.repeats and all(r['verified'] for r in reports)},indent=2))
        print(json.dumps(result),flush=True)
        if not result['verified']:return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
