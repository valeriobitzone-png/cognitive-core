import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def test_audit_40_reviewed_but_none_auto_promoted():
    raw=json.loads((ROOT/'catalog/reviewed_evidence_v09.json').read_text())
    assert raw['review_count']==40
    assert raw['with_direct_evidence']==39
    assert not raw['all_246_audited']
    assert len({r['repo'] for r in raw['records']})==40
    assert all(not r['autonomous_code_execution_allowed'] for r in raw['records'])
    assert all(not r['security_audit_complete'] for r in raw['records'])
    assert all(not r['license_reuse_cleared'] for r in raw['records'])
