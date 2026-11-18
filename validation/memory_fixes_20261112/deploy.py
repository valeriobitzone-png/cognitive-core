"""Guarded installation of the reviewed file list; never opens a runtime database."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,tempfile
R=Path(__file__).resolve().parent
SRC=Path('/Volumes/AMBRO/projects/CognitiveCore/cognitive-core')
DEST=SRC/'validation/memory_fixes_20261112'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
base=json.loads((R/'baseline.json').read_text());files=json.loads((R/'deployment-files.json').read_text())
checks=json.loads((R/'release-tests.json').read_text());assert checks['complete'] and not checks['failed']
assert not DEST.exists(),'Backup destination exists; do not overwrite'
for k,v in base.items():assert (SRC/k).is_file() and sha(SRC/k)==v,'Concurrent source change: '+k
for k in files:
 assert (R/k).is_file(),k
 if k not in base:assert not (SRC/k).exists(),'New file appeared: '+k
assert subprocess.check_output(['git','branch','--show-current'],cwd=SRC,text=True).strip()=='feature/intelligence-feed-runtime'
manifest={'files':[{'path':k,'before_sha256':base.get(k),'after_sha256':sha(R/k)} for k in files],
 'branch':'feature/intelligence-feed-runtime','databases_opened':False,'baseline_files':len(base)}
DEST.mkdir(parents=True)
for x in manifest['files']:
 if x['before_sha256']:
  p=DEST/'before'/x['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(SRC/x['path'],p)
(DEST/'deployment.json').write_text(json.dumps(manifest,indent=2))
shutil.copy2(SRC/'validation/decision_study_20261111/rollback.py',DEST/'rollback.py')
# Prove rollback on a disposable checkout; also prove refusal after a later edit.
with tempfile.TemporaryDirectory(prefix='cc-rollback-test-') as tmp:
 t=Path(tmp);test=t/'runtime';backup=t/'backup';shutil.copytree(DEST,backup)
 for x in manifest['files']:
  p=test/x['path'];p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/x['path'],p)
 cmd=[os.sys.executable,'-B',str(backup/'rollback.py'),'--runtime',str(test),'--backup',str(backup)]
 p=test/manifest['files'][0]['path'];original=p.read_bytes();p.write_bytes(original+b'\n# later edit\n')
 refusal=subprocess.run(cmd,capture_output=True,text=True);assert refusal.returncode!=0
 p.write_bytes(original);restored=subprocess.run(cmd,capture_output=True,text=True);assert restored.returncode==0,restored.stderr
 for x in manifest['files']:
  p=test/x['path']
  assert (p.is_file() and sha(p)==x['before_sha256']) if x['before_sha256'] else not p.exists()
(DEST/'rollback-verification.json').write_text(json.dumps({'temporary_rollback':'passed','later_edit_refusal':'passed'},indent=2))
# Recheck all target guards immediately before writing any reviewed file.
for x in manifest['files']:
 p=SRC/x['path'];assert sha(p)==x['before_sha256'] if x['before_sha256'] else not p.exists()
for x in manifest['files']:
 p=SRC/x['path'];tmp=p.with_name(p.name+'.audit-install-tmp');assert not tmp.exists()
 shutil.copy2(R/x['path'],tmp);os.replace(tmp,p)
for k,v in base.items():assert sha(SRC/k)==next((x['after_sha256'] for x in manifest['files'] if x['path']==k),v),k
for x in manifest['files']:assert sha(SRC/x['path'])==x['after_sha256']
for name in ('baseline.json','release-tests.json','release-progress.log','wheel-check.json','REPORT_CORREZIONI_IT.md','deployment-files.json'):
 if (R/name).exists():shutil.copy2(R/name,DEST/name)
for name in ('wheel','release-tests_logs'):
 if (R/name).exists():shutil.copytree(R/name,DEST/name)
(R/'deployment.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'installed':len(files),'backup':str(DEST),'unchanged_other_baseline_files':len(base)-sum(x['before_sha256'] is not None for x in manifest['files'])}))
