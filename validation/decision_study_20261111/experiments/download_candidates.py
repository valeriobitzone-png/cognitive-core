from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,time,urllib.request,os
root=Path(__file__).resolve().parent
metadata=json.loads((root/'candidate-metadata.json').read_text())
selection=[('LiquidAI/LFM2.5-350M-GGUF','LFM2.5-350M-Q8_0.gguf'),
 ('ibm-granite/granite-4.0-350m-GGUF','granite-4.0-350m-Q8_0.gguf'),
 ('ggml-org/functiongemma-270m-it-GGUF','functiongemma-270m-it-q8_0.gguf'),
 ('LiquidAI/LFM2.5-350M','model.safetensors')]
manifest=[]
for repo,name in selection:
 d=metadata[repo];entry=next(x for x in d['siblings'] if x['rfilename']==name)
 assert entry['size']<900_000_000
 manifest.append({'repo':repo,'revision':d['sha'],'name':name,'bytes':entry['size'],
  'sha256':entry['lfs']['sha256'],'license':d.get('cardData',{}).get('license'),
  'folder':'lfm-hf' if name.endswith('.safetensors') else repo.split('/')[0]})
assert sum(x['bytes'] for x in manifest)<2_000_000_000
(root/'download-plan.json').write_text(json.dumps(manifest,indent=2))
def fetch(m):
 folder=root/'models'/m['folder'];folder.mkdir(parents=True,exist_ok=True)
 target=folder/m['name'];stage=target.with_suffix(target.suffix+'.part')
 if target.exists():
  assert hashlib.sha256(target.read_bytes()).hexdigest()==m['sha256'];return m['name']+' verified'
 request=urllib.request.Request('https://huggingface.co/'+m['repo']+'/resolve/'+m['revision']+'/'+m['name'])
 sha=hashlib.sha256();total=0;began=time.monotonic()
 with urllib.request.urlopen(request,timeout=30) as r,stage.open('xb') as out:
  while True:
   if time.monotonic()-began>900:raise TimeoutError('bounded download deadline')
   b=r.read(1024*1024)
   if not b:break
   total+=len(b)
   if total>m['bytes']:raise ValueError('size exceeded')
   out.write(b);sha.update(b)
 assert total==m['bytes'] and sha.hexdigest()==m['sha256']
 os.replace(stage,target)
 return m['name']+' verified'
with ThreadPoolExecutor(max_workers=3) as pool:
 for result in pool.map(fetch,manifest):print(result,flush=True)
# Tokenizer/config/license: explicit primary repo revision, no remote code execution.
repo='LiquidAI/LFM2.5-350M';d=metadata[repo];folder=root/'models/lfm-hf'
for entry in d['siblings']:
 name=entry['rfilename']
 if '/' not in name and (name.endswith('.json') or name in ('README.md','LICENSE')):
  with urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/'+d['sha']+'/'+name,timeout=30) as response:
   body=response.read(12_000_001)
  assert len(body)<=12_000_000
  (folder/name).write_bytes(body)
print('Candidate downloads complete',flush=True)
