from pathlib import Path
import sys,json,tempfile,time,hashlib,resource
R=Path(__file__).resolve().parent;sys.path.insert(0,str(R/'runtime/src'))
from cognitive_core import CognitiveCore,Settings
from cognitive_core import ondemand
from unittest.mock import patch
archive=Path('/Volumes/AMBRO/projects/CognitiveCore/cognitive-core/validation/operational_20261110/isolated-home')
model=Path('/Volumes/AMBRO/models/rizzo-flow/rizzo-flow/spark-x2.5-4b-rizzo-flow-lora-q4_k_m.gguf')
fingerprint=lambda:{str(p.relative_to(archive)):hashlib.sha256(p.read_bytes()).hexdigest() for p in archive.rglob('*') if p.is_file()}
before=fingerprint();processes=[];original=ondemand.subprocess.Popen

def capture(*args,**kwargs):
 p=original(*args,**kwargs);processes.append(p);return p

with tempfile.TemporaryDirectory(prefix='cognitive-profile-smoke-') as td:
 c=CognitiveCore(Settings(home=Path(td),owner='ambrogio',namespace='realtest-bridge',enable_local_model=True,local_model_gguf=str(model),local_model_binary='/opt/homebrew/bin/llama-completion',local_model_jinja=True,max_model_file_bytes=3_000_000_000,model_timeout_seconds=30,max_cycle_seconds=35))
 event={'kind':'question_open','question':'Quali verifiche servono per CLICS4 e clima?'}
 with patch('cognitive_core.ondemand.subprocess.Popen',side_effect=capture):
  assert c.assess_local({'text':'ciao'},'/missing')['model_calls']==0
  assert c.assess_local({'kind':'external_action','text':'invia documento'},'/missing')['model_calls']==0
  start=time.monotonic();result=c.assess_local(event,archive);elapsed=time.monotonic()-start
  assert result['status']=='classified',result
  cached=c.assess_local(event,archive);assert cached['status']=='cached' and cached['model_calls']==0
 c.close()
assert before==fingerprint();assert all(p.poll() is not None for p in processes)
report={'elapsed_seconds':elapsed,'result':result,'cache_no_new_calls':True,'archive_unchanged':True,'inference_processes':len(processes),'remaining_processes':0,'peak_child_rss_bytes':resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,'network_calls':0,'paid_calls':0,'production_model_enabled':False,'note':'Real one-shot integration smoke; relevance schema, not the six-action routing accuracy benchmark.'}
(R/'profile-smoke-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='result'},indent=2))
