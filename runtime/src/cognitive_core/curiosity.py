"""Scoped information-directed local checks. Suggestions never confer authority.

Only built-in read-only verifiers can resolve a trial; source integrity and retrieval
availability are operational observations, never verification of scientific claims.
"""

from dataclasses import asdict
import hashlib
import json
from time import monotonic

from .information import Belief
from .experimental import check_storage, encoded
from .vault import uid, ts

SCHEMA = '''
CREATE TABLE IF NOT EXISTS curiosity_beliefs(
 namespace TEXT NOT NULL,question_key TEXT NOT NULL,context TEXT NOT NULL,kind TEXT NOT NULL,
 payload TEXT NOT NULL,PRIMARY KEY(namespace,question_key,context,kind));
CREATE TABLE IF NOT EXISTS curiosity_trials(
 namespace TEXT NOT NULL,id TEXT NOT NULL,topic_id TEXT NOT NULL,question_key TEXT NOT NULL,
 context TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,plan TEXT NOT NULL,
 result TEXT,created INTEGER NOT NULL,PRIMARY KEY(namespace,id),
 UNIQUE(namespace,question_key,context,kind));
'''


def initialize(db):
    for statement in SCHEMA.split(';'):
        if statement.strip():
            db.execute(statement)


class Curiosity:
    def __init__(self, core):
        self.core = core
        self.v = core.vault

    def context(self):
        """Inventory version excludes generated notes, audits and speculative futures."""
        began = monotonic()
        h = hashlib.sha256()
        size = 0
        count = 0
        streams = [
            self.v.db.execute("SELECT id,title,source_url,kind,sha256 FROM documents WHERE namespace=? AND kind!='cognitive_note' ORDER BY id", (self.v.ns,)),
            self.v.db.execute('SELECT id,digest,status FROM lab_batches WHERE namespace=? ORDER BY id', (self.v.ns,)),
        ]
        if self.core._worldcore is not None or self.core.s.worldcore_path.exists():
            db = self.core.worldcore.db
            scope = (self.core.s.owner, self.core.s.namespace)
            streams.extend(
                [
                    db.execute('SELECT id,fact_key,value,source,version,status FROM memories WHERE owner=? AND space=? ORDER BY id', scope),
                    (
                        db.execute('SELECT doc_id,title,source_url,license,sha256 FROM knowledge_sources WHERE owner=? AND space=? ORDER BY doc_id', scope)
                        if db.execute("SELECT 1 FROM sqlite_master WHERE name='knowledge_sources'").fetchone()
                        else []
                    ),
                ]
            )
        for index, stream in enumerate(streams):
            for row in stream:
                count += 1
                raw = encoded(list(row)).encode()
                size += len(raw)
                if count > 4096 or size > 2_000_000 or monotonic() - began > 2:
                    raise ValueError('curiosity inventory budget exceeded')
                h.update(str(index).encode() + raw)
        # Only externally attributed, visible assertions affect source versions.
        for record in self.core.memory.live(limit=4097):
            raw = encoded([record[k] for k in ('id', 'scope', 'key', 'source_sha256', 'source', 'valid_from', 'valid_to', 'recorded')]).encode()
            count += 1
            size += len(raw)
            if count > 4096 or size > 2_000_000 or monotonic() - began > 2:
                raise ValueError('curiosity inventory budget exceeded')
            h.update(b'shared-memory:' + raw)
        return 'local-evidence-v2:' + h.hexdigest()

    def _topic(self, ident):
        topic = self.v.get_topic(ident)
        if not topic:
            raise KeyError('topic not found in scope')
        if topic['status'] != 'open':
            raise PermissionError('topic is not open')
        self.core.drive  # Existing project schema; no inferred projects or approvals.
        if self.v.db.execute("SELECT 1 FROM drive_opportunities WHERE namespace=? AND topic_id=? AND status='dismissed'", (self.v.ns, ident)).fetchone():
            raise PermissionError('opportunity dismissed')
        from .drive import tokens

        words = set(tokens(topic['title'] + ' ' + topic['question']))
        projects = self.v.db.execute('SELECT keywords FROM drive_projects WHERE namespace=?', (self.v.ns,))
        if not any(words.intersection(json.loads(row[0])) for row in projects):
            raise PermissionError('no trusted project context')
        return topic

    def _belief(self, key, context, kind='local_evidence'):
        row = self.v.db.execute('SELECT payload FROM curiosity_beliefs WHERE namespace=? AND question_key=? AND context=? AND kind=?', (self.v.ns, key, context, kind)).fetchone()
        return Belief(**json.loads(row[0])) if row else Belief()

    def rank(self, topics):
        if len(topics) > 20:
            raise ValueError('at most 20 candidate topics')
        context = self.context()
        ranked = []
        for topic in topics:
            key = self.v.question_key(topic['question'])
            b = self._belief(key, context)
            old = self.v.db.execute('SELECT status FROM curiosity_trials WHERE namespace=? AND question_key=? AND context=? AND kind=?', (self.v.ns, key, context, 'local_evidence')).fetchone()
            covered = bool(old and old[0] != 'pending')
            score = 0 if covered else topic['importance'] * b.information_gain
            ranked.append(
                {
                    'topic_id': topic['id'],
                    'context': context,
                    'information_nats': b.information_gain,
                    'score': score,
                    'boredom': 'covered_current_context' if covered else 'unmeasured',
                    'target': 'local_source_integrity_and_availability',
                    'calibrated': False,
                }
            )
        return sorted(ranked, key=lambda r: (-r['score'], r['topic_id']))

    def next_topic(self):
        context = self.context()
        rows = self.v.db.execute(
            """SELECT t.* FROM topics t LEFT JOIN cognitive_cycles c
            ON c.namespace=t.namespace AND c.topic_id=t.id WHERE t.namespace=? AND t.status='open'
            AND (c.stage IS NULL OR c.stage NOT IN ('done','abstained','stopped') OR
                (?=1 AND EXISTS(SELECT 1 FROM curiosity_trials q WHERE q.namespace=t.namespace AND q.topic_id=t.id)
                 AND NOT EXISTS(SELECT 1 FROM curiosity_trials q WHERE q.namespace=t.namespace AND q.topic_id=t.id AND q.context=?)))
            ORDER BY t.importance DESC,t.created,t.id LIMIT 20""",
            (self.v.ns, self.core.s.curiosity_policy == 'information_only', context),
        ).fetchall()
        if not rows:
            return None
        if self.core.s.curiosity_policy == 'observe':
            return rows[0]['id']
        ranked = self.rank([dict(r) for r in rows])
        return ranked[0]['topic_id'] if ranked else None

    def needs_recheck(self, topic_id, state):
        previous = state.get('curiosity_context')
        return bool(previous and self.core.s.curiosity_policy == 'information_only' and previous != self.context())

    def plan(self, topic_id, kind='local_evidence'):
        if kind != 'local_evidence':
            raise ValueError('unsupported verifier; no arbitrary tool execution')
        with self.v.transaction():
            topic = self._topic(topic_id)
            context = self.context()
            key = self.v.question_key(topic['question'])
            row = self.v.db.execute('SELECT * FROM curiosity_trials WHERE namespace=? AND question_key=? AND context=? AND kind=?', (self.v.ns, key, context, kind)).fetchone()
            if row:
                return {**json.loads(row['plan']), 'status': row['status'], 'reused': True}
            check_storage(self.core, 65_536)
            count = self.v.db.execute('SELECT count(*) FROM curiosity_trials WHERE namespace=?', (self.v.ns,)).fetchone()[0]
            if count >= 1000:
                return {'status': 'blocked', 'reason': 'curiosity journal admission limit'}
            if not self.v.reserve_budget('curiosity_units', self.core.s.max_curiosity_units_per_day):
                return {'status': 'blocked', 'reason': 'daily curiosity budget exhausted'}
            b = self._belief(key, context, kind)
            ident = uid('curiosity')
            plan = {
                'id': ident,
                'topic_id': topic_id,
                'question_key': key,
                'context': context,
                'kind': kind,
                'policy': self.core.s.curiosity_policy,
                'prediction': b.mean,
                'expected_information_nats': b.information_gain,
                'cost_units': 1,
                'cost_semantics': 'one reserved local verification, not euros or tokens',
                'target': 'local_source_integrity_and_availability',
                'calibrated': False,
                'authority': 'read_only_local',
                'epistemic': 'INFERRED',
                'status': 'pending',
            }
            self.v.db.execute('INSERT INTO curiosity_trials VALUES(?,?,?,?,?,?,?,?,?,?)', (self.v.ns, ident, topic_id, key, context, kind, 'pending', encoded(plan), None, ts()))
            self.v.audit('curiosity_planned', plan)
            return plan

    def _source(self, hit):
        excerpt = hit.get('excerpt', '')
        ident = hit.get('id')
        kind = hit.get('kind', '')
        if not isinstance(excerpt, str) or not excerpt or kind == 'cognitive_note':
            return None
        if kind.startswith('lab_'):
            row = self.v.db.execute(
                '''SELECT r.payload,r.sha256 FROM lab_records r JOIN lab_batches b
                ON b.namespace=r.namespace AND b.id=r.batch_id WHERE r.namespace=? AND r.id=?
                AND b.status='active' AND r.kind NOT IN ('excluded','archive','quarantine','metadata')''',
                (self.v.ns, ident),
            ).fetchone()
            if row and excerpt in row['payload'] and hashlib.sha256(row['payload'].encode()).hexdigest() == row['sha256']:
                return row['sha256']
            return None
        if kind == 'shared_memory':
            if not self.core.memory.is_current(ident):
                return None
            row = self.v.db.execute('SELECT value FROM mem_facts WHERE namespace=? AND id=?', (self.v.ns, ident)).fetchone()
            digest = hashlib.sha256(row[0].encode()).hexdigest() if row else None
            return digest if row and excerpt in row[0] and digest == hit.get('source_sha256') else None
        if kind == 'worldcore_memory':
            row = self.core.worldcore.db.execute("SELECT value FROM memories WHERE owner=? AND space=? AND id=? AND status='active'", (self.core.s.owner, self.core.s.namespace, ident)).fetchone()
            return hashlib.sha256(row[0].encode()).hexdigest() if row and excerpt in row[0] else None
        if kind == 'worldcore_knowledge':
            row = self.core.worldcore.db.execute(
                '''SELECT s.sha256,k.content FROM knowledge_chunks k JOIN knowledge_sources s
                ON s.owner=k.owner AND s.space=k.space AND s.doc_id=k.doc_id
                WHERE k.owner=? AND k.space=? AND k.doc_id=? AND k.offset=?''',
                (self.core.s.owner, self.core.s.namespace, ident, hit.get('offset')),
            ).fetchone()
            return row['sha256'] if row and excerpt in row['content'] else None
        doc = self.v.get_document(ident)
        if doc and doc['kind'] != 'cognitive_note' and excerpt in doc['text'] and hashlib.sha256(doc['text'].encode()).hexdigest() == doc['sha256']:
            return doc['sha256']
        return None

    def run(self, ident):
        """Resolve only from built-in checks; caller-supplied evidence is not accepted."""
        began = monotonic()
        with self.v.transaction():
            row = self.v.db.execute('SELECT * FROM curiosity_trials WHERE namespace=? AND id=?', (self.v.ns, ident)).fetchone()
            if not row:
                raise KeyError('trial not found in scope')
            try:
                topic = self._topic(row['topic_id'])
            except PermissionError:
                return {'status': 'blocked', 'reason': 'project/topic permission changed', 'sources': []}
            if self.v.usage('curiosity_units') > self.core.s.max_curiosity_units_per_day:
                return {'status': 'blocked', 'reason': 'curiosity budget reduced', 'sources': []}
            current = self.context()
            if current != row['context']:
                stale = {'status': 'stale', 'reason': 'source context changed', 'sources': [], 'truth_updates': 0}
                if row['status'] == 'pending':
                    self.v.db.execute("UPDATE curiosity_trials SET status='stale',result=? WHERE namespace=? AND id=?", (encoded(stale), self.v.ns, ident))
                return stale
            if row['status'] != 'pending':
                cached = json.loads(row['result'] or '{}')
                if any(not self._source(hit) for hit in cached.get('sources', [])):
                    return {'status': 'stale', 'reason': 'cached source binding changed', 'sources': []}
                return {**cached, 'status': row['status'], 'cached': True}
            plan = json.loads(row['plan'])
            accepted = []
            rejected = []
            proof = []
            try:
                hits = self.core.memory_search(topic['question'], limit=self.core.s.max_cycle_sources)
                for hit in hits[: self.core.s.max_cycle_sources]:
                    digest = self._source(hit)
                    if digest:
                        accepted.append(hit)
                        proof.append({'id': hit['id'], 'sha256': digest, 'kind': hit['kind']})
                    elif hit.get('kind') != 'cognitive_note':
                        rejected.append(hit.get('id'))
                if self.context() != current:
                    raise ValueError('source context changed during verification')
                if monotonic() - began > self.core.s.max_cycle_seconds:
                    raise TimeoutError('verification time budget exhausted')
            except (OSError, ValueError, TimeoutError) as exc:
                result = {'status': 'inconclusive', 'error': type(exc).__name__, 'sources': [], 'truth_updates': 0}
            else:
                outcome = int(bool(accepted))
                b = self._belief(row['question_key'], current, row['kind'])
                b.observe(outcome)  # At most once per question/version. Never treat copied sources as new trials.
                self.v.db.execute(
                    'INSERT INTO curiosity_beliefs VALUES(?,?,?,?,?) ON CONFLICT(namespace,question_key,context,kind) DO UPDATE SET payload=excluded.payload',
                    (self.v.ns, row['question_key'], current, row['kind'], encoded(asdict(b))),
                )
                result = {
                    'status': 'completed',
                    'outcome': outcome,
                    'sources': accepted,
                    'observed_sources': [h for h in hits if h.get('kind') != 'cognitive_note'][: self.core.s.max_cycle_sources],
                    'rejected_sources': rejected,
                    'evidence': proof,
                    'evidence_sha256': hashlib.sha256(encoded(proof).encode()).hexdigest(),
                    'verifier': 'builtin-local-source-check-v1',
                    'brier': (plan['prediction'] - outcome) ** 2,
                    'observations': b.observations,
                    'epistemic': 'OBSERVED',
                    'target': plan['target'],
                    'truth_updates': 0,
                    'model_weight_updates': 0,
                    'progress': 'not_measured_on_independent_holdout',
                    'actual_cost_units': 1,
                    'elapsed_seconds': monotonic() - began,
                }
            self.v.db.execute('UPDATE curiosity_trials SET status=?,result=? WHERE namespace=? AND id=?', (result['status'], encoded(result), self.v.ns, ident))
            self.v.audit('curiosity_resolved', {'id': ident, 'status': result['status'], 'truth_updates': 0})
            return result

    def journal(self, limit=20):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('journal limit must be 1..100')
        return [
            {'id': r['id'], 'topic_id': r['topic_id'], 'status': r['status'], 'plan': json.loads(r['plan']), 'result': json.loads(r['result']) if r['result'] else None}
            for r in self.v.db.execute('SELECT * FROM curiosity_trials WHERE namespace=? ORDER BY created DESC,id LIMIT ?', (self.v.ns, limit))
        ]
