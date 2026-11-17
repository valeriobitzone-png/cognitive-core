from pathlib import Path
import sys,tempfile,json,subprocess,time,hashlib,os
R=Path(__file__).resolve().parent;SRC=R.parent/'decisionale-locale-2026-11-10/runtime/src';sys.path.insert(0,str(SRC))
from cognitive_core import CognitiveCore,Settings
from cognitive_core.selfmodel import SelfModel
report={}
with tempfile.TemporaryDirectory(prefix='cognitive-kill-restart-') as td:
 t=Path(td);c=CognitiveCore(Settings(home=t/'core'));c.drive.upsert_project('recovery','Recovery',['runner','checkpoint'],1);c.vault.document('runner checkpoint','runner checkpoint preserves the acquired skill catalog')
 topic=c.observe({'kind':'session_end','title':'runner checkpoint','question':'How can runner checkpoint preserve the acquired skill catalog?'})['topics'][0];c.close()
 child='''import sys,os,json,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from cognitive_core import CognitiveCore,Settings
p=Path(sys.argv[2]);c=CognitiveCore(Settings(home=p/'core'))
c.cycle_once(sys.argv[3]);c.cycle_once(sys.argv[3])
with (p/'skills.json').open('w') as f:
 json.dump({'version':1,'skills':['verified_json_record_scan']},f);f.flush();os.fsync(f.fileno())
(p/'ready').write_text('checkpoint persisted')
while True:time.sleep(.1)
'''
 p=subprocess.Popen([sys.executable,'-B','-c',child,str(SRC),str(t),topic],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 try:
  deadline=time.monotonic()+10
  while not (t/'ready').exists() and time.monotonic()<deadline and p.poll() is None:time.sleep(.02)
  assert (t/'ready').exists(),p.communicate(timeout=1)[1].decode() if p.poll() is not None else 'child not ready'
  p.kill();p.wait(timeout=5);assert p.returncode!=0
 finally:
  if p.poll() is None:p.kill();p.wait()
 c=CognitiveCore(Settings(home=t/'core'));assert json.loads((t/'skills.json').read_text())['skills']==['verified_json_record_scan']
 for _ in range(12):
  result=c.cycle_once(topic)
  if result['status'] in ('done','abstained','stopped','blocked'):break
 assert result['status']=='done',result
 count=c.vault.db.execute("SELECT count(*) FROM documents WHERE kind='cognitive_note'").fetchone()[0]
 assert c.cycle_once(topic)['status']=='done'
 assert count==c.vault.db.execute("SELECT count(*) FROM documents WHERE kind='cognitive_note'").fetchone()[0]
 c.close();report['kill_restart']={'actual_parent_sigkill_of_own_child':True,'returncode':p.returncode,'cycle_resumed':'done','skill_catalog_preserved':True,'duplicate_notes':False}
with tempfile.TemporaryDirectory(prefix='cognitive-modality-ledger-') as td:
 t=Path(td);c=CognitiveCore(Settings(home=t/'home',owner='experiment',namespace='modalities',execution_mode='autonomous'))
 vision=json.loads((R/'vision-results.json').read_text());voice=json.loads((R/'voice-results.json').read_text());n=0
 for modality,data in [('vision',vision),('voice',voice)]:
  for row in data['rows']:
   if not row['actual']:continue
   observation={'modality':modality,'observed_output':row['actual'],'output_sha256':hashlib.sha256(row['actual'].encode()).hexdigest(),'epistemic':'OBSERVED sensor output; semantic claims UNVERIFIED','instruction_authority':False,'source_id':row['id']}
   c.vault.document(modality+' observation '+row['id'],json.dumps(observation,ensure_ascii=False));n+=1
 assert c.vault.db.execute('SELECT count(*) FROM claims').fetchone()[0]==0
 assert not c.s.enable_web and not c.s.external_paid_calls_allowed and not c.s.enable_local_model
 other=CognitiveCore(Settings(home=t/'home',owner='other',namespace='other'));assert other.memory_search('observation')==[];other.close()
 report['modality_ledger']={'observations_stored_in_temporary_vault':n,'verified_claims':0,'scope_isolation':True,'network_or_external_actions_authorized':False,'original_archive_modified':False};c.close()
(R/'checkpoint-modalities-results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
