"""New v0.6 regression tests: abstention, isolation, leakage, immutable evidence."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import pytest
from worldcore import WorldCore, WorldCoreError

NOW=datetime(2025,1,1,tzinfo=timezone.utc)

def t(hours):return (NOW+timedelta(hours=hours)).isoformat()

@pytest.fixture
def w():
    with WorldCore(':memory:') as x:yield x

def test_wm_unknown_must_abstain(w):
    x=w.imagine_world('a','grid',{'x':0},['right'])
    assert x['status']=='abstain'

def test_wm_learns_deterministic_observations(w):
    for i in range(5):
        w.observe_world_transition('a','grid',f's{i}',{'x':0},'right',{'x':1})
    x=w.imagine_world('a','grid',{'x':0},['right'])
    assert x['status']=='simulated' and x['steps'][0]['states'][0]['state']=={'x':1}
    assert x['steps'][0]['states'][0]['likelihood']==1

def test_wm_simulated_samples_do_not_authorize_truth(w):
    for i in range(6):w.observe_world_transition('a','lab',f's{i}',0,'go',1,source='simulated')
    assert w.imagine_world('a','lab',0,['go'])['status']=='abstain'

def test_wm_multi_step_and_immutable(w):
    for i in range(3):
        w.observe_world_transition('a','e',f'a{i}',0,'step',1)
        w.observe_world_transition('a','e',f'b{i}',1,'step',2)
    x=w.imagine_world('a','e',0,['step','step'])
    assert x['steps'][-1]['states'][0]['state']==2
    assert w.observe_world_transition('a','e','a1',0,'step',1)['status']=='unchanged'
    with pytest.raises(WorldCoreError):w.observe_world_transition('a','e','a1',0,'step',5)

def test_wm_scopes_and_source_filter(w):
    for i in range(3):w.observe_world_transition('a','e',f's{i}',0,'go',1,space='p1')
    assert w.imagine_world('a','e',0,['go'],space='p2')['status']=='abstain'
    assert w.imagine_world('b','e',0,['go'],space='p1')['status']=='abstain'

def test_wm_prediction_resolve(w):
    for i in range(4):w.observe_world_transition('a','e',f's{i}',0,'go',1)
    p=w.submit_world_prediction('a','e',0,'go')
    assert p['status']=='pending'
    r=w.resolve_world_prediction('a',p['prediction_id'],1)
    assert r['correct']
    assert w.world_model_metrics('a','e')['top_state_accuracy']==1
    assert w.resolve_world_prediction('a',p['prediction_id'],1)['status']=='unchanged'
    with pytest.raises(WorldCoreError):w.resolve_world_prediction('b',p['prediction_id'],1)
    with pytest.raises(WorldCoreError):w.resolve_world_prediction('a',p['prediction_id'],2)

def test_world_model_discrete_branch(w):
    for i in range(5):w.observe_world_transition('a','e',f's{i}',0,'go',1 if i<3 else 2)
    result=w.imagine_world('a','e',0,['go'])
    ps=[x['likelihood'] for x in result['steps'][0]['states']]
    assert ps==[.6,.4]

def test_wm_rejects_nonfinite_and_large(w):
    with pytest.raises(WorldCoreError):w.observe_world_transition('a','e','x',{'x':float('nan')},'go',1)
    with pytest.raises(WorldCoreError):w.observe_world_transition('a','e','x','a'*4000,'go',1)
    with pytest.raises(WorldCoreError):w.imagine_world('a','e',0,['go']*9)

def prices(w, symbol, path):
    for hour,price in path:
        w.record_price('u',symbol,t(hour),price,source='fixture')

def test_market_underpowered_abstain(w):
    w.record_news('u','n1','ai',t(0),'News','https://example.org/n1',source='fixture')
    assert w.news_market_study('u','ai','A','B')['status']=='abstain'

def test_market_study_timing_and_overlap(w):
    for symbol,returns in [('A',[1.10,1.05,1.08,1.11,1.06]),('B',[1.01,1.02,1.01,1.03,1.01])]:
        vals=[]
        for i,ret in enumerate(returns):
            base=100
            vals.extend([(i*50,base),(i*50+24,base*ret)])
        prices(w,symbol,vals)
    for i in range(5):w.record_news('u',f'n{i}','ai',t(i*50),'News','https://example.org/news',source='fixture')
    d=w.news_market_study('u','ai','A','B',max_gap_hours=1)
    assert d['status']=='retrospective_only' and d['events']==5 and d['positive_fraction']==1
    assert 'causation' in str(d['limitations'])

def test_market_event_lookahead_no_prepublication_price(w):
    prices(w,'A',[(-1,1),(25,100)])
    prices(w,'B',[(-1,1),(25,100)])
    w.record_news('u','n','ai',t(0),'Breaking','https://example.org/news',source='fixture')
    x=w.news_market_study('u','ai','A','B',min_events=3)
    assert x['status']=='abstain'

def test_market_price_and_news_conflicts(w):
    assert w.record_price('u','BTC',t(0),300,source='a')['status']=='recorded'
    assert w.record_price('u','BTC',t(0),300,source='a')['status']=='unchanged'
    with pytest.raises(WorldCoreError):w.record_price('u','BTC',t(0),301,source='a')
    with pytest.raises(WorldCoreError):w.record_price('u','BTC',t(0),float('inf'),source='a')
    w.record_news('u','n','crypto',t(0),'A','https://example.org/a',source='x')
    with pytest.raises(WorldCoreError):w.record_news('u','n','crypto',t(0),'B','https://example.org/a',source='x')

def perception():
    return {'id':'z','modality':'image','source':'host_image','adapter':'host_vision',
            'at':t(0),'claims':['A diagram depicts a graph'],'confidence':.6,
            'verification':'unverified'}

def test_perception_host_contract(w):
    d=perception();out=w.ingest_perception('u',d)
    assert not out['trusted_as_instructions']
    assert w.explain_observation('u','z')['claims']==d['claims']
    assert w.explain_observation('other','z') is None
    assert w.ingest_perception('u',d)['status']=='unchanged'
    with pytest.raises(WorldCoreError):w.ingest_perception('u',{**d,'claims':['changed']})

def test_perception_rejects_unbounded_payload(w):
    d=perception();d['claims']=['a'*401]
    with pytest.raises(WorldCoreError):w.ingest_perception('u',d)
    d=perception();d['modality']='telepathy'
    with pytest.raises(WorldCoreError):w.ingest_perception('u',d)

def test_advisories_do_not_claim_certainty_or_act(w):
    for domain in ('medicine','psychology','finance','crypto','sports_science','general'):
        d=w.suggest_with_uncertainty(domain,'Consider examining evidence',[{'url':'https://example.org'}],confidence=.4)
        assert not d['confidence_calibrated'] and not d['authorized_action']
        assert d['notice']
    with pytest.raises(WorldCoreError):w.suggest_with_uncertainty('medicine','You are ill',[])

def test_skill_feedback_idempotent(w):
    assert w.record_skill_feedback('u','1','browser',True,'completed',at=t(0))['status']=='recorded'
    assert w.record_skill_feedback('u','1','browser',True,'completed',at=t(0))['status']=='unchanged'
    with pytest.raises(WorldCoreError):w.record_skill_feedback('u','1','browser',False,'failed',at=t(0))

def test_social_virality_is_descriptive(w):
    assert w.social_velocity('u','youtube','v1')['status']=='abstain'
    w.add_social_snapshot('u','youtube','v1',t(0),100,5,10,25,source='api')
    w.add_social_snapshot('u','youtube','v1',t(2),300,15,25,90,source='api')
    x=w.social_velocity('u','youtube','v1')
    assert x['views_per_hour']==100 and x['shares_per_hour']==5
    assert x['weighted_engagement_per_new_view']==round((10*3+15*2+65)/200,6)
    with pytest.raises(WorldCoreError):w.add_social_snapshot('u','youtube','v1',t(3),200,15,25,90,source='api')

def test_v06_catalog_candidates():
    catalog=Path(__file__).parents[1]/'catalog/repository_candidates_v06.json'
    records=json.loads(catalog.read_text())
    assert len(records)>=200
    assert len({r['repo'] for r in records})==len(records)
    assert all(r['quality_score'] is None and r['trained_on_code'] is False for r in records)
    assert all(r['url']=='https://github.com/'+r['repo'] for r in records)

def test_incremental_language_intent_and_isolation(w):
    for i,text in enumerate(('notizie recenti','ultime notizie di oggi','news online di oggi','leggi le notizie')):
        w.label_utterance('u',f'n{i}',text,'news')
    for i,text in enumerate(('ricorda la scadenza','salva nella memoria','memorizza questa data','ricordami la data')):
        w.label_utterance('u',f'm{i}',text,'memory')
    x=w.classify_intent('u','ultime notizie online')
    assert x['status']=='classified' and x['intent']=='news'
    assert w.classify_intent('other','ultime notizie online')['status']=='abstain'
    assert w.classify_intent('u','kvasar digitometro')['status']=='abstain'
    with pytest.raises(WorldCoreError):w.label_utterance('u','n1','notizie recenti','memory')

def test_new_modules_survive_restart(tmp_path):
    db=str(tmp_path/'restart.sqlite')
    with WorldCore(db) as w:
        for i in range(3):w.observe_world_transition('x','reality',f'{i}',{'state':'idle'},'start',{'state':'busy'})
        w.label_utterance('x','lang1','leggi notizie','news')
        w.add_social_snapshot('x','tiktok','p',t(0),20,2,3,4,source='api')
    with WorldCore(db) as w:
        assert w.imagine_world('x','reality',{'state':'idle'},['start'])['status']=='simulated'
        assert w.db.execute('SELECT count(*) FROM labeled_utterances').fetchone()[0]==1
        assert w.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_bridge_world_operations(tmp_path):
    from worldcore.bridge import dispatch
    with WorldCore(tmp_path/'db.sqlite') as w:
        assert dispatch({'owner':'a','op':'world_imagine','environment':'e','before':0,'actions':['go']},w)['status']=='abstain'
        assert dispatch({'owner':'a','op':'world_reliability','environment':'e'},w)['observed_transitions']==0
        assert dispatch({'owner':'a','op':'social_velocity','platform':'x','post':'p'},w)['status']=='abstain'
        assert dispatch({'owner':'a','op':'language_intent','text':'ciao'},w)['status']=='abstain'
        with pytest.raises(WorldCoreError):dispatch({'owner':'a','op':'remote_execute','command':'rm'},w)
