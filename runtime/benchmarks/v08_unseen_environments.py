"""Unseen simulation tasks: genuine held-out environments within familiar laws.

All worlds are SYNTHETIC; no generalized world comprehension is claimed.
"""
import json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from worldcore import WorldCore

def run():
    sample=[]
    # Different start distributions, identical physical law within declared family.
    for idx,env in enumerate(['robot_lab_A','robot_lab_B','robot_lab_C']):
        for x in range(40):
            for action,delta in [('move_forward',2.),('move_back',-1.)]:
                before={'position':x*1.25+idx*11.,'velocity':3.}
                after={'position':before['position']+delta,'velocity':3.}
                sample.append({'environment':env,'action':action,'before':before,'after':after,'source':'observed'})
    with WorldCore(':memory:') as core:
        trained=core.train_shared_dynamics('test','toy_robots',sample)
        # This environment wasn't included in training NOR the internal holdout.
        pred=core.predict_world_state('test','robot_lab_Z',{'position':17.5,'velocity':3.},'move_forward',family='toy_robots')
        unseen_action=core.predict_world_state('test','robot_lab_Z',{'position':17.5,'velocity':3.},'jump',family='toy_robots')
        outlier=core.predict_world_state('test','robot_lab_Z',{'position':999999.,'velocity':3.},'move_forward',family='toy_robots')
        return {'training':len(sample),'training_envs':['robot_lab_A','robot_lab_B'],
          'validation_env':'robot_lab_C','never_seen_env':'robot_lab_Z',
          'trained':trained['status'],'trained_action_statuses':trained.get('actions'),
          'new_environment_result':pred,'unseen_action':unseen_action,'out_of_training_range':outlier,
          'note':'Synthetic same-law transfer; unseen domains and new laws are not understood automatically.'}

if __name__=='__main__':
    res=run();p=Path(__file__).resolve().parents[1]/'training-artifacts/v08_unseen_environments.json'
    p.write_text(json.dumps(res,indent=2,ensure_ascii=False));print(json.dumps(res,indent=2)[:5000])
