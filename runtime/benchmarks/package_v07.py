"""Deterministic source+wheel+data archive with sha256 manifest."""
from pathlib import Path
import hashlib,json,zipfile,datetime
ROOT=Path(__file__).resolve().parents[1]
OUT=Path('/mnt/data/WorldCore_v0.7_PREDICTIVE_STATE_RESEARCH_ALPHA.zip')
ALLOWED={'src','scripts','adapters','docs','catalog','training-artifacts','tests','benchmarks','examples','fixtures','.github','dist'}
ROOTFILES={'README.md','LICENSE','pyproject.toml','.gitignore'}
def included(p):
    r=p.relative_to(ROOT)
    if '__pycache__' in r.parts or '.pytest_cache' in r.parts or any(part.endswith('.egg-info') for part in r.parts):return False
    if p.suffix in ('.pyc','.pyo','.log') or p.name in ('SHA256_MANIFEST.json','.DS_Store'):return False
    return r.parts[0] in ALLOWED or str(r) in ROOTFILES
files=sorted(p for p in ROOT.rglob('*') if p.is_file() and included(p))
manifest={'generated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'release':'0.7.0','files':[{'path':str(p.relative_to(ROOT)),'size':p.stat().st_size,
                              'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files]}
manifest_bytes=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode()
(ROOT/'SHA256_MANIFEST.json').write_bytes(manifest_bytes)
with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=8) as z:
    for p in files:z.write(p,str(p.relative_to(ROOT)))
    z.writestr('SHA256_MANIFEST.json',manifest_bytes)
with zipfile.ZipFile(OUT) as z:
    assert z.testzip() is None
    embedded=json.loads(z.read('SHA256_MANIFEST.json'))
    assert len(embedded['files'])==len(files)
    for f in embedded['files']:
        assert hashlib.sha256(z.read(f['path'])).hexdigest()==f['sha256']
print(json.dumps({'path':str(OUT),'files':len(files),'size_bytes':OUT.stat().st_size,
                  'sha256':hashlib.sha256(OUT.read_bytes()).hexdigest(),'integrity':'ok'},indent=2))
