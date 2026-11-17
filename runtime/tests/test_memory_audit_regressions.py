"""Regression cases from the 12 November audit, all databases are temporary."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from cognitive_core import CognitiveCore,Settings
from cognitive_core.portable import restore_state

@pytest.fixture
def c(tmp_path):
 core=CognitiveCore(Settings(home=tmp_path/'home',owner='alice',namespace='lab'))
 yield core
 core.close()

def hypothesis(c):
 c.memory.remember('p','a','value A','source:a')
 c.memory.remember('p','b','value B','source:b')
 ident=c.dream.run(idle=True)['hypotheses'][0]
 return c.vault.db.execute('SELECT key FROM mem_facts WHERE id=?',(ident,)).fetchone()[0]

def evidence(c,key,stance='supports',statement=None):
 value=c.memory.recall('dream',key)['value']
 topic=c.vault.topic('Review','Does the source support the proposed link?')
 doc=c.vault.document('Source','A and B co-occur in this observed example.','https://example.org/source')
 claim=c.vault.claim(topic,statement or value['text'])
 e=c.vault.add_evidence(claim,doc,'A and B co-occur',stance=stance)
 return e,doc

def test_memory_roundtrip_includes_history_suppression_and_order(c,tmp_path):
 with patch('cognitive_core.memory.ts',return_value=1000):
  first=c.memory.remember('p','city','Roma','source:one')
  last=c.memory.remember('p','city','Milano','source:two')
 c.memory.remember('p','secret','redacted-token','source:secret');c.memory.suppress('p','secret')
 c.export_state(tmp_path/'export');restore_state(tmp_path/'export',tmp_path/'restored')
 restored=CognitiveCore(Settings(home=tmp_path/'restored',owner='alice',namespace='lab'))
 try:
  assert restored.memory.recall('p','city')['id']==last
  assert [x['id'] for x in restored.memory.history('p','city')]==[first,last]
  assert restored.memory.search('redacted-token')==[]
  assert restored.memory.grounded('redacted-token')==[]
 finally:restored.close()

def test_old_export_without_memory_tables_still_restores(c,tmp_path):
 c.export_state(tmp_path/'export');p=tmp_path/'export/state.json';envelope=json.loads(p.read_text())
 for name in ('mem_facts','mem_suppressed','mem_order'):envelope['payload']['stores']['vault'].pop(name,None)
 body=json.dumps(envelope['payload'],ensure_ascii=False,sort_keys=True,allow_nan=False)
 envelope['sha256']=hashlib.sha256(body.encode()).hexdigest();p.write_text(json.dumps(envelope))
 restore_state(tmp_path/'export',tmp_path/'old-restored')
 r=CognitiveCore(Settings(home=tmp_path/'old-restored',owner='alice',namespace='lab'))
 try:assert r.memory.search('anything')==[]
 finally:r.close()

def test_legacy_closed_rows_keep_as_of_history(c):
 with patch('cognitive_core.memory.ts',return_value=1000):first=c.memory.remember('p','city','Roma','one',valid_from=100)
 with patch('cognitive_core.memory.ts',return_value=2000):c.memory.remember('p','city','Milano','two',valid_from=200)
 c.vault.db.execute('UPDATE mem_facts SET valid_to=200 WHERE id=?',(first,)) # old writer's on-disk layout
 assert c.memory.recall('p','city',valid_at=250,known_at=1500)['value']=='Roma'
 assert c.memory.recall('p','city',valid_at=250,known_at=2500)['value']=='Milano'
 assert c.memory.recall('p','city',valid_at=150,known_at=2500)['value']=='Roma'

def test_new_writes_do_not_rewrite_old_validity(c):
 with patch('cognitive_core.memory.ts',return_value=1000):first=c.memory.remember('p','k','one','one',valid_from=100)
 with patch('cognitive_core.memory.ts',return_value=2000):c.memory.remember('p','k','two','two',valid_from=200)
 assert c.vault.db.execute('SELECT valid_to FROM mem_facts WHERE id=?',(first,)).fetchone()[0] is None
 assert c.memory.history('p','k')[0]['valid_to']==200
 assert c.memory.recall('p','k',valid_at=250,known_at=1500)['value']=='one'

def test_future_and_backdated_values_use_world_and_transaction_time(c):
 with patch('cognitive_core.memory.ts',return_value=1000):
  c.memory.remember('p','city','Roma','one',valid_from=900)
  c.memory.remember('p','city','Milano','future',valid_from=2000)
  assert c.memory.search('city')[0]['value']=='Roma'
  assert c.memory.grounded('city')[0]['value']=='Roma'
 with patch('cognitive_core.memory.ts',return_value=2500):
  assert c.memory.search('city')[0]['value']=='Milano'
 with patch('cognitive_core.memory.ts',return_value=3000):c.memory.remember('p','city','Firenze','late',valid_from=1500)
 assert c.memory.recall('p','city',valid_at=1700,known_at=2500)['value']=='Roma'
 assert c.memory.recall('p','city',valid_at=1700,known_at=3500)['value']=='Firenze'
 assert c.memory.recall('p','city',valid_at=2100,known_at=3500)['value']=='Milano'

def test_forget_preserves_what_was_known_before_retraction(c):
 with patch('cognitive_core.memory.ts',return_value=1000):c.memory.remember('p','k','one','source',valid_from=100)
 with patch('cognitive_core.memory.ts',return_value=2000):c.memory.forget('p','k')
 assert c.memory.recall('p','k',valid_at=300,known_at=1500)['value']=='one'
 assert c.memory.recall('p','k',valid_at=300,known_at=2500) is None

@pytest.mark.parametrize('authority',['interactive','autonomous'])
def test_source_string_alone_cannot_verify(c,authority):
 key=hypothesis(c);c.s.execution_mode=authority
 with pytest.raises((PermissionError,ValueError)):c.dream.promote('dream',key,'invented:verifier')
 assert c.memory.recall('dream',key)['value']['status']=='unverified'

def test_actual_source_attaches_backing_without_claiming_truth(c):
 key=hypothesis(c);e,doc=evidence(c,key)
 c.dream.promote('dream',key,doc,evidence_id=e)
 value=c.memory.recall('dream',key)['value']
 assert value['status']=='source_backed' and value['semantic_truth_verified'] is False
 assert value['independence']=='not_established'
 assert c.memory.search('possible link')==[]
 assert c.memory.grounded('possible link')==[]

@pytest.mark.parametrize('change',['foreign','corrupt','wrong_source','contradicts','unrelated'])
def test_invalid_evidence_never_promotes(c,change):
 key=hypothesis(c);e,doc=evidence(c,key,stance='contradicts' if change=='contradicts' else 'supports',statement='unrelated claim' if change=='unrelated' else None)
 if change=='foreign':c.vault.db.execute("UPDATE evidence SET namespace='foreign' WHERE id=?",(e,))
 if change=='corrupt':c.vault.db.execute("UPDATE documents SET text='corrupt' WHERE id=?",(doc,))
 with pytest.raises(ValueError):c.dream.promote('dream',key,'invented' if change=='wrong_source' else doc,evidence_id=e)
 assert c.memory.recall('dream',key)['value']['status']=='unverified'

def test_autonomous_mode_cannot_attach_evidence_even_when_real(c):
 key=hypothesis(c);e,doc=evidence(c,key);c.s.execution_mode='autonomous'
 with pytest.raises(PermissionError):c.dream.promote('dream',key,doc,evidence_id=e)

def test_dependency_ids_prevent_cross_scope_and_same_key_replacement(c):
 key=hypothesis(c);c.memory.forget('p','a');c.memory.remember('q','a','unrelated','other')
 assert c.dream.grounding_check('dream',key) is False
 c.memory.remember('p','a','replacement','one')
 assert c.dream.grounding_check('dream',key) is False

def test_structured_dependency_keys_allow_colons_and_plus(c):
 c.memory.remember('p:q','a+b','one','source');c.memory.remember('p:q','c:d','two','source')
 ident=c.dream.run(idle=True)['hypotheses'][0];key=c.vault.db.execute('SELECT key FROM mem_facts WHERE id=?',(ident,)).fetchone()[0]
 assert c.dream.grounding_check('dream',key) is True

def test_suppression_hides_all_context_and_reflection_paths(c):
 c.memory.remember('p','private','redacted-token','source');c.memory.remember('p','other','second','source')
 c.memory.suppress('p','private')
 assert c.memory.search('redacted-token')==[] and c.memory.grounded('redacted-token')==[]
 assert c.memory_search('redacted-token')==[] and c.dream.run(idle=True)['hypotheses']==[]
 assert c.memory.recall('p','private')['value']=='redacted-token' # explicit operator lookup remains available
 c.memory.release('p','private');assert c.memory_search('redacted-token')

def test_shared_memory_reaches_cycle_and_does_not_self_confirm(c):
 c.drive.upsert_project('p','Runner',['runner','recovery'])
 c.memory.remember('p','runner','runner recovery checkpoints','source:fixture')
 topic=c.vault.topic('Runner','How can runner recovery preserve checkpoints?')
 assert c.memory_search('runner')[0]['kind']=='shared_memory'
 for _ in range(8):
  result=c.cycle_once(topic)
  if result['status'] in ('done','abstained'):break
 assert result['status']=='done'
 assert any(v['kind']=='shared_memory' for v in result['checkpoint']['sources'])
 assert c.vault.db.execute('SELECT count(*) FROM claims').fetchone()[0]==0
 assert c.cycle_once()['status']=='idle'

def test_reflection_does_not_change_curiosity_context_and_duplicates_do_not_grow(c):
 c.memory.remember('p','a','one','one');c.memory.remember('p','b','two','two')
 before=c.curiosity.context();assert c.dream.run(idle=True)['hypotheses']
 assert c.curiosity.context()==before
 assert c.dream.run(idle=True)['hypotheses']==[]

@pytest.mark.parametrize('owner,namespace',[('bob','lab'),('alice','other')])
def test_memory_and_evidence_scopes_are_isolated(c,owner,namespace):
 c.memory.remember('p','secret','needle','source')
 other=CognitiveCore(Settings(home=c.s.home,owner=owner,namespace=namespace))
 try:
  assert other.memory.recall('p','secret') is None
  assert other.memory.search('needle')==[] and other.memory_search('needle')==[]
 finally:other.close()

@pytest.mark.parametrize('value',['x'*65,{'x':float('nan')}])
def test_oversized_or_nonfinite_memory_is_rejected_atomically(c,value):
 c.s.max_text_bytes=64
 with pytest.raises(ValueError):c.memory.remember('p','k',value,'source')
 assert c.memory.history('p','k')==[]

def test_disk_budget_enforced_before_write(c):
 c.s.max_runtime_disk_bytes=1
 with pytest.raises(ValueError):c.memory.remember('p','k','value','source')
 assert c.memory.history('p','k')==[]

@pytest.mark.parametrize('limit',[-1,0,True,101])
def test_bad_search_limits_rejected(c,limit):
 with pytest.raises(ValueError):c.memory.search('anything',limit=limit)

def test_unicode_casefold_and_bounded_candidates(c):
 c.memory.remember('p','CITTÀ','LOCALITÀ','source')
 assert c.memory.search('città')[0]['value']=='LOCALITÀ'
 assert c.memory.search('località')[0]['key']=='CITTÀ'


def test_legacy_schema_order_backfill_is_additive(tmp_path):
 import sqlite3
 home=tmp_path/'legacy';home.mkdir();db=sqlite3.connect(home/'vault.sqlite3')
 db.execute('CREATE TABLE mem_facts(namespace TEXT,id TEXT,scope TEXT,key TEXT,value TEXT,source TEXT,agent TEXT,valid_from INTEGER,valid_to INTEGER,recorded INTEGER,retracted INTEGER,PRIMARY KEY(namespace,id))')
 db.execute("INSERT INTO mem_facts VALUES('lab','old','p','city','\"Roma\"','source','user',100,NULL,1000,NULL)");db.commit();db.close()
 core=CognitiveCore(Settings(home=home,namespace='lab'))
 try:
  assert core.memory.recall('p','city')['value']=='Roma'
  assert core.vault.db.execute("SELECT value,recorded,valid_from FROM mem_facts WHERE id='old'").fetchone()[:]==('"Roma"',1000,100)
 finally:core.close()

def test_withdrawn_or_tampered_memory_cannot_validate_cached_hit(c):
 ident=c.memory.remember('p','runner','checkpoint recovery','source:fixture')
 hit=c.memory_search('checkpoint')[0]
 assert c.curiosity._source(hit)==hit['source_sha256']
 c.memory.suppress('p','runner');assert c.curiosity._source(hit) is None
 c.memory.release('p','runner');assert c.curiosity._source(hit)
 c.vault.db.execute("UPDATE mem_facts SET value='\"tampered\"' WHERE id=?",(ident,))
 assert c.curiosity._source(hit) is None

def test_kill_before_commit_and_restart_preserve_atomic_memory(tmp_path):
 home=tmp_path/'home';ready=tmp_path/'ready'
 script='''
import sys,time
from pathlib import Path
from cognitive_core import CognitiveCore,Settings
c=CognitiveCore(Settings(home=Path(sys.argv[1]),owner='alice',namespace='lab'))
c.memory.remember('p','committed','kept','source:fixture')
with c.vault.transaction():
 c.memory.remember('p','pending','must roll back','source:fixture')
 Path(sys.argv[2]).write_text('ready')
 time.sleep(60)
'''
 proc=subprocess.Popen([sys.executable,'-B','-c',script,str(home),str(ready)])
 try:
  import time
  deadline=time.monotonic()+10
  while not ready.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.02)
  assert ready.exists(),'child did not reach uncommitted transaction'
  proc.kill();proc.wait(timeout=5)
 finally:
  if proc.poll() is None:proc.kill();proc.wait(timeout=5)
 core=CognitiveCore(Settings(home=home,owner='alice',namespace='lab'))
 try:
  assert core.memory.recall('p','committed')['value']=='kept'
  assert core.memory.recall('p','pending') is None
  assert core.vault.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
  assert core.vault.db.execute('SELECT count(*) FROM mem_facts').fetchone()[0]==core.vault.db.execute('SELECT count(*) FROM mem_order').fetchone()[0]==1
 finally:core.close()

def test_sql_read_deadline_is_enforced_and_handler_is_cleared(c):
 c.memory.remember('p','key','value','source')
 with patch('cognitive_core.memory.monotonic',side_effect=[0,3]):
  with pytest.raises(ValueError,match='time budget'):c.memory.recall('p','key')
 assert c.memory.recall('p','key')['value']=='value'
