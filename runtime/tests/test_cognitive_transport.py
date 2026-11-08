import json
from pathlib import Path
import random
import sqlite3
import subprocess
import sys

import pytest

from cognitive_core import CognitiveCore, Settings, __version__


def worker(home, frames):
    return subprocess.run([sys.executable,'-B','-m','cognitive_core.worker',
                           '--home',str(home),'--owner','alice','--namespace','project'],
                          input=frames,capture_output=True,timeout=5)


def test_strict_frames_recover_without_opening_databases(tmp_path):
    frames=(b'{"op":"health","op":"cognitive_status"}\n'
            b'{"op":"health","_req":"health"}\n'
            b'{"op":"cognitive_observe","event":{"text":"ciao"},"_req":"hello"}\n')
    result=worker(tmp_path,frames)
    assert result.returncode==0
    answers=[json.loads(line) for line in result.stdout.splitlines()]
    assert answers[0]['ok'] is False
    assert answers[1]['result']['version']==__version__
    assert answers[2]['result']['stored'] is False
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('frame',[b'x'*64001,b'{"op":"health","x":NaN}\n',
                                   b'{"_req":"missing_op"}\n',b'{"op":false}\n',
                                   b'{"op":"cognitive_status","owner":"bob"}\n',
                                   b'{"op":"action_propose"}\n',b'{"op":"cognitive_tick"}\n'])
def test_worker_rejects_unsafe_frames_without_opening_database(tmp_path,frame):
    result=worker(tmp_path,frame)
    assert json.loads(result.stdout)['ok'] is False
    assert not list(tmp_path.iterdir())


def test_worker_routes_real_worldcore_whatif_and_cognitive_topics(tmp_path):
    frames=[{'op':'cognitive_observe','event':{'kind':'question_open','question':'Which material should we investigate?'}},
            {'op':'whatif_compare','question':'Compare declared assumptions',
             'scenarios':[{'id':'a','actions':[]},{'id':'b','actions':[]}],'objectives':[]}]
    result=worker(tmp_path,('\n'.join(json.dumps(f) for f in frames)+'\n').encode())
    responses=[json.loads(line) for line in result.stdout.splitlines()]
    assert all(r['ok'] for r in responses)
    assert responses[1]['result']['action_executed'] is False
    with sqlite3.connect(tmp_path/'worldcore.sqlite3') as db:
        row=db.execute('SELECT owner,space FROM whatif_runs').fetchone()
        assert row==('alice','project')
    assert (tmp_path/'vault.sqlite3').exists()


def test_legacy_compare_cli_emits_strict_json(tmp_path):
    result=subprocess.run([sys.executable,'-B','-m','cognitive_core','--home',str(tmp_path),
                           'compare','[{"name":"denied","changes":{}}]'],
                          capture_output=True,text=True,timeout=5)
    assert result.returncode==0
    decoded=json.loads(result.stdout,parse_constant=lambda x:pytest.fail('invalid JSON '+x))
    assert decoded[0]['score'] is None
    assert not list(tmp_path.iterdir())


def test_state_counterfactual_property_preserves_input_and_baseline(tmp_path):
    import copy
    rng=random.Random(981)
    c=CognitiveCore(Settings(home=tmp_path))
    try:
        for _ in range(25):
            initial=rng.uniform(-1000,1000);change=rng.uniform(-100,100)
            c.worldcore.set_state('local','x',initial)
            alternatives=[{'id':'base','actions':[]},
                          {'id':'change','actions':[{'op':'add','key':'x','value':change}]}]
            before=copy.deepcopy(alternatives)
            result=c.compare_futures('Check declared state changes',alternatives,persist=False)
            assert alternatives==before
            assert c.worldcore.state('local')['x']==initial
            assert result['scenarios'][1]['projected_state']['x']==pytest.approx(initial+change)
            assert result['candidate_for_review'] is None
    finally:
        c.close()


def test_prediction_resolution_is_single_winner_across_connections(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from cognitive_core.vault import Vault
    settings=Settings(home=tmp_path)
    vault=Vault(settings)
    topic=vault.topic('Test','Will a synthetic outcome occur?')
    ident=vault.predict(topic,'Synthetic outcome',.75,'test')
    vault.close()
    def resolve(happened):
        v=Vault(settings)
        try:
            try:return v.resolve_prediction(ident,happened)
            except ValueError:return None
        finally:v.close()
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(resolve,[True,False]))
    assert sum(r is not None for r in results)==1


@pytest.mark.parametrize('headers,body,status',[
    ({'Origin':'https://outside.example'},b'{"text":"ciao"}',403),
    ({'Host':'outside.example:8731'},b'{"text":"ciao"}',403),
    ({'Content-Type':'text/plain'},b'{"text":"ciao"}',415),
    ({},b'{"text":"ciao","text":"overwrite"}',400),
    ({},b'{"text":"ciao"}',200),
])
def test_rest_browser_guards_without_network(tmp_path,monkeypatch,headers,body,status):
    import io
    from types import SimpleNamespace
    from cognitive_core.api import serve
    c=CognitiveCore(Settings(home=tmp_path))
    output=bytearray()
    class Connection:
        def makefile(self,*args):return io.BytesIO(request)
        def settimeout(self,value):assert value==5
        def sendall(self,data):output.extend(data)
    def factory(address,handler):
        server=SimpleNamespace(server_port=8731,server_name='localhost',server_close=lambda:None)
        server.serve_forever=lambda:handler(Connection(),('127.0.0.1',1234),server)
        return server
    fields={'Host':'127.0.0.1:8731','Content-Type':'application/json',
            'Content-Length':str(len(body)),**headers}
    request=('POST /v1/events HTTP/1.0\r\n'+''.join(k+': '+v+'\r\n' for k,v in fields.items())+'\r\n').encode()+body
    monkeypatch.setattr('cognitive_core.api.HTTPServer',factory)
    try:
        serve(c)
        assert bytes(output).split(b'\r\n')[0].split()[1]==str(status).encode()
        assert not list(tmp_path.iterdir())
    finally:c.close()


def test_v01_topic_schema_migration_preserves_existing_ids(tmp_path):
    with sqlite3.connect(tmp_path/'vault.sqlite3') as db:
        db.executescript('''CREATE TABLE topics(
            id TEXT PRIMARY KEY, namespace TEXT NOT NULL, title TEXT NOT NULL,
            question TEXT NOT NULL, status TEXT NOT NULL, importance REAL NOT NULL,
            reason TEXT NOT NULL, trigger TEXT NOT NULL DEFAULT '',
            created INTEGER NOT NULL, updated INTEGER NOT NULL);
            INSERT INTO topics VALUES('legacy','default','Existing topic',
                'Which material should be used?','discarded',.5,'observed','question_open',1,1);''')
    c=CognitiveCore(Settings(home=tmp_path))
    try:
        result=c.observe({'kind':'question_open','question':'Which material should be used?'})
        assert result['topics']==['legacy']
        assert c.vault.pending_jobs()==[]
        assert c.vault.get_topic('legacy')['status']=='discarded'
    finally:c.close()
