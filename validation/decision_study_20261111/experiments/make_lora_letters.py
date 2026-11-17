from pathlib import Path
import json,hashlib
ROOT=Path(__file__).resolve().parent;d=json.loads((ROOT/'dataset.json').read_text())
letters=dict(zip(d['actions'],'ABCDEF'))
system=('Choose the next action. Reply with one letter only: '+', '.join(v+'='+k for k,v in letters.items())+'. '+
        d['system'][d['system'].index('WAIT for greetings'):])
folder=ROOT/'lora-letters';folder.mkdir(exist_ok=True)
for split,source in [('train','train'),('valid','dev'),('test','test')]:
 with (folder/(split+'.jsonl')).open('w') as f:
  for r in d[source]:
   messages=[{'role':'system','content':system},{'role':'user','content':json.dumps(r['input'],ensure_ascii=False)},
             {'role':'assistant','content':letters[r['expected']]}]
   f.write(json.dumps({'messages':messages},ensure_ascii=False)+'\n')
(ROOT/'lora-eval-protocol.json').write_text(json.dumps({'system':system,'letters':letters,'iterations':24,
 'batch_size':1,'layers':4,'learning_rate':.0002,'max_seq_length':512,'seeds':[0,1,2],
 'evaluation':'Identical full-precision MLX base checkpoint: next-token log-likelihood among six one-token action letters. Separate protocol from GGUF generated-action benchmark.',
 'selection':'Final fixed step for each seed; no choice based on holdout; no adapter promoted.',
 'base_data_sha256':hashlib.sha256((ROOT/'dataset.json').read_bytes()).hexdigest()},indent=2))
