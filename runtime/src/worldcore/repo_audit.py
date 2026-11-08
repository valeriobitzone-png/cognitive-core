"""Audits GitHub source evidence. Discovery alone grants NO trusted capabilities.

Online audit is opt-in; read-only; respects rate limits; never executes repo code.
A successful screen is NOT a full security audit, endorsement, or training.
"""
from __future__ import annotations
import datetime as dt
import base64
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

_ALLOWED={'MIT','Apache-2.0','BSD-2-Clause','BSD-3-Clause','ISC','MPL-2.0'}
_COPYLEFT={'GPL-2.0','GPL-3.0','AGPL-3.0','LGPL-2.1','LGPL-3.0'}
_SOURCE_EXT=('.py','.ts','.tsx','.go','.rs','.java','.cpp','.js')
_TEST_RE=re.compile(r'(^|/)(tests?|spec|__tests__)/|(^|/)(test_[^/]+|[^/]+\.test\.|[^/]+\.spec\.)',re.I)


def screen_snapshot(repo, files, *, license_id=None, maintenance_date=None, commit=None):
    """Screen file-manifest evidence; no unknown file or license is treated as verified.

    files: list of {path,sha,bytes?}. Must be collected by a trusted adapter;
    caller controls this input, so results are *screening*, not authentication.
    """
    if not isinstance(repo,str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):
        raise ValueError('invalid GitHub repository')
    if not isinstance(files,list) or len(files)>200000:raise ValueError('invalid manifest')
    paths={f['path']: f for f in files if isinstance(f,dict) and isinstance(f.get('path'),str)}
    source=[p for p in paths if p.endswith(_SOURCE_EXT) and not _TEST_RE.search(p) and len(p.split('/'))>1]
    tests=[p for p in paths if _TEST_RE.search(p) and p.endswith(_SOURCE_EXT)]
    workflows=[p for p in paths if p.startswith('.github/workflows/') and p.endswith(('.yml','.yaml'))]
    docs=[p for p in paths if re.search(r'(^|/)(readme|documentation|contributing)',p,re.I)]
    lock=[p for p in paths if p.endswith(('uv.lock','poetry.lock','package-lock.json','pnpm-lock.yaml','Cargo.lock','go.sum'))]
    security=[p for p in paths if p.upper() in ('SECURITY.MD','.GITHUB/SECURITY.MD')]
    lic=[p for p in paths if p.upper() in ('LICENSE','LICENSE.MD','LICENSE.TXT','COPYING')]
    license_status=('permissive' if license_id in _ALLOWED else 'copyleft_review' if license_id in _COPYLEFT else 'unknown_or_other')
    # A named license by itself is only evidence if a license file exists in this tree.
    # Repositories with permissive-looking SPDX metadata can contain additional
    # restrictions. Inline license contents (when available) always take priority.
    license_bodies=[str(paths[p].get('content',''))[:300000].lower() for p in lic]
    if any('commons clause' in x or 'you may not sell' in x or 'business source license' in x for x in license_bodies):
        license_status='restricted_review'
    permitted=license_status=='permissive' and bool(lic)
    signals={'license_verified':bool(lic) and license_status!='unknown_or_other',
             'source_present':bool(source),'tests_present':bool(tests),'ci_present':bool(workflows),
             'documentation_present':bool(docs),'security_policy_present':bool(security),'lockfile_present':bool(lock)}
    if maintenance_date:
        try:
            age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(maintenance_date.replace('Z','+00:00'))).days
            signals['maintained_in_365_days']=0<=age<=365
        except (ValueError,TypeError):signals['maintained_in_365_days']=None
    else:signals['maintained_in_365_days']=None
    # Only an explicit code-inspection record can promote beyond manifest screening.
    gate='review_required'
    if permitted and all(signals[k] for k in ('source_present','tests_present','ci_present','documentation_present')):
        gate='manifest_screened'
    return {'repo':repo,'commit':commit,'license':license_id,'license_status':license_status,
            'reuse_policy':'must_review_license' if not permitted else 'license_preliminarily_permissive',
            'gate':gate,'signals':signals,'evidence_paths':{k:sorted(v)[:6] for k,v in
                [('source',source),('tests',tests),('ci',workflows),('license',lic),('docs',docs),('security',security),('lock',lock)]},
            'source_executed':False,'security_audit_completed':False,'model_trained_on_code':False,
            'trusted_for_autonomous_execution':False}


def authorized_for_capability(audit):
    """Never install/execute 3rd-party code from a discovery/screening result."""
    return audit.get('gate')=='human_approved' and audit.get('security_audit_completed') is True and audit.get('license_status')=='permissive'


class GitHubReadOnlyAuditor:
    """GitHub REST manifest verifier. Network opt-in; token belongs to the operator.

    Use a verified pinned SHA, rate limits, and bounded file lists. Never runs code.
    """
    def __init__(self,token=None,timeout=10):self.token=token;self.timeout=timeout
    def _fetch(self,path):
        req=urllib.request.Request('https://api.github.com/'+path,headers={
            'Accept':'application/vnd.github+json','User-Agent':'WorldCore-ReadOnly-Auditor/0.7',
            **({'Authorization':'Bearer '+self.token} if self.token else {})})
        with urllib.request.urlopen(req,timeout=self.timeout) as res:
            b=res.read(8_000_001)
            if len(b)>8_000_000:raise ValueError('oversized GitHub response')
        return json.loads(b)
    def _blob(self,repo,sha):
        raw=self._fetch('repos/'+repo+'/git/blobs/'+sha)
        if raw.get('encoding')!='base64':raise ValueError('unsupported blob encoding')
        return base64.b64decode(raw['content']).decode('utf-8','replace')[:300000]
    def audit(self,repo):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('invalid repo name')
        meta=self._fetch('repos/'+repo)
        default=meta['default_branch'];commit=self._fetch('repos/'+repo+'/commits/'+urllib.parse.quote(default,safe=''))['sha']
        tree=self._fetch('repos/'+repo+'/git/trees/'+commit+'?recursive=1')
        if tree.get('truncated'):return {'repo':repo,'gate':'review_required','reason':'incomplete_git_tree','commit':commit}
        files=[{'path':i['path'],'sha':i['sha']} for i in tree.get('tree',[]) if i.get('type')=='blob']
        lic=meta.get('license') or {}
        audit=screen_snapshot(repo,files,license_id=lic.get('spdx_id'),maintenance_date=meta.get('pushed_at'),commit=commit)
        audit['evidence']={'repo_url':meta.get('html_url'),'commit_url':f'https://github.com/{repo}/commit/{commit}',
                           'snapshot_sha256':hashlib.sha256(json.dumps(files,sort_keys=True).encode()).hexdigest(),
                           'files_in_tree':len(files),'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),
                           'data_source':'GitHub REST pinned commit'}
        # Inspect actual pinned license and representative code/test/CI files.
        candidates=audit['evidence_paths']
        inspected={}
        try:
            for kind in ('license','source','tests','ci'):
                if not candidates[kind]:continue
                filename=candidates[kind][0]
                blob=next(f for f in files if f['path']==filename)
                body=self._blob(repo,blob['sha'])
                inspected[kind]={'path':filename,'blob_sha':blob['sha'],'read_bytes':len(body.encode()),
                                 'nonempty':bool(body.strip())}
                if kind=='license':
                    lower=body.lower()
                    if 'commons clause' in lower or 'you may not sell' in lower or 'business source license' in lower:
                        audit['license_status']='restricted_review';audit['reuse_policy']='must_review_license'
                        audit['gate']='review_required'
                    if len(body)<100:audit['gate']='review_required'
                if kind=='tests' and len(body)<60:audit['gate']='review_required'
        except (KeyError,ValueError,urllib.error.URLError) as exc:
            audit['gate']='review_required'
            audit['inspection_error']=type(exc).__name__
        audit['inspected_pinned_files']=inspected
        if meta.get('archived') or meta.get('disabled'):audit['gate']='review_required'
        if audit['license_status']!='permissive':audit['gate']='review_required'
        if not all(x in inspected and inspected[x]['nonempty'] for x in ('license','source','tests','ci')):
            audit['gate']='review_required'
        # Quality flag means ONLY eligible for human code review; never execution.
        if audit['gate']=='manifest_screened':audit['gate']='source_screened_needs_human_review' 
        audit['warnings']=['Manifest quality is NOT a source code security review; license may vary across files',
                          'No repository code executed or downloaded for training']
        return audit


def audit_catalog(candidates,output,*,token=None,limit=30,delay=0.3):
    """Use on an Internet-connected machine, not inside an LLM prompt loop."""
    if not 1<=limit<=1000:raise ValueError('limit out of bounds')
    auditor=GitHubReadOnlyAuditor(token)
    results=[]
    for item in candidates[:limit]:
        repo=item['repo']
        try:results.append(auditor.audit(repo))
        except (urllib.error.URLError,KeyError,ValueError,TimeoutError) as e:
            results.append({'repo':repo,'gate':'review_required','error':type(e).__name__,'reason':str(e)[:160]})
        time.sleep(delay)
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(results,indent=2,ensure_ascii=False))
    return {'processed':len(results),'source_screened':sum(r.get('gate')=='source_screened_needs_human_review' for r in results),
            'review_required':sum(r.get('gate')!='source_screened_needs_human_review' for r in results)}
