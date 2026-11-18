"""Small real filesystem environment: observed OS effects, not invented transition rows.
Each episode uses a separate temporary directory and creates an actual 64-byte file.
Train/validate on 3 distinct directories, predict a 4th unseen directory.
No permission to access user files; uses TemporaryDirectory exclusively.
"""
import json,random,tempfile,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldcore import WorldCore

def _state(path):
    files=list(path.iterdir());return {'file_count':float(len(files)),'total_bytes':float(sum(f.stat().st_size for f in files))}

def _episode(path,initial):
    for j in range(initial): (path/f'initial_{j}.dat').write_bytes(b'*'*64)
    before=_state(path)
    (path/'new.txt').write_bytes(b'+'*64)
    after=_state(path)
    return before,after

def run():
    rng=random.Random(410)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='worldcore-09-filesys-') as root:
        for env in ('folderA','folderB','folderC'):
            for idx in range(24):
                d=Path(root)/env/str(idx);d.mkdir(parents=True)
                a,b=_episode(d,rng.randint(0,10))
                rows.append({'environment':env,'before':a,'after':b,'action':'add_64byte_file','source':'observed'})
        with WorldCore(':memory:') as core:
            trained=core.train_shared_dynamics('isolated','filesystem_64byte',rows)
            d=Path(root)/'never_seen_folder'/ 'new_episode';d.mkdir(parents=True)
            actual_before,actual_after=_episode(d,5)
            prediction=core.predict_shared_dynamics('isolated','filesystem_64byte',actual_before,'add_64byte_file')
            guessed=prediction.get('predicted_state',prediction.get('predicted_next_state'))
            return {'train_observations':len(rows),'created_real_files':True,
              'trained':trained['status'],'validation_environment':'folderC',
              'never_seen_environment':'never_seen_folder','prediction':prediction,'actual':actual_after,
              'limitations':'Real sandbox file effects but trivial fixed-size synthetic workload, not universal environment understanding'}
if __name__=='__main__':
 obj=run();p=Path(__file__).resolve().parents[1]/'training-artifacts/v09_real_filesystem.json'
 p.write_text(json.dumps(obj,indent=2));print(json.dumps(obj,indent=2)[:2800])
