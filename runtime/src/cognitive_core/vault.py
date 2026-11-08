"""Canonical knowledge & evidence store. SQLite is replaceable via this adapter.

Stores raw content + traceability, never silently upgrades an assertion to a fact.
"""
import hashlib
import json
import sqlite3
import time
import uuid
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from .config import Settings


def ts():
    return int(time.time())


def uid(prefix: str):
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class Vault:
    def __init__(self, settings: Settings):
        self.settings = settings
        settings.home.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db = sqlite3.connect(str(settings.db_path), timeout=8, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS events(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, kind TEXT NOT NULL,
                payload TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS topics(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, title TEXT NOT NULL,
                question TEXT NOT NULL, status TEXT NOT NULL, importance REAL NOT NULL,
                reason TEXT NOT NULL, trigger TEXT NOT NULL DEFAULT '',
                created INTEGER NOT NULL, updated INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS jobs(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, topic_id TEXT NOT NULL,
                kind TEXT NOT NULL, status TEXT NOT NULL, plan TEXT NOT NULL,
                checkpoint TEXT NOT NULL DEFAULT '{}', attempts INTEGER NOT NULL DEFAULT 0,
                lease_until INTEGER NOT NULL DEFAULT 0, created INTEGER NOT NULL,
                updated INTEGER NOT NULL, FOREIGN KEY(topic_id) REFERENCES topics(id));
            CREATE TABLE IF NOT EXISTS documents(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, kind TEXT NOT NULL,
                title TEXT NOT NULL, text TEXT NOT NULL, source_url TEXT NOT NULL,
                sha256 TEXT NOT NULL, retrieved INTEGER NOT NULL,
                metadata TEXT NOT NULL DEFAULT '{}',
                UNIQUE(namespace,sha256,source_url));
            CREATE TABLE IF NOT EXISTS claims(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, topic_id TEXT NOT NULL,
                statement TEXT NOT NULL, status TEXT NOT NULL, confidence REAL NOT NULL,
                conditions TEXT NOT NULL DEFAULT '', created INTEGER NOT NULL,
                FOREIGN KEY(topic_id) REFERENCES topics(id));
            CREATE TABLE IF NOT EXISTS evidence(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, claim_id TEXT NOT NULL,
                document_id TEXT NOT NULL, excerpt TEXT NOT NULL, stance TEXT NOT NULL,
                verified_by TEXT NOT NULL, created INTEGER NOT NULL,
                FOREIGN KEY(claim_id) REFERENCES claims(id),
                FOREIGN KEY(document_id) REFERENCES documents(id));
            CREATE TABLE IF NOT EXISTS graph_edges(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, source_id TEXT NOT NULL,
                relation TEXT NOT NULL, target_id TEXT NOT NULL,
                derived_from TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS predictions(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, topic_id TEXT NOT NULL,
                hypothesis TEXT NOT NULL, probability REAL NOT NULL,
                horizon TEXT NOT NULL, predicted_at INTEGER NOT NULL,
                resolved_at INTEGER, observed_outcome TEXT, score REAL,
                FOREIGN KEY(topic_id) REFERENCES topics(id));
            CREATE TABLE IF NOT EXISTS experiences(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, topic_id TEXT NOT NULL,
                action TEXT NOT NULL, expected TEXT NOT NULL, observed TEXT NOT NULL,
                evidence_ref TEXT NOT NULL, created INTEGER NOT NULL,
                FOREIGN KEY(topic_id) REFERENCES topics(id));
            CREATE TABLE IF NOT EXISTS budget_usage(
                namespace TEXT NOT NULL, day TEXT NOT NULL, name TEXT NOT NULL,
                value INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY(namespace, day, name));
            CREATE TABLE IF NOT EXISTS audit(
                id TEXT PRIMARY KEY, namespace TEXT NOT NULL, event TEXT NOT NULL,
                detail TEXT NOT NULL, created INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_topics_ns_status ON topics(namespace,status,importance);
            CREATE INDEX IF NOT EXISTS idx_jobs_ns_status ON jobs(namespace,status,created);
            CREATE INDEX IF NOT EXISTS idx_documents_ns_url ON documents(namespace,source_url);
        """)
        with self.transaction():
            if 'lease_token' not in {r['name'] for r in self.db.execute('PRAGMA table_info(jobs)')}:
                self.db.execute("ALTER TABLE jobs ADD COLUMN lease_token TEXT NOT NULL DEFAULT ''")
            if 'question_key' not in {r['name'] for r in self.db.execute('PRAGMA table_info(topics)')}:
                self.db.execute("ALTER TABLE topics ADD COLUMN question_key TEXT NOT NULL DEFAULT ''")
                for row in self.db.execute('SELECT id,question FROM topics').fetchall():
                    self.db.execute('UPDATE topics SET question_key=? WHERE id=?',
                                    (self.question_key(row['question']),row['id']))
            self.db.execute('CREATE INDEX IF NOT EXISTS idx_topic_question ON topics(namespace,question_key)')
        try:
            self.db.executescript("""
                CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts
                USING fts5(id UNINDEXED, title, text, tokenize='unicode61');
            """)
            self.fts = True
        except sqlite3.OperationalError:
            self.fts = False
        if os.name=='posix':settings.db_path.chmod(0o600)

    @contextmanager
    def transaction(self):
        savepoint=uid('savepoint') if self.db.in_transaction else None
        self.db.execute('SAVEPOINT '+savepoint if savepoint else 'BEGIN IMMEDIATE')
        try:
            yield
        except BaseException:
            self.db.execute('ROLLBACK TO '+savepoint if savepoint else 'ROLLBACK')
            if savepoint:self.db.execute('RELEASE '+savepoint)
            raise
        else:
            self.db.execute('RELEASE '+savepoint if savepoint else 'COMMIT')

    @staticmethod
    def question_key(question):
        return hashlib.sha256(' '.join(question.split()).casefold().encode('utf-8')).hexdigest()

    def close(self):
        self.db.close()

    @property
    def ns(self):
        if self.settings.owner=='local':return self.settings.namespace
        return '@owner='+self.settings.owner+'|space='+self.settings.namespace

    def audit(self, event: str, detail: dict):
        self.db.execute("INSERT INTO audit VALUES(?,?,?,?,?)",
                        (uid('audit'), self.ns, event, json.dumps(detail, ensure_ascii=False), ts()))

    def event(self, kind: str, payload: dict):
        ident = uid('evt')
        self.db.execute("INSERT INTO events VALUES(?,?,?,?,?)",
                        (ident, self.ns, kind, json.dumps(payload, ensure_ascii=False), ts()))
        return ident

    def topic(self, title: str, question: str, importance=0.5,
              status='open', reason='observed', trigger=''):
        if status not in {'open', 'paused', 'discarded', 'done'}:
            raise ValueError('invalid status')
        ident = uid('topic')
        key=self.question_key(question[:4000])
        with self.transaction():
            old=self.db.execute('SELECT id FROM topics WHERE namespace=? AND question_key=? ORDER BY created,id LIMIT 1',
                                (self.ns,key)).fetchone()
            if old:return old['id']
            self.db.execute("INSERT INTO topics(id,namespace,title,question,status,importance,reason,trigger,created,updated,question_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (ident,self.ns,title[:300],question[:4000],status,
                             max(0.0,min(1.0,float(importance))),reason[:400],trigger[:1000],ts(),ts(),key))
        return ident

    def set_topic_status(self, topic_id: str, status: str):
        if status not in {'open', 'paused', 'discarded', 'done'}:
            raise ValueError('invalid status')
        with self.transaction():
            cur = self.db.execute("UPDATE topics SET status=?,updated=? WHERE id=? AND namespace=?",
                                  (status,ts(),topic_id,self.ns))
            if cur.rowcount != 1:raise KeyError(topic_id)
            if status in ('done','discarded','paused'):
                self.db.execute("UPDATE jobs SET status='cancelled',lease_token='',lease_until=0,updated=? WHERE namespace=? AND topic_id=? AND status IN ('pending','running')",
                                (ts(),self.ns,topic_id))
        return True

    def get_topic(self, topic_id: str):
        row = self.db.execute('SELECT * FROM topics WHERE id=? AND namespace=?', (topic_id,self.ns)).fetchone()
        return dict(row) if row else None

    def list_topics(self, status=None):
        if status:
            rows = self.db.execute("SELECT * FROM topics WHERE namespace=? AND status=? ORDER BY importance DESC,created DESC",
                                   (self.ns,status)).fetchall()
        else:
            rows = self.db.execute("SELECT * FROM topics WHERE namespace=? ORDER BY created DESC",
                                   (self.ns,)).fetchall()
        return [dict(r) for r in rows]

    def job(self, topic_id: str, kind='research', plan=None):
        ident = uid('job')
        with self.transaction():
            topic = self.get_topic(topic_id)
            if not topic or topic['status']!='open':raise ValueError('topic not eligible')
            old=self.db.execute("SELECT id FROM jobs WHERE namespace=? AND topic_id=? AND kind=? AND status IN ('pending','running')",
                                (self.ns,topic_id,kind)).fetchone()
            if old:return old['id']
            self.db.execute("INSERT INTO jobs(id,namespace,topic_id,kind,status,plan,created,updated) VALUES(?,?,?,?,?,?,?,?)",
                            (ident,self.ns,topic_id,kind,'pending',json.dumps(plan or {},ensure_ascii=False),ts(),ts()))
        return ident

    def get_job(self, ident):
        r=self.db.execute('SELECT * FROM jobs WHERE id=? AND namespace=?', (ident,self.ns)).fetchone()
        return dict(r) if r else None

    def pending_jobs(self):
        return [dict(r) for r in self.db.execute(
            "SELECT * FROM jobs WHERE namespace=? AND status IN ('pending','running') ORDER BY created",(self.ns,)).fetchall()]

    def lease_job(self, lease_seconds=90):
        """Atomic lease; crashed jobs can resume after expiry."""
        if type(lease_seconds) is not int or not 1<=lease_seconds<=3600:raise ValueError('invalid lease duration')
        now=ts()
        with self.transaction():
            row=self.db.execute("""
                SELECT j.* FROM jobs j JOIN topics t ON t.id=j.topic_id AND t.namespace=j.namespace
                WHERE j.namespace=? AND t.status='open'
                AND (j.status='pending' OR (j.status='running' AND j.lease_until < ?))
                ORDER BY j.created LIMIT 1""", (self.ns,now)).fetchone()
            if not row:
                return None
            self.db.execute("UPDATE jobs SET status='running',lease_until=?,lease_token=?,attempts=attempts+1,updated=? WHERE id=?",
                            (now+lease_seconds,uid('lease'),now,row['id']))
            return self.get_job(row['id'])

    def update_job(self, ident, *, status, checkpoint=None, lease_token=None):
        if status not in ('pending','running','done','blocked','failed','cancelled'):
            raise ValueError('invalid job status')
        with self.transaction():
            job = self.get_job(ident)
            if not job:raise KeyError(ident)
            if lease_token is not None or job['status']=='running':
                if (not lease_token or job['status']!='running' or job['lease_token']!=lease_token
                        or job['lease_until']<ts()):
                    raise PermissionError('job lease expired or revoked')
            if checkpoint is None:checkpoint=json.loads(job['checkpoint'])
            until=ts()+90 if status=='running' else 0
            token=job['lease_token'] if status=='running' else ''
            self.db.execute("UPDATE jobs SET status=?,checkpoint=?,lease_until=?,lease_token=?,updated=? WHERE id=? AND namespace=?",
                            (status,json.dumps(checkpoint,ensure_ascii=False),until,token,ts(),ident,self.ns))

    def document(self, title, text, source_url='', kind='note', metadata=None):
        text=text.encode('utf-8')[:self.settings.max_text_bytes].decode('utf-8',errors='ignore')
        digest=hashlib.sha256(text.encode('utf-8')).hexdigest()
        ident=uid('doc')
        with self.transaction():
            exists=self.db.execute('SELECT id FROM documents WHERE namespace=? AND sha256=? AND source_url=?',
                                  (self.ns,digest,source_url)).fetchone()
            if exists:return exists['id']
            self.db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?)",
                            (ident,self.ns,kind,title[:350],text,source_url,digest,ts(),
                             json.dumps(metadata or {},ensure_ascii=False)))
            if self.fts:
                self.db.execute('INSERT INTO documents_fts(id,title,text) VALUES(?,?,?)',(ident,title[:350],text))
        return ident

    def get_document(self, ident):
        r=self.db.execute('SELECT * FROM documents WHERE id=? AND namespace=?',(ident,self.ns)).fetchone()
        return dict(r) if r else None

    def search(self, query, limit=10):
        query=query.strip()[:350]
        if not query:
            return []
        if self.fts:
            import re
            terms = re.findall(r'\w+',query,flags=re.UNICODE)[:12]
            if terms:
                try:
                    expr = ' OR '.join('"'+t.replace('"','')+'"' for t in terms)
                    rows=self.db.execute("""SELECT d.id,d.title,d.source_url,d.kind,
                      substr(d.text,1,500) excerpt
                      FROM documents_fts f JOIN documents d ON d.id=f.id
                      WHERE documents_fts MATCH ? AND d.namespace=? LIMIT ?""",
                      (expr,self.ns, min(100,max(1,limit)))).fetchall()
                    return [dict(r) for r in rows]
                except sqlite3.OperationalError:
                    pass
        rows=self.db.execute("""SELECT id,title,source_url,kind,substr(text,1,500) excerpt
            FROM documents WHERE namespace=? AND (title LIKE ? OR text LIKE ?) LIMIT ?""",
            (self.ns, '%'+query+'%', '%'+query+'%',min(100,max(1,limit)))).fetchall()
        return [dict(r) for r in rows]

    def claim(self, topic_id, statement, confidence=.1, conditions=''):
        if not self.get_topic(topic_id):
            raise KeyError(topic_id)
        ident=uid('claim')
        self.db.execute("INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)",
                        (ident,self.ns,topic_id,statement[:4000],'unverified',
                         max(0,min(float(confidence),1)),conditions[:500],ts()))
        return ident

    def add_evidence(self, claim_id, document_id, excerpt, stance='supports', verifier='source_link'):
        if stance not in ('supports','contradicts','context'):
            raise ValueError('invalid stance')
        with self.transaction():
            claim=self.db.execute('SELECT id FROM claims WHERE id=? AND namespace=?',(claim_id,self.ns)).fetchone()
            if not claim or not self.get_document(document_id):
                raise KeyError('claim or document')
            ident=uid('evidence')
            self.db.execute('INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?)',
                            (ident,self.ns,claim_id,document_id,excerpt[:1500],stance,verifier[:80],ts()))
            # Attaching a source is not independent verification or a test.
            rows=self.db.execute('SELECT stance FROM evidence WHERE claim_id=? AND namespace=?',
                                 (claim_id,self.ns)).fetchall()
            states={r['stance'] for r in rows}
            status='conflicted' if 'supports' in states and 'contradicts' in states else (
                'source_backed' if 'supports' in states else 'unverified')
            self.db.execute('UPDATE claims SET status=? WHERE id=? AND namespace=?',(status,claim_id,self.ns))
        return ident

    def evidence_for_claim(self, claim_id):
        return [dict(r) for r in self.db.execute("SELECT * FROM evidence WHERE namespace=? AND claim_id=?",
                                                  (self.ns,claim_id)).fetchall()]

    def link(self, source_id, relation, target_id, derived_from=''):
        ident=uid('edge')
        self.db.execute('INSERT INTO graph_edges VALUES(?,?,?,?,?,?,?)',
                        (ident,self.ns,source_id,relation[:80],target_id,derived_from,ts()))
        return ident

    def predict(self, topic_id, hypothesis, probability, horizon):
        if not self.get_topic(topic_id):
            raise KeyError(topic_id)
        p=float(probability)
        if not 0<=p<=1:
            raise ValueError('probability out of range')
        ident=uid('pred')
        self.db.execute("""INSERT INTO predictions(id,namespace,topic_id,hypothesis,probability,horizon,predicted_at)
                           VALUES(?,?,?,?,?,?,?)""",(ident,self.ns,topic_id,hypothesis,p,horizon,ts()))
        return ident

    def resolve_prediction(self, ident, happened: bool, observation=''):
        if type(happened) is not bool:raise ValueError('observed outcome must be boolean')
        with self.transaction():
            row=self.db.execute('SELECT probability,resolved_at FROM predictions WHERE id=? AND namespace=?',
                                (ident,self.ns)).fetchone()
            if not row or row['resolved_at'] is not None:
                raise ValueError('prediction not open')
            score=(row['probability'] - int(happened))**2  # Brier score, lower is better
            self.db.execute("UPDATE predictions SET resolved_at=?,observed_outcome=?,score=? WHERE id=? AND namespace=?",
                            (ts(),json.dumps({'happened':happened,'observation':observation},ensure_ascii=False),score,ident,self.ns))
        return round(score,6)

    def experience(self, topic_id, action, expected, observed, evidence_ref=''):
        if not self.get_topic(topic_id):
            raise KeyError(topic_id)
        ident=uid('exp')
        self.db.execute('INSERT INTO experiences VALUES(?,?,?,?,?,?,?,?)',
                        (ident,self.ns,topic_id,action,expected,observed,evidence_ref,ts()))
        return ident

    def usage(self, name, day=None):
        day=day or time.strftime('%Y-%m-%d',time.gmtime())
        r=self.db.execute('SELECT value FROM budget_usage WHERE namespace=? AND day=? AND name=?',
                          (self.ns,day,name)).fetchone()
        return r['value'] if r else 0

    def reserve_budget(self, name, limit, amount=1):
        """Atomic read/modify; use for budget admission, not estimated external spend."""
        if type(limit) is not int or limit<0 or type(amount) is not int or amount<1:
            raise ValueError('quota limit and reservation must be nonnegative/positive integers')
        day=time.strftime('%Y-%m-%d',time.gmtime())
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO budget_usage VALUES(?,?,?,0)",(self.ns,day,name))
            cur=self.db.execute("UPDATE budget_usage SET value=value+? WHERE namespace=? AND day=? AND name=? AND value+?<=?",
                                (amount,self.ns,day,name,amount,limit))
            return cur.rowcount == 1

    def export_markdown(self, output: Path):
        """Portable, inspectable export. IDs remain stable; source provenance retained."""
        output=Path(output)
        output.mkdir(parents=True,exist_ok=True)
        count=0
        for r in self.db.execute('SELECT * FROM documents WHERE namespace=?',(self.ns,)):
            md=(f"---\nid: {r['id']}\nkind: {r['kind']}\nsha256: {r['sha256']}\n"
                f"source_url: {json.dumps(r['source_url'])}\nretrieved: {r['retrieved']}\n---\n\n"
                f"# {r['title']}\n\n{r['text']}\n")
            (output/(r['id']+'.md')).write_text(md,encoding='utf-8')
            count+=1
        for name,table in [('topics','topics'),('claims','claims'),('evidence','evidence'),
                           ('predictions','predictions'),('experiences','experiences'),
                           ('graph','graph_edges'),('jobs','jobs')]:
            content=[dict(row) for row in self.db.execute(f'SELECT * FROM {table} WHERE namespace=?',(self.ns,))]
            (output/(name+'.json')).write_text(json.dumps(content,ensure_ascii=False,indent=2),encoding='utf-8')
        return count
