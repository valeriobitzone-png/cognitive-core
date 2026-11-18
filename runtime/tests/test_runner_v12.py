import concurrent.futures
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from run_bounded_pytests import bounded


def test_detached_stdout_cannot_block_report(tmp_path):
    # The original communicate()-based runner raises during timeout cleanup.
    code='import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time;time.sleep(.5)"],start_new_session=True);print("leader_done")'
    result=bounded([sys.executable,'-c',code],timeout_seconds=.2,log_path=tmp_path/'job.log')
    assert result['duration_seconds'] < 1.5
    assert 'leader_done' in result['output']
    assert result['outcome'] in ('passed','failed_leaked_descendants')


@pytest.mark.parametrize('seconds',[float('nan'),float('inf'),0,-1])
def test_invalid_deadlines(seconds):
    with pytest.raises(ValueError):bounded([sys.executable,'-c','pass'],timeout_seconds=seconds)


def test_output_flood_is_not_memory_buffered(tmp_path):
    result=bounded([sys.executable,'-c','import sys;sys.stdout.write("x"*2000000)'],timeout_seconds=3,log_path=tmp_path/'flood.log')
    assert result['outcome']=='passed'
    assert result['output_bytes']==2000000
    assert len(result['output'])<=65536
    assert Path(result['log_path']).stat().st_size==2000000


def test_deadlocked_thread_has_dump_and_deadline(tmp_path):
    code='import faulthandler,threading;faulthandler.dump_traceback_later(.08);threading.Event().wait()'
    result=bounded([sys.executable,'-c',code],timeout_seconds=.25,log_path=tmp_path/'deadlock.log')
    assert result['outcome']=='timeout' and result['duration_seconds']<2
    assert 'Timeout' in result['output'] and 'threading.py' in result['output']


def test_concurrent_watchdogs_do_not_overwrite_active_child(tmp_path):
    def run(i):
        return bounded([sys.executable,'-c','import time;time.sleep(10)'],timeout_seconds=.15,log_path=tmp_path/f'{i}.log')
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(run,range(8)))
    assert all(r['outcome']=='timeout' and r['duration_seconds']<2 for r in results)


def test_missing_executable_is_reported(tmp_path):
    result=bounded(['worldcore-nonexistent-7a3c'],log_path=tmp_path/'missing.log')
    assert result['outcome']=='error' and result['cleanup_errors']


def test_unknown_selection_and_nonfinite_cli_cannot_pass(tmp_path):
    runner=Path(__file__).resolve().parents[1]/'scripts/run_bounded_pytests.py'
    for args in [ ['--only','not_a_real_test'], ['--timeout','nan'], ['--total-timeout','inf'] ]:
        result=bounded([sys.executable,str(runner),*args],timeout_seconds=3,log_path=tmp_path/(str(len(args))+args[-1]+'.log'))
        assert result['outcome']=='failed' and result['exit_code']==2


def test_sigterm_supervisor_reaps_its_active_process(tmp_path):
    psutil=pytest.importorskip('psutil')
    pidfile=tmp_path/'child.pid'
    script_dir=Path(__file__).resolve().parents[1]/'scripts'
    child=f'import os,pathlib,time;pathlib.Path({str(pidfile)!r}).write_text(str(os.getpid()));time.sleep(60)'
    code=(f'import sys,signal;sys.path.insert(0,{str(script_dir)!r});'
          'from run_bounded_pytests import bounded,shutdown_children;'
          'signal.signal(signal.SIGTERM,shutdown_children);'
          f'bounded([sys.executable,"-c",{child!r}],timeout_seconds=60)')
    log=(tmp_path/'supervisor.log').open('wb')
    supervisor=subprocess.Popen([sys.executable,'-B','-c',code],stdout=log,stderr=log,start_new_session=True)
    try:
        deadline=time.monotonic()+3
        while not pidfile.exists() and time.monotonic()<deadline:time.sleep(.02)
        assert pidfile.exists()
        pid=int(pidfile.read_text())
        supervisor.send_signal(signal.SIGTERM)
        assert supervisor.wait(timeout=3)==128+signal.SIGTERM
        try:
            process=psutil.Process(pid)
            assert not process.is_running() or process.status()==psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:pass
    finally:
        if supervisor.poll() is None:supervisor.kill();supervisor.wait(timeout=2)
        log.close()
