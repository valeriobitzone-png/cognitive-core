import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from certify_hermes_personal import verify_certificate


def fixture():
    whatif={'run_id':'receipt','action_executed':False,'scenarios':[
        {'id':'keep','projected_state':{'budget':120}}, {'id':'prepare','projected_state':{'budget':95}}]}
    advice={'events':[{'event_id':'conflict','conflict':True}], 'unanswered_mail':[{'subject':'mailtoken'}]}
    calls=[{'id':str(i),'function':{'name':name,'arguments':json.dumps({'question':'nonce'})}} for i,name in enumerate(['worldcore_personal_advice','worldcore_whatif'])]
    return {'process_outcome':'passed','nonce':'nonce','conflict_id':'conflict','mail_token':'mailtoken',
        'state_after':{'budget':100},'receipts':[{'id':'receipt','question':'nonce','result_json':json.dumps(whatif)}],
        'plugin_events':[{'source':'hermes','summary':'tool='+name+' status=ok duration_ms=3'} for name in ('worldcore_personal_advice','worldcore_whatif')],
        'result':{'completed':True,'failed':False,'final_response':'conflict mailtoken receipt false','messages':[
            {'role':'assistant','tool_calls':calls},
            {'role':'tool','tool_call_id':'0','content':json.dumps(advice)},
            {'role':'tool','tool_call_id':'1','content':json.dumps(whatif)}]}}


def test_complete_evidence_passes():
    assert verify_certificate(fixture())['verified']


@pytest.mark.parametrize('attack',['claim_only','provider_failed','tool_error','receipt_missing','wrong_nonce','wrong_projection','changed_state','no_hook','no_ack','foreign_tool'])
def test_claims_and_inconsistent_evidence_do_not_pass(attack):
    c=fixture()
    if attack=='claim_only':c['result']['messages']=[]
    elif attack=='provider_failed':c['result']['completed']=False
    elif attack=='tool_error':c['result']['messages'][2]['content']='{"error":"WorldCoreError"}'
    elif attack=='receipt_missing':c['receipts']=[]
    elif attack=='wrong_nonce':c['result']['messages'][0]['tool_calls'][1]['function']['arguments']='{"question":"other"}'
    elif attack=='wrong_projection':c['receipts'][0]['result_json']='{}'
    elif attack=='changed_state':c['state_after']['budget']=95
    elif attack=='no_hook':c['plugin_events']=[]
    elif attack=='no_ack':c['result']['final_response']='done'
    elif attack=='foreign_tool':c['result']['messages'][0]['tool_calls'][1]['function']['name']='shell'
    assert not verify_certificate(c)['verified']
