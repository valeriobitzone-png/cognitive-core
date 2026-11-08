from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_bounded_pytests import bounded

def test_real_timeout_cannot_be_reported_as_success():
    r=bounded([sys.executable,'-c','import time;time.sleep(60)'],timeout_seconds=.3)
    assert r['outcome']=='timeout' and r['exit_code'] is None and r['duration_seconds']<3

def test_process_nonzero_fails():
    r=bounded([sys.executable,'-c','raise SystemExit(7)'],timeout_seconds=3)
    assert r['outcome']=='failed' and r['exit_code']==7

def test_normal_process_passes():
    r=bounded([sys.executable,'-c','print(5)'],timeout_seconds=3)
    assert r['outcome']=='passed' and '5' in r['output']
