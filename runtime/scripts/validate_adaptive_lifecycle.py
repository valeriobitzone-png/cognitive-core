"""Reproduce adaptive DATA lifecycle; controlled fixtures, no real-user claims."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import hashlib
import json
import mmap
import random
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from worldcore import WorldCore


def source_hashes():
    result={}
    for p in sorted((ROOT/'src/worldcore').rglob('*')):
        if not p.is_file() or '__pycache__' in p.parts:continue
        with p.open('rb') as f:data=mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ)[:] if p.stat().st_size else b''
        result[str(p.relative_to(ROOT))]=hashlib.sha256(data).hexdigest()
    return result


def samples(batch,offset):
    rng=random.Random(531);start=datetime(2024+batch,6,1,tzinfo=timezone.utc)
    rows=[]
    for i in range(120):
        at=start+timedelta(minutes=i*3);x=(i*17)%31
        rows.append({'sample_id':f'b{batch}_{i}','environment':'controlled_fixture','action':'move',
            'before':{'x':x},'after':{'x':x+offset+rng.uniform(-1,1)},'source':'observed',
            'provenance':'controlled_synthetic_host_fixture_not_real_user',
            'before_at':at.isoformat(),'observed_at':(at+timedelta(seconds=1)).isoformat(),
            'available_at':(at+timedelta(seconds=2)).isoformat()})
    return rows


def main():
    destination=Path(sys.argv[1]).resolve();destination.mkdir(parents=True,exist_ok=True)
    database=destination/'lifecycle.db'
    if database.exists():raise ValueError('use a new output directory; never overwrite evidence')
    before=source_hashes();trace=[]
    with WorldCore(database) as w:
        w.remember('fixture','preference','prepare concise drafts',source='controlled_host_fixture')
        w.remember('fixture','preference','prepare concise drafts with evidence',source='controlled_host_fixture')
        assert len(w.history('fixture','preference'))==2
        for batch,offset in [(0,10),(1,12)]:
            result=w.refresh_adaptive_world('fixture','numeric',samples(batch,offset),
                as_of=f'{2025+batch}-01-01T00:00:00Z')
            assert result['status']=='promoted';trace.append(result)
        for expected in ('rolled_back','suspended'):
            ids=[w.predict_calibrated_world('fixture','numeric',{'x':12},'move',persist=True)['prediction_id'] for _ in range(10)]
            for identifier in ids:w.resolve_calibrated_prediction('fixture',identifier,{'x':1000},source='host_verified')
            status=w.adaptive_status('fixture','numeric')
            assert status['events'][0]['status']==expected;trace.append(status['events'][0])
        w.register_adaptive_procedure('fixture','meeting','draft',['Prepare a draft','Request permission before sending'])
        for i in range(20):choice=w.record_adaptive_procedure_outcome('fixture','meeting','draft',f'pass{i}',True,source='host_verified')
        assert choice['status']=='recommended' and not choice['execution_authorized'];trace.append(choice)
        for i in range(40):choice=w.record_adaptive_procedure_outcome('fixture','meeting','draft',f'fail{i}',False,source='host_verified')
        assert choice['status']=='abstain';trace.append(choice)
        assert w.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
    after=source_hashes();assert before==after
    report={'verified':True,'source_files_unchanged':len(before),'source_sha256':after,
            'observation_nature':'controlled synthetic fixtures; actual engine/SQLite; no LLM or live host loop',
            'memory_versions':2,'trace':trace,'sqlite_integrity':'ok','code_generated_or_executed_from_procedures':False}
    (destination/'report.json').write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ('source_sha256','trace')}))


if __name__=='__main__':main()
