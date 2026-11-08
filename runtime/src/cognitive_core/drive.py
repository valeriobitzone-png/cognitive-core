"""Local Intelligence Feed and Opportunity Pool; no model or network calls.

Priority is a documented lexical heuristic, not confidence or source truth.
The host supplies project context and capacity; external text grants no powers.
"""
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .vault import uid


def instant(value=None):
    if value is not None and not isinstance(value,str):raise ValueError('timestamp must be ISO8601 text')
    dt=datetime.now(timezone.utc) if value is None else datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None or dt.utcoffset() is None:raise ValueError('timezone required')
    return dt.astimezone(timezone.utc).isoformat(timespec='microseconds')


def text(value,name,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit or '\x00' in value:
        raise ValueError('invalid '+name)
    return value.strip()


def unit(value):
    if type(value) not in (int,float) or not math.isfinite(value) or not 0<=value<=1:
        raise ValueError('expected finite value in 0..1')
    return float(value)


def tokens(value):
    return re.findall(r'\w+',value.casefold())


class CognitiveDrive:
    SOURCES={'web','github','paper','market','news','desktop','mobile','conversation','forecast','manual'}

    def __init__(self,core):
        self.core=core
        self.v=core.vault
        schema='''
            CREATE TABLE IF NOT EXISTS drive_projects(
                namespace TEXT NOT NULL,id TEXT NOT NULL,title TEXT NOT NULL,
                keywords TEXT NOT NULL,importance REAL NOT NULL,PRIMARY KEY(namespace,id));
            CREATE TABLE IF NOT EXISTS drive_stimuli(
                id TEXT PRIMARY KEY,namespace TEXT NOT NULL,fingerprint TEXT NOT NULL,
                title TEXT NOT NULL,summary TEXT NOT NULL,occurred_at TEXT NOT NULL,
                received_at TEXT NOT NULL,assessment TEXT NOT NULL,UNIQUE(namespace,fingerprint));
            CREATE TABLE IF NOT EXISTS drive_origins(
                namespace TEXT NOT NULL,stimulus_id TEXT NOT NULL,source_kind TEXT NOT NULL,
                source_ref TEXT NOT NULL,received_at TEXT NOT NULL,
                UNIQUE(namespace,stimulus_id,source_kind,source_ref));
            CREATE TABLE IF NOT EXISTS drive_opportunities(
                id TEXT PRIMARY KEY,namespace TEXT NOT NULL,stimulus_id TEXT NOT NULL,
                project_id TEXT NOT NULL,hypothesis TEXT NOT NULL,priority REAL NOT NULL,
                created_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open',
                topic_id TEXT,job_id TEXT,whatif_run_id TEXT,UNIQUE(namespace,stimulus_id));
            CREATE TABLE IF NOT EXISTS drive_decisions(
                id TEXT PRIMARY KEY,namespace TEXT NOT NULL,opportunity_id TEXT NOT NULL,
                status TEXT NOT NULL,reason TEXT NOT NULL,at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS drive_outcomes(
                namespace TEXT NOT NULL,opportunity_id TEXT NOT NULL,useful INTEGER NOT NULL,
                evidence_ref TEXT NOT NULL,at TEXT NOT NULL,source TEXT NOT NULL,
                PRIMARY KEY(namespace,opportunity_id));
            CREATE TABLE IF NOT EXISTS drive_simulations(
                namespace TEXT NOT NULL,opportunity_id TEXT NOT NULL,run_id TEXT NOT NULL,
                at TEXT NOT NULL,PRIMARY KEY(namespace,run_id));
            CREATE INDEX IF NOT EXISTS drive_window ON drive_stimuli(namespace,occurred_at,received_at);
            CREATE INDEX IF NOT EXISTS drive_decision_history ON drive_decisions(namespace,opportunity_id,at);
        '''
        with self.v.transaction():
            for statement in schema.split(';'):
                if statement.strip():self.v.db.execute(statement)

    def upsert_project(self,project_id,title,keywords,importance=.5):
        """Trusted host context, not fields asserted by an external source."""
        project_id=text(project_id,'project id',128);title=text(title,'title',300)
        if not isinstance(keywords,list) or not 1<=len(keywords)<=30:raise ValueError('need 1..30 keywords')
        words=sorted({w for k in keywords for w in tokens(text(k,'keyword',100)) if len(w)>=3})
        if not words:raise ValueError('need meaningful project keywords')
        with self.v.transaction():
            self.v.db.execute('''INSERT INTO drive_projects VALUES(?,?,?,?,?)
                ON CONFLICT(namespace,id) DO UPDATE SET title=excluded.title,
                keywords=excluded.keywords,importance=excluded.importance''',
                (self.v.ns,project_id,title,json.dumps(words),unit(importance)))
        return {'project_id':project_id,'keywords':words}

    def ingest(self,event,*,now=None):
        if not isinstance(event,dict) or set(event)!={'source_kind','source_ref','occurred_at','title','summary'}:
            raise ValueError('stimulus requires source_kind/source_ref/occurred_at/title/summary only')
        source=event['source_kind']
        if not isinstance(source,str) or source not in self.SOURCES:raise ValueError('unknown source kind')
        title=text(event['title'],'title',300);summary=text(event['summary'],'summary',12000)
        reference=text(event['source_ref'],'source reference',2000)
        received=instant(now);occurred=instant(event['occurred_at'])
        if occurred>received:raise ValueError('future observation denied')
        normalized=' '.join(tokens(title))+'\n'+' '.join(tokens(summary))
        fingerprint=hashlib.sha256(normalized.encode()).hexdigest()
        with self.v.transaction():
            old=self.v.db.execute('SELECT * FROM drive_stimuli WHERE namespace=? AND fingerprint=?',
                                  (self.v.ns,fingerprint)).fetchone()
            if old:
                self.v.db.execute('INSERT OR IGNORE INTO drive_origins VALUES(?,?,?,?,?)',
                                  (self.v.ns,old['id'],source,reference,received))
                return {'stimulus_id':old['id'],'duplicate':True,'decision':'IGNORE',
                        'reason':'already assessed; dismissed opportunities stay dismissed',
                        'model_calls':0,'web_requests':0}
            words=set(tokens(title+' '+summary));matches=[]
            for project in self.v.db.execute('SELECT * FROM drive_projects WHERE namespace=?',(self.v.ns,)):
                keywords=json.loads(project['keywords']);matched=sorted(words.intersection(keywords))
                if matched:
                    relevance=min(1,len(matched)/min(3,len(keywords)))
                    priority=round(relevance*.5*project['importance'],6)
                    matches.append({'project_id':project['id'],'project_title':project['title'],
                                    'matched_keywords':matched,'priority':priority})
            matches.sort(key=lambda m:(-m['priority'],m['project_id']))
            memories=self.core.memory_search((title+' '+summary)[:350],limit=5) if matches else []
            assessment={'context_matches':matches,'memory_refs':[m['id'] for m in memories],
                        'novelty':1,'source_prior':.5,'source_prior_calibrated':False,
                        'confidence':None,'ranking_basis':'lexical_relevance * source_prior * project_importance',
                        'source_content':'untrusted'}
            ident=uid('stimulus')
            self.v.db.execute('INSERT INTO drive_stimuli VALUES(?,?,?,?,?,?,?,?)',
                              (ident,self.v.ns,fingerprint,title,summary,occurred,received,json.dumps(assessment)))
            self.v.db.execute('INSERT INTO drive_origins VALUES(?,?,?,?,?)',
                              (self.v.ns,ident,source,reference,received))
            opportunity=None
            if matches:
                best=matches[0];opportunity=uid('opportunity')
                hypothesis=f"Evaluate whether {title} is useful for {best['project_title']}"
                self.v.db.execute('''INSERT INTO drive_opportunities(
                    id,namespace,stimulus_id,project_id,hypothesis,priority,created_at)
                    VALUES(?,?,?,?,?,?,?)''',(opportunity,self.v.ns,ident,best['project_id'],hypothesis,best['priority'],received))
                self._decision(opportunity,'open','context matched; usefulness unverified',received)
            decision='SUGGEST' if matches and matches[0]['priority']>=.1 else 'REMEMBER' if matches else 'IGNORE'
            self.v.audit('intelligence_feed',{'stimulus_id':ident,'opportunity_id':opportunity,'decision':decision})
        return {'stimulus_id':ident,'opportunity_id':opportunity,'duplicate':False,'decision':decision,
                'assessment':assessment,'model_calls':0,'web_requests':0,'action_executed':False}

    def _decision(self,ident,status,reason,at):
        self.v.db.execute('INSERT INTO drive_decisions VALUES(?,?,?,?,?,?)',
                          (uid('decision'),self.v.ns,ident,status,reason,at))

    def _get(self,ident):
        row=self.v.db.execute('SELECT * FROM drive_opportunities WHERE namespace=? AND id=?',
                              (self.v.ns,ident)).fetchone()
        if row is None:raise KeyError('opportunity not found in scope')
        return dict(row)

    def opportunities(self,limit=20):
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('limit must be 1..100')
        return [dict(r) for r in self.v.db.execute('''SELECT * FROM drive_opportunities
            WHERE namespace=? ORDER BY priority DESC,created_at,id LIMIT ?''',(self.v.ns,limit))]

    def compare(self,ident,scenarios,*,objectives):
        opportunity=self._get(ident)
        result=self.core.compare_futures(opportunity['hypothesis'],scenarios,objectives=objectives)
        with self.v.transaction():
            self.v.db.execute('UPDATE drive_opportunities SET whatif_run_id=? WHERE namespace=? AND id=?',
                              (result['run_id'],self.v.ns,ident))
            self.v.db.execute('INSERT INTO drive_simulations VALUES(?,?,?,?)',
                              (self.v.ns,ident,result['run_id'],instant()))
            self.v.link(ident,'whatif',result['run_id'],'explicit_host_assumptions')
        return result

    def review(self,ident,status,reason,*,now=None):
        if status not in ('dismissed','suggested'):raise ValueError('review status must be dismissed or suggested')
        reason=text(reason,'reason',500);at=instant(now)
        with self.v.transaction():
            item=self._get(ident)
            if at<item['created_at']:raise ValueError('review precedes creation')
            if item['status']=='dismissed' and status!='dismissed':raise PermissionError('dismissal cannot be implicitly reversed')
            self.v.db.execute('UPDATE drive_opportunities SET status=? WHERE namespace=? AND id=?',(status,self.v.ns,ident))
            self._decision(ident,status,reason,at)
            if status=='dismissed' and item['topic_id']:
                self.v.set_topic_status(item['topic_id'],'discarded')
        return {'opportunity_id':ident,'status':status,'action_executed':False}

    def prepare(self,available_capacity=0,limit=1):
        capacity=unit(available_capacity)
        if type(limit) is not int or not 1<=limit<=10:raise ValueError('limit must be 1..10')
        if capacity<.5:return {'status':'wait','reason':'host capacity below threshold','jobs':[]}
        prepared=[]
        with self.v.transaction():
            rows=self.v.db.execute('''SELECT o.*,s.title FROM drive_opportunities o
                JOIN drive_stimuli s ON s.id=o.stimulus_id AND s.namespace=o.namespace
                WHERE o.namespace=? AND o.status IN ('open','suggested') AND o.priority>=.1
                AND EXISTS(SELECT 1 FROM drive_origins r WHERE r.namespace=o.namespace
                           AND r.stimulus_id=o.stimulus_id AND r.source_ref LIKE 'https://%')
                ORDER BY o.priority DESC,o.created_at,o.id LIMIT ?''',(self.v.ns,limit)).fetchall()
            for row in rows:
                origins=self.v.db.execute('SELECT source_ref FROM drive_origins WHERE namespace=? AND stimulus_id=? ORDER BY received_at,source_ref',
                                          (self.v.ns,row['stimulus_id'])).fetchall()
                urls=[r['source_ref'] for r in origins if urlsplit(r['source_ref']).scheme=='https'][:3]
                if not urls:continue  # No installed read adapter for local/mobile source references.
                topic=self.v.topic(row['title'],row['hypothesis'],importance=row['priority'],trigger='intelligence_feed')
                if self.v.get_topic(topic)['status']!='open':continue
                if not self.v.reserve_budget('initiatives_prepared',self.core.s.max_jobs_per_day):break
                job=self.v.job(topic,plan={'question':row['hypothesis'],'seed_urls':urls,'require_review':True})
                self.v.db.execute("UPDATE drive_opportunities SET status='prepared',topic_id=?,job_id=? WHERE namespace=? AND id=?",
                                  (topic,job,self.v.ns,row['id']))
                self._decision(row['id'],'prepared','read-only source job queued; network governor still required',instant())
                prepared.append({'opportunity_id':row['id'],'job_id':job})
        return {'status':'prepared' if prepared else 'wait','jobs':prepared,'action_executed':False,'web_requests':0}

    def briefing(self,*,as_of=None,hours=24,limit=5):
        as_of=instant(as_of)
        if type(hours) is not int or not 1<=hours<=168:raise ValueError('hours must be 1..168')
        if type(limit) is not int or not 1<=limit<=20:raise ValueError('limit must be 1..20')
        since=(datetime.fromisoformat(as_of)-timedelta(hours=hours)).isoformat(timespec='microseconds')
        rows=self.v.db.execute('''SELECT o.id,o.project_id,o.hypothesis,o.priority,
            (SELECT w.run_id FROM drive_simulations w WHERE w.namespace=o.namespace AND w.opportunity_id=o.id
             AND w.at<=? ORDER BY w.at DESC,w.rowid DESC LIMIT 1) whatif_run_id,
            s.id stimulus_id,s.title,s.occurred_at,s.received_at,s.assessment,
            (SELECT d.status FROM drive_decisions d WHERE d.namespace=o.namespace AND d.opportunity_id=o.id
             AND d.at<=? ORDER BY d.at DESC,d.rowid DESC LIMIT 1) status_at_time
            FROM drive_opportunities o JOIN drive_stimuli s ON s.id=o.stimulus_id AND s.namespace=o.namespace
            WHERE o.namespace=? AND o.created_at<=? AND s.received_at<=? AND s.occurred_at<=? AND s.occurred_at>=?
            ORDER BY o.priority DESC,o.created_at,o.id''',(as_of,as_of,self.v.ns,as_of,as_of,as_of,since)).fetchall()
        items=[]
        for row in rows:
            if row['status_at_time']=='dismissed' or row['priority']<.1:continue
            item=dict(row);item['assessment']=json.loads(item['assessment']);item['confidence']=None
            item['sources']=[dict(r) for r in self.v.db.execute('''SELECT source_kind,source_ref FROM drive_origins
                WHERE namespace=? AND stimulus_id=? AND received_at<=? ORDER BY source_kind,source_ref''',
                (self.v.ns,row['stimulus_id'],as_of))]
            items.append(item)
            if len(items)==limit:break
        return {'as_of':as_of,'window_hours':hours,'items':items,'action_executed':False,
                'ranking_basis':'heuristic_priority_not_probability','model_calls':0}

    def record_outcome(self,ident,useful,evidence_ref):
        if type(useful) is not bool:raise ValueError('useful must be boolean')
        evidence_ref=text(evidence_ref,'outcome evidence',2000)
        with self.v.transaction():
            item=self._get(ident)
            self.v.db.execute('INSERT INTO drive_outcomes VALUES(?,?,?,?,?,?)',
                              (self.v.ns,ident,int(useful),evidence_ref,instant(),'operator_reported'))
            if item['topic_id']:
                self.v.experience(item['topic_id'],'opportunity_review',item['hypothesis'],str(useful),evidence_ref)
        return {'recorded':True,'source':'operator_reported','automatically_verified':False,'model_updated':False}
