from __future__ import annotations
import concurrent.futures
import multiprocessing
import importlib
import json
import os
import sqlite3
import subprocess
import sys
import types
from datetime import datetime, timedelta, timezone
import pytest
from worldcore import WorldCore, WorldCoreError


def _consume(args):
    path, owner, aid, action, data = args
    with WorldCore(path) as w:
        return w.consume_approval(owner,aid,action,data)


def _tick(args):
    path, owner=args
    with WorldCore(path) as w:return len(w.tick(owner))


def test_concurrent_one_time_approval(tmp_path):
    path=str(tmp_path/'permission.db')
    with WorldCore(path) as w:
        req=w.request_action('u','send_message',{'to':'abc'},'operator reviewed')
        w.approve_action('u',req['id'],approve=True)
    params=[(path,'u',req['id'],'send_message',{'to':'abc'})]*8
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn')) as executor:
        outcomes=list(executor.map(_consume,params))
    assert outcomes.count(True)==1


def test_concurrent_proactive_cooldown(tmp_path):
    path=str(tmp_path/'rules.db')
    with WorldCore(path) as w:
        w.set_state('u','risk',10)
        w.add_rule('u','risk','>',5,'Investigate',cooldown_seconds=86400)
    with concurrent.futures.ProcessPoolExecutor(max_workers=4, mp_context=multiprocessing.get_context('spawn')) as executor:
        counts=list(executor.map(_tick,[(path,'u')]*8))
    assert sum(counts)==1


def test_fts_search_over_thousand_entries(tmp_path):
    with WorldCore(tmp_path/'many.db') as w:
        for i in range(1101):w.remember('u',f'item.{i}',f'ordinary note {i}')
        w.remember('u','deep.discovery','zirconium uniquely unusual')
        assert len(w.recall('u','zirconium'))==1
        assert w.recall('u','zirconium')[0]['fact_key']=='deep.discovery'
        assert w.fts_enabled
        assert w.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        w.forget('u','deep.discovery')
        assert w.recall('u','zirconium')==[]


def test_fts_backfill_existing_legacy_db(tmp_path):
    p=tmp_path/'old.db'
    with WorldCore(p) as w:
        w.remember('x','legacy','migrateable unique')
        w.db.executescript('DROP TRIGGER IF EXISTS memories_fts_insert; DROP TRIGGER IF EXISTS memories_fts_delete; DROP TABLE IF EXISTS memories_fts;')
    with WorldCore(p) as w:
        assert w.recall('x','migrateable')[0]['fact_key']=='legacy'
        assert w.fts_enabled


def test_fts_no_cross_project_leak(tmp_path):
    with WorldCore(tmp_path/'db.db') as w:
        for i in range(100):
            w.remember('alice',f'a{i}','classified QWERTY',space='company')
            w.remember('alice',f'a{i}','harmless QWERTY',space='home')
        assert all(x['value']=='harmless QWERTY' for x in w.recall('alice','QWERTY',space='home',limit=50))
        assert w.recall('bob','QWERTY',space='company')==[]


def test_mcp_contract_fake_server(monkeypatch,tmp_path):
    from worldcore import mcp_server
    monkeypatch.setenv('WORLDCORE_DB',str(tmp_path/'db.db'))
    monkeypatch.setenv('WORLDCORE_OWNER','mcp-owner')
    monkeypatch.setenv('WORLDCORE_SPACE','mcp-space')
    class FakeMCP:
        def __init__(self,*args,**kwargs):self.tools={}
        def tool(self):
            def deco(fn):self.tools[fn.__name__]=fn;return fn
            return deco
    fake_root=types.ModuleType('mcp')
    fake_server=types.ModuleType('mcp.server')
    fake_fast=types.ModuleType('mcp.server.fastmcp')
    fake_fast.FastMCP=FakeMCP
    monkeypatch.setitem(sys.modules,'mcp',fake_root)
    monkeypatch.setitem(sys.modules,'mcp.server',fake_server)
    monkeypatch.setitem(sys.modules,'mcp.server.fastmcp',fake_fast)
    srv=mcp_server.create_server()
    assert 'approve_action' not in srv.tools and 'consume_approval' not in srv.tools
    assert 'memory_save' in srv.tools and 'action_request' in srv.tools
    memory=srv.tools['memory_save']('arch','predict first')
    assert memory['owner']=='mcp-owner'
    assert srv.tools['memory_recall']('arch')[0]['value']=='predict first'
    assert srv.tools['world_simulate']([{'op':'set','key':'x','value':2}])['executed'] is False
    assert srv.tools['prediction_stats']()['resolved']==0
    request=srv.tools['action_request']('send_mail',{},'please review')
    assert request['status']=='pending'


def test_bridge_rejects_large_input(tmp_path):
    env={**os.environ,'WORLDCORE_DB':str(tmp_path/'db.db')}
    p=subprocess.run([sys.executable,'-m','worldcore.bridge'],input=' '*64001,capture_output=True,text=True,env=env)
    assert p.returncode!=0
    assert 'too large' in json.loads(p.stdout)['error']


def test_json_nan_and_invalid_state(tmp_path):
    with WorldCore(tmp_path/'db.db') as w:
        for value in [float('nan'),float('inf'),{3},object()]:
            with pytest.raises(WorldCoreError):w.set_state('u','thing',value)


def test_recall_context_max_bytes(tmp_path):
    with WorldCore(tmp_path/'db.db') as w:
        w.remember('u','a','x'*2000)
        # Value may be too large for context budget, but no partial line should appear.
        result=w.context_for('u','a',max_chars=100)
        assert not result


def test_forecast_not_due_safety(tmp_path):
    with WorldCore(tmp_path/'db.db') as w:
        due=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
        f=w.forecast('u','event',True,.9,due)
        with pytest.raises(WorldCoreError):w.resolve_forecast('u',f['id'],True)


def test_nested_tx_rollback_on_exception(tmp_path):
    with WorldCore(tmp_path/'db.db') as w:
        try:
            with w._transaction():
                w.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?)", ('x','a','s','event','test','time','test','test',None))
                raise RuntimeError('rollback')
        except RuntimeError:pass
        assert len(w.events('a',space='s'))==0


def test_expired_memory_excluded_from_search_and_context(tmp_path):
    with WorldCore(tmp_path/'db.db') as w:
        m=w.remember('u','temporary','short lived evidence',valid_until=(datetime.now(timezone.utc)+timedelta(minutes=2)).isoformat())
        w.db.execute("UPDATE memories SET valid_until=? WHERE id=?", ((datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat(),m['id']))
        assert w.recall('u','evidence') == []
        assert not w.context_for('u','temporary')
        assert len(w.history('u','temporary')) == 1
