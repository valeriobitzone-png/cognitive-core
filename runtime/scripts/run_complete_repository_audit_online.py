"""Opt-in online audit of every discovered candidate, resumable and fail-closed.

Requires network + GITHUB_TOKEN for adequate authenticated GitHub API rate limit.
No repo code is executed, installed or used for model training. This screens
source, license, test and CI files; deeper security audits still require review.
"""
from __future__ import annotations
import argparse,json,os,time
from pathlib import Path
from worldcore.repo_audit import GitHubReadOnlyAuditor


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--candidates',default='catalog/repository_candidates_v06.json')
    ap.add_argument('--output',default='catalog/online_source_screening.json')
    ap.add_argument('--delay',type=float,default=1)
    ap.add_argument('--limit',type=int,default=1000)
    args=ap.parse_args()
    if not os.getenv('GITHUB_TOKEN'):
        raise SystemExit('GITHUB_TOKEN required; unauthenticated quotas insufficient for this audit')
    if not .1<=args.delay<=120 or not 1<=args.limit<=5000:
        raise SystemExit('invalid throttling/limit')
    raw=json.loads(Path(args.candidates).read_text())
    target=Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
    previous={}
    if target.exists():
        for row in json.loads(target.read_text()).get('results',[]):previous[row['repo']]=row
    auditor=GitHubReadOnlyAuditor(token=os.environ['GITHUB_TOKEN'],timeout=20)
    count=0
    for item in raw[:args.limit]:
        repo=item['repo']
        if repo in previous and previous[repo].get('commit'):continue
        try:
            audit=auditor.audit(repo)
        except Exception as exc:
            audit={'repo':repo,'gate':'review_required','reason':'online_audit_error',
                   'error_type':type(exc).__name__,'error':str(exc)[:180]}
        audit['trusted_for_autonomous_execution']=False
        audit['security_audit_completed']=False
        previous[repo]=audit;count+=1
        target.write_text(json.dumps({'mode':'read_only_source_screening','results':list(previous.values())},indent=2,ensure_ascii=False))
        if count%10==0:print(f'screened this run: {count}; unique results: {len(previous)}',flush=True)
        time.sleep(args.delay)
    print(json.dumps({'processed_this_run':count,'known':len(previous),
                     'human_review_and_sandbox_tests_still_required':True}))

if __name__=='__main__':main()
