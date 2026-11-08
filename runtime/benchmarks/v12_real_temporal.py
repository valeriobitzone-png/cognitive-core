"""Frozen-protocol real filesystem observations, then prospective forecasts."""
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldcore import WorldCore
from worldcore.engine import utcnow

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/'evidence'/'temporal'


def run():
    protocol_path=Path(__file__).with_name('v12_protocol.json')
    protocol=json.loads(protocol_path.read_text())
    rng=random.Random(protocol['seed'])
    DEST.mkdir(parents=True,exist_ok=True)
    rows=[];future=[]
    with tempfile.TemporaryDirectory(prefix='worldcore-real-v12-') as directory:
        folder=Path(directory)
        def prepare(identifier):
            file=folder/(identifier+'.bin')
            file.write_bytes(b'a'*(rng.randint(0,10)*64))
            return file, {'size':float(file.stat().st_size)}
        def act(file, count):
            with file.open('ab') as stream:stream.write(b'b'*count)
            return {'size':float(file.stat().st_size)}
        for i in range(protocol['training_observations']):
            file,before=prepare('train'+str(i));before_at=utcnow()
            after=act(file,rng.randint(56,72));observed_at=utcnow()
            rows.append({'sample_id':str(i),'environment':f'episode{i}','action':protocol['action'],
                         'before':before,'after':after,'source':'observed','provenance':'os.stat_after_real_append_in_temporary_directory',
                         'before_at':before_at,'observed_at':observed_at,'available_at':utcnow()})
        with WorldCore(DEST/'forecast_ledger.db') as w:
            trained=w.train_calibrated_dynamics('benchmark','filesystem',rows,as_of=utcnow(),coverage=protocol['coverage_target'])
            ood=[w.predict_calibrated_world('benchmark','filesystem',{'size':x},protocol['action']) for x in (-1,10000000)]
            w.train_calibrated_dynamics('benchmark','filesystem_shift',rows,as_of=utcnow(),coverage=protocol['coverage_target'])
            for phase,count in [('forward',protocol['forward_observations']),('shift',protocol['shift_observations'])]:
                for i in range(count):
                    file,before=prepare(phase+str(i))
                    prediction=w.predict_calibrated_world('benchmark','filesystem' if phase=='forward' else 'filesystem_shift',before,protocol['action'],persist=True)
                    after=act(file,rng.randint(56,72) if phase=='forward' else 200)
                    observed_at=utcnow()
                    resolution=None
                    if prediction['status']=='predicted':
                        resolution=w.resolve_calibrated_prediction('benchmark',prediction['prediction_id'],after,observed_at=observed_at,source='host_verified')
                    future.append({'phase':phase,'index':i,'before':before,'prediction':prediction,'actual':after,
                                   'observed_at':observed_at,'resolution':resolution})
            shift_metrics=w.calibrated_prediction_metrics('benchmark','filesystem_shift')
            metrics=w.calibrated_prediction_metrics('benchmark','filesystem')
            integrity=w.db.execute('PRAGMA integrity_check').fetchone()[0]
    accepted=[r for r in future if r['phase']=='forward' and r['resolution']]
    shifted=[r for r in future if r['phase']=='shift']
    from worldcore.calibrated import wilson
    hits=sum(r['resolution']['covered'] for r in accepted)
    summary={'protocol_sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
             'training':trained, 'forward':{'total':protocol['forward_observations'],'accepted':len(accepted),
             'joint_coverage':hits/len(accepted) if accepted else None,'coverage_wilson_95':wilson(hits,len(accepted)),
             'mae':sum(r['resolution']['mae'] for r in accepted)/len(accepted) if accepted else None,
             'persistence_mae':sum(abs(r['before']['size']-r['actual']['size']) for r in accepted)/len(accepted) if accepted else None},
             'shift':{'total':len(shifted),'abstained':sum(r['prediction']['status']=='abstain' for r in shifted)},
             'ood':ood,'all_resolved_metrics':metrics,'shift_metrics':shift_metrics,'db_integrity':integrity,'limitations':protocol['limitations']}
    (DEST/'observations.json').write_text(json.dumps(rows,indent=2))
    (DEST/'forward_outcomes.json').write_text(json.dumps(future,indent=2))
    (DEST/'summary.json').write_text(json.dumps(summary,indent=2))
    print(json.dumps({k:v for k,v in summary.items() if k!='training'},indent=2))
    print('TRAINING',trained['status'])

if __name__=='__main__':run()
