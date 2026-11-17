"""Bounded synthetic factorial pilot on the same six-action task, no actions executed."""
from pathlib import Path
import os,json,itertools,time,re,math,hashlib
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import mlx.core as mx
mx.set_memory_limit(6_000_000_000);mx.set_cache_limit(300_000_000)
from mlx_lm import load
R=Path(__file__).resolve().parent;OLD=R.parent/'esperimenti-2026-11-11'
d=json.loads((OLD/'dataset.json').read_text());protocol=json.loads((OLD/'lora-eval-protocol.json').read_text());actions=list(protocol['letters']);letters=protocol['letters'];system=protocol['system']
fresh=json.loads((R/'fresh48.json').read_text());tasks=[x for action in actions for x in [[v for v in fresh if v['expected']==action][i] for i in (0,7)]]
# Train-only aggregate prior. It is deliberately weak, and not a six-action quantum oracle.
group={'LOCAL_RESEARCH','WEB_RESEARCH'};train_binary=[int(v['expected'] in group) for v in d['train']]
p=(sum(train_binary)+1)/(len(train_binary)+2);angle=2*math.acos(math.sqrt(p));qstay=math.cos(angle/2)**2
words=lambda s:set(re.findall(r'\w+',s.casefold()));tw=[words(v['input']['message']) for v in d['train']]
base_dev=json.loads((OLD/'lfm-results.json').read_text())['rows'];dev=[x for x in base_dev if x['split']=='dev']
family_errors={a:sum(x['action']!=x['expected'] for x in dev if x['expected']==a)/max(1,sum(x['expected']==a for x in dev)) for a in actions}
rows=[];start=time.monotonic()
for lora in (0,1):
 model,tok=load(str(OLD/'models/lfm-hf'),adapter_path=str(OLD/'adapters/seed0') if lora else None);model.eval()
 ids=[tok.encode(letters[a],add_special_tokens=False)[0] for a in actions]
 for memory,self_state,progress,quantum in itertools.product((0,1),repeat=4):
  config={'memory':memory,'self_state':self_state,'progress_cost':progress,'lora':lora,'quantum':quantum};name=''.join(str(config[k]) for k in config)
  for repeat in range(2):
   ordered=list(tasks if repeat==0 else reversed(tasks))
   if progress:
    # Value is estimated by matching train examples, never by the hidden test label.
    def priority(v):
     ws=words(v['input']['message']);idx=max(range(len(tw)),key=lambda i:len(ws&tw[i])/max(1,len(ws|tw[i])))
     return family_errors[d['train'][idx]['expected']]/max(1,len(json.dumps(v['input'])))
    ordered.sort(key=priority,reverse=True)
   previous=False
   for position,item in enumerate(ordered):
    if time.monotonic()-start>600:raise TimeoutError('factorial wall budget')
    user=dict(item['input'])
    if self_state:
     state=user['state'];user['self_model']={'capabilities':{'local_research':state['local_sources']>0,'web_research':bool(state['browser_available'] and state['web_opt_in'] and state['requests_left']>0)},'runtime':'experiment-local','source':'observed runtime state, also available to all arms','calibrated':False}
    msgs=[{'role':'system','content':system}]
    if memory:
     ws=words(user['message']);rank=sorted(range(len(tw)),key=lambda i:(len(ws&tw[i])/max(1,len(ws|tw[i])),i))[-2:]
     for i in rank:msgs.extend([{'role':'user','content':json.dumps(d['train'][i]['input'],ensure_ascii=False)},{'role':'assistant','content':letters[d['train'][i]['expected']]}])
    msgs.append({'role':'user','content':json.dumps(user,ensure_ascii=False)})
    prompt=tok.apply_chat_template(msgs,tokenize=True,add_generation_prompt=True);t=time.monotonic();logits=model(mx.array([prompt]))[0,-1,mx.array(ids)];pr=mx.softmax(logits.astype(mx.float32));mx.eval(pr);probs=pr.tolist()
    raw=list(probs)
    if quantum:
     # Binary sequential pure-state prior; matched classical calculation is exactly equal.
     q=qstay if previous else 1-qstay
     adjusted=[v*(q if a in group else 1-q)**.2 for a,v in zip(actions,probs)];norm=sum(adjusted);probs=[v/norm for v in adjusted]
    pred=actions[max(range(6),key=lambda i:probs[i])];previous=pred in group
    brier=sum((v-int(a==item['expected']))**2 for a,v in zip(actions,probs))
    rows.append({'cell':name,'config':config,'repeat':repeat,'position':position,'id':item['id'],'expected':item['expected'],'actual':pred,'probabilities':probs,'unadjusted':raw,'correct':pred==item['expected'],'brier':brier,'prompt_tokens':len(prompt),'seconds':time.monotonic()-t})
   print(name,repeat,sum(v['correct'] for v in rows if v['cell']==name and v['repeat']==repeat),flush=True)
 del model,tok;mx.clear_cache()
summary=[]
for name in sorted({v['cell'] for v in rows}):
 rr=[v for v in rows if v['cell']==name];summary.append({'cell':name,'config':rr[0]['config'],'n':len(rr),'accuracy':sum(v['correct'] for v in rr)/len(rr),'brier':sum(v['brier'] for v in rr)/len(rr),'budget_first6_accuracy':sum(v['correct'] for v in rr if v['position']<6)/12,'prompt_tokens':sum(v['prompt_tokens'] for v in rr),'seconds':sum(v['seconds'] for v in rr)})
named={'A':'00000','B':'10000','C':'11000','D':'11100','E':'11010','F':'11001'}
report={'epistemic':'SIMULATED','design':'V2:2^5 full factorial,32 cells;12 tasks x2 order controls;observed user state identical across arms','factor_order':['memory','self_state','progress_cost','lora','quantum'],'named_arms':{k:next(v for v in summary if v['cell']==name) for k,name in named.items()},'summary':summary,'rows':rows,'mlx_peak_bytes':mx.get_peak_memory(),'seconds':time.monotonic()-start,'external_observer_same_information':'Identical input and deterministic classifier => identical forecasts; no privileged introspection claim','limits':'12 easy synthetic tasks, ordering repeats not independent samples; D orders work but real acquisition is a separate executable longitudinal experiment. Quantum prior is binary and classically equivalent.'}
(R/'matrix-results.json').write_text(json.dumps(report,indent=2));print(json.dumps(report['named_arms'],indent=2))
