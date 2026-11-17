import pytest
from cognitive_core import CognitiveCore,Settings

@pytest.fixture
def c(tmp_path):
 x=CognitiveCore(Settings(home=tmp_path/'home',owner='alice',namespace='lab'))
 yield x
 x.close()

def test_bitemporal_supersede_and_as_of(c):
 m=c.memory
 m.remember('p','city','Roma','user',valid_from=100)
 m.remember('p','city','Milano','user',valid_from=200)
 assert m.recall('p','city',valid_at=150)['value']=='Roma'
 assert m.recall('p','city',valid_at=250)['value']=='Milano'
 assert len(m.history('p','city'))==2

def test_source_required_and_forget_keeps_history(c):
 m=c.memory
 with pytest.raises(ValueError):m.remember('p','k','v','')
 m.remember('p','k','v','user')
 assert m.forget('p','k')==1
 assert m.recall('p','k') is None
 assert len(m.history('p','k'))==1

def test_rules_handoff_grounded_and_scopes(c):
 m=c.memory
 m.remember('p','style','short','user',kind='rule')
 assert m.rules('p')[0]['value']=='short'
 m.handoff('p','a','b','done x',['todo y'])
 m.remember('q','tool','pytest','file:notes.md')
 assert m.grounded('pytest')[0]['source']=='file:notes.md'
 assert m.scopes()==['p','q']

def test_dream_idle_budget_and_no_self_confirmation(c):
 m=c.memory;d=c.dream
 m.remember('p','a','1','user');m.remember('p','b','2','user')
 assert d.run(idle=False)['status']=='skipped'
 r=d.run(idle=True,daily_limit=1)
 assert r['status']=='done' and 1<=len(r['hypotheses'])<=3
 assert d.run(idle=True,daily_limit=1)['reason']=='budget exhausted'
 key=m.history('dream',m.v.db.execute("SELECT key FROM mem_facts WHERE scope='dream'").fetchone()['key'])[0]['key']
 with pytest.raises(ValueError):d.promote('dream',key,'dream:self')
 d.promote('dream',key,'test:independent')
 assert m.recall('dream',key)['value']['status']=='verified'

def test_bm25_freshness_suppress_release(c):
 m=c.memory
 m.remember('p','runner','checkpoint recovery for the runner','file:a.md')
 m.remember('p','voice','archived legacy voice notes','file:b.md')
 m.remember('p','other','unrelated cooking','file:c.md')
 r=m.search('runner checkpoint')
 assert r[0]['key']=='runner' and r[0]['label']=='CURRENT' and r[0]['source']=='file:a.md'
 assert m.search('voice')[0]['label']=='HISTORICAL'
 m.suppress('p','runner');assert m.search('runner checkpoint')==[]
 m.release('p','runner');assert m.search('runner checkpoint')[0]['key']=='runner'
 assert m.recall('p','runner')['value']

def test_dream_grounding_and_wake_context(c):
 m=c.memory;d=c.dream
 m.remember('p','a','1','user');m.remember('p','b','2','user')
 d.run(idle=True)
 k=c.vault.db.execute("SELECT key FROM mem_facts WHERE scope='dream'").fetchone()['key']
 assert d.grounding_check('dream',k)
 assert d.wake_context().startswith('[UNVERIFIED]')
 m.forget('p','a');assert not d.grounding_check('dream',k)
