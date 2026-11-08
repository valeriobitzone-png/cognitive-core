"""Three complete suites, each inside an additional independent process deadline."""
import json
import os
from pathlib import Path
import sys
from run_bounded_pytests import bounded
ROOT=Path(__file__).resolve().parents[1]
DEST=Path(sys.argv[1]).resolve();DEST.mkdir(parents=True,exist_ok=True)
reports=[]
for iteration in range(3):
    report=DEST/f'suite_{iteration+1}.json'
    command=[sys.executable,'-B',str(ROOT/'scripts/run_bounded_pytests.py'),'--selftest','--timeout','40','--total-timeout','150','--output',str(report)]
    result=bounded(command,timeout_seconds=165,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},log_path=DEST/f'suite_{iteration+1}_outer.log')
    result['iteration']=iteration+1
    reports.append(result)
    (DEST/'outer_report.json').write_text(json.dumps(reports,indent=2))
    print('REPEAT',iteration+1,result['outcome'],result['duration_seconds'],flush=True)
    if result['outcome']!='passed':
        print(result['output'][-2000:],flush=True)
        raise SystemExit(1)
