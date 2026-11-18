"""A confident model claim cannot substitute for a matching tool/DB receipt."""
import copy
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from certify_opencode import verify_cycle


def valid_certificate():
    receipt={'id':'receipt123','question':'nonce','result':{'scenarios':[
       {'id':'save','projected_state':{'budget':90}}, {'id':'spend','projected_state':{'budget':110}}],
       'action_executed':False}}
    output={**receipt['result'],'run_id':receipt['id']}
    return {'nonce':'nonce','receipts':[receipt],'events':[
      {'type':'tool_use','part':{'state':{'status':'completed','output':json.dumps(output),
         'metadata':{'metadata':{'toolCalls':[{'tool':'worldcore.whatif_compare','status':'completed','input':{'question':'nonce'}}]}}}}},
      {'type':'text','part':{'text':'run_id=receipt123 action_executed=false'}}],
      'process_outcome':'passed','expected_budgets':{'save':90,'spend':110},
      'state_before':{'budget':100},'state_after':{'budget':100},
      'plugin_events':[{'source':'opencode-v2','summary':'tool=worldcore_whatif_compare completed=true'}]}


def test_matching_evidence_passes():
    assert verify_cycle(valid_certificate())['verified']


@pytest.mark.parametrize('attack', ['claim_without_call','wrong_id','wrong_nonce','wrong_projection','real_mutation',
    'no_ack','no_hook','process_failed','tool_error','foreign_tool','nonobject_output','double_receipt'])
def test_missing_or_forged_evidence_cannot_pass(attack):
    c=valid_certificate()
    if attack=='claim_without_call':c['events']=c['events'][1:];c['receipts']=[]
    elif attack=='wrong_id':c['receipts'][0]['id']='different'
    elif attack=='wrong_nonce':c['receipts'][0]['question']='other'
    elif attack=='wrong_projection':c['receipts'][0]['result']['scenarios'][0]['projected_state']['budget']=500
    elif attack=='real_mutation':c['state_after']['budget']=90
    elif attack=='no_ack':c['events']=c['events'][:1]
    elif attack=='no_hook':c['plugin_events']=[]
    elif attack=='process_failed':c['process_outcome']='failed'
    elif attack=='tool_error':c['events'][0]['part']['state']['metadata']['metadata']['error']=True
    elif attack=='foreign_tool':c['events'][0]['part']['state']['metadata']['metadata']['toolCalls'].append({'tool':'shell'})
    elif attack=='nonobject_output':c['events'][0]['part']['state']['output']='123'
    elif attack=='double_receipt':c['receipts'].append(copy.deepcopy(c['receipts'][0]))
    assert not verify_cycle(c)['verified']


def test_discovery_requires_nonempty_catalog_and_rejects_other_queries():
    c=valid_certificate();c['require_discovery']=True
    assert not verify_cycle(c)['verified']
    event={'type':'tool_use','part':{'state':{'status':'completed','output':json.dumps({'items':[{'path':'tools.worldcore.whatif_compare'}]}),
       'metadata':{'metadata':{'toolCalls':[{'tool':'search','status':'completed','input':{'query':'whatif_compare','namespace':'worldcore','limit':5}}]}}}}}
    c['events'].insert(0,event)
    assert verify_cycle(c)['verified']
    event['part']['state']['output']='{"items":[]}'
    assert not verify_cycle(c)['verified']
    event['part']['state']['output']='{"items":["worldcore.whatif_compare"]}'
    event['part']['state']['metadata']['metadata']['toolCalls'][0]['input']['namespace']='shell'
    assert not verify_cycle(c)['verified']


def test_catalog_observed_after_invocation_is_too_late():
    c=valid_certificate();c['require_discovery']=True
    c['events'].append({'type':'tool_use','part':{'state':{'status':'completed',
        'output':'{"items":[{"path":"tools.worldcore.whatif_compare"}]}',
        'metadata':{'metadata':{'toolCalls':[{'tool':'search','status':'completed',
            'input':{'query':'whatif_compare','namespace':'worldcore','limit':5}}]}}}}})
    assert not verify_cycle(c)['verified']
