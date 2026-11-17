from pathlib import Path
import json,urllib.request,hashlib,time,concurrent.futures,os
R=Path(__file__).resolve().parent
plan=json.loads((R/'download-plan.json').read_text())
def download(x):
 p=R/'models'/x['name'];partial=p.with_suffix('.partial')
 if p.exists():return 'already complete'
 offset=partial.stat().st_size if partial.exists() else 0
 req=urllib.request.Request('https://huggingface.co/'+x['repo']+'/resolve/'+x['revision']+'/'+x['name']+'?download=true',headers={'Range':f'bytes={offset}-'})
 began=time.monotonic()
 with urllib.request.urlopen(req,timeout=60) as response:
  assert response.status==206 and response.headers.get('Content-Range','').startswith(f'bytes {offset}-'),'Range unsupported; original partial preserved'
  with partial.open('ab') as out:
   while True:
    block=response.read(1048576)
    if not block:break
    out.write(block)
    if out.tell()>x['bytes'] or time.monotonic()-began>900:raise TimeoutError('resume budget')
 h=hashlib.sha256()
 with partial.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 assert partial.stat().st_size==x['bytes'] and h.hexdigest()==x['sha256']
 os.replace(partial,p);return x['name']+' verified'
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for future in [pool.submit(download,x) for x in plan]:
  try:print(future.result(),flush=True)
  except Exception as e:print(type(e).__name__,str(e),flush=True)
