"""Verify packaged release checksums and standalone SQLite integrity."""
from pathlib import Path
import hashlib
import json
import sqlite3
import sys


def digest_file(path):
    """Read exactly the declared length, including empty logs without an EOF read."""
    digest=hashlib.sha256()
    size=path.stat().st_size
    remaining=size
    with path.open('rb',buffering=0) as stream:
        while remaining:
            data=stream.read(min(remaining,1024*1024))
            if not data:
                raise OSError('file truncated during verification')
            digest.update(data)
            remaining-=len(data)
    if path.stat().st_size!=size:
        raise OSError('file size changed during verification')
    return digest.hexdigest()


def main():
    root=Path(__file__).resolve().parents[1]
    manifest=root/'MANIFEST_SHA256.json'
    if not manifest.exists():
        print('MANIFEST_SHA256.json missing',file=sys.stderr)
        return 1
    with manifest.open('rb',buffering=0) as stream:
        records=json.loads(stream.read(manifest.stat().st_size))
    errors=[]
    for relative,expected in records.items():
        file=root/relative
        if not file.is_file():
            errors.append(f'{relative}: missing')
            continue
        try:
            if digest_file(file)!=expected:errors.append(f'{relative}: sha mismatch')
        except OSError as exc:
            errors.append(f'{relative}: {exc}')
    databases=list((root/'training-artifacts').rglob('*.db'))
    for database in databases:
        connection=sqlite3.connect(f'file:{database}?mode=ro',uri=True)
        try:
            if connection.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                errors.append(str(database)+': integrity')
        finally:
            connection.close()
    print('FILES',len(records),'DBS',len(databases),'ERRORS',len(errors))
    for item in errors:print(item,file=sys.stderr)
    return 1 if errors else 0


if __name__=='__main__':
    raise SystemExit(main())
