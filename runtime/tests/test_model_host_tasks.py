"""Generic Core host settings regressions; no real model calls."""
from unittest.mock import patch
import pytest
from cognitive_core import CognitiveCore,Settings
from cognitive_core.models import ModelProfile
from cognitive_core.ondemand import build_command

@pytest.mark.parametrize('kwargs',[{'local_model_device':'--evil'},{'local_model_device':'x;evil'},{'local_model_threads':True},{'local_model_threads':9},{'local_model_gpu_layers':100},{'local_model_gpu_layers':True}])
def test_invalid_host_hardware(kwargs):
 with pytest.raises(ValueError):Settings(**kwargs)

def test_default_hardware_and_opt_in_override(tmp_path):
 weights=tmp_path/'test.gguf';weights.write_bytes(b'GGUF')
 default=Settings(local_model_gguf=str(weights))
 command=build_command(default,tmp_path/'prompt','safe')
 for flag,value in [('--device','none'),('--gpu-layers','0'),('--threads','2')]:assert command[command.index(flag)+1]==value
 explicit=Settings(local_model_gguf=str(weights),local_model_device='MTL0',local_model_gpu_layers=99,local_model_threads=4)
 command=build_command(explicit,tmp_path/'prompt','safe')
 for flag,value in [('--device','MTL0'),('--gpu-layers','99'),('--threads','4')]:assert command[command.index(flag)+1]==value
 assert not explicit.enable_local_model

def test_host_task_keeps_core_rules_and_quota(tmp_path):
 weights=tmp_path/'test.gguf';weights.write_bytes(b'GGUF')
 c=CognitiveCore(Settings(home=tmp_path/'home',enable_local_model=True,local_model_gguf=str(weights)))
 try:
  c.program.models.register(ModelProfile('author',weights=str(weights),enabled=True,system_prompt='Write bounded SVG source.'))
  with patch('cognitive_core.models.run_bounded',return_value='{"svg":"fixture"}') as run:
   out=c.run({'op':'model','model':'author','prompt':'Draw a source fixture'})
  command=run.call_args.args[0];system=command[command.index('--system-prompt')+1]
  assert system.startswith('Write bounded SVG source.') and 'No tool calls are allowed' in system
  assert out['model_calls']==1 and c.vault.usage('program_model_calls')==1
  c.s.execution_mode='autonomous'
  with pytest.raises(PermissionError):c.program.models.register(ModelProfile('another'))
 finally:c.close()

@pytest.mark.parametrize('value',[None,123,'x'*3001])
def test_host_instruction_bounded(value):
 with pytest.raises(ValueError):ModelProfile('author',system_prompt=value)
