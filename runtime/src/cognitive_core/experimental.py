"""Versioned read-only laboratory bridge. Source assertions never become facts."""

import hashlib
import json
import os
import re
import time
from pathlib import Path

FORMAT = 'cognitive-lab-v1'
SCHEMA = '''
CREATE TABLE IF NOT EXISTS lab_batches(
 id TEXT NOT NULL, namespace TEXT NOT NULL, source TEXT NOT NULL,
 digest TEXT NOT NULL, status TEXT NOT NULL, manifest TEXT NOT NULL,
 PRIMARY KEY(namespace,id), UNIQUE(namespace,source,digest));
CREATE TABLE IF NOT EXISTS lab_records(
 id TEXT NOT NULL, namespace TEXT NOT NULL, batch_id TEXT NOT NULL,
 kind TEXT NOT NULL, source_ref TEXT NOT NULL, epistemic TEXT NOT NULL,
 payload TEXT NOT NULL, sha256 TEXT NOT NULL,
 PRIMARY KEY(namespace,id));
CREATE INDEX IF NOT EXISTS lab_batch_records ON lab_records(namespace,batch_id);
CREATE TABLE IF NOT EXISTS cognitive_cycles(
 namespace TEXT NOT NULL, topic_id TEXT NOT NULL, stage TEXT NOT NULL,
 checkpoint TEXT NOT NULL, PRIMARY KEY(namespace,topic_id));
'''


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def initialize(db):
    for statement in SCHEMA.split(';'):
        if statement.strip():
            db.execute(statement)


def require_interactive(core):
    if core.s.execution_mode != 'interactive':
        raise PermissionError('interactive authority required')


def check_storage(core, additional=0):
    # Admission bound includes allocated pages, WAL and the second store. This is
    # a conservative runtime bound, not a filesystem quota against other writers.
    total = sum(p.stat().st_size for p in core.s.home.iterdir() if p.is_file() and (p.name.endswith(('.sqlite3', '-wal', '-shm'))))
    if total + additional > core.s.max_runtime_disk_bytes:
        raise ValueError('runtime disk admission budget exhausted')


def import_lab(core, root, *, source='realtest'):
    require_interactive(core)
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', source):
        raise ValueError('invalid portable source name')
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('laboratory root must be a directory')
    started = time.monotonic()
    files = {}
    skipped = []
    visited = 0
    total = 0
    # Fixed data layout; never execute code, read SQLite, or follow symlinks.
    for relative in ('data/ensemble/connection_graph.json', 'data/ensemble/HYPOTHESIS_QUEUE.json', 'data/ensemble/ERROR_REGISTRY.json'):
        files[relative] = root / relative
    notes = root / 'obsidian-vault'
    for directory, dirs, names in os.walk(notes, followlinks=False):
        visited += 1
        if visited > core.s.max_import_files or time.monotonic() - started > core.s.max_cycle_seconds:
            raise ValueError('import scan budget exhausted')
        dirs[:] = sorted(d for d in dirs if not d.startswith('.') and not (Path(directory) / d).is_symlink())
        for name in sorted(names):
            visited += 1
            if visited > core.s.max_import_files or time.monotonic() - started > core.s.max_cycle_seconds:
                raise ValueError('import scan budget exhausted')
            if name.endswith('.md'):
                path = Path(directory) / name
                files[path.relative_to(root).as_posix()] = path
    blobs = {}
    for relative, path in sorted(files.items()):
        if time.monotonic() - started > core.s.max_cycle_seconds:
            raise ValueError('import time budget exhausted')
        if not path.exists():
            skipped.append({'path': relative, 'reason': 'missing'})
            continue
        if any(p.is_symlink() for p in (path, *path.parents) if p != root.parent):
            skipped.append({'path': relative, 'reason': 'symlink'})
            continue
        if not path.is_file():
            skipped.append({'path': relative, 'reason': 'not a regular file'})
            continue
        if not path.resolve().is_relative_to(root):
            raise ValueError('source escaped root')
        if len(blobs) >= core.s.max_import_files:
            raise ValueError('import file budget exhausted')
        # Bounded read even if a source grows concurrently.
        with path.open('rb') as stream:
            blob = stream.read(core.s.max_import_bytes - total + 1)
        if (relative.endswith('.md') and len(blob) > core.s.max_text_bytes) or total + len(blob) > core.s.max_import_bytes:
            raise ValueError('import byte budget exhausted; no partial import')
        total += len(blob)
        blobs[relative] = blob
    if not blobs:
        raise ValueError('no source files')
    rows = []
    manifest = {'format': FORMAT, 'files': {}, 'skipped': skipped, 'quarantined': []}

    def add(kind, ref, payload, epistemic):
        if len(rows) >= core.s.max_import_records or time.monotonic() - started > core.s.max_cycle_seconds:
            raise ValueError('import record/time budget exhausted')
        raw = encoded(payload)
        rows.append((kind, ref, epistemic, raw, digest(raw.encode())))

    for relative, blob in blobs.items():
        manifest['files'][relative] = {'sha256': digest(blob), 'bytes': len(blob)}
        text = blob.decode('utf-8')
        if relative.endswith('.md'):
            add('note', relative, {'text': text}, 'OBSERVED')
            continue
        data = json.loads(text, parse_constant=lambda value: {'__nonfinite__': value})
        add('archive', relative, {'raw_utf8': text}, 'OBSERVED')
        if not isinstance(data, dict):
            raise ValueError('laboratory JSON must be an object')
        collections = {
            'connection_graph.json': (('nodes', 'node', 'OBSERVED'), ('edges', 'edge', 'INFERRED')),
            'HYPOTHESIS_QUEUE.json': (('queue', 'hypothesis', 'INFERRED'), ('excluded_already_tested_later_same_pair', 'excluded', 'INFERRED')),
        }.get(Path(relative).name, ())
        for key, kind, epistemic in collections:
            values = data.get(key, [])
            if not isinstance(values, list):
                raise ValueError('invalid ' + key)
            for i, value in enumerate(values):
                if not isinstance(value, dict) and kind != 'excluded':
                    raise ValueError('invalid ' + kind)
                if '__nonfinite__' in encoded(value):
                    manifest['quarantined'].append({'path': relative + '#' + key + '/' + str(i), 'reason': 'nonfinite number'})
                    kind_for_row = 'quarantine'
                elif isinstance(value, dict) and str(value.get('status', '')).lower() in {'blocked', 'discarded', 'excluded', 'dismissed', 'rejected'}:
                    kind_for_row = 'excluded'
                else:
                    kind_for_row = kind
                # Preserve source status verbatim in payload, without certifying it.
                state = 'SIMULATED' if isinstance(value, dict) and value.get('status') in ('simulated', 'SIMULATED') else epistemic
                add(kind_for_row, relative + '#' + key + '/' + str(i), value, state)
        add('metadata', relative, {k: v for k, v in data.items() if k not in {c[0] for c in collections}}, 'OBSERVED')
    if len(rows) > core.s.max_import_records:
        raise ValueError('import record budget exhausted')
    if time.monotonic() - started > core.s.max_cycle_seconds:
        raise ValueError('import time budget exhausted')
    fingerprint = digest(encoded(manifest).encode())
    batch = digest((FORMAT + '\n' + source + '\n' + fingerprint).encode())
    v = core.vault
    with v.transaction():
        old = v.db.execute('SELECT status FROM lab_batches WHERE namespace=? AND id=?', (v.ns, batch)).fetchone()
        if old:
            return {'batch_id': batch, 'status': old['status'], 'duplicate': True, 'records': 0}
        check_storage(core, sum(len(r[3].encode()) for r in rows) * 3 + 1_048_576)
        v.db.execute("UPDATE lab_batches SET status='superseded' WHERE namespace=? AND source=? AND status='active'", (v.ns, source))
        v.db.execute('INSERT INTO lab_batches VALUES(?,?,?,?,?,?)', (batch, v.ns, source, fingerprint, 'active', encoded(manifest)))
        for kind, ref, epistemic, raw, sha in rows:
            ident = digest((batch + '\n' + kind + '\n' + ref).encode())
            v.db.execute('INSERT INTO lab_records VALUES(?,?,?,?,?,?,?,?)', (ident, v.ns, batch, kind, 'lab:' + source + '/' + ref, epistemic, raw, sha))
        v.audit('lab_import', {'batch_id': batch, 'records': len(rows), 'manifest': manifest})
    return {'batch_id': batch, 'status': 'active', 'duplicate': False, 'records': len(rows), 'bytes': total, 'skipped': skipped, 'quarantined': manifest['quarantined'], 'verified_facts': 0}


def rollback_lab(core, batch_id):
    require_interactive(core)
    v = core.vault
    with v.transaction():
        row = v.db.execute('SELECT status FROM lab_batches WHERE namespace=? AND id=?', (v.ns, batch_id)).fetchone()
        if not row:
            raise KeyError(batch_id)
        v.db.execute("UPDATE lab_batches SET status='rolled_back' WHERE namespace=? AND id=?", (v.ns, batch_id))
        v.audit('lab_rollback', {'batch_id': batch_id, 'deletes': 0})
    return {'batch_id': batch_id, 'status': 'rolled_back', 'history_retained': True}


def search_lab(core, query, limit):
    terms = re.findall(r'\w+', query)[:12]
    if not terms:
        return []
    where = ' OR '.join('r.payload LIKE ? ESCAPE \'\\\'' for _ in terms)
    values = ['%' + t.replace('\\', '\\\\').replace('_', '\\_').replace('%', '\\%') + '%' for t in terms]
    rows = core.vault.db.execute(
        '''SELECT r.* FROM lab_records r JOIN lab_batches b
        ON b.namespace=r.namespace AND b.id=r.batch_id WHERE r.namespace=? AND b.status='active'
        AND r.kind NOT IN ('metadata','excluded','archive','quarantine') AND (''' + where + ') LIMIT ?',
        (core.vault.ns, *values, limit),
    ).fetchall()
    return [
        {
            'id': r['id'],
            'title': r['kind'] + ' ' + r['source_ref'],
            'excerpt': r['payload'][:500],
            'source_url': r['source_ref'],
            'kind': 'lab_' + r['kind'],
            'epistemic': r['epistemic'],
            'source_sha256': r['sha256'],
            'batch_id': r['batch_id'],
            'verified': False,
        }
        for r in rows
    ]


def export_lab_markdown(vault, output):
    """Inspectable original notes, including explicit withdrawal provenance."""
    rows = vault.db.execute(
        '''SELECT r.*,b.status batch_status FROM lab_records r JOIN lab_batches b
        ON b.namespace=r.namespace AND b.id=r.batch_id WHERE r.namespace=? AND r.kind='note' ''',
        (vault.ns,),
    ).fetchall()
    for row in rows:
        header = {
            'id': row['id'],
            'kind': 'lab_note',
            'source_ref': row['source_ref'],
            'batch_id': row['batch_id'],
            'batch_status': row['batch_status'],
            'epistemic': row['epistemic'],
            'verified': False,
            'payload_sha256': row['sha256'],
            'owner': vault.settings.owner,
            'namespace': vault.settings.namespace,
        }
        body = '---\n' + ''.join(k + ': ' + json.dumps(v, ensure_ascii=False) + '\n' for k, v in header.items()) + '---\n\n'
        body += json.loads(row['payload'])['text']
        (output / ('lab-' + row['id'] + '.md')).write_text(body, encoding='utf-8')
    return len(rows)
