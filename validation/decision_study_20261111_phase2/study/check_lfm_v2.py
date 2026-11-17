from pathlib import Path
import subprocess,time,json
R=Path(__file__).resolve().parent;CC='/Users/ambrogio/Developer/cc-venv-test/bin/python';deadline=time.monotonic()+180
while time.monotonic()<deadline:
 if (R/'finish-queue.log').read_text().rstrip().endswith('COMPLETE'):break
 time.sleep(1)
else:raise TimeoutError('preceding model still running')
def run(split):
 with (R/f'lfm12-v2-{split}.log').open('w') as f:subprocess.run([CC,'-u','-B',str(R/'bench_phase2.py'),'lfm12','v2',split],stdout=f,stderr=subprocess.STDOUT,timeout=1200,check=True)
 return json.loads((R/f'lfm12-v2-{split}.json').read_text())
dev=run('dev');print('DEV',dev['correct'],dev['n'],flush=True)
if dev['correct']>=12:
 test=run('test');print('TEST',test['correct'],test['n'],flush=True)
 if test['correct']>=25:
  fresh=run('fresh');print('FRESH',fresh['correct'],fresh['n'],flush=True)
print('COMPLETE',flush=True)
