"""Read-only opt-in GitHub manifest screening with provenance and license gates."""
import argparse,json,os
from pathlib import Path
from worldcore.repo_audit import audit_catalog
p=argparse.ArgumentParser()
p.add_argument('--catalog',default='catalog/repository_candidates_v06.json')
p.add_argument('--output',required=True)
p.add_argument('--limit',type=int,default=30)
a=p.parse_args()
print(audit_catalog(json.loads(Path(a.catalog).read_text()),a.output,token=os.environ.get('GITHUB_TOKEN'),limit=a.limit))
