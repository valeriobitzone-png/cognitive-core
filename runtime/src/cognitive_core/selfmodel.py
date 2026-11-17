"""Functional, evidence-based self-model. Configuration is not consciousness.

Forecasts precede outcomes; only this actor's observed executions update estimates.
History lives in a bounded sidecar, never in original archive databases or weights.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

from worldcore.calibrated import wilson


def encode(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)


def runtime_snapshot(settings,archive):
    model=Path(settings.local_model_gguf)
    binary=shutil.which(settings.local_model_binary)
    model_ready=model.is_file() and model.suffix.lower()=='.gguf' and model.stat().st_size<=settings.max_model_file_bytes
    archive_ready=(Path(archive)/'vault.sqlite3').is_file() and os.access(Path(archive)/'vault.sqlite3',os.R_OK)
    return {'model_configured':settings.enable_local_model,'model_file_ready':model_ready,
            'binary_ready':bool(binary),'archive_readable':archive_ready,
            'local_inference_available':bool(settings.enable_local_model and model_ready and binary and archive_ready),
            'source':'filesystem_and_host_configuration','epistemic':'OBSERVED',
            'warning':'Prerequisites observed, not proof of inference or semantic accuracy.'}


class SelfModel:
    def __init__(self,folder,owner='local',namespace='default'):
        folder=Path(folder);folder.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.path=folder/'self-model.sqlite3';self.scope=encode([owner,namespace])
        self.db=sqlite3.connect(self.path,timeout=1,isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.execute('''CREATE TABLE IF NOT EXISTS self_trials(
            scope TEXT NOT NULL,id TEXT NOT NULL,request_key TEXT NOT NULL,capability TEXT NOT NULL,
            context TEXT NOT NULL,runtime_key TEXT NOT NULL,epistemic TEXT NOT NULL,
            before_at REAL NOT NULL,forecast TEXT NOT NULL,outcome TEXT,
            PRIMARY KEY(scope,id))''')
        if os.name=='posix':self.path.chmod(0o600)

    def close(self):
        self.db.close()

    def forecast(self,capability,context,snapshot,runtime,*,request_key='',epistemic='OBSERVED'):
        if self.path.stat().st_size>1_900_000:
            raise ValueError('self-model disk budget exhausted')
        if not isinstance(snapshot,dict) or type(snapshot.get('local_inference_available')) is not bool:
            raise ValueError('runtime availability must be explicit')
        if epistemic not in ('OBSERVED','SIMULATED'):raise ValueError('invalid evidence origin')
        for value in (capability,context,request_key):
            if not isinstance(value,str) or len(value)>160:raise ValueError('invalid forecast identifier')
        if len(encode(snapshot).encode())>4000 or len(encode(runtime).encode())>4000:
            raise ValueError('self-model state exceeds byte budget')
        runtime_key=hashlib.sha256(encode(runtime).encode()).hexdigest()
        records=self.db.execute('''SELECT outcome FROM self_trials WHERE scope=? AND capability=?
            AND context=? AND runtime_key=? AND epistemic=? AND outcome IS NOT NULL ORDER BY before_at DESC LIMIT 1000''',
            (self.scope,capability,context,runtime_key,epistemic)).fetchall()
        outcomes=[json.loads(r['outcome']) for r in records]
        outcomes=[r for r in outcomes if r['actor']=='self' and type(r['successful']) is bool]
        n=len(outcomes);successes=sum(r['successful'] for r in outcomes)
        available=snapshot['local_inference_available']
        estimate=(successes+1)/(n+2) if available else 0.0
        status='unavailable' if not available else 'insufficient_history' if n<5 else 'empirical_uncalibrated'
        ident=uuid.uuid4().hex
        prediction={'id':ident,'capability':capability,'context':context,'runtime_key':runtime_key,
            'epistemic':'INFERRED','evidence_origin':epistemic,'snapshot':snapshot,
            'admitted':available,'probability':estimate if n>=5 or not available else None,
            'estimate_for_scoring':estimate,'samples':n,'successes':successes,'interval_95':wilson(successes,n),
            'status':status,'calibrated':False,'target':'validated_local_inference_execution',
            'semantic_accuracy':'not_measured','question':None if available else 'Is local inference still available?'}
        self.db.execute('INSERT INTO self_trials VALUES(?,?,?,?,?,?,?,?,?,NULL)',
            (self.scope,ident,request_key,capability,context,runtime_key,epistemic,time.time(),encode(prediction)))
        return prediction

    def resolve(self,ident,successful,evidence_ref,*,actor='self'):
        if successful is not None and type(successful) is not bool:raise ValueError('outcome must be boolean or unattempted')
        if actor not in ('self','other'):raise ValueError('invalid actor')
        if not isinstance(evidence_ref,str) or not evidence_ref.strip() or len(evidence_ref)>500:
            raise ValueError('outcome requires a bounded evidence reference')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT forecast,outcome FROM self_trials WHERE scope=? AND id=?',(self.scope,ident)).fetchone()
            if not row:raise KeyError(ident)
            if row['outcome'] is not None:
                old=json.loads(row['outcome'])
                if (old['successful'],old['evidence_ref'],old['actor'])!=(successful,evidence_ref,actor):
                    raise ValueError('outcome immutable; append a new episode for a correction')
                self.db.execute('COMMIT');return old
            prediction=json.loads(row['forecast'])
            result={'successful':successful,'actor':actor,'evidence_ref':evidence_ref,'observed_at':time.time(),
                    'epistemic':prediction['evidence_origin'],'semantic_truth_verified':False,
                    'brier':None if successful is None or actor!='self' else
                        (prediction['estimate_for_scoring']-int(successful))**2}
            self.db.execute('UPDATE self_trials SET outcome=? WHERE scope=? AND id=?',(encode(result),self.scope,ident))
            self.db.execute('COMMIT');return result
        except BaseException:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise

    def episodes(self):
        return [{'id':r['id'],'request_key':r['request_key'],'before_at':r['before_at'],
                 'forecast':json.loads(r['forecast']),'outcome':json.loads(r['outcome']) if r['outcome'] else None}
                for r in self.db.execute('SELECT * FROM self_trials WHERE scope=? ORDER BY before_at,id',(self.scope,))]

    def export(self,target):
        target=Path(target)
        with target.open('x',encoding='utf-8') as output:
            json.dump({'format':'cognitive-self-v1','scope':json.loads(self.scope),'episodes':self.episodes()},
                      output,ensure_ascii=False,indent=2,allow_nan=False)
        target.chmod(0o600)
        return str(target)
