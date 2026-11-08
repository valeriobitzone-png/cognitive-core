"""Repeated adversarial jobs; every job has a deadline and a complete disk log."""
import concurrent.futures
import json
import os
from pathlib import Path
import sys
from run_bounded_pytests import bounded

DEST=Path(sys.argv[1]).resolve()
DEST.mkdir(parents=True,exist_ok=True)
CASES={
 'pass':('print("ok")','passed',1),
 'nonzero':('raise SystemExit(7)','failed',1),
 'sleep':('import time;time.sleep(60)','timeout',.12),
 'ignore_term':('import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)','timeout',.12),
 'thread_lock':('import faulthandler,threading;faulthandler.dump_traceback_later(.04);threading.Lock().acquire();threading.Event().wait()','timeout',.15),
 'output_flood':('import sys;sys.stdout.write("x"*200000)','passed',1),
 'grandchild':('import subprocess,sys,time;subprocess.Popen([sys.executable,"-c","import time;time.sleep(60)"]);time.sleep(60)','timeout',.15)
}

def run(job):
    iteration,name=job
    code,expected,timeout=CASES[name]
    result=bounded([sys.executable,'-B','-c',code],timeout_seconds=timeout,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},log_path=DEST/f'{iteration:02d}_{name}.log')
    result.update(case=name,iteration=iteration,expected=expected)
    result['verified']=result['outcome']==expected and not result['cleanup_errors'] and result['duration_seconds']<3
    return result

try:
    import psutil
    fd_before=psutil.Process().num_fds()
except (ImportError,OSError):fd_before=None
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    results=list(pool.map(run,[(i,name) for i in range(20) for name in CASES]))
try:fd_after=psutil.Process().num_fds()
except (NameError,OSError):fd_after=None
summary={'jobs':len(results),'verified':sum(r['verified'] for r in results),'failures':[{'case':r['case'],'iteration':r['iteration'],'outcome':r['outcome']} for r in results if not r['verified']],
         'fd_before':fd_before,'fd_after':fd_after,'fd_growth':fd_after-fd_before if fd_after is not None and fd_before is not None else None,'results':results}
(DEST/'report.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
raise SystemExit(0 if summary['verified']==summary['jobs'] and (summary['fd_growth'] is None or summary['fd_growth']<=2) else 1)
