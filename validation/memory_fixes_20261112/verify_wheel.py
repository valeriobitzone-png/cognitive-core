from pathlib import Path
import hashlib,json,subprocess,tempfile,zipfile
r=Path(__file__).resolve().parent;wheel=next((r/'wheel').glob('*.whl'))
code='''
import sys,tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from cognitive_core import CognitiveCore,Settings
from cognitive_core.portable import restore_state
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);c=CognitiveCore(Settings(home=p/'a',owner='test',namespace='wheel'))
 first=c.memory.remember('p','city','Roma','fixture',valid_from=100)
 c.memory.remember('p','city','Milano','fixture',valid_from=200)
 assert c.memory.recall('p','city')['value']=='Milano'
 assert c.memory_search('Milano')[0]['kind']=='shared_memory'
 c.memory.remember('p','secret','private-token','fixture');c.memory.suppress('p','secret')
 c.export_state(p/'export');c.close();restore_state(p/'export',p/'b')
 c=CognitiveCore(Settings(home=p/'b',owner='test',namespace='wheel'))
 assert c.memory.recall('p','city')['value']=='Milano'
 assert len(c.memory.history('p','city'))==2
 assert c.memory_search('private-token')==[]
 c.close()
print('temporal memory, unified retrieval, suppression, portable roundtrip OK')
'''
with tempfile.TemporaryDirectory() as tmp:
 with zipfile.ZipFile(wheel) as z:
  modules=[n for n in z.namelist() if n.endswith('.py') and n.startswith(('cognitive_core/','worldcore/'))]
  for n in modules:assert z.read(n)==(r/'runtime/src'/n).read_bytes(),n
  z.extractall(tmp)
 results=[]
 for python in ('/opt/homebrew/bin/python3.11','/Users/ambrogio/Developer/cc-venv-test/bin/python'):
  p=subprocess.run([python,'-I','-B','-c',code,tmp],capture_output=True,text=True,timeout=30)
  assert p.returncode==0,p.stdout+p.stderr
  results.append({'python':subprocess.check_output([python,'--version'],text=True).strip(),'result':p.stdout.strip()})
output={'wheel':str(wheel),'sha256':hashlib.sha256(wheel.read_bytes()).hexdigest(),'modules_compared':len(modules),'isolated_smokes':results}
(r/'wheel-check.json').write_text(json.dumps(output,indent=2));print(json.dumps(output,indent=2))
