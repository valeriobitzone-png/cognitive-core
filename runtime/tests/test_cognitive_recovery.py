import json
import subprocess
import sys
import time
from unittest.mock import patch

import pytest

from cognitive_core import CognitiveCore, Settings


@pytest.fixture
def core(tmp_path):
    c=CognitiveCore(Settings(home=tmp_path,enable_web=True,domain_allowlist=('example.org',),
                            max_web_requests_per_day=8,max_web_requests_per_job=8))
    yield c
    c.close()


def interrupted(core,checkpoint):
    topic=core.vault.topic('Recovery','How should interrupted source research resume?')
    ident=core.vault.job(topic,plan={'question':'research','seed_urls':['https://example.org/a']})
    job=core.vault.lease_job()
    core.vault.update_job(ident,status='running',checkpoint=checkpoint,lease_token=job['lease_token'])
    core.vault.db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(ident,))
    return ident


def test_governor_preserves_checkpoint_when_resume_hits_quota(core):
    saved={'completed':['https://example.org/done'],'documents':['doc_already_collected'],
           'images':[],'requests_reserved':4,'errors':[]}
    ident=interrupted(core,saved)
    assert core.vault.reserve_budget('web_requests',8,8)
    result=core.work_once()
    assert result['status']=='blocked'
    checkpoint=json.loads(core.vault.get_job(ident)['checkpoint'])
    assert all(checkpoint[key]==value for key,value in saved.items())
    assert checkpoint['blocker']=='daily request budget exhausted'


def test_keyboard_interrupt_rolls_back_lease_transaction(core):
    topic=core.vault.topic('Recovery','How should interrupted source research resume?')
    core.vault.job(topic)
    actual=core.vault.db
    class InterruptOnce:
        armed=True
        def execute(self,sql,*args):
            if self.armed and 'SELECT j.*' in sql:
                self.armed=False
                raise KeyboardInterrupt('simulated interruption')
            return actual.execute(sql,*args)
        def __getattr__(self,name):return getattr(actual,name)
    core.vault.db=InterruptOnce()
    try:
        with pytest.raises(KeyboardInterrupt):core.vault.lease_job()
        assert not actual.in_transaction
        assert core.vault.lease_job()['attempts']==1
    finally:
        if actual.in_transaction:actual.rollback()
        core.vault.db=actual


def test_completed_checkpoint_finalizes_without_more_network_or_budget(core):
    doc=core.vault.document('Already collected','Source text',source_url='https://example.org/a')
    ident=interrupted(core,{'completed':['https://example.org/a'],'documents':[doc],
                            'source_urls':['https://example.org/a'],'requests_reserved':8})
    assert core.vault.reserve_budget('web_requests',8,8)
    assert core.vault.reserve_budget('jobs_run',core.s.max_jobs_per_day,core.s.max_jobs_per_day)
    with patch('cognitive_core.engine.Researcher.fetch',side_effect=AssertionError('network repeated')):
        result=core.work_once()
    assert result['status']=='done' and result['sources']==[doc]
    assert core.vault.get_job(ident)['status']=='done'
    assert core.vault.usage('web_requests')==8


def test_discovered_urls_survive_interruption_without_repeating_search(core):
    core.s.searxng_url='http://127.0.0.1:8888'
    topic=core.vault.topic('Recovery','How should interrupted source research resume?')
    ident=core.vault.job(topic,plan={'question':'research'})
    page={'title':'Source','text':'Collected source text','url':'https://example.org/a',
          'content_type':'text/plain','images':[]}
    with patch('cognitive_core.engine.Researcher.search',return_value=[{'url':page['url']}]) as search:
        with patch('cognitive_core.engine.Researcher.fetch',side_effect=KeyboardInterrupt):
            with pytest.raises(KeyboardInterrupt):core.work_once()
        checkpoint=json.loads(core.vault.get_job(ident)['checkpoint'])
        assert checkpoint['source_urls']==[page['url']]
        core.vault.db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(ident,))
        with patch('cognitive_core.engine.Researcher.fetch',return_value=page):
            assert core.work_once()['status']=='done'
        assert search.call_count==1


def test_final_status_and_experience_roll_back_together(core):
    doc=core.vault.document('Source','Source text','https://example.org/a')
    ident=interrupted(core,{'completed':['https://example.org/a'],'documents':[doc],
                            'source_urls':['https://example.org/a'],'requests_reserved':2})
    with patch.object(core.vault,'experience',side_effect=RuntimeError('simulated ledger failure')):
        with pytest.raises(RuntimeError):core.work_once()
    assert core.vault.get_job(ident)['status']=='running'


def test_actual_worker_kill_preserves_durable_checkpoint(core,tmp_path,monkeypatch):
    from cognitive_core import vault as module
    topic=core.vault.topic('Recovery','How should interrupted source research resume?')
    ident=core.vault.job(topic,plan={'seed_urls':['https://example.org/a']})
    marker=tmp_path/'worker-ready'
    code='''
import sys,time
from pathlib import Path
from cognitive_core import CognitiveCore,Settings
c=CognitiveCore(Settings(home=sys.argv[1]))
job=c.vault.lease_job()
c.vault.update_job(job['id'],status='running',lease_token=job['lease_token'],
    checkpoint={'requests_reserved':1,'completed':[],'documents':[]})
Path(sys.argv[2]).write_text(job['id'])
time.sleep(60)
'''
    proc=subprocess.Popen([sys.executable,'-B','-c',code,str(core.s.home),str(marker)],
                           stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+5
        while not marker.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.01)
        assert marker.exists() and marker.read_text()==ident
        proc.kill();proc.wait(timeout=2)
        assert proc.returncode<0
    finally:
        if proc.poll() is None:proc.kill();proc.wait(timeout=2)
    old=module.ts()
    monkeypatch.setattr(module,'ts',lambda:old+100)
    core.s.enable_web=False
    assert core.work_once()['status']=='blocked'
    job=core.vault.get_job(ident)
    assert job['attempts']==2
    assert json.loads(job['checkpoint'])['requests_reserved']==1
