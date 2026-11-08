from datetime import datetime,timedelta,timezone
import pytest
from worldcore import WorldCore,WorldCoreError

T='2031-03-16T'
def dt(h,m=0):return f'{T}{h:02d}:{m:02d}:00+00:00'

@pytest.fixture
def core(tmp_path):
    with WorldCore(tmp_path/'personal.db') as w:yield w

def test_calendar_versions_cancel_and_scoping(core):
    core.put_calendar_event('a','e1','Work',dt(9),dt(10),place='office',space='work')
    core.put_calendar_event('a','e1','Rescheduled',dt(11),dt(12),place='office',space='work')
    assert len(core.calendar_window('a',dt(8),dt(18),space='work'))==1
    assert core.calendar_window('a',dt(8),dt(18),space='private')==[]
    assert core.calendar_window('b',dt(8),dt(18),space='work')==[]
    core.put_calendar_event('a','e1','Cancelled',dt(11),dt(12),place='office',space='work',status='cancelled')
    assert core.calendar_window('a',dt(8),dt(18),space='work')==[]

def test_planner_conflict_email_and_commute(core):
    for minutes in [23,28,31,40,26]:core.observe_travel('a','home','office',dt(6),minutes)
    core.put_calendar_event('a','meeting1','Meeting',dt(9),dt(10),place='office')
    core.put_calendar_event('a','meeting2','Overlaps',dt(9,45),dt(11),place='office')
    core.put_mail_signal('a','m1',dt(7),'Please reply',deadline=dt(8))
    answer=core.day_advice('a',dt(8),dt(16),from_place='home',now=dt(7,30))
    assert len(answer['events'])==2
    assert answer['events'][0]['leave_at']==dt(8,19)
    assert answer['events'][1]['conflict'] is True
    assert answer['unanswered_mail'][0]['urgent']
    assert not core.mail_attention('b',now=dt(8))
    assert core.travel_forecast('a','home','nowhere')['status']=='abstain'

def test_slot_with_unknown_travel_abstains(core):
    core.put_calendar_event('a','a','Busy',dt(9),dt(10),place='office')
    r=core.recommend_slot('a',dt(9),dt(11),30,place='studio',from_place='home')
    assert r['status']=='abstain'

def test_remote_slot_when_free(core):
    core.put_calendar_event('a','a','Meeting',dt(10),dt(11),place='remote')
    r=core.recommend_slot('a',dt(9),dt(13),30,place='remote',from_place='remote')
    assert r['status']=='suggested'
    s=datetime.fromisoformat(r['best']['start']);e=datetime.fromisoformat(r['best']['end'])
    assert not (s<datetime.fromisoformat(dt(11)) and e>datetime.fromisoformat(dt(10)))

def test_route_optimization_learning(core):
    for a,b,m in [('home','A',50),('home','B',10),('B','A',12),('A','B',35)]:
        for i in range(4):core.observe_travel('a',a,b,dt(6),m)
    r=core.optimize_stop_order('a','home',['A','B'])
    assert r['status']=='suggested' and r['order']==['B','A']
    assert core.optimize_stop_order('a','home',['A','C'])['status']=='abstain'

def test_no_bad_dates_or_negative_commute(core):
    with pytest.raises(WorldCoreError):core.put_calendar_event('a','bad','test',dt(11),dt(10))
    with pytest.raises(WorldCoreError):core.observe_travel('a','home','office',dt(6),-5)
    with pytest.raises(WorldCoreError):core.put_calendar_event('a','bad','test','2031-03-16T10:00:00',dt(11))

def test_mail_redaction(core):
    core.put_mail_signal('a','mail','2031-03-16T07:00:00Z','password: secretValue',requires_reply=True)
    res=core.mail_attention('a',now=dt(8))
    assert 'secretValue' not in res[0]['subject']
