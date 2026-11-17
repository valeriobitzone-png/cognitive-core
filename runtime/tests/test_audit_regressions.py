"""Regressions reproduced during the SSD audit; only synthetic local data."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from cognitive_core import CognitiveCore, Settings


@pytest.fixture
def core(tmp_path):
    c=CognitiveCore(Settings(home=tmp_path/'source',owner='alice',namespace='work'))
    yield c
    c.close()


def test_search_includes_knowledge_store_and_provenance(core):
    core.worldcore.ingest_document('alice','source','XylophoneUnique evidence for a scoped retrieval test. '*2,
        space='work',title='Source',source_url='https://example.org/source',license='CC0')
    results=core.memory_search('XylophoneUnique')
    assert len(results)==1
    assert results[0]['source_url']=='https://example.org/source'
    assert results[0]['source_sha256']
    assert results[0]['kind']=='worldcore_knowledge'
    other=CognitiveCore(Settings(home=core.s.home,owner='bob',namespace='work'))
    try:assert other.memory_search('XylophoneUnique')==[]
    finally:other.close()


def test_search_interleaves_all_three_stores(core):
    for i in range(5):core.vault.document(str(i),'XylophoneUnique document '+str(i))
    core.worldcore.remember('alice','instrument','XylophoneUnique preference',space='work')
    core.worldcore.ingest_document('alice','source','XylophoneUnique evidence for a scoped retrieval test. '*2,
        space='work',title='Source',source_url='https://example.org/source',license='CC0')
    assert {r['kind'] for r in core.memory_search('XylophoneUnique',3)}=={'note','worldcore_memory','worldcore_knowledge'}


def test_resume_blocked_reuses_checkpoint_and_quota(core):
    t=core.vault.topic('Research','How should the source be inspected?')
    ident=core.vault.job(t,plan={'seed_urls':['https://example.org/a']})
    lease=core.vault.lease_job()
    checkpoint={'source_urls':['https://example.org/a'],'completed':[], 'documents':['saved'],
                'requests_reserved':2,'blocker':'network disabled'}
    core.vault.update_job(ident,status='blocked',checkpoint=checkpoint,lease_token=lease['lease_token'])
    core.vault.reserve_budget('web_requests',30,2)
    assert core.resume(t)==ident
    assert core.resume(t)==ident
    job=core.vault.get_job(ident)
    assert json.loads(job['checkpoint'])==checkpoint
    assert job['attempts']==1
    assert core.vault.usage('web_requests')==2
    assert core.vault.lease_job()['id']==ident


def test_resume_completed_checkpoint_does_not_fetch_again(core):
    t=core.vault.topic('Research','How should the source be inspected?')
    doc=core.vault.document('Source','Already inspected source','https://example.org/a')
    ident=core.vault.job(t,plan={'seed_urls':['https://example.org/a']})
    lease=core.vault.lease_job()
    core.vault.update_job(ident,status='blocked',lease_token=lease['lease_token'],checkpoint={
        'source_urls':['https://example.org/a'],'completed':['https://example.org/a'],
        'documents':[doc],'requests_reserved':2})
    assert core.resume(t)==ident
    with patch('cognitive_core.engine.Researcher.fetch',side_effect=AssertionError('duplicate fetch')):
        assert core.work_once()['status']=='done'


@pytest.mark.parametrize('excerpt',['Invented sentence','', '   ', 'Source sentence plus invented tail'])
def test_fabricated_excerpt_is_rejected_without_orphan_claim(core,excerpt):
    t=core.vault.topic('Evidence','What does the source actually say?')
    doc=core.vault.document('Source','Source sentence')
    with pytest.raises(ValueError):core.remember_claim(t,'Candidate',doc,excerpt)
    assert core.vault.db.execute('SELECT count(*) FROM claims').fetchone()[0]==0
    assert core.vault.db.execute('SELECT count(*) FROM evidence').fetchone()[0]==0


def test_real_excerpt_keeps_conflicts_and_never_becomes_tested(core):
    t=core.vault.topic('Evidence','What does the source actually say?')
    doc=core.vault.document('Source','Source sentence. Contrary sentence.')
    result=core.remember_claim(t,'Candidate',doc,'Source sentence.')
    core.vault.add_evidence(result['claim_id'],doc,'Contrary sentence.',stance='contradicts')
    status=core.vault.db.execute('SELECT status FROM claims WHERE id=?',(result['claim_id'],)).fetchone()[0]
    assert status=='conflicted'


def test_markdown_export_includes_pool_and_operational_tables(core,tmp_path):
    core.drive.upsert_project('p','Project',['runner'])
    core.drive.ingest({'source_kind':'manual','source_ref':'https://example.org/runner',
        'occurred_at':'2026-11-09T00:00:00Z','title':'Runner','summary':'Runner checkpoint review'})
    core.vault.event('audit',{'text':'Scoped event'})
    core.vault.reserve_budget('web_requests',30)
    target=tmp_path/'notes';core.vault.export_markdown(target)
    assert len(json.loads((target/'drive_opportunities.json').read_text()))==1
    assert len(json.loads((target/'events.json').read_text()))==1
    assert json.loads((target/'budget_usage.json').read_text())[0]['value']==1


def test_portable_state_roundtrip_restores_both_stores_and_scope(core,tmp_path):
    from cognitive_core.portable import restore_state
    core.drive.upsert_project('p','Project',['runner'])
    core.drive.ingest({'source_kind':'manual','source_ref':'https://example.org/runner',
        'occurred_at':'2026-11-09T00:00:00Z','title':'Runner','summary':'Runner checkpoint review'})
    t=core.vault.topic('Research','How should persistent sources be inspected?')
    ident=core.vault.job(t);lease=core.vault.lease_job()
    core.vault.update_job(ident,status='running',lease_token=lease['lease_token'],
                          checkpoint={'documents':['preserved'],'requests_reserved':2})
    core.vault.reserve_budget('web_requests',30,2)
    core.worldcore.ingest_document('alice','doc','XylophoneUnique evidence from a portable source. '*2,
        space='work',title='Source',source_url='https://example.org/source',license='CC0')
    core.worldcore.remember('bob','private','FOREIGN_PRIVATE_VALUE',space='work')
    core.worldcore.set_state('alice','budget',10,space='work')
    core.compare_futures('Compare alternatives',[{'id':'a','actions':[]},{'id':'b','actions':[]}],objectives=[])
    approval=core.worldcore.request_action('alice','note.create',{'title':'T','body':'B'},'Test',space='work')
    core.worldcore.approve_action('alice',approval['id'],space='work',approve=True)
    target=tmp_path/'export';core.export_state(target)
    assert 'FOREIGN_PRIVATE_VALUE' not in (target/'state.json').read_text()
    restored_home=tmp_path/'restored';restore_state(target,restored_home)
    restored=CognitiveCore(Settings(home=restored_home,owner='alice',namespace='work'))
    try:
        assert len(restored.drive.opportunities())==1
        assert restored.memory_search('XylophoneUnique')[0]['source_url']=='https://example.org/source'
        job=restored.vault.get_job(ident)
        assert job['status']=='pending' and job['lease_token']=='' and job['lease_until']==0
        assert json.loads(job['checkpoint'])['documents']==['preserved']
        assert restored.vault.usage('web_requests')==2
        assert restored.worldcore.state('alice',space='work')=={'budget':10}
        assert len(restored.worldcore.whatif_history('alice',space='work'))==1
        assert not restored.worldcore.consume_approval('alice',approval['id'],'note.create',{'title':'T','body':'B'},space='work')
        assert restored.s.enable_web is False and restored.s.enable_local_model is False
    finally:restored.close()
    with pytest.raises(FileExistsError):restore_state(target,restored_home)


def test_restore_rejects_tampering_and_never_publishes_partial_home(core,tmp_path):
    import hashlib
    from cognitive_core.portable import restore_state
    target=tmp_path/'export';core.export_state(target)
    state=target/'state.json';original=state.read_text()
    envelope=json.loads(original);envelope['payload']['namespace']='different'
    state.write_text(json.dumps(envelope))
    home=tmp_path/'restore-bad'
    with pytest.raises(ValueError,match='checksum'):restore_state(target,home)
    assert not home.exists()
    # Even with a recomputed checksum, foreign records cannot cross the bound scope.
    envelope=json.loads(original)
    envelope['payload']['stores']['worldcore']['state']=[{
        'owner':'bob','space':'work','state_key':'secret','value':'1','revision':1,'at':'2026-11-09T00:00:00Z'}]
    body=json.dumps(envelope['payload'],ensure_ascii=False,sort_keys=True,allow_nan=False)
    envelope['sha256']=hashlib.sha256(body.encode()).hexdigest()
    state.write_text(json.dumps(envelope))
    with pytest.raises(ValueError,match='scope'):restore_state(target,home)
    assert not home.exists()
    assert list(tmp_path.glob('.cognitive-transfer-*'))==[]


def test_export_never_overwrites_existing_artifacts(core,tmp_path):
    target=tmp_path/'existing';target.mkdir();(target/'keep').write_text('preserve')
    with pytest.raises(FileExistsError):core.export_state(target)
    assert (target/'keep').read_text()=='preserve'


def test_source_override_does_not_destroy_checkpoint(core):
    t=core.vault.topic('Research','Which source should we inspect?')
    ident=core.vault.job(t,plan={'seed_urls':['https://example.org/a']})
    job=core.vault.lease_job()
    core.vault.update_job(ident,status='blocked',checkpoint={'requests_reserved':2},lease_token=job['lease_token'])
    with pytest.raises(ValueError,match='sources'):core.resume(t,['https://example.org/b'])
    assert core.vault.get_job(ident)['status']=='blocked'


def test_evidence_limit_is_checked_before_truncation(core):
    t=core.vault.topic('Evidence','What does the source actually say?')
    doc=core.vault.document('Source','x'*1500)
    with pytest.raises(ValueError):core.remember_claim(t,'Candidate',doc,'x'*1500+'invented')
    assert core.vault.db.execute('SELECT count(*) FROM claims').fetchone()[0]==0


def test_cli_export_restore_roundtrip_uses_new_home(core,tmp_path,capsys):
    from cognitive_core.cli import main
    core.vault.document('Source','Recoverable note')
    core.close()
    exported=tmp_path/'exported';home=tmp_path/'new-home'
    main(['--home',str(core.s.home),'--owner','alice','--namespace','work','export',str(exported)])
    assert json.loads(capsys.readouterr().out)['format']=='cognitive-core-state-v1'
    main(['--home',str(home),'restore',str(exported)])
    assert json.loads(capsys.readouterr().out)['owner']=='alice'
    restored=CognitiveCore(Settings(home=home,owner='alice',namespace='work'))
    try:assert len(restored.memory_search('Recoverable'))==1
    finally:restored.close()


def test_export_roundtrip_preserves_rows_ledgers_and_search_indexes(core,tmp_path):
    from cognitive_core.portable import restore_state
    core.drive.upsert_project('p','Project',['runner'])
    event={'source_kind':'manual','source_ref':'https://example.org/runner',
           'occurred_at':'2026-11-09T00:00:00Z','title':'Runner','summary':'Runner checkpoint review'}
    oid=core.drive.ingest(event)['opportunity_id']
    core.drive.compare(oid,[{'id':'a','actions':[]},{'id':'b','actions':[]}],objectives=[])
    core.drive.prepare(available_capacity=1)
    core.drive.record_outcome(oid,True,'operator-reviewed-result')
    topic=core.drive._get(oid)['topic_id']
    doc=core.vault.document('Source','Exact source sentence','https://example.org/source')
    core.remember_claim(topic,'Candidate',doc,'Exact source sentence')
    pred=core.vault.predict(topic,'Will recovery work?',.8,'next session')
    core.vault.resolve_prediction(pred,True,'Local test')
    core.vault.event('test',{'checkpoint':'preserved'})
    core.worldcore.remember('alice','instrument','XylophoneUnique memory',space='work')
    core.worldcore.learn_evidence('alice',{'source':'test','record_id':'test','kind':'news',
        'title':'XylophoneUnique report','summary':'Original metadata about the XylophoneUnique test result.',
        'url':'https://example.org/news','license':'METADATA-ONLY','topics':['ai'],
        'published_at':'2026-11-08T00:00:00Z'},space='work')
    first=tmp_path/'first';core.export_state(first)
    home=tmp_path/'restored';restore_state(first,home)
    restored=CognitiveCore(Settings(home=home,owner='alice',namespace='work'))
    try:
        assert restored.worldcore.recall('alice','XylophoneUnique',space='work')
        assert restored.worldcore.query_intelligence('alice','XylophoneUnique',space='work')
        assert restored.memory_search('Exact')[0]['source_url']=='https://example.org/source'
        second=tmp_path/'second';restored.export_state(second)
    finally:restored.close()
    a=json.loads((first/'state.json').read_text())['payload']['stores']
    b=json.loads((second/'state.json').read_text())['payload']['stores']
    # Only the explicit restore audit event is new; all other rows survive exactly.
    assert len(b['vault']['audit'])==len(a['vault']['audit'])+1
    del a['vault']['audit'];del b['vault']['audit']
    assert a==b


def test_pause_resume_preserves_checkpoint_and_revokes_old_worker(core):
    t=core.vault.topic('Research','What should resume after a pause?')
    ident=core.vault.job(t)
    lease=core.vault.lease_job()
    core.vault.update_job(ident,status='running',lease_token=lease['lease_token'],
                          checkpoint={'documents':['saved'],'requests_reserved':1})
    core.vault.set_topic_status(t,'paused')
    assert core.resume(t)==ident
    assert json.loads(core.vault.get_job(ident)['checkpoint'])['documents']==['saved']
    with pytest.raises(PermissionError):
        core.vault.update_job(ident,status='done',lease_token=lease['lease_token'])


def test_pause_resume_selects_latest_cancelled_job_when_timestamps_tie(core):
    t=core.vault.topic('Research','Which paused attempt should be resumed?')
    first=core.vault.job(t)
    core.vault.update_job(first,status='cancelled',checkpoint={'attempt':'old'})
    latest=core.vault.job(t)
    lease=core.vault.lease_job()
    core.vault.update_job(latest,status='running',lease_token=lease['lease_token'],checkpoint={'attempt':'latest'})
    core.vault.set_topic_status(t,'paused')
    core.vault.db.execute('UPDATE jobs SET updated=123 WHERE topic_id=?',(t,))
    assert core.resume(t)==latest
    assert json.loads(core.vault.get_job(latest)['checkpoint'])=={'attempt':'latest'}
