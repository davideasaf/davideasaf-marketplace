"""Local run supervisor and atomic terminal publication; no provider calls of its own."""
import contextlib
import datetime
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time


def atomic(path, text):
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            out.write(text)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


@contextlib.contextmanager
def locked(directory):
    with (directory / '.metadata.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def finalize(directory):
    wrapper = Path(__file__).with_name('ask.sh')
    for action in ['__remove-auth', '__finalize']:
        result = subprocess.run(['bash', str(wrapper), action, directory.name],
                                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        if result.returncode:
            with (directory / 'stderr.log').open('a') as err:
                err.write(f'{action} failed: {result.stderr}')
            raise RuntimeError(f'{action} failed with code {result.returncode}')


def supervise(directory, cwd, command):
    child = None
    interrupted = False
    def stop(_signum, _frame):
        nonlocal interrupted
        interrupted = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        with (directory / 'prompt.txt').open('rb') as inp, (directory / 'events.jsonl').open('wb') as out, (directory / 'stderr.log').open('ab') as err:
            child = subprocess.Popen(command, cwd=cwd or None, stdin=inp, stdout=out, stderr=err, start_new_session=True)
            with locked(directory):
                meta = json.loads((directory / 'meta.json').read_text())
                meta.update(pid=os.getpid(), child_pid=child.pid)
                atomic(directory / 'meta.json', json.dumps(meta, indent=2) + '\n')
            atomic(directory / 'ready', 'ready\n')
            while child.poll() is None:
                if interrupted or (directory / 'cancel.request').exists():
                    atomic(directory / 'cancel.request', 'cancel\n')
                    # Signal all contained descendants, even when Claude exits first.
                    try:
                        os.killpg(child.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    time.sleep(0.5)
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    break
                time.sleep(0.05)
            code = child.wait()
            atomic(directory / 'exit_code', str(code if code >= 0 else 128 - code) + '\n')
    except Exception as exc:
        if child is not None and child.poll() is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        with (directory / 'stderr.log').open('a') as err:
            err.write(f'Supervisor error: {exc}\n')
        atomic(directory / 'exit_code', '1\n')
    finally:
        try:
            finalize(directory)
        except Exception as exc:
            with (directory / 'stderr.log').open('a') as err:
                err.write(f'Finalization error: {exc}\n')
            with locked(directory):
                meta = json.loads((directory / 'meta.json').read_text())
                cancelled = (directory / 'cancel.request').exists() or meta.get('status') == 'cancelled'
                meta.update(status='cancelled' if cancelled else 'failed', failure_reason='finalize_error')
                if not meta.get('exit_code'):
                    meta['exit_code'] = 1
                atomic(directory / 'meta.json', json.dumps(meta, indent=2) + '\n')
        finally:
            atomic(directory / 'supervisor.done', 'done\n')


if __name__ == '__main__':
    mode, directory = sys.argv[1:3]
    directory = Path(directory)
    if mode == 'finalize':
        finalize(directory)
    elif mode == 'supervise':
        supervise(directory, sys.argv[3], sys.argv[4:])
    else:
        raise SystemExit('Unknown lifecycle command')
