from pathlib import Path
import json,time,subprocess
R=Path(__file__).resolve().parent;CC='/Users/ambrogio/Developer/cc-venv-test/bin/python';runs=[];start=time.monotonic()
# Do not overlap the existing one-shot language-model experiment.
end=time.monotonic()+600
while time.monotonic()<end:
 p=R/'rizzo4-typed-dev.json'
 if p.exists() and json.loads(p.read_text()).get('complete'):break
 time.sleep(1)
else:raise TimeoutError('previous run not complete')
time.sleep(1)
def run(name,cmd,limit):
 remaining=1800-(time.monotonic()-start)
 if remaining<30:raise TimeoutError('final study execution budget')
 print('START',name,flush=True);t=time.monotonic()
 with (R/(name+'.log')).open('w') as f:
  try:code=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=min(limit,remaining)).returncode
  except subprocess.TimeoutExpired:code='timeout'
 runs.append({'name':name,'exit_code':code,'seconds':time.monotonic()-t});(R/'finish-queue-results.json').write_text(json.dumps(runs,indent=2));print('END',name,code,flush=True)
 return code
run('profile-smoke',[CC,'-B',str(R/'profile_smoke.py')],90)
for model,protocol in [('lfm12','v1'),('arch','native')]:
 if run(model+'-'+protocol+'-dev',[CC,'-u','-B',str(R/'bench_phase2.py'),model,protocol,'dev'],600):continue
 score=json.loads((R/f'{model}-{protocol}-dev.json').read_text())['correct']
 if score>=12:
  for split in ('test','fresh'):run(model+'-'+protocol+'-'+split,[CC,'-u','-B',str(R/'bench_phase2.py'),model,protocol,split],1500)
 else:print('DEV_SCREEN',model,score,'/16; no test-based tuning',flush=True)
print('COMPLETE',flush=True)
