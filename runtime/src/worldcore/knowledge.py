"""Evidence-indexed document memory. No web scraping, model execution or implicit trust.

A retrieved paragraph is UNTRUSTED DATA, never an instruction to the host agent.
The operator supplies locally obtained material and explicitly declares rights.
"""
from __future__ import annotations
import hashlib
import json
import re
from urllib.parse import urlsplit

_ALLOWED_LICENSES = frozenset({'CC-BY-4.0', 'CC-BY-SA-4.0', 'CC0', 'PUBLIC-DOMAIN', 'APACHE-2.0', 'MIT', 'USER-PROVIDED'})
_STOPWORDS = frozenset('a an and are as at be by for from how in into is it of on or the to was were what when where which who why with this that can does do about'.split())


def _tokens(query: str):
    # Regex is used instead of passing external FTS syntax through to SQLite.
    words = re.findall(r'[^\W_]+', query.lower(), flags=re.UNICODE)
    return [w[:48] for w in words if len(w) > 1 and w not in _STOPWORDS][:14]


def _chunks(text: str, size=750, overlap=110):
    """Bounded sliding text chunks; stable offsets and no silent omissions."""
    step = size-overlap
    for start in range(0, len(text), step):
        part = text[start:start+size]
        if not part: break
        yield start, part
        if start+size >= len(text): break


class KnowledgeMixin:
    def _init_knowledge_schema(self):
        # Avoid DDL work and full-table counts on every agent hook invocation.
        present = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_sources'").fetchone()
        if not present:
            self.db.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_sources (
              owner TEXT NOT NULL, space TEXT NOT NULL, doc_id TEXT NOT NULL,
              title TEXT NOT NULL, source_url TEXT NOT NULL, license TEXT NOT NULL,
              sha256 TEXT NOT NULL, observed_at TEXT NOT NULL,
              PRIMARY KEY (owner,space,doc_id));
            CREATE TABLE IF NOT EXISTS knowledge_chunks (
              chunk_id TEXT PRIMARY KEY, owner TEXT NOT NULL, space TEXT NOT NULL,
              doc_id TEXT NOT NULL, offset INTEGER NOT NULL, content TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS knowledge_scoped ON knowledge_chunks(owner,space,doc_id);
            """)
        self.knowledge_fts = False
        try:
            present_fts = self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='knowledge_fts'").fetchone()
            if not present_fts:
                self.db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(chunk_id UNINDEXED, title, content, tokenize='unicode61')")
                # Initial upgrade backfill only; ingestion uses atomic transactions.
                with self._transaction():
                    self.db.execute("INSERT INTO knowledge_fts(chunk_id,title,content) "
                      "SELECT k.chunk_id,s.title,k.content FROM knowledge_chunks k "
                      "JOIN knowledge_sources s ON (s.owner=k.owner AND s.space=k.space AND s.doc_id=k.doc_id)")
            self.knowledge_fts = True
        except __import__('sqlite3').OperationalError as exc:
            if 'fts5' not in str(exc).lower() and 'no such module' not in str(exc).lower():
                raise

    def ingest_document(self, owner: str, doc_id: str, text: str, *, space: str='default', title: str,
                        source_url: str, license: str, observed_at: str | None=None):
        from .engine import WorldCoreError, _check_id, _text, _when
        owner, space, doc_id = (_check_id(owner),_check_id(space),_check_id(doc_id))
        title = _text(title,'title',180)
        if not isinstance(text,str) or not 40 <= len(text) <= 240000 or '\x00' in text:
            raise WorldCoreError('document must have 40..240000 Unicode characters and no null')
        if not isinstance(source_url,str) or len(source_url)>2048:
            raise WorldCoreError('invalid source URL')
        parsed = urlsplit(source_url)
        if not ((parsed.scheme=='https' and parsed.netloc and not parsed.username and not parsed.password)
                or (parsed.scheme=='conversation' and parsed.netloc)):
            raise WorldCoreError('source must be https://... or conversation://...')
        if license not in _ALLOWED_LICENSES:
            raise WorldCoreError('license declaration is required; unsupported rights declaration')
        if parsed.scheme=='conversation' and license!='USER-PROVIDED':
            raise WorldCoreError('conversation material must be marked USER-PROVIDED')
        if parsed.scheme=='https' and license=='USER-PROVIDED':
            raise WorldCoreError('public web content cannot be declared user-provided')
        at = _when(observed_at)
        text = text.replace('\r\n','\n')
        sha = hashlib.sha256(text.encode()).hexdigest()
        chunks = list(_chunks(text))
        with self._transaction():
            old = self.db.execute('SELECT sha256 FROM knowledge_sources WHERE owner=? AND space=? AND doc_id=?',(owner,space,doc_id)).fetchone()
            if old is not None and old['sha256']==sha:
                # A changed provenance for identical content is suspicious.
                old_record=self.db.execute('SELECT source_url,license FROM knowledge_sources WHERE owner=? AND space=? AND doc_id=?',(owner,space,doc_id)).fetchone()
                if old_record['source_url']!=source_url or old_record['license']!=license:
                    raise WorldCoreError('source provenance conflict: use new document id')
                return {'document':doc_id,'status':'unchanged','sha256':sha,'chunks':len(chunks)}
            if old is not None:
                ids=[r['chunk_id'] for r in self.db.execute('SELECT chunk_id FROM knowledge_chunks WHERE owner=? AND space=? AND doc_id=?',(owner,space,doc_id))]
                if self.knowledge_fts:
                    for chunk_id in ids:self.db.execute('DELETE FROM knowledge_fts WHERE chunk_id=?',(chunk_id,))
                self.db.execute('DELETE FROM knowledge_chunks WHERE owner=? AND space=? AND doc_id=?',(owner,space,doc_id))
            self.db.execute('''INSERT INTO knowledge_sources VALUES(?,?,?,?,?,?,?,?)
              ON CONFLICT(owner,space,doc_id) DO UPDATE SET title=excluded.title,source_url=excluded.source_url,
              license=excluded.license,sha256=excluded.sha256,observed_at=excluded.observed_at''',
              (owner,space,doc_id,title,source_url,license,sha,at))
            for off,content in chunks:
                cid=hashlib.sha256(f'{owner}:{space}:{doc_id}:{sha}:{off}'.encode()).hexdigest()
                self.db.execute('INSERT INTO knowledge_chunks VALUES(?,?,?,?,?,?)',(cid,owner,space,doc_id,off,content))
                if self.knowledge_fts:self.db.execute('INSERT INTO knowledge_fts VALUES(?,?,?)',(cid,title,content))
        return {'document':doc_id,'status':'updated' if old else 'added','sha256':sha,'chunks':len(chunks)}

    def search_evidence(self, owner: str, query: str, *, space: str='default', limit: int=5):
        from .engine import WorldCoreError, _check_id
        owner,space=_check_id(owner),_check_id(space)
        if not isinstance(query,str) or len(query)>500 or not 1<=limit<=30:
            raise WorldCoreError('invalid search query or limit')
        ts=_tokens(query)
        if not ts:return []
        with self.lock:
            if self.knowledge_fts:
                # OR allows partial matches; rank by BM25 then by stable document ID.
                match=' OR '.join('"'+t+'"' for t in ts)
                rows=self.db.execute('''SELECT s.doc_id,s.title,s.source_url,s.license,s.sha256,k.content,k.offset,
                    bm25(knowledge_fts,0,2.5,1.0) AS score
                    FROM knowledge_fts
                    JOIN knowledge_chunks k ON k.chunk_id=knowledge_fts.chunk_id
                    JOIN knowledge_sources s ON s.owner=k.owner AND s.space=k.space AND s.doc_id=k.doc_id
                    WHERE knowledge_fts MATCH ? AND k.owner=? AND k.space=?
                    ORDER BY score ASC, s.doc_id ASC, k.offset ASC LIMIT ?''',
                    (match,owner,space,limit*4)).fetchall()
            else:
                # True no-FTS fallback (no raw SQL query insertion).
                where=' OR '.join('lower(k.content) LIKE ?' for _ in ts)
                rows=self.db.execute(f'''SELECT s.doc_id,s.title,s.source_url,s.license,s.sha256,k.content,k.offset,0.0 as score
                    FROM knowledge_chunks k JOIN knowledge_sources s ON (s.owner=k.owner AND s.space=k.space AND s.doc_id=k.doc_id)
                    WHERE k.owner=? AND k.space=? AND ({where}) ORDER BY s.doc_id,k.offset LIMIT ?''',
                    (owner,space,*('%'+t+'%' for t in ts),limit*4)).fetchall()
        # At most one result per document: prevents a long book crowding out all other sources.
        result=[]; seen=set()
        for r in rows:
            if r['doc_id'] in seen:continue
            seen.add(r['doc_id'])
            result.append({'document':r['doc_id'],'title':r['title'],'source_url':r['source_url'],
                           'license':r['license'],'source_sha256':r['sha256'],
                           'excerpt':r['content'][:750], 'offset':r['offset'],
                           'score':float(r['score']),'trusted_instruction':False})
            if len(result)>=limit:break
        return result

    def knowledge_stats(self, owner: str, *, space: str='default'):
        from .engine import _check_id
        owner,space=_check_id(owner),_check_id(space)
        with self.lock:
            documents=self.db.execute('SELECT count(*) FROM knowledge_sources WHERE owner=? AND space=?',(owner,space)).fetchone()[0]
            chunks=self.db.execute('SELECT count(*) FROM knowledge_chunks WHERE owner=? AND space=?',(owner,space)).fetchone()[0]
        return {'documents':documents,'chunks':chunks,'fts5':self.knowledge_fts,'owner':owner,'space':space}

    def evaluate_retrieval(self,owner: str, cases: list[dict], *,space: str='default', k: int=3):
        from .engine import WorldCoreError
        if not isinstance(cases,list) or not 1<=len(cases)<=500 or not 1<=k<=10:
            raise WorldCoreError('invalid retrieval evaluation')
        scores=[]
        for case in cases:
            if not isinstance(case,dict) or set(case)!={'query','expected_document'}:
                raise WorldCoreError('each case requires query and expected_document')
            found=self.search_evidence(owner,case['query'],space=space,limit=k)
            rank=next((i+1 for i,r in enumerate(found) if r['document']==case['expected_document']),None)
            scores.append(1/rank if rank else 0.0)
        return {'cases':len(scores),'k':k,'recall_at_k':sum(v>0 for v in scores)/len(scores),
                'mrr_at_k':sum(scores)/len(scores),'explanation':'operator-labelled queries; not LLM question-answering accuracy'}
