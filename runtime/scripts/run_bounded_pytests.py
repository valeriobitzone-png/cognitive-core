"""Bounded test supervisor: disk logs, sampled process trees, atomic reports.

POSIX groups and observed detached descendants are terminated after every job.
This is fault containment, not a security sandbox: SIGKILL of the supervisor,
unsampled double-forks, kernel stalls and disk exhaustion need an OS/container
supervisor. Install the test extra for psutil process/thread/fd diagnostics.
"""
from __future__ import annotations
import argparse
import errno
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time

try:
    import psutil
except ImportError:
    psutil = None

ROOT = Path(__file__).resolve().parents[1]
ACTIVE = set()
ACTIVE_LOCK = threading.Lock()


def _kill_group(proc):
    try:
        if os.name == 'posix':
            os.killpg(proc.pid, signal.SIGKILL)
        elif proc.poll() is None:
            proc.kill()
        return None
    except ProcessLookupError:
        return None
    except OSError as exc:
        # macOS may return EPERM for a vanished group. Do not hide a live failure.
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        return str(exc)


def shutdown_children(signum, _frame):
    with ACTIVE_LOCK:
        children = list(ACTIVE)
    for proc in children:
        _kill_group(proc)
    raise SystemExit(128 + signum)


def _sample(proc, tracked):
    if psutil is None:
        return {'diagnostics': 'psutil_not_installed'}
    try:
        parent = psutil.Process(proc.pid)
        processes = [parent] + parent.children(recursive=True)
    except (psutil.Error, OSError) as exc:
        return {'diagnostics': type(exc).__name__}
    snapshot = []
    for item in processes:
        try:
            tracked[(item.pid, item.create_time())] = item
            snapshot.append({'pid': item.pid, 'ppid': item.ppid(),
                             'status': item.status(), 'threads': item.num_threads(),
                             'fds': item.num_fds() if hasattr(item, 'num_fds') else None})
        except (psutil.Error, OSError):
            continue
    return {'processes': snapshot}


def bounded(cmd, *, timeout_seconds=110, cwd=ROOT, env=None, log_path=None):
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('timeout must be finite and > 0')
    began = time.monotonic()
    if log_path is None:
        fd, name = tempfile.mkstemp(prefix='worldcore-job-', suffix='.log')
        os.close(fd)
        log_path = Path(name)
    log_path = Path(log_path).resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tracked = {}
    snapshots = []
    cleanup_errors = []
    proc = None
    outcome = 'error'
    try:
        # Regular files cannot keep communicate() waiting for pipe EOF when a
        # detached descendant inherits stdout. Full output stays on disk.
        with log_path.open('wb', buffering=0) as log:
            proc = subprocess.Popen(cmd, cwd=str(cwd), stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    start_new_session=(os.name == 'posix'), env=env)
            with ACTIVE_LOCK:
                ACTIVE.add(proc)
            snapshots.append(_sample(proc, tracked))
            while proc.poll() is None:
                if time.monotonic() - began >= timeout_seconds:
                    outcome = 'timeout'
                    break
                snapshot = _sample(proc, tracked)
                # Keep bounded diagnostic history, including the final sample.
                if len(snapshots) < 16:
                    snapshots.append(snapshot)
                else:
                    snapshots[-1] = snapshot
                time.sleep(min(.025, max(.001, timeout_seconds - (time.monotonic()-began))))
            else:
                outcome = 'passed' if proc.returncode == 0 else 'failed'
    except OSError as exc:
        cleanup_errors.append(str(exc))
    finally:
        if proc is not None:
            # Clean groups even when the leader has exited; children may remain.
            snapshots.append(_sample(proc, tracked))
            err = _kill_group(proc)
            if err and proc.poll() is None:
                cleanup_errors.append(err)
            live_descendants = []
            for (pid, created), item in tracked.items():
                if pid == proc.pid:
                    continue
                try:
                    if item.is_running() and item.create_time() == created and item.status() != psutil.STATUS_ZOMBIE:
                        live_descendants.append(pid)
                        item.kill()
                except psutil.NoSuchProcess:
                    pass
                except (psutil.Error, OSError) as exc:
                    cleanup_errors.append(str(exc))
            if live_descendants and outcome == 'passed':
                outcome = 'failed_leaked_descendants'
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                cleanup_errors.append('parent did not exit within cleanup deadline')
            with ACTIVE_LOCK:
                ACTIVE.discard(proc)
    with log_path.open('rb') as log:
        log.seek(0, os.SEEK_END)
        output_bytes = log.tell()
        log.seek(max(0, output_bytes - 65536))
        output = log.read().decode('utf-8', errors='replace')
    if cleanup_errors and outcome == 'passed':
        outcome = 'cleanup_error'
    return {'outcome': outcome, 'exit_code': None if outcome == 'timeout' else (proc.returncode if proc else None),
            'output': output, 'log_path': str(log_path), 'output_bytes': output_bytes,
            'duration_seconds': round(time.monotonic()-began, 3),
            'diagnostics': snapshots, 'cleanup_errors': cleanup_errors}


def _write_report(dest, reports, complete=False):
    summary = {'passed': sum(x['passed'] for x in reports), 'total': len(reports),
               'failed': [x['test'] for x in reports if not x['passed']],
               'complete': complete, 'runner': 'disk-log-process-watchdog-v12', 'tests': reports}
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_suffix(dest.suffix + '.tmp')
    temporary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(dest)
    return summary


def main():
    signal.signal(signal.SIGTERM, shutdown_children)
    signal.signal(signal.SIGINT, shutdown_children)
    parser = argparse.ArgumentParser()
    parser.add_argument('--timeout', type=float, default=110)
    parser.add_argument('--total-timeout', type=float, default=1800)
    parser.add_argument('--output', default='training-artifacts/v12_test_runner_report.json')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--skip-node', action='store_true')
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    if any(not math.isfinite(v) or v <= 0 for v in (args.timeout, args.total_timeout)):
        parser.error('timeouts must be finite and > 0')
    env = {**os.environ, 'PYTHONPATH': str(ROOT/'src') + os.pathsep + str(ROOT),
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1',
           'WORLDCORE_PYTHON': sys.executable}
    files = sorted((ROOT/'tests').glob('test_*.py'))
    if args.only:
        unknown = set(args.only) - {v for f in files for v in (f.name, f.stem)}
        if unknown:
            parser.error('unknown tests: ' + ', '.join(sorted(unknown)))
        files = [f for f in files if f.stem in args.only or f.name in args.only]
    jobs = []
    if args.selftest:
        jobs.append(('watchdog_selftest', [sys.executable, '-c', 'import time; time.sleep(20)'], .3))
    for file in files:
        # A Python thread dump goes to the same job log BEFORE the hard deadline.
        wrapper = ('import faulthandler; faulthandler.enable(); '
                   f'faulthandler.dump_traceback_later({max(.05,args.timeout*.8)!r}); '
                   'import pytest; raise SystemExit(pytest.main())')
        jobs.append((file.name, [sys.executable, '-c', wrapper, '-q', '-p', 'no:cacheprovider', str(file)], args.timeout))
    if not args.skip_node:
        jobs.extend((f.name, ['node', '--test', str(f)], args.timeout) for f in sorted((ROOT/'tests').glob('*.test.mjs')))
    if not jobs:
        parser.error('no test jobs selected')
    dest = (ROOT/args.output).resolve()
    reports = []
    deadline = time.monotonic() + args.total_timeout
    _write_report(dest, reports)
    try:
        for index, (name, cmd, limit) in enumerate(jobs):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                reports.append({'test': name, 'outcome': 'total_deadline', 'passed': False})
                break
            result = bounded(cmd, timeout_seconds=min(limit, remaining), env=env,
                             log_path=dest.parent/(dest.stem + '_logs')/f'{index:02d}_{name}.log')
            result['test'] = name
            result['passed'] = result['outcome'] == ('timeout' if name == 'watchdog_selftest' else 'passed') and not result['cleanup_errors']
            reports.append(result)
            _write_report(dest, reports)
            print(name, result['outcome'], result['duration_seconds'], flush=True)
    finally:
        summary = _write_report(dest, reports, complete=len(reports)==len(jobs))
    print('SUMMARY:', summary['passed'], '/', summary['total'], 'failed', summary['failed'], flush=True)
    return 0 if summary['complete'] and not summary['failed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
