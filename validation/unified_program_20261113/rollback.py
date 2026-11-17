"""Explicit rollback on a chosen runtime; abort if any installed file has changed."""
from pathlib import Path
import argparse,hashlib,json,shutil,os,time
p=argparse.ArgumentParser();p.add_argument('--runtime',required=True);p.add_argument('--backup',required=True);a=p.parse_args()
r=Path(a.runtime).resolve();b=Path(a.backup).resolve();m=json.loads((b/'deployment.json').read_text())
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
for x in m['files']:
 f=r/x['path'];assert f.is_file() and sha(f)==x['after_sha256'],f'Changed since installation: {f}'
 if x['before_sha256']:assert sha(b/'before'/x['path'])==x['before_sha256'],'Backup hash mismatch'
retired=b/('retired-'+str(time.time_ns()));retired.mkdir()
for x in m['files']:
 f=r/x['path'];save=retired/x['path'];save.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,save)
 if x['before_sha256']:
  tmp=f.with_name(f.name+'.restore-tmp');assert not tmp.exists();shutil.copy2(b/'before'/x['path'],tmp);os.replace(tmp,f)
 else:f.rename(save.with_name(save.name+'.removed-from-runtime'))
print('Restored previous files; new files retained in',retired)
