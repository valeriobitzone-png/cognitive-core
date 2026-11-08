"""Portable, evidence-first knowledge/event intelligence for any agent host.

Metadata and original short summaries only. No remote text is trusted as commands.
No causal inferences from correlation; no autonomous action or network calls.
Owner/space are selectors, NOT authentication; host must enforce ACLs.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from urllib.parse import urlsplit

DOMAINS = (
    'agents','ai','software','science','finance','crypto','economics','news','history',
    'geopolitics','psychology','medicine','sports_science','sports_analytics',
    'biology','chemistry','physics','climate','maps','geospatial','architecture',
    'bim','3d_modeling','3d_printing','robotics','marketing','social_media',
    'education','security','other')
RECORD_TYPES = ('repo','news','research','event','observation','market','dataset','correction')
RIGHTS = ('CC0','CC-BY-4.0','CC-BY-SA-4.0','PUBLIC-DOMAIN','METADATA-ONLY','USER-PROVIDED','OTHER-REVIEW-REQUIRED')
SAFE_RE = re.compile(r'^[A-Za-z0-9_./:@-]{1,128}$')


def _id(v, field='identifier'):
    from .engine import WorldCoreError
    if not isinstance(v,str) or not SAFE_RE.fullmatch(v):
        raise WorldCoreError(f'invalid {field}')
    return v


def _url(v):
    from .engine import WorldCoreError
    if not isinstance(v,str) or len(v)>2048:
        raise WorldCoreError('invalid source URL')
    p=urlsplit(v)
    if p.scheme!='https' or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise WorldCoreError('public records require HTTPS URL without userinfo or nonstandard ports')
    return v


def _txt(v,cap):
    from .engine import WorldCoreError
    if not isinstance(v,str) or not v.strip() or len(v)>cap or '\x00' in v:
        raise WorldCoreError(f'invalid text (max {cap})')
    return v.strip()


def _tags(v):
    from .engine import WorldCoreError
    if not isinstance(v,list) or len(v)>12 or not all(isinstance(x,str) and x in DOMAINS for x in v):
        raise WorldCoreError('unknown topic or too many topics')
    if not v or len(set(v))!=len(v):raise WorldCoreError('topics must be non-empty and unique')
    return v


def _utc(v):
    from .engine import _when
    return _when(v)


def _jsoncanon(v):
    return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)


class IntelligenceMixin:
    def _init_intelligence_schema(self):
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS intel_records(
          owner TEXT NOT NULL,space TEXT NOT NULL, source TEXT NOT NULL,record_id TEXT NOT NULL,
          version INTEGER NOT NULL, kind TEXT NOT NULL, title TEXT NOT NULL, summary TEXT NOT NULL,
          source_url TEXT NOT NULL, license TEXT NOT NULL, published_at TEXT NOT NULL,
          observed_at TEXT NOT NULL,topics TEXT NOT NULL,entities TEXT NOT NULL,
          confidence REAL NOT NULL, content_sha256 TEXT NOT NULL,
          PRIMARY KEY(owner,space,source,record_id,version));
        CREATE TABLE IF NOT EXISTS intel_current(
          owner TEXT NOT NULL,space TEXT NOT NULL,source TEXT NOT NULL,record_id TEXT NOT NULL,
          version INTEGER NOT NULL,
          PRIMARY KEY(owner,space,source,record_id));
        CREATE INDEX IF NOT EXISTS intel_timeline ON intel_records(owner,space,published_at);
        CREATE TABLE IF NOT EXISTS intel_interests(
          owner TEXT NOT NULL,space TEXT NOT NULL,topic TEXT NOT NULL, weight REAL NOT NULL,
          updated_at TEXT NOT NULL,PRIMARY KEY(owner,space,topic));
        CREATE TABLE IF NOT EXISTS intel_links(
          owner TEXT NOT NULL,space TEXT NOT NULL,subject TEXT NOT NULL,predicate TEXT NOT NULL,
          object TEXT NOT NULL, record_source TEXT NOT NULL,record_id TEXT NOT NULL,
          published_at TEXT NOT NULL, strength REAL NOT NULL,
          PRIMARY KEY(owner,space,subject,predicate,object,record_source,record_id));
        CREATE TABLE IF NOT EXISTS intel_feed_runs(
          owner TEXT NOT NULL,space TEXT NOT NULL,provider TEXT NOT NULL,
          last_success_at TEXT, last_result_sha256 TEXT,
          PRIMARY KEY(owner,space,provider));
        ''')
        try:
            with self._transaction():
                found=self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='intel_index'").fetchone()
                if not found:
                    self.db.execute('''CREATE VIRTUAL TABLE intel_index USING fts5(owner UNINDEXED,space UNINDEXED,
                         source UNINDEXED,record_id UNINDEXED,version UNINDEXED,title,summary,tokenize='unicode61')''')
                    self.db.execute('''INSERT INTO intel_index(owner,space,source,record_id,version,title,summary)
                      SELECT owner,space,source,record_id,version,title,summary FROM intel_records''')
            self._intel_fts=True
        except __import__('sqlite3').OperationalError as exc:
            if 'fts5' not in str(exc).lower() and 'no such module' not in str(exc).lower():raise
            self._intel_fts=False

    def learn_evidence(self, owner:str, record:dict, *,space:str='default'):
        """Import bounded public metadata + original summaries; idempotent with version history."""
        from .engine import WorldCoreError,utcnow
        owner,space=_id(owner),_id(space)
        if not isinstance(record,dict):raise WorldCoreError('record must be dictionary')
        required={'source','record_id','kind','title','summary','url','license','published_at','topics'}
        if not required.issubset(record):raise WorldCoreError('required evidence fields missing')
        src,rid=_id(record['source'],'source'),_id(record['record_id'],'record id')
        kind=record['kind'];license=record['license']
        if kind not in RECORD_TYPES or license not in RIGHTS:raise WorldCoreError('unsupported record type or rights')
        title,summary=_txt(record['title'],200),_txt(record['summary'],1200)
        url=_url(record['url']);topics=_tags(record['topics'])
        entities=record.get('entities',[])
        if not isinstance(entities,list) or len(entities)>20 or not all(isinstance(e,str) and 1<=len(e)<=90 for e in entities):
            raise WorldCoreError('invalid entities')
        if not (0 <= float(record.get('confidence',0.5)) <= 1) or not math.isfinite(float(record.get('confidence',0.5))):
            raise WorldCoreError('confidence outside [0,1]')
        confidence=float(record.get('confidence',0.5))
        published=_utc(record['published_at']); observed=_utc(record.get('observed_at') or utcnow())
        if datetime.fromisoformat(published)>datetime.fromisoformat(observed):raise WorldCoreError('publication timestamp after observation')
        data={'kind':kind,'title':title,'summary':summary,'url':url,'license':license,'published_at':published,
              'topics':topics,'entities':entities,'confidence':confidence}
        fingerprint=sha256(_jsoncanon(data).encode()).hexdigest()
        with self._transaction():
            existing=self.db.execute('''SELECT c.version,r.content_sha256 FROM intel_current c
                JOIN intel_records r ON c.owner=r.owner AND c.space=r.space AND c.source=r.source
                AND c.record_id=r.record_id AND c.version=r.version
                WHERE c.owner=? AND c.space=? AND c.source=? AND c.record_id=?''',
                (owner,space,src,rid)).fetchone()
            if existing and existing['content_sha256']==fingerprint:
                return {'status':'unchanged','version':existing['version'],'sha256':fingerprint}
            ver=1 if existing is None else existing['version']+1
            self.db.execute('''INSERT INTO intel_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
              (owner,space,src,rid,ver,kind,title,summary,url,license,published,observed,
               _jsoncanon(topics),_jsoncanon(entities),confidence,fingerprint))
            self.db.execute('''INSERT INTO intel_current VALUES(?,?,?,?,?) ON CONFLICT(owner,space,source,record_id)
                 DO UPDATE SET version=excluded.version''',(owner,space,src,rid,ver))
            if self._intel_fts:
                self.db.execute('INSERT INTO intel_index(owner,space,source,record_id,version,title,summary) VALUES(?,?,?,?,?,?,?)',
                                (owner,space,src,rid,ver,title,summary))
        return {'status':'added' if not existing else 'updated','version':ver,'sha256':fingerprint}

    def query_intelligence(self,owner:str,query:str,*,space:str='default',topics:list[str]|None=None,limit:int=10):
        """Bouned lexical search, scoped and source-attributed; does not execute text."""
        from .engine import WorldCoreError
        owner,space=_id(owner),_id(space)
        if not isinstance(query,str) or not 1<=len(query)<=300 or not 1<=limit<=50:raise WorldCoreError('invalid query or limit')
        if topics is not None:_tags(topics)
        tokens=re.findall(r'[^\W_]+',query.casefold())[:10]
        if not tokens:return []
        with self.lock:
            if self._intel_fts:
                # Search all history through an index, but join only CURRENT versions
                # in this authenticated owner's namespace. Never run raw FTS syntax.
                fts_query=' OR '.join('"'+t[:48].replace('"','')+'"' for t in tokens if t)
                rows=self.db.execute('''SELECT r.* FROM intel_index JOIN intel_current c
                  ON c.owner=intel_index.owner AND c.space=intel_index.space
                  AND c.source=intel_index.source AND c.record_id=intel_index.record_id
                  AND c.version=CAST(intel_index.version AS INTEGER)
                  JOIN intel_records r ON r.owner=c.owner AND r.space=c.space
                  AND r.source=c.source AND r.record_id=c.record_id AND r.version=c.version
                  WHERE intel_index MATCH ? AND r.owner=? AND r.space=?
                  ORDER BY bm25(intel_index),r.published_at DESC LIMIT 500''',
                  (fts_query,owner,space)).fetchall()
            else:
                # No FTS5 fallback preserves correctness (slower, not capped to 5000).
                condition=' OR '.join('(lower(r.title) LIKE ? OR lower(r.summary) LIKE ?)' for _ in tokens)
                params=[p for t in tokens for p in ('%'+t+'%','%'+t+'%')]
                rows=self.db.execute(f'''SELECT r.* FROM intel_records r JOIN intel_current c
                  ON r.owner=c.owner AND r.space=c.space AND r.source=c.source AND r.record_id=c.record_id
                  AND r.version=c.version WHERE r.owner=? AND r.space=? AND ({condition})
                  ORDER BY r.published_at DESC LIMIT 500''',(owner,space,*params)).fetchall()
        results=[]
        for row in rows:
            d=dict(row)
            its=json.loads(d['topics'])
            if topics and not (set(topics)&set(its)):continue
            hay=(d['title']+' '+d['summary']+' '+' '.join(its)+' '+' '.join(json.loads(d['entities']))).casefold()
            score=sum(3 if t in d['title'].casefold() else 1 for t in tokens if t in hay)
            # Multiword exact phrases outrank a single shared token (e.g. 'world').
            if len(tokens)>1 and ' '.join(tokens) in hay:score+=6
            if score==0:continue
            results.append({'source':d['source'],'record_id':d['record_id'],'title':d['title'],
                'summary':d['summary'],'url':d['source_url'],'license':d['license'],'published_at':d['published_at'],
                'topics':its,'version':d['version'],'confidence':d['confidence'],'score':score,'trusted_instruction':False})
        return sorted(results,key=lambda r:(r['score'],r['published_at'],r['record_id']),reverse=True)[:limit]

    def set_interest(self,owner:str,topic:str,weight:float,*,space:str='default'):
        """Explicit opt-in interests. Sensitive traits are not inferred from browsing."""
        from .engine import WorldCoreError,utcnow
        owner,space=_id(owner),_id(space)
        if topic not in DOMAINS or isinstance(weight,bool) or not isinstance(weight,(int,float)) or not math.isfinite(weight) or not 0<=weight<=5:
            raise WorldCoreError('invalid topic or user-supplied weight [0..5]')
        with self._transaction():
            self.db.execute('''INSERT INTO intel_interests VALUES(?,?,?,?,?) ON CONFLICT(owner,space,topic)
              DO UPDATE SET weight=excluded.weight,updated_at=excluded.updated_at''',(owner,space,topic,float(weight),utcnow()))

    def personalized_digest(self,owner:str,*,space:str='default',as_of:str|None=None,limit:int=12,max_age_days:int=14):
        from .engine import WorldCoreError,utcnow
        owner,space=_id(owner),_id(space)
        if not 1<=limit<=50 or not 1<=max_age_days<=365:raise WorldCoreError('invalid digest bounds')
        now=datetime.fromisoformat(_utc(as_of or utcnow()))
        with self.lock:
            prefs={r['topic']:r['weight'] for r in self.db.execute('SELECT topic,weight FROM intel_interests WHERE owner=? AND space=?',(owner,space))}
            rows=self.db.execute('''SELECT r.* FROM intel_records r JOIN intel_current c
              ON r.owner=c.owner AND r.space=c.space AND r.source=c.source AND r.record_id=c.record_id
              AND r.version=c.version WHERE r.owner=? AND r.space=? AND r.kind IN ('news','research','event','market')
              ORDER BY r.published_at DESC LIMIT 10000''',(owner,space)).fetchall()
        ranked=[]
        for d in rows:
            age=(now-datetime.fromisoformat(d['published_at'])).total_seconds()/86400
            if not 0<=age<=max_age_days:continue
            topics=json.loads(d['topics'])
            # Without explicit interests, diverse and recent non-sensitive public records only.
            weight=max((prefs.get(t,0) for t in topics),default=0) if prefs else 0
            if prefs and weight<=0:continue
            score=(1+weight)*math.exp(-age/7.0)*(.5+.5*d['confidence'])
            ranked.append({'source':d['source'],'record_id':d['record_id'],'title':d['title'],
              'url':d['source_url'],'published_at':d['published_at'],'topics':topics,
              'interest_weight':weight,'ranking_score':round(score,6),
              'explanation':'explicit_topic_interest+recency+source_confidence' if prefs else 'recency+source_confidence',
              'summary':d['summary'],'license':d['license'],'requires_source_verification':True})
        ranked.sort(key=lambda x:(-x['ranking_score'],x['source'],x['record_id']))
        # Prefer source diversity over 10 copies of one feed.
        out=[];per_source=Counter()
        for x in ranked:
            if per_source[x['source']]>=max(2,limit//2):continue
            out.append(x);per_source[x['source']]+=1
            if len(out)>=limit:break
        return out

    def link_evidence(self,owner:str,*,subject:str,predicate:str,object:str,source:str,record_id:str,
                      space:str='default',strength:float=0.5):
        """Evidence-backed links; forbids asserting CAUSES from co-mentions alone."""
        from .engine import WorldCoreError
        owner,space=_id(owner),_id(space)
        subject,object=_txt(subject,120),_txt(object,120)
        source,record_id=_id(source),_id(record_id)
        if predicate not in ('mentions','precedes','associated_with','contradicts','supports','responds_to'):
            raise WorldCoreError('unsupported evidence relation; causal relations require external experiment')
        if isinstance(strength,bool) or not isinstance(strength,(int,float)) or not math.isfinite(strength) or not 0<=strength<=1:
            raise WorldCoreError('invalid strength')
        with self._transaction():
            r=self.db.execute('''SELECT r.published_at FROM intel_current c JOIN intel_records r
                ON c.owner=r.owner AND c.space=r.space AND c.source=r.source AND c.record_id=r.record_id AND c.version=r.version
                WHERE c.owner=? AND c.space=? AND c.source=? AND c.record_id=?''',(owner,space,source,record_id)).fetchone()
            if r is None:raise WorldCoreError('relationship must cite an existing record')
            self.db.execute('''INSERT INTO intel_links VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(owner,space,subject,predicate,object,record_source,record_id)
               DO UPDATE SET strength=excluded.strength''',
               (owner,space,subject,predicate,object,source,record_id,r['published_at'],float(strength)))

    def find_associations(self,owner:str,*,space:str='default',min_events:int=3,limit:int=12):
        """Topic co-occurrence ONLY, explicitly non-causal; distinct source records, no causal claims."""
        from .engine import WorldCoreError
        owner,space=_id(owner),_id(space)
        if not 2<=min_events<=100 or not 1<=limit<=50:raise WorldCoreError('invalid association request')
        with self.lock:
            rows=self.db.execute('''SELECT r.topics FROM intel_records r JOIN intel_current c
              ON c.owner=r.owner AND c.space=r.space AND c.source=r.source AND c.record_id=r.record_id AND c.version=r.version
              WHERE r.owner=? AND r.space=?''',(owner,space)).fetchall()
        singles=Counter(); pairs=Counter(); n=len(rows)
        for r in rows:
            t=sorted(set(json.loads(r[0])))
            singles.update(t)
            pairs.update((t[i],t[j]) for i in range(len(t)) for j in range(i+1,len(t)))
        result=[]
        for (a,b),count in pairs.items():
            if count<min_events:continue
            expected=singles[a]*singles[b]/max(1,n)
            lift=count/max(expected,1e-12)
            result.append({'topics':[a,b],'co_mentions':count,'records':n,'lift':round(lift,4),
                'interpretation':'descriptive co-occurrence, not causation or predictive validation'})
        result.sort(key=lambda r:(-r['co_mentions'],-r['lift'],r['topics']))
        return result[:limit]

    def intelligence_stats(self,owner:str,*,space:str='default'):
        owner,space=_id(owner),_id(space)
        with self.lock:
            records=self.db.execute('SELECT count(*) FROM intel_current WHERE owner=? AND space=?',(owner,space)).fetchone()[0]
            history=self.db.execute('SELECT count(*) FROM intel_records WHERE owner=? AND space=?',(owner,space)).fetchone()[0]
            prefs=self.db.execute('SELECT count(*) FROM intel_interests WHERE owner=? AND space=?',(owner,space)).fetchone()[0]
        return {'records':records,'versions_total':history,'explicit_interests':prefs,'owner':owner,'space':space}

    def feedback_on_record(self,owner:str,source:str,record_id:str,*,space:str='default',positive:bool):
        """Explicit operator/user feedback updates topic weights conservatively, with record evidence.

        No implicit sensitive profiling or automated behavioral inference.
        """
        from .engine import WorldCoreError,utcnow
        owner,space,source,record_id=map(_id,(owner,space,source,record_id))
        if type(positive) is not bool:raise WorldCoreError('feedback must be explicit boolean')
        with self._transaction():
            row=self.db.execute('''SELECT r.topics FROM intel_records r JOIN intel_current c
               ON c.owner=r.owner AND c.space=r.space AND c.source=r.source AND c.record_id=r.record_id AND c.version=r.version
               WHERE c.owner=? AND c.space=? AND c.source=? AND c.record_id=?''',
               (owner,space,source,record_id)).fetchone()
            if row is None:raise WorldCoreError('feedback record must exist in user namespace')
            weights={}
            for topic in json.loads(row['topics']):
                previous=self.db.execute('''SELECT weight FROM intel_interests WHERE owner=? AND space=? AND topic=?''',
                   (owner,space,topic)).fetchone()
                old=float(previous[0]) if previous else 1.0
                new=min(5.,max(0.,round(old+(.15 if positive else -.15),4)))
                self.db.execute('''INSERT INTO intel_interests VALUES(?,?,?,?,?) ON CONFLICT(owner,space,topic)
                  DO UPDATE SET weight=excluded.weight,updated_at=excluded.updated_at''',
                  (owner,space,topic,new,utcnow()))
                weights[topic]=new
        return {'weights':weights,'method':'explicit feedback, bounded rule, not model training'}

    def temporal_associations(self,owner:str,*,space:str='default',max_lag_days:int=14,min_pairs:int=3,limit:int=15):
        """Exploratory topic lead/lag statistics; NOT causal evidence.

        Each pair counts distinct records in increasing timestamp order, never
        within the same record. Not a calibrated or significant forecast.
        """
        from .engine import WorldCoreError
        owner,space=_id(owner),_id(space)
        if not 1<=max_lag_days<=365 or not 2<=min_pairs<=100 or not 1<=limit<=50:
            raise WorldCoreError('invalid lag configuration')
        with self.lock:
            rows=self.db.execute('''SELECT r.source,r.record_id,r.topics,r.published_at
             FROM intel_records r JOIN intel_current c
             ON r.owner=c.owner AND r.space=c.space AND r.source=c.source AND r.record_id=c.record_id AND r.version=c.version
             WHERE r.owner=? AND r.space=? ORDER BY r.published_at DESC LIMIT 3000''',(owner,space)).fetchall()
        # Order bounded to avoid O(n²) runaway on an infinite historical corpus.
        events=[(datetime.fromisoformat(r['published_at']),r['source'],r['record_id'],set(json.loads(r['topics']))) for r in rows[:500]]
        events.sort(key=lambda x:x[0]);edges=Counter()
        from datetime import timedelta
        lag=timedelta(days=max_lag_days)
        for i,(time_a,src_a,id_a,topics_a) in enumerate(events):
            for time_b,src_b,id_b,topics_b in events[i+1:]:
                if time_b-time_a>lag:break
                if time_b<=time_a or (src_a,id_a)==(src_b,id_b):continue
                for a in topics_a:
                    for b in topics_b:
                        if a!=b:edges[(a,b)]+=1
        out=[{'earlier':a,'later':b,'ordered_pairs':v,'max_lag_days':max_lag_days,
              'warning':'observed lead-lag counts only; news coverage bias, confounding and duplicates possible; NOT causal'}
              for (a,b),v in edges.items() if v>=min_pairs]
        out.sort(key=lambda x:(-x['ordered_pairs'],x['earlier'],x['later']))
        return out[:limit]

    def query_links(self,owner:str,entity:str,*,space:str='default',limit:int=20):
        """Fetch attributed links, including historical human responses.

        Neither associated_with nor responds_to implies proof of causality.
        """
        from .engine import WorldCoreError
        owner,space=_id(owner),_id(space)
        entity=_txt(entity,120)
        if not 1<=limit<=100:raise WorldCoreError('invalid link limit')
        with self.lock:
            rows=self.db.execute('''SELECT l.subject,l.predicate,l.object,l.strength,l.published_at,
                l.record_source,l.record_id,r.source_url,r.title FROM intel_links l
                JOIN intel_current c ON c.owner=l.owner AND c.space=l.space
                  AND c.source=l.record_source AND c.record_id=l.record_id
                JOIN intel_records r ON r.owner=c.owner AND r.space=c.space AND r.source=c.source
                  AND r.record_id=c.record_id AND r.version=c.version
                WHERE l.owner=? AND l.space=? AND (l.subject=? OR l.object=?)
                ORDER BY l.published_at DESC LIMIT ?''',(owner,space,entity,entity,limit)).fetchall()
        return [{**dict(r),'causal_claim':False,'trusted_instruction':False} for r in rows]

    def query_public_catalog(self,query:str,*,limit:int=8,spaces:tuple[str,...]=(
                         'repo_catalog','source_guides','historical_events','daily_evidence','news_examples')):
        """Opt-in source-verified PUBLIC research records; no private tenant reads."""
        from .engine import WorldCoreError
        if not 1<=limit<=40:raise WorldCoreError('invalid limit')
        allowed={'repo_catalog','source_guides','historical_events','daily_evidence','news_examples'}
        if not isinstance(spaces,tuple) or not spaces or any(s not in allowed for s in spaces):
            raise WorldCoreError('only explicit public research spaces allowed')
        result=[]
        for s in spaces:
            hits=self.query_intelligence('public_research',query,space=s,limit=limit)
            for h in hits:
                result.append({**h,'public_space':s})
        result.sort(key=lambda h:(-h['score'],h['source'],h['title']))
        return result[:limit]

    def search_repo_candidates(self,query:str,*,limit:int=10):
        """Search unreviewed GitHub discoveries; never equivalent to trained code."""
        hits=self.query_intelligence('public_research',query,space='repo_candidates',limit=limit)
        return [{**h,'review_stage':'discovery_only','quality_certified':False,
                'model_trained_on_repository':False,
                'warning':'Search discovery is not a software audit, rights clearance, or model training'} for h in hits]

    def personalized_public_digest(self,owner:str,*,space:str='default',as_of:str|None=None,
                                   limit:int=10,max_age_days:int=14):
        """Public daily news, ranked by the caller's EXPLICIT per-user interests.

        News metadata is unverified until corroborated; no autonomous trading or
        medical advice. The personalization database never exposes private records.
        """
        from .engine import WorldCoreError,utcnow
        owner,space=_id(owner),_id(space)
        if not 1<=limit<=40 or not 1<=max_age_days<=365:raise WorldCoreError('invalid digest bounds')
        now=datetime.fromisoformat(_utc(as_of or utcnow()))
        with self.lock:
            prefs={r['topic']:float(r['weight']) for r in self.db.execute(
                'SELECT topic,weight FROM intel_interests WHERE owner=? AND space=?',(owner,space))}
            rows=self.db.execute('''SELECT r.* FROM intel_records r JOIN intel_current c
                ON r.owner=c.owner AND r.space=c.space AND r.source=c.source AND r.record_id=c.record_id
                   AND r.version=c.version WHERE r.owner='public_research'
                AND r.space IN ('daily_evidence','news_examples')
                AND r.kind IN ('news','research','event','market')
                ORDER BY r.published_at DESC LIMIT 5000''').fetchall()
        out=[]
        for d in rows:
            age=(now-datetime.fromisoformat(d['published_at'])).total_seconds()/86400
            if not 0<=age<=max_age_days:continue
            topics=json.loads(d['topics'])
            weight=max((prefs.get(t,0.) for t in topics),default=0.) if prefs else 0.
            if prefs and weight<=0:continue
            score=(1+weight)*math.exp(-age/7)*(.5+.5*d['confidence'])
            out.append({'source':d['source'],'record_id':d['record_id'],'title':d['title'],
               'url':d['source_url'],'topics':topics,'published_at':d['published_at'],
               'summary':d['summary'],'license':d['license'],'rank':round(score,6),
               'review_required':True,'warning':'unverified report metadata; not personalized advice'})
        out.sort(key=lambda r:(-r['rank'],r['source'],r['record_id']))
        chosen=[];per_source=Counter()
        for r in out:
            if per_source[r['source']]>=max(2,limit//2):continue
            chosen.append(r);per_source[r['source']]+=1
            if len(chosen)>=limit:break
        return chosen
