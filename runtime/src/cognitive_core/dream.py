"""Bounded reflection with explicit dependencies. Never verifies its own claims."""

import hashlib
from .memory import Memory, identifier
from .experimental import require_interactive

MAX_HYPOTHESES = 3
BUDGET = 'dream_cycles'


class Dreamer:
    def __init__(self, core):
        self.core = core
        self.m = Memory(core)
        self.v = core.vault

    def run(self, idle=False, daily_limit=2, scope='dream'):
        if type(idle) is not bool:
            raise ValueError('idle must be a trusted boolean')
        scope = identifier(scope, 'scope')
        if not idle:
            return {'status': 'skipped', 'reason': 'not idle'}
        with self.v.transaction():
            if not self.v.reserve_budget(BUDGET, daily_limit):
                return {'status': 'skipped', 'reason': 'budget exhausted'}
            facts = self.m.live(limit=50)
            seen = {}
            out = []
            for fact in facts:
                if fact['scope'] != scope:
                    seen.setdefault(fact['scope'], []).append(fact)
            for project, parents in seen.items():
                if len(parents) < 2 or len(out) >= MAX_HYPOTHESES:
                    continue
                parents = parents[:2]
                keys = [v['key'] for v in parents]
                dependencies = [{k: v[k] for k in ('id', 'scope', 'key', 'source_sha256')} for v in parents]
                text = 'possible link between %s and %s in %s' % (keys[0], keys[1], project)
                value = {'text': text, 'status': 'unverified', 'parents': dependencies, 'epistemic': 'INFERRED'}
                key = 'hypothesis:' + project + ':' + keys[0] + '+' + keys[1]
                previous = self.m.recall(scope, key)
                if previous and isinstance(previous['value'], dict) and previous['value'].get('parents') == dependencies:
                    continue
                out.append(self.m.remember(scope, key, value, 'dream:self', agent='dream'))
            self.v.audit('dream_cycle', {'hypotheses': len(out), 'verified_claims': 0})
        return {'status': 'done', 'hypotheses': out}

    def promote(self, scope, key, verifier_source, *, evidence_id=None):
        """Attach existing literal evidence under interactive authority, never mark truth.

        The old source-string-only verification contract is deliberately rejected.
        A quote establishes source backing, not independent semantic verification.
        """
        require_interactive(self.core)
        with self.v.transaction():
            hypothesis = self.m.recall(scope, key)
            if hypothesis is None:
                raise KeyError(key)
            if not isinstance(hypothesis['value'], dict) or not key.startswith('hypothesis:'):
                raise ValueError('expected a hypothesis')
            if not evidence_id:
                raise ValueError('a verifier label is not evidence; provide an evidence id')
            if not self.grounding_check(scope, key):
                raise ValueError('hypothesis dependencies are not live in their original scopes')
            evidence = self.v.db.execute(
                '''SELECT e.*,d.text,d.sha256,d.source_url,c.statement,c.status claim_status FROM evidence e JOIN documents d
                ON d.id=e.document_id AND d.namespace=e.namespace JOIN claims c ON c.id=e.claim_id AND c.namespace=e.namespace
                WHERE e.namespace=? AND e.id=?''',
                (self.v.ns, evidence_id),
            ).fetchone()
            if not evidence:
                raise ValueError('evidence not found in scope')
            if evidence['statement'] != hypothesis['value'].get('text') or evidence['stance'] != 'supports' or evidence['claim_status'] != 'source_backed':
                raise ValueError('evidence must support this exact hypothesis without unresolved contradiction')
            if not isinstance(verifier_source, str) or verifier_source.startswith('dream:') or verifier_source not in (evidence['document_id'], evidence['source_url']):
                raise ValueError('source must match the referenced document')
            if not evidence['excerpt'] or evidence['excerpt'] not in evidence['text'] or hashlib.sha256(evidence['text'].encode()).hexdigest() != evidence['sha256']:
                raise ValueError('evidence is not literally bound to intact source content')
            value = {
                **hypothesis['value'],
                'status': 'source_backed',
                'evidence_id': evidence_id,
                'evidence_document_sha256': evidence['sha256'],
                'semantic_truth_verified': False,
                'independence': 'not_established',
            }
            return self.m.remember(scope, key, value, verifier_source, agent='reviewer')

    def grounding_check(self, scope, key):
        hypothesis = self.m.recall(scope, key)
        if not hypothesis or not isinstance(hypothesis['value'], dict):
            return False
        parents = hypothesis['value'].get('parents')
        if not isinstance(parents, list) or len(parents) != 2:
            return False
        for parent in parents:
            if not isinstance(parent, dict) or set(parent) != {'id', 'scope', 'key', 'source_sha256'}:
                return False
            current = self.m.recall(parent['scope'], parent['key'])
            if not current or current['id'] != parent['id'] or current['source_sha256'] != parent['source_sha256'] or not self.m.is_current(current['id']):
                return False
        return True

    def wake_context(self, limit=3, scope='dream'):
        if type(limit) is not int or not 1 <= limit <= MAX_HYPOTHESES:
            raise ValueError('wake context limit must be 1..3')
        rows = self.m.search('possible link', limit=limit, scope=scope, include_hypotheses=True)
        return '\n'.join('[UNVERIFIED] ' + v['value']['text'] for v in rows if isinstance(v['value'], dict) and v['value'].get('status') == 'unverified')
