"""Scoped, source-attributed assertions with append-only validity revisions.

World time and knowledge time are distinct. New assertions never rewrite old
validity intervals; deterministic revision order survives export and restore.
No memory row constitutes verified truth or grants execution authority.
"""
import hashlib
import json
import sqlite3
from functools import wraps
from time import monotonic
from .retrieval import BM25,freshness,RANK
from .vault import uid,ts
from .experimental import check_storage

SCHEMA='''
CREATE TABLE IF NOT EXISTS mem_facts(
 namespace TEXT NOT NULL,id TEXT NOT NULL,scope TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,
 source TEXT NOT NULL,agent TEXT NOT NULL,valid_from INTEGER NOT NULL,valid_to INTEGER,
 recorded INTEGER NOT NULL,retracted INTEGER,PRIMARY KEY(namespace,id));
CREATE INDEX IF NOT EXISTS mem_facts_key ON mem_facts(namespace,scope,key);
CREATE TABLE IF NOT EXISTS mem_suppressed(namespace TEXT NOT NULL,scope TEXT NOT NULL,key TEXT NOT NULL,since INTEGER NOT NULL,PRIMARY KEY(namespace,scope,key));
CREATE TABLE IF NOT EXISTS mem_order(namespace TEXT NOT NULL,id TEXT NOT NULL,ordinal INTEGER NOT NULL,
 PRIMARY KEY(namespace,id),UNIQUE(namespace,ordinal));
'''
KINDS=('fact','rule','handoff')
MAX_RECORDS=10000
MAX_CANDIDATES=128
MAX_READ_BYTES=2_000_000


def initialize(db):
    for statement in SCHEMA.split(';'):
        if statement.strip():db.execute(statement)
    # Add ordering metadata only; existing assertions and their timestamps remain intact.
    missing=db.execute('''SELECT m.namespace,m.id FROM mem_facts m LEFT JOIN mem_order o
        ON o.namespace=m.namespace AND o.id=m.id WHERE o.id IS NULL ORDER BY m.rowid''')
    for row in missing:
        db.execute('INSERT INTO mem_order SELECT ?,?,COALESCE(MAX(ordinal),0)+1 FROM mem_order WHERE namespace=?',
                   (row[0],row[1],row[0]))


def identifier(value,label,maximum=256):
    if not isinstance(value,str) or not value.strip() or '\x00' in value or len(value)>maximum:
        raise ValueError('invalid '+label)
    return value


def bounded_read(method):
    """Include SQLite execution in the elapsed-time budget, not just row decoding."""
    @wraps(method)
    def read(self,*args,**kwargs):
        deadline=monotonic()+min(2,self.core.s.max_cycle_seconds)
        self.v.db.set_progress_handler(lambda: int(monotonic()>deadline),1000)
        try:
            result=method(self,*args,**kwargs)
            if monotonic()>deadline:raise ValueError('memory read time budget exceeded')
            return result
        except sqlite3.OperationalError as exc:
            if 'interrupted' in str(exc):raise ValueError('memory read time budget exceeded') from exc
            raise
        finally:self.v.db.set_progress_handler(None,0)
    return read


class Memory:
    def __init__(self,core):
        self.core=core;self.v=core.vault
        if not getattr(self.v,"_memory_casefold",False):
            self.v.db.create_function("memory_casefold",1,lambda value:value.casefold() if isinstance(value,str) else "",deterministic=True)
            self.v._memory_casefold=True

    def remember(self,scope,key,value,source,agent='user',valid_from=None,kind='fact'):
        scope=identifier(scope,'scope');key=identifier(key,'key');source=identifier(source,'source',2048);agent=identifier(agent,'agent',128)
        if kind not in KINDS:raise ValueError('unknown kind')
        if valid_from is not None and type(valid_from) is not int:raise ValueError('valid_from must be an integer')
        k=kind+':'+key if kind!='fact' else key
        blob=json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)
        size=len(blob.encode())
        if size>self.core.s.max_text_bytes:raise ValueError('memory value exceeds text budget')
        now=ts();vf=now if valid_from is None else valid_from
        with self.v.transaction():
            check_storage(self.core,size*3+16_384)
            count=self.v.db.execute('SELECT count(*) FROM mem_facts WHERE namespace=?',(self.v.ns,)).fetchone()[0]
            if count>=MAX_RECORDS:raise ValueError('memory record admission limit')
            ident=uid('mem')
            self.v.db.execute('INSERT INTO mem_facts VALUES(?,?,?,?,?,?,?,?,NULL,?,NULL)',
                              (self.v.ns,ident,scope,k,blob,source,agent,vf,now))
            self.v.db.execute('INSERT INTO mem_order SELECT ?,?,COALESCE(MAX(ordinal),0)+1 FROM mem_order WHERE namespace=?',
                              (self.v.ns,ident,self.v.ns))
            self.v.audit('memory_remember',{'id':ident,'scope':scope,'key':k,'agent':agent})
        return ident

    def _where(self,valid_at=None,known_at=None,*,visible=False,history=False,include_hypotheses=True,scope=None,key=None):
        va=ts() if valid_at is None else valid_at;ka=ts()+1 if known_at is None else known_at
        if type(va) is not int or type(ka) is not int:raise ValueError('memory clocks must be integer timestamps')
        where=['m.namespace=?','m.recorded<=?','(m.retracted IS NULL OR m.retracted>?)'];args=[self.v.ns,ka,ka]
        if not history:
            where.extend(['m.valid_from<=?', '''(m.valid_to IS NULL OR m.valid_to>? OR EXISTS(
                SELECT 1 FROM mem_facts legacy WHERE legacy.namespace=m.namespace AND legacy.scope=m.scope AND legacy.key=m.key
                AND legacy.valid_from=m.valid_to AND legacy.recorded>?))''',
                '''NOT EXISTS(SELECT 1 FROM mem_facts n JOIN mem_order no ON no.namespace=n.namespace AND no.id=n.id
                WHERE n.namespace=m.namespace AND n.scope=m.scope AND n.key=m.key AND n.recorded<=?
                AND (n.retracted IS NULL OR n.retracted>?) AND n.valid_from<=?
                AND (n.valid_from>m.valid_from OR (n.valid_from=m.valid_from AND
                    (n.recorded>m.recorded OR (n.recorded=m.recorded AND no.ordinal>o.ordinal)))))'''])
            args.extend([va,va,ka,ka,ka,va])
        if visible:where.append('NOT EXISTS(SELECT 1 FROM mem_suppressed s WHERE s.namespace=m.namespace AND s.scope=m.scope AND s.key=m.key)')
        if not include_hypotheses:where.extend(["m.key NOT LIKE 'hypothesis:%'","m.source NOT LIKE 'dream:%'","m.agent!='dream'"])
        if scope is not None:where.append('m.scope=?');args.append(identifier(scope,'scope'))
        if key is not None:where.append('m.key=?');args.append(identifier(key,'key',300))
        return ' AND '.join(where),args

    def _query(self,*,limit=MAX_CANDIDATES,**filters):
        where,args=self._where(**filters)
        return self.v.db.execute('SELECT m.*,o.ordinal FROM mem_facts m JOIN mem_order o ON o.namespace=m.namespace AND o.id=m.id WHERE '+where+' ORDER BY m.valid_from DESC,m.recorded DESC,o.ordinal DESC LIMIT ?',(*args,limit))

    def _row(self,r,known_at=None):
        ka=ts()+1 if known_at is None else known_at
        end=r['valid_to']
        if end is not None and self.v.db.execute('SELECT 1 FROM mem_facts WHERE namespace=? AND scope=? AND key=? AND valid_from=?',
                (self.v.ns,r['scope'],r['key'],end)).fetchone():end=None
        successor=self.v.db.execute('''SELECT MIN(n.valid_from) FROM mem_facts n JOIN mem_order no ON no.namespace=n.namespace AND no.id=n.id
            WHERE n.namespace=? AND n.scope=? AND n.key=? AND n.recorded<=? AND (n.retracted IS NULL OR n.retracted>?)
            AND (n.valid_from>? OR (n.valid_from=? AND (n.recorded>? OR (n.recorded=? AND no.ordinal>?))))''',
            (self.v.ns,r['scope'],r['key'],ka,ka,r['valid_from'],r['valid_from'],r['recorded'],r['recorded'],r['ordinal'])).fetchone()[0]
        if successor is not None:end=successor if end is None else min(end,successor)
        return {'id':r['id'],'scope':r['scope'],'key':r['key'],'value':json.loads(r['value']),'text':r['value'],
                'source':r['source'],'agent':r['agent'],'valid_from':r['valid_from'],'valid_to':end,
                'recorded':r['recorded'],'retracted':r['retracted'],'revision':r['ordinal'],
                'source_sha256':hashlib.sha256(r['value'].encode()).hexdigest(),'epistemic':'INFERRED','verified':False}

    @bounded_read
    def recall(self,scope,key,valid_at=None,known_at=None):
        row=self._query(scope=scope,key=key,valid_at=valid_at,known_at=known_at,limit=1).fetchone()
        return self._row(row,known_at) if row else None

    @bounded_read
    def is_current(self,ident,*,include_hypotheses=False):
        where,args=self._where(visible=True,include_hypotheses=include_hypotheses)
        return bool(self.v.db.execute('SELECT 1 FROM mem_facts m JOIN mem_order o ON o.namespace=m.namespace AND o.id=m.id WHERE '+where+' AND m.id=?',(*args,ident)).fetchone())

    @bounded_read
    def history(self,scope,key):
        rows=self.v.db.execute('''SELECT m.*,o.ordinal FROM mem_facts m JOIN mem_order o ON o.namespace=m.namespace AND o.id=m.id
            WHERE m.namespace=? AND m.scope=? AND m.key=? ORDER BY o.ordinal LIMIT 1001''',
            (self.v.ns,identifier(scope,'scope'),identifier(key,'key',300)))
        return [self._row(r) for r in self._bounded(rows,1000)]

    def forget(self,scope,key):
        scope=identifier(scope,'scope');key=identifier(key,'key',300)
        with self.v.transaction():
            check_storage(self.core,16_384)
            count=self.v.db.execute('UPDATE mem_facts SET retracted=? WHERE namespace=? AND scope=? AND key=? AND retracted IS NULL',
                                    (ts(),self.v.ns,scope,key)).rowcount
            self.v.audit('memory_forget',{'scope':scope,'key':key,'rows':count})
        return count

    @bounded_read
    def scopes(self):
        where,args=self._where(visible=True)
        rows=self.v.db.execute('SELECT DISTINCT m.scope FROM mem_facts m JOIN mem_order o ON o.namespace=m.namespace AND o.id=m.id WHERE '+where+' ORDER BY m.scope LIMIT 1001',args).fetchall()
        if len(rows)>1000:raise ValueError('memory scope budget exceeded')
        return [r[0] for r in rows]

    @bounded_read
    def rules(self,scope):
        return [self._row(r) for r in self._bounded(self._query(scope=scope,visible=True),MAX_CANDIDATES) if r['key'].startswith('rule:')]

    def handoff(self,scope,from_agent,to_agent,summary,open_items=()):
        return self.remember(scope,from_agent+'->'+to_agent,{'from':from_agent,'to':to_agent,'summary':summary,'open':list(open_items)},'handoff:'+from_agent,agent=from_agent,kind='handoff')

    def grounded(self,query,limit=5):
        return self.search(query,limit)

    def suppress(self,scope,key):
        scope=identifier(scope,'scope');key=identifier(key,'key',300)
        with self.v.transaction():
            check_storage(self.core,16_384)
            self.v.db.execute('INSERT OR REPLACE INTO mem_suppressed VALUES(?,?,?,?)',(self.v.ns,scope,key,ts()))
            self.v.audit('memory_suppress',{'scope':scope,'key':key})

    def release(self,scope,key):
        scope=identifier(scope,'scope');key=identifier(key,'key',300)
        with self.v.transaction():
            check_storage(self.core,16_384)
            count=self.v.db.execute('DELETE FROM mem_suppressed WHERE namespace=? AND scope=? AND key=?',(self.v.ns,scope,key)).rowcount
            self.v.audit('memory_release',{'scope':scope,'key':key})
        return count

    def _bounded(self,rows,maximum):
        total=0;began=monotonic()
        for i,row in enumerate(rows):
            total+=len(row['value'].encode())
            if i>=maximum or total>MAX_READ_BYTES or monotonic()-began>min(2,self.core.s.max_cycle_seconds):
                raise ValueError('memory read budget exceeded; narrow the query')
            yield row

    @bounded_read
    def live(self,scope=None,limit=50,include_hypotheses=False):
        if type(limit) is not int or not 1<=limit<=MAX_RECORDS:raise ValueError('invalid memory limit')
        return [self._row(r) for r in self._bounded(self._query(scope=scope,visible=True,include_hypotheses=include_hypotheses,limit=limit),limit)]

    @bounded_read
    def search(self,query,limit=5,include_history=False,max_age_days=90,*,scope=None,include_hypotheses=False):
        if not isinstance(query,str) or len(query.encode())>2000:raise ValueError('memory query exceeds budget')
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('memory limit must be 1..100')
        if type(max_age_days) is not int or not 0<=max_age_days<=36500:raise ValueError('invalid freshness window')
        from .retrieval import tokenize
        terms=tokenize(query)[:12]
        if not terms:return []
        where,args=self._where(visible=True,history=include_history,scope=scope,include_hypotheses=include_hypotheses)
        matches=' OR '.join("(memory_casefold(m.key) LIKE ? ESCAPE '\\' OR memory_casefold(m.value) LIKE ? ESCAPE '\\')" for _ in terms)
        parameters=[]
        for term in terms:
            pattern='%'+term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%';parameters.extend([pattern,pattern])
        rows=list(self._bounded(self.v.db.execute('SELECT m.*,o.ordinal FROM mem_facts m JOIN mem_order o ON o.namespace=m.namespace AND o.id=m.id WHERE '+where+' AND ('+matches+') ORDER BY m.recorded DESC,o.ordinal DESC LIMIT ?',(*args,*parameters,MAX_CANDIDATES)),MAX_CANDIDATES))
        if not rows:return []
        index=BM25([r['key']+' '+r['value'] for r in rows]);out=[];now=ts()
        for score,i in index.rank(query,limit=len(rows)):
            record=self._row(rows[i]);record['label']=freshness(str(record['value']),record['valid_to'],record['recorded'],now,max_age_days)
            if record['key'].startswith('hypothesis:') or record['source'].startswith('dream:'):record['label']='UNVERIFIED'
            record['score']=round(score,4);out.append(record)
        out.sort(key=lambda d:(-RANK[d['label']],-d['score']))
        return out[:limit]
