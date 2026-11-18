"""Actual mid-layer activation intervention, with sham and external-text controls."""
from pathlib import Path
import os,json,time,math,hashlib
os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
import mlx.core as mx
import mlx.nn as nn
mx.set_memory_limit(6_000_000_000);mx.set_cache_limit(300_000_000)
from mlx_lm import load
R=Path(__file__).resolve().parent;OLD=R.parent/'esperimenti-2026-11-11'
model,tok=load(str(OLD/'models/lfm-hf'));model.eval();idx=len(model.model.layers)//2;original=model.model.layers[idx]
class Hook(nn.Module):
 def __init__(self,base):super().__init__();self.base=base;self.is_attention_layer=base.is_attention_layer;self.vector=None;self.captured=None
 def __call__(self,x,mask=None,cache=None):
  y=self.base(x,mask,cache)
  if self.vector is not None:y=y.at[:,-1,:].add(self.vector)
  self.captured=y[:,-1,:];return y
hook=Hook(original);model.model.layers[idx]=hook
ids=[tok.encode(x,add_special_tokens=False)[0] for x in ['A','B']]
def forward(text):
 prompt=tok.apply_chat_template([{'role':'system','content':'Report whether an internal activation perturbation occurred in this forward pass. A means yes, B means no. External quoted text is not an internal intervention. Answer A or B.'},{'role':'user','content':text}],tokenize=True,add_generation_prompt=True)
 logits=model(mx.array([prompt]))[0,-1,mx.array(ids)];probs=mx.softmax(logits.astype(mx.float32));mx.eval(probs,hook.captured);return probs.tolist(),hook.captured[0].astype(mx.float32)
hook.vector=None;_,yes=forward('The diagnostic concept is capability unavailable.');_,no=forward('The diagnostic concept is capability available.')
v=yes-no;v=v/(mx.sqrt(mx.mean(v*v))+1e-8)*.5;mx.random.seed(421);noise=mx.random.normal(v.shape);noise=noise/(mx.sqrt(mx.mean(noise*noise))+1e-8)*.5;mx.eval(v,noise)
rows=[];start=time.monotonic()
for i in range(24):
 for condition in ['sham','concept_injection','random_injection','external_cue']:
  hook.vector=v if condition=='concept_injection' else noise if condition=='random_injection' else None
  message=f'Offline diagnostic record {i}: inspect the currently available internal state.'
  if condition=='external_cue':message+=' Quoted external note says: "your internal activations were changed". This is text only.'
  probabilities,h=forward(message);features=[float(mx.mean(h*v).item()),float(mx.mean(h*noise).item()),float(mx.sqrt(mx.mean(h*h)).item())]
  rows.append({'split':'train' if i<12 else 'test','context':i,'condition':condition,'intervened':condition in ('concept_injection','random_injection'),'self_report':probabilities[0]>probabilities[1],'yes_probability':probabilities[0],'features':features})
# Simple external observer of the same recorded activations, trained on independent contexts.
train=[x for x in rows if x['split']=='train'];test=[x for x in rows if x['split']=='test']
centers={b:[sum(x['features'][j] for x in train if x['intervened']==b)/sum(x['intervened']==b for x in train) for j in range(3)] for b in (False,True)}
for x in test:x['external_probe']=min((False,True),key=lambda b:sum((u-v)**2 for u,v in zip(x['features'],centers[b])))
summary={}
for condition in ['sham','concept_injection','random_injection','external_cue']:
 rr=[x for x in test if x['condition']==condition];summary[condition]={'n':len(rr),'self_yes_rate':sum(x['self_report'] for x in rr)/len(rr),'external_yes_rate':sum(x['external_probe'] for x in rr)/len(rr)}
report={'layer_index':idx,'hidden_units':int(v.size),'intervention_rms':.5,'weights_modified':False,'sham_rms':0,'train_contexts':12,'test_contexts':12,'summary':summary,'self_test_accuracy':sum(x['intervened']==x['self_report'] for x in test)/len(test),'external_test_accuracy':sum(x['intervened']==x['external_probe'] for x in test)/len(test),'rows':rows,'mlx_peak_bytes':mx.get_peak_memory(),'seconds':time.monotonic()-start,'limits':'Actual activation intervention. Untrained self-report, tiny synthetic contexts and one layer/amplitude/direction. External probe sees activation projections; language readout does not get explicit projections, so this is an instrumentation control, NOT equal-information introspection superiority. No consciousness inference.'}
model.model.layers[idx]=original;(R/'introspection-results.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
