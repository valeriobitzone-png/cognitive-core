import copy
import json
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest

from cognitive_core import CognitiveCore, Settings
from cognitive_core.vault import Vault


@pytest.fixture
def core(tmp_path):
    c = CognitiveCore(Settings(home=tmp_path, namespace='alice'))
    yield c
    c.close()


def test_greeting_does_not_open_either_database(core):
    with patch('cognitive_core.engine.Vault', side_effect=AssertionError('DB opened')):
        assert core.observe({'text': 'ciao'})['action'] == 'WAIT'
    assert list(core.s.home.iterdir()) == []


def test_observe_does_not_mutate_input(core):
    event = {'kind': 'session_end', 'question': 'Which printer is suitable?',
             'open_questions': ['Which material is suitable?']}
    before = copy.deepcopy(event)
    core.observe(event)
    assert event == before


def test_checkpoint_keeps_exclusive_lease(core):
    topic = core.vault.topic('printer', 'Which material should be used?')
    core.vault.job(topic)
    job = core.vault.lease_job()
    core.vault.update_job(job['id'], status='running', checkpoint={'completed': ['a']},
                          lease_token=job['lease_token'])
    other = Vault(core.s)
    try:
        assert other.lease_job() is None
    finally:
        other.close()


def test_stale_worker_cannot_overwrite_new_lease(core):
    topic = core.vault.topic('T', 'Which material should be used?')
    core.vault.job(topic)
    first = core.vault.lease_job()
    core.vault.db.execute('UPDATE jobs SET lease_until=0 WHERE id=?', (first['id'],))
    second = core.vault.lease_job()
    assert first['lease_token'] != second['lease_token']
    with pytest.raises(PermissionError):
        core.vault.update_job(first['id'], status='done', lease_token=first['lease_token'])
    core.vault.update_job(second['id'], status='done', lease_token=second['lease_token'])


def test_pausing_revokes_running_worker(core):
    topic = core.vault.topic('T', 'Which material should be used?')
    core.vault.job(topic)
    job = core.vault.lease_job()
    core.vault.set_topic_status(topic, 'paused')
    with pytest.raises(PermissionError):
        core.vault.update_job(job['id'], status='done', lease_token=job['lease_token'])


def test_repeated_event_does_not_revive_discarded_topic(core):
    event = {'kind': 'question_open', 'question': 'Which material should be used?'}
    first = core.observe(event)
    core.vault.set_topic_status(first['topics'][0], 'discarded')
    again = core.observe(event)
    assert again['topics'] == first['topics']
    assert len(core.vault.list_topics()) == 1
    assert core.vault.pending_jobs() == []


@pytest.mark.parametrize('amount', [-1, 0, True, 1.5])
def test_invalid_budget_amount_cannot_mint_quota(core, amount):
    with pytest.raises(ValueError):
        core.vault.reserve_budget('requests', 10, amount)


def test_concurrent_budget_and_topic_dedup(core):
    core.vault
    def reserve(_):
        vault = Vault(core.s)
        try:
            topic = vault.topic('T', 'Which material should be used?')
            return topic, vault.reserve_budget('requests', 3)
        finally:
            vault.close()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(reserve, range(12)))
    assert len({topic for topic, _ in results}) == 1
    assert sum(ok for _, ok in results) == 3


def test_integrated_whatif_uses_worldcore_and_isolates_namespace(core):
    core.worldcore.set_state('local', 'budget', 100, space='alice')
    result = core.compare_futures('Compare budget assumptions', [
        {'id': 'keep', 'actions': []},
        {'id': 'prepare', 'actions': [{'op': 'add', 'key': 'budget', 'value': -5}]}],
        objectives=[{'key': 'budget', 'direction': 'minimize', 'scale': 1}])
    assert result['ranking'] == ['prepare', 'keep']
    assert result['action_executed'] is False
    assert core.worldcore.state('local', space='alice')['budget'] == 100
    assert len(core.worldcore.whatif_history('local', space='alice')) == 1
    other = CognitiveCore(Settings(home=core.s.home, namespace='bob'))
    try:
        assert other.worldcore.whatif_history('local', space='bob') == []
    finally:
        other.close()


def test_memory_search_returns_both_backends(core):
    core.vault.document('PLA', 'PLA printing material')
    core.worldcore.remember('local', 'material', 'PLA printing preference', space='alice')
    assert len(core.memory_search('PLA')) == 2


def test_integrated_worker_preserves_zero_db_and_scope(core):
    from cognitive_core.worker import dispatch
    assert dispatch({'op': 'cognitive_observe', 'event': {'text': 'ciao'}}, core)['action'] == 'WAIT'
    assert list(core.s.home.iterdir()) == []
    with pytest.raises(ValueError):
        dispatch({'op': 'remember', 'owner': 'other', 'key': 'x', 'value': 'bad'}, core)
    with pytest.raises(ValueError):
        dispatch({'op': 'action_execute_approved'}, core)
    assert list(core.s.home.iterdir()) == []


def test_same_namespace_different_owners_cannot_read_vault(core):
    core.vault.document('Private', 'unique private content')
    other=CognitiveCore(Settings(home=core.s.home,namespace='alice',owner='other'))
    try:
        assert other.memory_search('unique') == []
    finally:
        other.close()


def test_repeated_observation_creates_one_pending_job(core):
    event={'kind':'question_open','question':'Which material should be used?'}
    for _ in range(5):core.observe(event)
    assert len(core.vault.pending_jobs()) == 1


def test_per_job_budget_counts_robots_and_page(tmp_path):
    from cognitive_core.research import Researcher
    c=CognitiveCore(Settings(home=tmp_path,enable_web=True,domain_allowlist=('example.org',),
                            max_web_requests_per_job=3,max_web_requests_per_day=10))
    try:
        c.observe({'kind':'research_requested','question':'Research source documentation',
                   'seed_urls':['https://example.org/a','https://example.org/b']})
        def fetch(researcher,url):
            researcher.reserve_additional_request()
            return {'title':'Source','text':'Untrusted source material','url':url,
                    'content_type':'text/plain','images':[]}
        with patch.object(Researcher,'fetch',fetch):result=c.work_once()
        assert result['status']=='blocked'
        assert c.vault.usage('web_requests')==3
        checkpoint=json.loads(c.vault.get_job(result['job_id'])['checkpoint'])
        assert checkpoint['requests_reserved']==3
        assert len(checkpoint['documents'])==1
    finally:
        c.close()


def test_public_transport_rejects_private_resolution_before_connect():
    from cognitive_core.research import PublicHTTPSConnection
    address=[(2,1,6,'',('127.0.0.1',443))]
    with patch('socket.getaddrinfo',return_value=address),patch('socket.create_connection') as connect:
        with pytest.raises(PermissionError):PublicHTTPSConnection('example.org').connect()
        connect.assert_not_called()


def test_local_model_ignores_external_proxy_environment(core):
    from cognitive_core.decision import LocalDecisionModel
    with patch('urllib.request.build_opener') as opener:
        opener.return_value.open.side_effect=OSError('no local model')
        with pytest.raises(OSError):LocalDecisionModel(core.s).decide({'kind':'question_open'})
        assert opener.call_args.args[0].proxies=={}


def test_web_redirects_require_explicit_new_url():
    from cognitive_core.research import NoRedirect
    with pytest.raises(PermissionError):
        NoRedirect().redirect_request(None,None,302,'redirect',{},'https://example.org/b')


def test_explicit_scheduler_reconsiders_expired_running_job(tmp_path,monkeypatch,capsys):
    from cognitive_core.cli import main
    c=CognitiveCore(Settings(home=tmp_path))
    c.observe({'kind':'question_open','question':'Which documentation should we investigate?'})
    job=c.vault.lease_job()
    c.vault.db.execute('UPDATE jobs SET lease_until=0 WHERE id=?',(job['id'],))
    c.close()
    def stop(_):raise KeyboardInterrupt
    monkeypatch.setattr('time.sleep',stop)
    main(['--home',str(tmp_path),'daemon','--interval','5'])
    assert 'web is disabled' in capsys.readouterr().out
    c=CognitiveCore(Settings(home=tmp_path))
    try:assert c.vault.get_job(job['id'])['status']=='blocked'
    finally:c.close()


def test_concurrent_sources_preserve_conflicted_status(core):
    topic=core.vault.topic('Evidence','Which material should be used?')
    doc=core.vault.document('Source','Observed source statement')
    claim=core.vault.claim(topic,'Candidate statement')
    def attach(stance):
        v=Vault(core.s)
        try:return v.add_evidence(claim,doc,'Observed source statement',stance=stance)
        finally:v.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(attach,['supports','contradicts']))
    row=core.vault.db.execute('SELECT status FROM claims WHERE id=?',(claim,)).fetchone()
    assert row['status']=='conflicted'


def test_canonical_whatif_rejects_invalid_objective_mapping(core):
    with pytest.raises(ValueError):
        core.compare_futures('Compare declared effects',[
            {'id':'a','actions':[]},{'id':'b','actions':[]}],objectives={})
