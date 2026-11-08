"""Read-only host discovery, with bounded subprocesses and local-only logs."""
import json
import os
from pathlib import Path
import shutil
import sys
from run_bounded_pytests import bounded

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT.parent/'evidence'/'hosts'
DEST.mkdir(parents=True,exist_ok=True)
env={**os.environ,'PYTHONPATH':str(ROOT/'src'),'WORLDCORE_PYTHON':sys.executable,
     'XDG_DATA_HOME':str(DEST/'data'),'XDG_CACHE_HOME':str(DEST/'cache')}
report={}
for name in ('claude','opencode','hermes','openclaw'):
    path=shutil.which(name)
    report[name]={'path':path,'authenticated_integration':False}
    if not path:continue
    result=bounded([path,'--version'],timeout_seconds=10,env=env,log_path=DEST/(name+'_version.log'))
    report[name]['version']=result
    if name in ('claude','opencode'):
        report[name]['help']=bounded([path,'--help'],timeout_seconds=10,env=env,log_path=DEST/(name+'_help.log'))
if report['claude']['path']:
    # Auth status only. No credentials or configuration files are read by this script.
    result=bounded([report['claude']['path'],'auth','status','--json'],timeout_seconds=15,env=env,log_path=DEST/'claude_auth_private.log')
    try:
        parsed=json.loads(result['output'])
        report['claude']['auth_status']={k:parsed[k] for k in ('loggedIn','authMethod','apiProvider') if k in parsed}
    except ValueError:
        report['claude']['auth_status']={'outcome':result['outcome'],'exit_code':result['exit_code']}
    # Auth can contain account identifiers; omit that raw log from deliverables.
    (DEST/'claude_auth_private.log').unlink(missing_ok=True)
(DEST/'probe.json').write_text(json.dumps(report,indent=2))
print(json.dumps({k:{'path':v['path'],'version_outcome':v.get('version',{}).get('outcome'),'version_output':v.get('version',{}).get('output'),'auth_status':v.get('auth_status')} for k,v in report.items()},indent=2))
