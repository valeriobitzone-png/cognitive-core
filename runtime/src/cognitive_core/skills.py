"""Small data-only recipes. No eval, generated code, filesystem or model calls."""

import hashlib, itertools, json, math, time
from .experimental import check_storage, require_interactive
from .vault import uid

TYPES = {'text', 'strings', 'numbers', 'scalar'}
OPS = {
    'split_commas': ('text', 'strings'),
    'split_lines': ('text', 'strings'),
    'strip': ('strings', 'strings'),
    'lower': ('strings', 'strings'),
    'nonempty': ('strings', 'strings'),
    'unique': ('strings', 'strings'),
    'alpha_sort': ('strings', 'strings'),
    'lengths': ('strings', 'numbers'),
    'positive': ('numbers', 'numbers'),
    'fahrenheit': ('numbers', 'numbers'),
    'sum': ('numbers', 'scalar'),
    'mean': ('numbers', 'scalar'),
    'count_strings': ('strings', 'scalar'),
}


def typed(value, kind):
    if kind == 'text':
        return isinstance(value, str) and len(value) <= 2000
    if kind == 'scalar':
        return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1e10
    if not isinstance(value, list) or len(value) > 100:
        return False
    if kind == 'strings':
        return all(isinstance(x, str) and len(x) <= 500 for x in value)
    if kind == 'numbers':
        return all(type(x) in (int, float) and math.isfinite(x) and abs(x) <= 1e7 for x in value)
    return False


def execute(kind, steps, value):
    if kind not in TYPES or not typed(value, kind) or not isinstance(steps, list) or not 1 <= len(steps) <= 3:
        raise ValueError('invalid recipe input')
    for op in steps:
        if op not in OPS or OPS[op][0] != kind:
            raise ValueError('invalid typed operation')
        if op == 'split_commas':
            value = value.split(',')
        elif op == 'split_lines':
            value = value.splitlines()
        elif op == 'strip':
            value = [x.strip() for x in value]
        elif op == 'lower':
            value = [x.lower() for x in value]
        elif op == 'nonempty':
            value = [x for x in value if x]
        elif op == 'unique':
            value = list(dict.fromkeys(value))
        elif op == 'alpha_sort':
            value = sorted(value)
        elif op == 'lengths':
            value = [len(x) for x in value]
        elif op == 'positive':
            value = [x for x in value if x > 0]
        elif op == 'fahrenheit':
            value = [round(x * 1.8 + 32, 6) for x in value]
        elif op == 'sum':
            value = sum(value)
        elif op == 'mean':
            value = sum(value) / len(value) if value else 0
        elif op == 'count_strings':
            value = len(value)
        kind = OPS[op][1]
        if not typed(value, kind):
            raise ValueError('recipe intermediate value exceeds budget')
    return value


class SkillBook:
    def __init__(self, program):
        self.program = program
        self.core = program.core
        self.adopted = set()

    def _read(self, ident):
        if not isinstance(ident, str) or len(ident) > 80:
            raise ValueError('invalid skill id')
        row = self.core.vault.db.execute('SELECT payload FROM events WHERE namespace=? AND kind=? ORDER BY rowid DESC LIMIT 1', (self.core.vault.ns, 'program_skill:' + ident)).fetchone()
        if not row:
            raise KeyError('skill not found in scope')
        return json.loads(row[0])

    def propose(self, name, input_type, output_type, development, evaluation):
        self.program.check_scope()
        require_interactive(self.core)
        if self.program.stopped():
            raise PermissionError('program stopped')
        if len(json.dumps([development, evaluation], allow_nan=False).encode()) > 64000:
            raise ValueError('fixtures exceed byte budget')
        if not isinstance(name, str) or not 1 <= len(name) <= 100 or input_type not in TYPES or output_type not in TYPES:
            raise ValueError('invalid skill specification')
        for cases in (development, evaluation):
            if not isinstance(cases, list) or not 2 <= len(cases) <= 8:
                raise ValueError('at least two development and two held-out cases required')
            for case in cases:
                if not isinstance(case, dict) or set(case) != {'input', 'want'} or not typed(case['input'], input_type) or not typed(case['want'], output_type):
                    raise ValueError('invalid fixture')
        key = lambda x: json.dumps(x, sort_keys=True, allow_nan=False)
        if {key(x['input']) for x in development} & {key(x['input']) for x in evaluation}:
            raise ValueError('development and held-out inputs must differ')
        found = None
        tried = 0
        began = time.monotonic()
        # Selection uses development cases only; held-out failure is never repaired.
        for depth in range(1, 4):
            for recipe in itertools.product(OPS, repeat=depth):
                if time.monotonic() - began > min(2, self.core.s.max_cycle_seconds):
                    return {'status': 'abstained', 'reason': 'recipe search deadline exceeded'}
                tried += 1
                if tried > 2500:
                    break
                kind = input_type
                for op in recipe:
                    if OPS[op][0] != kind:
                        break
                    kind = OPS[op][1]
                else:
                    if kind != output_type:
                        continue
                    try:
                        ok = all(execute(input_type, list(recipe), x['input']) == x['want'] for x in development)
                    except ValueError:
                        ok = False
                    if ok:
                        found = list(recipe)
                        break
            if found or tried > 2500:
                break
        if not found:
            return {'status': 'abstained', 'reason': 'no bounded recipe matched development cases'}
        if not all(execute(input_type, found, x['input']) == x['want'] for x in evaluation):
            return {'status': 'rejected', 'reason': 'held-out evaluation failed; no retry'}
        v = self.core.vault
        with v.transaction():
            check_storage(self.core, 16384)
            count = v.db.execute("SELECT count(DISTINCT kind) FROM events WHERE namespace=? AND kind LIKE 'program_skill:%'", (v.ns,)).fetchone()[0]
            if count >= 24:
                raise ValueError('skill registry budget exhausted')
            ident = uid('skill')
            record = {
                'id': ident,
                'name': name,
                'input_type': input_type,
                'output_type': output_type,
                'steps': found,
                'status': 'proposed',
                'epistemic': 'INFERRED',
                'verified': False,
                'fixture_cases_passed': len(development) + len(evaluation),
                'fixture_digest': hashlib.sha256(key([development, evaluation]).encode()).hexdigest(),
            }
            v.event('program_skill:' + ident, record)
        return record

    def adopt(self, ident):
        self.program.check_scope()
        require_interactive(self.core)
        if self.program.stopped():
            raise PermissionError('program stopped')
        record = self._read(ident)
        self.adopted.add(ident)
        self.core.vault.audit('program_skill_adopted', {'skill_id': ident, 'authority': 'current_process_only'})
        return {**record, 'status': 'adopted_for_data_only_use', 'permissions_exported': False}

    def use(self, ident, value):
        self.program.check_scope()
        if self.program.stopped():
            raise PermissionError('program stopped')
        if ident not in self.adopted:
            raise PermissionError('skill needs interactive adoption in this process')
        record = self._read(ident)
        if not self.core.vault.reserve_budget('program_skill_uses', 24):
            raise ValueError('daily skill budget exhausted')
        output = execute(record['input_type'], record['steps'], value)
        self.core.vault.audit('program_skill_used', {'skill_id': ident, 'input_persisted': False, 'external_actions': 0})
        return {'status': 'done', 'output': output, 'external_actions': 0, 'scope': 'provided_data_only'}
