"""Versioned, scoped local state transfer. Never restores execution grants.

Only data is imported into the installed schema, never SQL or configuration.
Restore requires a new home; existing databases are never merged or overwritten.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from .config import Settings


FORMAT='cognitive-core-state-v1'


def _tables(db,scope_columns):
    tables={}
    for row in db.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY rowid"):
        name,sql=row
        if name.startswith('sqlite_') or not sql or sql.upper().startswith('CREATE VIRTUAL TABLE'):
            continue
        columns=[r[1] for r in db.execute('PRAGMA table_info("'+name.replace('"','""')+'")')]
        if set(scope_columns)<=set(columns):tables[name]=columns
    return tables


@contextmanager
def _new_folder(target):
    target=Path(target)
    if target.exists() or target.is_symlink():raise FileExistsError(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.cognitive-transfer-',dir=target.parent))
    try:
        yield stage
        if target.exists() or target.is_symlink():raise FileExistsError(target)
        stage.rename(target)
    finally:
        if stage.exists():shutil.rmtree(stage)


def export_state(core,output):
    """Export only the bound owner/namespace, with a consistent two-store snapshot."""
    world=core.worldcore
    core.drive  # Ensure the Opportunity Pool schema is included even when empty.
    stores={}
    with _new_folder(output) as stage:
        with core.vault.transaction(),world._transaction():
            count=core.vault.export_markdown(stage)
            for name,db,scope in (
                ('vault',core.vault.db,{'namespace':core.vault.ns}),
                ('worldcore',world.db,{'owner':core.s.owner,'space':core.s.namespace})):
                tables={}
                for table in _tables(db,scope):
                    where=' AND '.join('"'+key+'"=?' for key in scope)
                    tables[table]=[dict(row) for row in db.execute(
                        'SELECT * FROM "'+table.replace('"','""')+'" WHERE '+where,tuple(scope.values()))]
                stores[name]=tables
        payload={'format':FORMAT,'owner':core.s.owner,'namespace':core.s.namespace,'stores':stores}
        body=json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False)
        envelope={'sha256':hashlib.sha256(body.encode()).hexdigest(),'payload':payload}
        path=stage/'state.json'
        path.write_text(json.dumps(envelope,ensure_ascii=False,indent=2),encoding='utf-8')
        path.chmod(0o600)
    return {'path':str(output),'format':FORMAT,'exported_documents':count,
            'owner':core.s.owner,'namespace':core.s.namespace}


def restore_state(folder,home):
    """Restore into a new home. Expire grants and revoke old worker leases.

    The checksum detects accidental edits, not authenticity. Treat the export
    as private operator data; restoration does not verify its factual claims.
    """
    from .engine import CognitiveCore
    envelope=json.loads((Path(folder)/'state.json').read_text(encoding='utf-8'))
    payload=envelope['payload']
    body=json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False)
    if envelope['sha256']!=hashlib.sha256(body.encode()).hexdigest():
        raise ValueError('state checksum mismatch')
    if payload['format']!=FORMAT or set(payload['stores'])!={'vault','worldcore'}:
        raise ValueError('unsupported state format')
    with _new_folder(home) as stage:
        core=CognitiveCore(Settings(home=stage,owner=payload['owner'],namespace=payload['namespace']))
        try:
            core.drive
            world=core.worldcore
            for name,db,scope in (
                ('vault',core.vault.db,{'namespace':core.vault.ns}),
                ('worldcore',world.db,{'owner':core.s.owner,'space':core.s.namespace})):
                schema=_tables(db,scope)
                data=payload['stores'][name]
                if set(data)!=set(schema):raise ValueError('state schema differs from installed runtime')
                with (core.vault.transaction() if name=='vault' else world._transaction()):
                    for table,columns in schema.items():
                        for record in data[table]:
                            if set(record)!=set(columns) or any(record[key]!=value for key,value in scope.items()):
                                raise ValueError('invalid state record or foreign scope')
                            row=dict(record)
                            if name=='vault' and table=='jobs':
                                row['lease_token']='';row['lease_until']=0
                                if row['status']=='running':row['status']='pending'
                            if name=='worldcore' and table=='approvals' and row['status'] in ('pending','approved'):
                                row['status']='denied'
                            quoted=','.join('"'+c+'"' for c in columns)
                            db.execute('INSERT INTO "'+table+'" ('+quoted+') VALUES ('+','.join('?' for _ in columns)+')',
                                       tuple(row[c] for c in columns))
                    if name=='vault' and core.vault.fts:
                        db.execute('INSERT INTO documents_fts(id,title,text) SELECT id,title,text FROM documents')
                    if name=='worldcore':
                        if world.knowledge_fts:
                            db.execute('''INSERT INTO knowledge_fts(chunk_id,title,content)
                                SELECT k.chunk_id,s.title,k.content FROM knowledge_chunks k JOIN knowledge_sources s
                                ON s.owner=k.owner AND s.space=k.space AND s.doc_id=k.doc_id''')
                        if world._intel_fts:
                            db.execute('''INSERT INTO intel_index(owner,space,source,record_id,version,title,summary)
                                SELECT owner,space,source,record_id,version,title,summary FROM intel_records''')
            core.vault.audit('restore',{'format':FORMAT,'approvals_revoked':True,'leases_revoked':True})
        finally:core.close()
    return {'path':str(home),'owner':payload['owner'],'namespace':payload['namespace'],
            'approvals_revoked':True,'leases_revoked':True}
