"""Read an archive through stable temporary copies; persist only a sidecar.

Reuse the core's unified retrieval on disposable copies, never migrate originals.
The model advises or vetoes local research; it cannot raise execution authority.
"""
from dataclasses import replace
import os
import subprocess
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import time

from .selfmodel import SelfModel,runtime_snapshot
from .ondemand import infer


def archive_context(core,archive,query):
    from .engine import CognitiveCore
    archive=Path(archive).resolve(strict=True)
    began=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='cognitive-archive-read-') as folder:
        folder=Path(folder)
        observed={};total=0
        for name in ('vault.sqlite3','worldcore.sqlite3'):
            main=archive/name
            if not main.is_file():
                if name=='vault.sqlite3':raise FileNotFoundError('archive has no Vault')
                continue
            for suffix in ('','-wal'):
                source=archive/(name+suffix)
                if not source.exists():
                    observed[source]=None;continue
                before=source.stat()
                observed[source]=(before.st_ino,before.st_size,before.st_mtime_ns)
                with source.open('rb') as reader,(folder/source.name).open('xb') as writer:
                    while True:
                        block=reader.read(65536)
                        if not block:break
                        total+=len(block)
                        if total>32_000_000 or time.monotonic()-began>2:
                            raise TimeoutError('archive copy exceeds read budget')
                        writer.write(block)
        # Detect concurrent checkpoints/writes, including WAL creation/removal.
        # Never connect SQLite to originals: even mode=ro can create shm/WAL files.
        for source,before in observed.items():
            current=source.stat() if source.exists() else None
            after=(current.st_ino,current.st_size,current.st_mtime_ns) if current else None
            if before!=after:raise ValueError('archive changed during read; retry later')
        copy=CognitiveCore(replace(core.s,home=folder,enable_local_model=False))
        try:
            hits=[hit for hit in copy.memory_search(query[:350],limit=6) if hit.get('kind')!='cognitive_note'][:3]
            return [{**hit,'excerpt':hit.get('excerpt','')[:300],
                     'title':hit.get('title','')[:100]} for hit in hits]
        finally:copy.close()


def assess(core,event,archive,*,timeout_seconds=None):
    if not isinstance(event,dict):raise TypeError('event must be an object')
    if len(json.dumps(event,allow_nan=False).encode())>2000:raise ValueError('decision event exceeds byte budget')
    first=core.decision.reflex.classify(event)
    base={'decision':first.asdict(),'model_calls':0,'source_facts_modified':0,'action_executed':False}
    if first.action in ('WAIT','REQUEST_APPROVAL'):
        return {**base,'status':'reflex'}
    if not core.s.enable_local_model or not core.s.local_model_gguf:
        return {**base,'status':'disabled'}
    archive=Path(archive).resolve(strict=True)
    # Separate the operational sidecar from the original archive directory.
    state=Path(core.s.local_decision_state or core.s.home/'local-decision').resolve()
    if state==archive or state.is_relative_to(archive):
        raise ValueError('decision state must be outside the read-only archive')
    effective=core.s if timeout_seconds is None else replace(core.s,
        model_timeout_seconds=min(core.s.model_timeout_seconds,timeout_seconds))
    snapshot=runtime_snapshot(core.s,archive)
    if not snapshot['local_inference_available']:
        observer=SelfModel(state,core.s.owner,core.s.namespace)
        try:
            forecast=observer.forecast('local_inference','archive_relevance',snapshot,
                {'model':core.s.local_model_gguf,'binary':core.s.local_model_binary})
            observer.resolve(forecast['id'],None,'not_attempted:runtime_prerequisites_unavailable')
        finally:observer.close()
        return {**base,'status':'capability_unavailable','strategy':'deterministic_local_fallback',
                'self_forecast':forecast}
    model=Path(core.s.local_model_gguf).resolve(strict=True)
    identity={'file':str(model),'bytes':model.stat().st_size,'mtime_ns':model.stat().st_mtime_ns,
              'binary':core.s.local_model_binary,'tokens':core.s.max_model_tokens,'timeout':effective.model_timeout_seconds,'policy':'local-advice-v4'}
    query=' '.join(str(event.get(key,'')) for key in ('question','title','text'))
    context=archive_context(core,archive,query)
    base['sources']=context
    if not context:return {**base,'status':'no_local_evidence'}
    raw=json.dumps({'owner':core.s.owner,'namespace':core.s.namespace,'archive':str(archive),
        'event':event,'context':context,'model':identity},sort_keys=True,ensure_ascii=False)
    key=hashlib.sha256(raw.encode()).hexdigest()
    # One bounded sidecar, independent of the Vault schema and export format.
    state.mkdir(parents=True,exist_ok=True,mode=0o700)
    path=state/'decisions.sqlite3'
    if path.exists() and path.stat().st_size>3_900_000:
        return {**base,'status':'sidecar_disk_budget'}
    db=sqlite3.connect(path,timeout=1,isolation_level=None)
    db.row_factory=sqlite3.Row
    try:
        db.executescript('''
          CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,result TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS budget(scope TEXT,day TEXT,calls INTEGER,PRIMARY KEY(scope,day));
          CREATE TABLE IF NOT EXISTS lease(id INTEGER PRIMARY KEY,until REAL);
          INSERT OR IGNORE INTO lease VALUES(1,0);
        ''')
        if os.name=='posix':path.chmod(0o600)
        db.execute('BEGIN IMMEDIATE')
        cached=db.execute('SELECT result FROM cache WHERE key=?',(key,)).fetchone()
        if cached:
            db.execute('COMMIT')
            return {**json.loads(cached['result']),'status':'cached','model_calls':0}
        now=time.time();scope=json.dumps([core.s.owner,core.s.namespace]);day=time.strftime('%Y-%m-%d',time.gmtime())
        if db.execute('SELECT until FROM lease WHERE id=1').fetchone()[0]>now:
            db.execute('COMMIT');return {**base,'status':'model_busy'}
        db.execute('INSERT OR IGNORE INTO budget VALUES(?,?,0)',(scope,day))
        reserved=db.execute('UPDATE budget SET calls=calls+1 WHERE scope=? AND day=? AND calls<?',
            (scope,day,core.s.max_model_calls_per_day)).rowcount
        if not reserved:
            db.execute('COMMIT');return {**base,'status':'daily_model_budget'}
        db.execute('UPDATE lease SET until=? WHERE id=1',(now+effective.model_timeout_seconds+5,))
        db.execute('COMMIT')  # Persist admission BEFORE loading the model, even on crash.
        observer=SelfModel(state,core.s.owner,core.s.namespace)
        try:
            forecast=observer.forecast('local_inference','archive_relevance',snapshot,identity,request_key=key)
        except (ValueError,sqlite3.Error):
            observer.close()
            db.execute('UPDATE lease SET until=0 WHERE id=1')
            return {**base,'status':'self_model_budget_or_storage','strategy':'deterministic_local_fallback'}
        try:
            decision=infer(effective,event,context)
            decision.priority=first.priority  # Preserve deterministic priority; model emits only a class.
            if first.action=='STORE_ONLY' and decision.action=='PREPARE_SILENTLY':
                decision.action='STORE_ONLY';decision.rationale='research escalation denied by reflex'
            result={**base,'decision':decision.asdict(),'status':'classified','model_calls':1,
                    'model_identity':identity,'epistemic':'INFERRED'}
        except (ValueError,OSError,TimeoutError,subprocess.TimeoutExpired) as exc:
            result={**base,'status':'fallback','model_calls':1,'error':type(exc).__name__}
        except BaseException:
            db.execute('UPDATE lease SET until=0 WHERE id=1')
            raise
        finally:observer.close()
        observer=SelfModel(state,core.s.owner,core.s.namespace)
        try:
            outcome=observer.resolve(forecast['id'],result['status']=='classified',
                'schema_validated_process_result:'+hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest())
        finally:observer.close()
        result.update({'self_forecast':forecast,'self_outcome':outcome,'strategy':'local_model_advice'})
        db.execute('BEGIN IMMEDIATE')
        db.execute('INSERT OR IGNORE INTO cache VALUES(?,?)',(key,json.dumps(result,ensure_ascii=False)))
        db.execute('UPDATE lease SET until=0 WHERE id=1')
        db.execute('COMMIT')
        return result
    finally:db.close()
