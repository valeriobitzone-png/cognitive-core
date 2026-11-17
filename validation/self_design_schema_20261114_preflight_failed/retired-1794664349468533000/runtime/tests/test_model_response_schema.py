import json
from unittest.mock import patch
import pytest
from cognitive_core import CognitiveCore,Settings

@pytest.fixture
def c(tmp_path):
 c=CognitiveCore(Settings(home=tmp_path/'home',enable_local_model=True,local_model_gguf=str(tmp_path/'fixture.gguf')))
 (tmp_path/'fixture.gguf').write_bytes(b'fixture');yield c;c.close()

def test_structured_generation_reuses_quota_and_one_shot(c):
 schema={'type':'object','properties':{'answer':{'type':'string'}},'required':['answer'],'additionalProperties':False}
 with patch('cognitive_core.models.run_bounded',return_value='{"answer":"ciao"}') as run:
  out=c.run({'op':'model','prompt':'Give a constrained answer','response_schema':schema})
 assert out['status']=='generated' and out['model_calls']==1
 assert '--json-schema' in run.call_args.args[0]
 assert json.loads(run.call_args.args[0][run.call_args.args[0].index('--json-schema')+1])==schema
 assert c.vault.usage('program_model_calls')==1

@pytest.mark.parametrize('schema',[[],{'$ref':'https://remote.example/schema'},{'$ref':'file:///private/data'},{'description':'x'*8001}])
def test_unbounded_or_external_schemas_rejected_before_model(c,schema):
 with patch('cognitive_core.models.run_bounded',side_effect=AssertionError('model')):
  with pytest.raises(ValueError):c.run({'op':'model','prompt':'Do not execute','response_schema':schema})
 assert not c.s.home.exists()
