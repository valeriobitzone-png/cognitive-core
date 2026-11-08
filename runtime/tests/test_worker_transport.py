"""Black-box stdio contracts for the distributable worker."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import pytest
from worldcore import WorldCore


def environment(tmp_path):
    return {**os.environ,'WORLDCORE_DB':str(tmp_path/'worker.db'),'PYTHONDONTWRITEBYTECODE':'1'}


def run(payload,tmp_path,*,worker=False):
    command=[sys.executable,'-B','-c','from worldcore.bridge import worker_main; worker_main()'] if worker else [sys.executable,'-B','-m','worldcore.bridge']
    return subprocess.run(command,input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment(tmp_path),timeout=4)


def test_oversize_line_rejected_before_newline_or_eof(tmp_path):
    proc=subprocess.Popen([sys.executable,'-B','-m','worldcore.bridge','--lines'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment(tmp_path))
    try:
        proc.stdin.write(b'x'*64001);proc.stdin.flush()
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout,selectors.EVENT_READ)
            assert selector.select(timeout=1.5),'oversize unterminated frame left the worker waiting'
        result=json.loads(proc.stdout.readline())
        assert not result['ok'] and 'too large' in result['error']
        assert proc.wait(timeout=1)!=0
    finally:
        if proc.poll() is None:proc.kill()
        proc.communicate(timeout=2)


def test_limits_are_utf8_bytes_not_characters(tmp_path):
    result=run(json.dumps({'op':'unknown','owner':'a','extra':'界'*22000},ensure_ascii=False).encode(),tmp_path)
    assert 'too large' in json.loads(result.stdout)['error']


@pytest.mark.parametrize('payload',[
    b'{"op":"simulate","owner":"a","actions":[],"ignored":NaN}',
    b'{"op":"simulate","owner":"a","owner":"b","actions":[]}',
    b'{"op":"simulate","owner":"a","actions":[],"_req":{"untrusted":"object"}}',
    b'{"op":"simulate","owner":"a","actions":[],"_req":"'+b'x'*129+b'"}',
    b'{"op":"context","owner":"a","query":"\xff"}',
])
def test_invalid_frames_are_errors_and_not_echoed(payload,tmp_path):
    result=run(payload,tmp_path)
    response=json.loads(result.stdout)
    assert result.returncode!=0 and response['ok'] is False
    assert not result.stderr
    assert response.get('_req') is None


def test_bad_frame_does_not_poison_next_request(tmp_path):
    payload=b'{bad}\n'+json.dumps({'op':'simulate','owner':'a','actions':[],'_req':'next'}).encode()+b'\n'
    result=subprocess.run([sys.executable,'-B','-m','worldcore.bridge','--lines'],input=payload,capture_output=True,env=environment(tmp_path),timeout=4)
    responses=[json.loads(line) for line in result.stdout.splitlines()]
    assert responses[0]['ok'] is False and responses[1]['ok'] is True
    assert responses[1]['_req']=='next'


def test_worker_identity_is_bound_by_operator(tmp_path):
    with WorldCore(tmp_path/'worker.db') as w:
        w.remember('operator','only','operator-owned value',space='project')
    env={**environment(tmp_path),'WORLDCORE_OWNER':'operator','WORLDCORE_SPACE':'project'}
    payloads=[{'op':'health','_req':'ready'},
              {'op':'recall','query':'owned','_req':'allowed'},
              {'op':'remember','owner':'attacker','key':'foreign','value':'bad','_req':'foreign'},
              {'op':'remember','space':'other','key':'foreign','value':'bad','_req':'space'}]
    result=subprocess.run([sys.executable,'-B','-c','from worldcore.bridge import worker_main; worker_main()'],
        input=('\n'.join(json.dumps(p) for p in payloads)+'\n').encode(),capture_output=True,env=env,timeout=4)
    frames=[json.loads(line) for line in result.stdout.splitlines()]
    assert len(frames)==4, result.stderr
    assert frames[0]['result']['protocol']=='worldcore-jsonl-v1'
    assert frames[1]['result']['memories'][0]['owner']=='operator'
    assert not frames[2]['ok'] and not frames[3]['ok']
    with WorldCore(tmp_path/'worker.db') as w:
        assert w.history('attacker','foreign')==[]
        assert w.history('operator','foreign',space='other')==[]


def test_worker_version_does_not_open_database(tmp_path):
    env={**environment(tmp_path),'WORLDCORE_DB':str(tmp_path/'must_not_exist'/'worker.db')}
    result=subprocess.run([sys.executable,'-B','-c','from worldcore.bridge import worker_main;worker_main()','--version'],capture_output=True,env=env,timeout=4)
    assert result.returncode==0,result.stderr
    assert not (tmp_path/'must_not_exist').exists()


def test_bound_worker_cannot_enable_real_actions_from_ambient_flag(tmp_path):
    env={**environment(tmp_path),'WORLDCORE_HOST_REAL_ACTIONS':'1'}
    result=subprocess.run([sys.executable,'-B','-c','from worldcore.bridge import worker_main;worker_main()'],
        input=b'{"op":"action_execute_approved","request_id":"fake","action":"write_note","args":{},"_req":"blocked"}\n',
        capture_output=True,env=env,timeout=4)
    response=json.loads(result.stdout)
    assert response['ok'] is False and 'does not execute' in response['error']
