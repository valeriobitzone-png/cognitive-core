from pathlib import Path
import argparse,json,time,os,resource,re
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import mlx.core as mx
mx.set_memory_limit(6_000_000_000);mx.set_cache_limit(300_000_000)
from mlx_lm import load
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--adapter',default='');p.add_argument('--name',required=True);args=p.parse_args()
d=json.loads((ROOT/'dataset.json').read_text());protocol=json.loads((ROOT/'lora-eval-protocol.json').read_text())
letters=list(protocol['letters'].values());actions=list(protocol['letters']);system=protocol['system']
model,tokenizer=load(str(ROOT/'models/lfm-hf'),adapter_path=args.adapter or None)
model.eval()
tokens=[tokenizer.encode(x,add_special_tokens=False) for x in letters]
assert all(len(v)==1 for v in tokens),tokens
ids=[v[0] for v in tokens]
def words(text):return set(re.findall(r'\w+',text.lower()))
train_words=[words(r['input']['message']) for r in d['train']]
def accuracy_score(gold,pred):return sum(a==b for a,b in zip(gold,pred))/len(gold)
def macro_f1(gold,pred):
 scores=[]
 for label in actions:
  tp=sum(a==label and b==label for a,b in zip(gold,pred));fp=sum(a!=label and b==label for a,b in zip(gold,pred));fn=sum(a==label and b!=label for a,b in zip(gold,pred))
  scores.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.)
 return sum(scores)/len(scores)
rows=[];began=time.monotonic()
modes=('prompt','memory') if not args.adapter else ('lora',)
for mode in modes:
 for item in d['test']:
  messages=[{'role':'system','content':system}]
  if mode=='memory':
   query=words(item['input']['message'])
   similar=[len(query.intersection(v))/max(1,len(query.union(v))) for v in train_words]
   for i in sorted(range(len(similar)),key=lambda i:(similar[i],i))[-2:]:
    r=d['train'][int(i)]
    messages.extend([{'role':'user','content':json.dumps(r['input'],ensure_ascii=False)},
                     {'role':'assistant','content':protocol['letters'][r['expected']]}])
  messages.append({'role':'user','content':json.dumps(item['input'],ensure_ascii=False)})
  prompt=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True)
  start=time.monotonic();logits=model(mx.array([prompt]))[0,-1,mx.array(ids)]
  probs=mx.softmax(logits.astype(mx.float32));mx.eval(probs)
  scores=probs.tolist();pred=actions[max(range(6),key=lambda i:scores[i])]
  rows.append({'id':item['id'],'expected':item['expected'],'actual':pred,'mode':mode,'candidate_probabilities':scores,
               'prompt_tokens':len(prompt),'seconds':time.monotonic()-start})
  print(args.name,mode,item['id'],item['expected'],pred,flush=True)
summary={}
for mode in modes:
 r=[x for x in rows if x['mode']==mode]
 summary[mode]={'n':len(r),'accuracy':accuracy_score([x['expected'] for x in r],[x['actual'] for x in r]),
  'macro_f1':macro_f1([x['expected'] for x in r],[x['actual'] for x in r])}
report={'name':args.name,'adapter':args.adapter or None,'epistemic':'SIMULATED','protocol':'single-token conditional classification; not generated JSON',
 'summary':summary,'rows':rows,'elapsed_seconds':time.monotonic()-began,'mlx_peak_bytes':mx.get_peak_memory(),
 'note':'Warm MLX evaluation. Do not compare latency directly to CPU cold-process GGUF measurements.'}
(ROOT/(args.name+'-lora-eval.json')).write_text(json.dumps(report,indent=2));print(json.dumps(summary,indent=2))
