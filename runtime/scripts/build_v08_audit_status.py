"""Publish a complete candidate *disposition*, not a fictional complete security audit.

No approval is inferred from repository stars, popularity or README evidence.
"""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
candidates=json.loads((root/'catalog/repository_candidates_v06.json').read_text())
reviewed=json.loads((root/'catalog/reviewed_evidence_v08.json').read_text())['records']
indexed={i['repo'].lower():i for i in reviewed}
rows=[]
for i in candidates:
    repo=i['repo']
    review=indexed.get(repo.lower(),{})
    evidence=review.get('evidence',{})
    has_license='license' in evidence
    has_source='source' in evidence
    has_ci='ci' in evidence
    has_tests='tests' in evidence
    license_type=review.get('license_detected','NOT_VERIFIED')
    restrictive=license_type in ('GPL-3.0','AGPL-3.0','Apache-2.0-with-Commons-Clause','UNKNOWN_LICENSE')
    status='source_and_quality_screened' if all([has_license,has_source,has_ci,has_tests]) else 'partial_source_review' if evidence else 'no_direct_code_review'
    rows.append({'repo':repo,'domain':i.get('domain'),'screen_status':status,
         'license_observed':license_type,'license_text_evidence':evidence.get('license'),
         'representative_code':evidence.get('source'),'test_file':evidence.get('tests'),
         'ci_file':evidence.get('ci'),
         'candidate_summary':i.get('original_capability_summary'),
         'flags':(['copyleft_or_restricted_license_review'] if restrictive else [])+(
               ['missing_test_evidence'] if not has_tests else [])+(['missing_ci_evidence'] if not has_ci else [])+(
               ['license_not_directly_verified'] if not has_license else []),
         'training_rights_cleared':False,
         'integration_approved':False,'code_security_audit_complete':False,
         'tests_executed':False,'gate':'QUARANTINE',
         'next_step':'Network-enabled pinned-commit repository inventory, license analysis and CI/tests in sandbox'})
if len(rows)!=len({r['repo'].lower() for r in rows}):raise SystemExit('duplicate repo candidate')
output={'as_of':'2026-10-30','audit_type':'COMPLETE CANDIDATE DISPOSITION; NOT COMPLETE REPOSITORY AUDIT',
 'repo_count':len(rows),'with_direct_evidence':sum(r['screen_status']!='no_direct_code_review' for r in rows),
 'source_and_quality_screened':sum(r['screen_status']=='source_and_quality_screened' for r in rows),
 'quarantined':len(rows),'approved':0,'license_reuse_cleared':0,
 'why_not_full_audit':'Sandbox has no direct network access to download 246 pinned git trees. Github connector review covered selected files only; no source execution.',
 'policy':'No ability or dependency installed from this catalog until license, code, security and applicable use are reviewed.',
 'records':rows}
p=root/'catalog/audit_disposition_246_v08.json';p.write_text(json.dumps(output,indent=2,ensure_ascii=False))
print(json.dumps({k:v for k,v in output.items() if k!='records'},indent=2))
