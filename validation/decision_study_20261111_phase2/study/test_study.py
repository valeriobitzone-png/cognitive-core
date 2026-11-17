import ast,itertools,json,stat
from pathlib import Path
from unittest.mock import patch
import pytest
import bench_phase2 as b
R=Path(__file__).resolve().parent

def test_typed_protocol_matches_published_system_and_never_inserts_label():
 tree=ast.parse((R/'reference-source/prompts.py').read_text());official=next(ast.literal_eval(x.value) for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEM' for t in x.targets))
 item=b.D['dev'][0]['input']
 def fake(command,timeout):
  assert command[command.index('--system-prompt')+1]==official
  assert command[command.index('--predict')+1]=='1'
  assert '--jinja' in command and '--grammar' in command and '--json-schema' not in command
  p=Path(command[command.index('--file')+1]);text=p.read_text()
  assert '<evidence>\n' in text and '\nOptions:\nA. WAIT:' in text
  assert 'expected' not in text and 'dev-000' not in text
  assert stat.S_IMODE(p.stat().st_mode)==0o600
  return 'D'
 with patch.object(b.old,'run_bounded',side_effect=fake):out=b.call('rizzo4','typed',item)
 assert out['action']=='WEB_RESEARCH' and out['status']=='valid'

@pytest.mark.parametrize('state',[{'topic_status':'paused','browser_available':True,'web_opt_in':True,'requests_left':10,'local_sources':3},{'topic_status':'open','browser_available':True,'web_opt_in':False,'requests_left':10,'local_sources':3}])
def test_scope_and_consent_not_bypassed_in_measurement(state):
 assert not b.permitted('WEB_RESEARCH',{'state':state})

def test_longitudinal_equal_budget_and_finite_workload():
 report=json.loads((R/'longitudinal-results.json').read_text())
 for run in report['runs']:
  assert run['cost_units']<=24
  assert all(sum(v['family']==f for v in run['rows'])<=6 for f in ('csv','json','graph','noise'))
  assert run['successes']==sum(v['evidence']['correct'] for v in run['rows'])
  for v in run['rows']:
   if v['action']=='acquire_verified_procedure':assert v['observed_heldout_progress']==1 and v['family']!='noise'

def test_matrix_has_all_factor_combinations_and_same_cases():
 report=json.loads((R/'matrix-results.json').read_text());cells=report['summary'];assert len(cells)==32
 assert len({tuple(v['config'].values()) for v in cells})==32
 sets=[{x['id'] for x in report['rows'] if x['cell']==v['cell']} for v in cells]
 assert all(s==sets[0] for s in sets) and len(sets[0])==12
 assert len(report['rows'])==32*12*2
