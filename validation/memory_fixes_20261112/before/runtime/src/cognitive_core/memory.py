"""Shared bitemporal memory with provenance (clean-room, MIT-compatible).

Two clocks: valid time (when a fact is true in the world) and transaction time
(when the Core learned/retracted it). Nothing is overwritten: a new value closes the
old row's validity; forget() retracts with a transaction stamp and keeps the audit trail.
Memory never confers authority: rows are claims with a source, not verified truth.
"""
import json
from .retrieval import BM25,freshness,RANK
from .vault import uid, ts

SCHEMA='''
CREATE TABLE IF NOT EXISTS mem_facts(
 namespace TEXT NOT NULL,id TEXT NOT NULL,scope TEXT NOT NULL,key TEXT NOT NULL,value TEXT NOT NULL,
 source TEXT NOT NULL,agent TEXT NOT NULL,valid_from INTEGER NOT NULL,valid_to INTEGER,
 recorded INTEGER NOT NULL,retracted INTEGER,PRIMARY KEY(namespace,id));
CREATE INDEX IF NOT EXISTS mem_facts_key ON mem_facts(namespace,scope,key);
CREATE TABLE IF NOT EXISTS mem_suppressed(namespace TEXT NOT NULL,scope TEXT NOT NULL,key TEXT NOT NULL,since INTEGER NOT NULL,PRIMARY KEY(namespace,scope,key));
'''
KINDS=('fact','rule','handoff')


def initialize(db):
    for statement in SCHEMA.split(';'):
        if statement.strip():db.execute(statement)


class Memory:
    def __init__(self,core):
        self.core=core;self.v=core.vault
        initialize(self.v.db)

    def remember(self,scope,key,value,source,agent='user',valid_from=None,kind='fact'):
        if not source or not str(source).strip():raise ValueError('every memory needs a source')
        if kind not in KINDS:raise ValueError('unknown kind')
        k=kind+':'+key if kind!='fact' else key
        now=ts();vf=now if valid_from is None else int(valid_from)
        with self.v.transaction():
            self.v.db.execute('UPDATE mem_facts SET valid_to=? WHERE namespace=? AND scope=? AND key=? AND valid_to IS NULL AND retracted IS NULL AND valid_from<=?',
                              (vf,self.v.ns,scope,k,vf))
            i=uid('mem')
            self.v.db.execute('INSERT INTO mem_facts VALUES(?,?,?,?,?,?,?,?,NULL,?,NULL)',
                              (self.v.ns,i,scope,k,json.dumps(value,ensure_ascii=False),source,agent,vf,now))
            self.v.audit('memory_remember',{'id':i,'scope':scope,'key':k,'agent':agent})
        return i

    def _row(self,r):
        return {'id':r['id'],'scope':r['scope'],'key':r['key'],'value':json.loads(r['value']),'source':r['source'],
                'agent':r['agent'],'valid_from':r['valid_from'],'valid_to':r['valid_to'],'recorded':r['recorded'],'retracted':r['retracted']}

    def recall(self,scope,key,valid_at=None,known_at=None):
        """Value true at valid_at, as the Core knew it at known_at (defaults: now/now)."""
        va=ts() if valid_at is None else int(valid_at);ka=ts()+1 if known_at is None else int(known_at)
        rows=self.v.db.execute('SELECT * FROM mem_facts WHERE namespace=? AND scope=? AND key=? AND recorded<=? AND (retracted IS NULL OR retracted>?) '
                               'AND valid_from<=? ORDER BY valid_from DESC,recorded DESC',(self.v.ns,scope,key,ka,ka,va)).fetchall()
        for r in rows:
            if r['valid_to'] is None or r['valid_to']>va:return self._row(r)
        return None

    def history(self,scope,key):
        return [self._row(r) for r in self.v.db.execute('SELECT * FROM mem_facts WHERE namespace=? AND scope=? AND key=? ORDER BY recorded,valid_from',(self.v.ns,scope,key))]

    def forget(self,scope,key):
        n=ts()
        with self.v.transaction():
            c=self.v.db.execute('UPDATE mem_facts SET retracted=? WHERE namespace=? AND scope=? AND key=? AND retracted IS NULL',(n,self.v.ns,scope,key)).rowcount
            self.v.audit('memory_forget',{'scope':scope,'key':key,'rows':c})
        return c

    def scopes(self):
        return [r[0] for r in self.v.db.execute('SELECT DISTINCT scope FROM mem_facts WHERE namespace=? AND retracted IS NULL ORDER BY scope',(self.v.ns,))]

    def rules(self,scope):
        out=[]
        for r in self.v.db.execute("SELECT key FROM mem_facts WHERE namespace=? AND scope=? AND key LIKE 'rule:%' AND valid_to IS NULL AND retracted IS NULL",(self.v.ns,scope)):
            x=self.recall(scope,r['key'])
            if x:out.append(x)
        return out

    def handoff(self,scope,from_agent,to_agent,summary,open_items=()):
        card={'from':from_agent,'to':to_agent,'summary':summary,'open':list(open_items)}
        return self.remember(scope,from_agent+'->'+to_agent,card,'handoff:'+from_agent,agent=from_agent,kind='handoff')

    def grounded(self,query,limit=5):
        """Recall only claims that carry a source; sources are returned so answers can cite them."""
        q='%'+query.lower()+'%'
        rows=self.v.db.execute("SELECT * FROM mem_facts WHERE namespace=? AND retracted IS NULL AND valid_to IS NULL AND source!='' AND (lower(key) LIKE ? OR lower(value) LIKE ?) ORDER BY recorded DESC LIMIT ?",
                               (self.v.ns,q,q,limit)).fetchall()
        return [self._row(r) for r in rows]

    def suppress(self,scope,key):
        """Reversible hide from search/recall of search results; unlike forget, history is untouched."""
        self.v.db.execute('INSERT OR REPLACE INTO mem_suppressed VALUES(?,?,?,?)',(self.v.ns,scope,key,ts()))
        self.v.audit('memory_suppress',{'scope':scope,'key':key})

    def release(self,scope,key):
        c=self.v.db.execute('DELETE FROM mem_suppressed WHERE namespace=? AND scope=? AND key=?',(self.v.ns,scope,key)).rowcount
        self.v.audit('memory_release',{'scope':scope,'key':key});return c

    def search(self,query,limit=5,include_history=False,max_age_days=90):
        """BM25 over live claims; fresher labels first, ties broken by lexical score. Always cites source."""
        now=ts()
        rows=self.v.db.execute('SELECT m.* FROM mem_facts m WHERE m.namespace=? AND m.retracted IS NULL AND NOT EXISTS('
                               'SELECT 1 FROM mem_suppressed s WHERE s.namespace=m.namespace AND s.scope=m.scope AND s.key=m.key)',(self.v.ns,)).fetchall()
        rows=[r for r in rows if include_history or r['valid_to'] is None]
        if not rows:return []
        idx=BM25([r['key']+' '+json.loads(r['value']).__str__() for r in rows])
        out=[]
        for sc,i in idx.rank(query,limit=len(rows)):
            d=self._row(rows[i]);d['label']=freshness(str(d['value']),d['valid_to'],d['recorded'],now,max_age_days);d['score']=round(sc,4);out.append(d)
        out.sort(key=lambda d:(-RANK[d['label']],-d['score']))
        return out[:limit]
