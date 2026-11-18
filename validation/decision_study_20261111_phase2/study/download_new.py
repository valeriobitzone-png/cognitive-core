from pathlib import Path
import urllib.request,json,hashlib,time,os,sys
R=Path(__file__).resolve().parent
plan=json.loads((R/'download-plan.json').read_text())
for x in plan:
 if len(sys.argv)>1 and sys.argv[1] not in x['name']:continue
 p=R/'models'/x['name'];p.parent.mkdir(exist_ok=True)
 if p.exists():assert hashlib.sha256(p.read_bytes()).hexdigest()==x['sha256'];continue
 url='https://huggingface.co/'+x['repo']+'/resolve/'+x['revision']+'/'+x['name']+'?download=true'
 h=hashlib.sha256();n=0;t=time.monotonic();partial=p.with_suffix('.partial')
 with urllib.request.urlopen(url,timeout=60) as resp,partial.open('xb') as f:
  while True:
   block=resp.read(1048576)
   if not block:break
   n+=len(block)
   if n>x['bytes'] or time.monotonic()-t>1500:raise ValueError('download budget')
   f.write(block);h.update(block)
   if n%104857600==0:print(x['name'],n,round(time.monotonic()-t),flush=True)
 assert n==x['bytes'] and h.hexdigest()==x['sha256'],'integrity'
 os.replace(partial,p);print('VERIFIED',x['name'],flush=True)
