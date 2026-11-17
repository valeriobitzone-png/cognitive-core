from pathlib import Path
import subprocess,json,time,sys,os
R=Path(__file__).resolve().parent;CC='/Users/ambrogio/Developer/cc-venv-test/bin/python';MLX='/opt/homebrew/Cellar/rapid-mlx/0.10.1/libexec/bin/python';runs=[];started=time.monotonic()
def run(name,command,timeout):
 t=time.monotonic();print('START',name,flush=True)
 with (R/(name+'.log')).open('w') as log:
  try:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=timeout).returncode
  except subprocess.TimeoutExpired:code='timeout'
 runs.append({'name':name,'exit_code':code,'seconds':time.monotonic()-t});(R/'queue-results.json').write_text(json.dumps(runs,indent=2));print('END',name,code,round(time.monotonic()-t),flush=True)
 return code
run('matrix',[MLX,'-B',str(R/'matrix_experiment.py')],600)
run('introspection',[MLX,'-B',str(R/'introspection_probe.py')],300)
run('voice',[CC,'-B',str(R/'voice_probe.py')],600)
for split in ('test','fresh'):run('rizzo4-v1-'+split,[CC,'-u','-B',str(R/'bench_phase2.py'),'rizzo4','v1',split],1800)
# Compare genuinely different routing candidates when pinned downloads are ready.
for model,filename,protocol in [('lfm12','LFM2.5-1.2B-Instruct-Q6_K.gguf','v1'),('arch','Arch-Router-1.5B-Q4_K_M.gguf','native')]:
 deadline=time.monotonic()+1000
 while not (R/'models'/filename).exists() and time.monotonic()<deadline:time.sleep(2)
 if not (R/'models'/filename).exists():print('DOWNLOAD_UNAVAILABLE',model,flush=True);continue
 code=run(model+'-'+protocol+'-dev',[CC,'-u','-B',str(R/'bench_phase2.py'),model,protocol,'dev'],600)
 if code:continue
 score=json.loads((R/f'{model}-{protocol}-dev.json').read_text())['correct']
 if score>=12:
  for split in ('test','fresh'):run(model+'-'+protocol+'-'+split,[CC,'-u','-B',str(R/'bench_phase2.py'),model,protocol,split],1500)
 else:print('DEV_BELOW_SCREEN',model,score,flush=True)
 if time.monotonic()-started>5000:break
print('COMPLETE',flush=True)
