from pathlib import Path
import struct,json,hashlib
R=Path(__file__).resolve().parent
paths=list(Path('/Volumes/AMBRO/models/rizzo-flow').rglob('*.gguf'))
def info(p):
 f=p.open('rb');u=lambda fmt:struct.unpack('<'+fmt,f.read(struct.calcsize('<'+fmt)))[0]
 def string(keep=True):
  n=u('Q')
  if keep:return f.read(n).decode('utf-8',errors='replace')
  f.seek(n,1)
 def val(t,keep=False):
  codes={0:'B',1:'b',2:'H',3:'h',4:'I',5:'i',6:'f',7:'?',10:'Q',11:'q',12:'d'}
  if t==8:return string(keep)
  if t==9:
   a=u('I');n=u('Q')
   for _ in range(n):val(a,False)
   return {'array_type':a,'count':n} if keep else None
  if t in codes:return u(codes[t])
  raise ValueError(t)
 assert f.read(4)==b'GGUF';version=u('I');n=u('Q');k=u('Q');meta={}
 for _ in range(k):
  key=string();t=u('I');keep=key.startswith('general.') or key in ('tokenizer.chat_template','tokenizer.ggml.model');v=val(t,keep)
  if keep:meta[key]=v
 f.close();h=hashlib.sha256()
 with p.open('rb') as f:
  for block in iter(lambda:f.read(1048576),b''):h.update(block)
 return {'path':str(p),'bytes':p.stat().st_size,'sha256':h.hexdigest(),'gguf_version':version,'tensor_count':n,'metadata':meta}
results=[info(p) for p in paths];(R/'existing-weights-manifest.json').write_text(json.dumps(results,indent=2));print(json.dumps([{k:v for k,v in x.items() if k!='metadata'}|{'architecture':x['metadata'].get('general.architecture'),'name':x['metadata'].get('general.name')} for x in results],indent=2))
