from pathlib import Path
import hashlib,json,subprocess,sys,zipfile
root=Path(__file__).resolve().parent;wheel=next((root/'dist').glob('*.whl'))
with zipfile.ZipFile(wheel) as package:
 files=list((root/'runtime/src').glob('*/*.py'))
 assert all(package.read(str(p.relative_to(root/'runtime/src')))==p.read_bytes() for p in files)
code='''import sys,tempfile,pathlib
sys.path.insert(0,sys.argv[1])
from unittest.mock import patch
from cognitive_core import CognitiveCore,Settings
from cognitive_core.decision import Decision
with tempfile.TemporaryDirectory() as folder:
 root=pathlib.Path(folder)
 original=CognitiveCore(Settings(home=root/'archive'))
 original.vault.document('runner','runner recovery source evidence');original.close()
 model=root/'model.gguf';model.write_bytes(b'GGUF')
 c=CognitiveCore(Settings(home=root/'sidecar',enable_local_model=True,local_model_gguf=str(model)))
 assert c.assess_local({'text':'ciao'},'/missing')['model_calls']==0
 with patch('cognitive_core.advisor.infer',return_value=Decision('STORE_ONLY',.5,'inspect',model_used=True)):
  assert c.assess_local({'kind':'question_open','question':'runner recovery'},root/'archive')['status']=='classified'
 assert c.assess_local({'kind':'question_open','question':'runner recovery'},root/'archive')['status']=='cached'
 assert not c.s.db_path.exists();c.close()
print('wheel archive/advisor/cache/reflex OK')
'''
r=subprocess.run([sys.executable,'-I','-S','-B','-c',code,str(wheel)],capture_output=True,text=True,timeout=20)
assert r.returncode==0,r.stderr
report={'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'python_files_compared':len(files),
 'isolated_smoke':r.stdout.strip(),'python':sys.version.split()[0],'external_dependencies':False}
(root/('wheel-'+str(sys.version_info.major)+str(sys.version_info.minor)+'.json')).write_text(json.dumps(report,indent=2));print(json.dumps(report))
