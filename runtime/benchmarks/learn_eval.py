"""Reproducible, FINITE synthetic training & never-seen-ID holdout checks.

Only pseudorandom synthetic observations from explicitly documented toy processes.
Not real world knowledge, language model training, or a claim of general intelligence.
"""
from __future__ import annotations
import argparse
import json
import math
import random
import time
from pathlib import Path

from worldcore.engine import WorldCore


def logistic(z):
    return 1/(1+math.exp(-z))


def line_rows(prefix, rng, size, shifted=False):
    result=[]
    for i in range(size):
        x,y=rng.random(),rng.random()
        p=logistic((-2.8 + 5.8*x-1.5*y) if not shifted else (1.8 - 4.0*x+0.8*y))
        result.append({'id':f'{prefix}{i:06d}','features':{'x':x,'y':y},'outcome':rng.random()<p})
    return result


def xor_rows(prefix, rng, size, augmented):
    result=[]
    for i in range(size):
        x,y=rng.randint(0,1),rng.randint(0,1)
        p=.96 if x^y else .04
        features={'x':float(x),'y':float(y)}
        if augmented:features['xy']=float(x*y)
        result.append({'id':f'{prefix}{i:06d}','features':features,'outcome':rng.random()<p})
    return result


def transitions(prefix,rng,size):
    result=[]
    dynamics={('cold','heat'):'warm',('warm','heat'):'hot',('hot','heat'):'hot',
              ('cold','cool'):'cold',('warm','cool'):'cold',('hot','cool'):'warm'}
    for i in range(size):
        state=rng.choice(['cold','warm','hot'])
        action=rng.choice(['heat','cool'])
        next_state=dynamics[(state,action)] if rng.random()<.89 else rng.choice(['cold','warm','hot'])
        result.append({'id':f'{prefix}{i:06d}','current_state':state,'action':action,'next_state':next_state})
    return result


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,default=Path('training-artifacts'))
    ap.add_argument('--seed',type=int,default=20261029)
    ap.add_argument('--train-size',type=int,default=12000)
    ap.add_argument('--holdout-size',type=int,default=4000)
    args=ap.parse_args()
    if args.train_size<200 or args.train_size>30000 or args.holdout_size<100 or args.holdout_size>20000:
        ap.error('invalid train/holdout sizes')
    args.output.mkdir(parents=True,exist_ok=True)
    db=args.output/'worldcore_synthetic_training.db'
    # Re-running the script recreates ONLY this dedicated synthetic benchmark DB.
    if db.exists():db.unlink()
    for suffix in ('-wal','-shm'):
        f=Path(str(db)+suffix)
        if f.exists():f.unlink()
    start=time.perf_counter()
    rng=random.Random(args.seed)
    report={'benchmark':'WorldCore synthetic learning verification','seed':args.seed,
            'train_rows_per_scenario':args.train_size,'holdout_rows_per_scenario':args.holdout_size,
            'dataset':'toy synthetic pseudorandom events only, known generation rules',
            'data_sources':[],'cases':{},'limitations':[
            'This does not train an LLM or transfer the model knowledge of ChatGPT.',
            'No evidence of general intelligence or real-world predictive ability.',
            'The holdout data have different IDs; independence of real external data is not established.',
            'Synthetic rules are stationary except the intentional distribution-shift test.',
            'No actions are autonomously executed by the learning components.']}
    with WorldCore(db) as world:
        world.create_model('synthetic','linear',['x','y'],provenance='synthetic')
        tr=line_rows('lin-train-',rng,args.train_size)
        world.train_model('synthetic','linear',tr)
        held=line_rows('lin-holdout-',rng,args.holdout_size)
        report['cases']['linear_independent_holdout']=world.evaluate_model('synthetic','linear',held)
        drift=line_rows('lin-drift-',rng,args.holdout_size,shifted=True)
        report['cases']['linear_distribution_shift']=world.evaluate_model('synthetic','linear',drift)
        report['drift_check']=world.detect_drift(report['cases']['linear_independent_holdout'], report['cases']['linear_distribution_shift'])

        for augmented in [False, True]:
            names=['x','y','xy'] if augmented else ['x','y']
            name='xor_with_interaction' if augmented else 'xor_linear_only'
            world.create_model('synthetic',name,names,provenance='synthetic')
            train=xor_rows(f'{name}-train-',rng,args.train_size,augmented)
            world.train_model('synthetic',name,train)
            heldout=xor_rows(f'{name}-holdout-',rng,args.holdout_size,augmented)
            report['cases'][name]=world.evaluate_model('synthetic',name,heldout)

        world.create_transition_model('synthetic','toy_states',provenance='synthetic')
        for row in transitions('trans-train-',rng,args.train_size):
            world.observe_transition('synthetic','toy_states',row['current_state'],row['action'],row['next_state'],sample_id=row['id'])
        held=transitions('trans-holdout-',rng,args.holdout_size)
        report['cases']['controlled_transition_holdout']=world.evaluate_transitions('synthetic','toy_states',held)
        report['db_integrity']=world.db.execute('PRAGMA integrity_check').fetchone()[0]
        report['model_count']=world.db.execute('SELECT COUNT(*) FROM learned_models').fetchone()[0]
        report['transition_count']=world.db.execute('SELECT COUNT(*) FROM transition_samples').fetchone()[0]
    report['wall_seconds']=round(time.perf_counter()-start,3)
    report['gates']={
      'linear_beats_holdout_constant':report['cases']['linear_independent_holdout']['brier_skill_vs_constant']>.12,
      'detects_shift_with_alarm':report['drift_check']['status']=='alarm',
      'linear_degrades_on_shift':report['cases']['linear_distribution_shift']['brier_skill_vs_constant']<report['cases']['linear_independent_holdout']['brier_skill_vs_constant'],
      'xor_with_interaction_beats_without':report['cases']['xor_with_interaction']['brier']<report['cases']['xor_linear_only']['brier']*.75,
      'transition_top1_above_80pct':report['cases']['controlled_transition_holdout']['top1_accuracy']>.8,
      'all_holdouts_disjoint_by_id':all(c.get('training_overlap_checked') for c in report['cases'].values()),
      'database_integrity':report['db_integrity']=='ok',
    }
    report['passed']=all(report['gates'].values())
    (args.output/'learning_report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())
