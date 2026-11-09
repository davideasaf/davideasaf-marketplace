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
    with locked(directory):
        meta = json.loads((directory / 'meta.json').read_text())
        events, malformed = [], False
        if (directory / 'events.jsonl').exists():
            for line in (directory / 'events.jsonl').read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    malformed = True
        result = next((e for e in reversed(events) if e.get('type') == 'result'), None)
        text = (result or {}).get('result') or ''
        if not text:
            text = ''.join(e.get('event', {}).get('delta', {}).get('text', '')
                           for e in events if e.get('type') == 'stream_event')
        atomic(directory / 'final.txt', text + ('\n' if text and not text.endswith('\n') else ''))
        for e in events:
            if e.get('session_id'):
                meta['session_id'] = e['session_id']
            # Record provider metadata separately from the requested model.
            message = e.get('message')
            actual = message.get('model') if isinstance(message, dict) else None
            if actual:
                meta['response_model'] = actual
        exit_file = directory / 'exit_code'
        code = int(exit_file.read_text()) if exit_file.exists() else None
        if code is not None:
            meta['exit_code'] = code
        cancelled = (directory / 'cancel.request').exists() or meta.get('status') == 'cancelled'
        failed = code != 0 or result is None or malformed or not text.strip() or bool((result or {}).get('is_error'))
        meta['status'] = 'cancelled' if cancelled else 'failed' if failed else 'done'
        if result:
            usage = result.get('usage', {})
            fields = {k: result.get(k) for k in ['subtype', 'duration_ms', 'duration_api_ms', 'num_turns', 'stop_reason', 'terminal_reason']}
            fields.update(cost_usd=result.get('total_cost_usd', result.get('cost_usd')))
            fields.update({k: usage.get(k, result.get(k)) for k in ['input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens']})
            meta.update({k: v for k, v in fields.items() if v is not None})
        meta['ended_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        # Publish final.txt before terminal metadata, under the same lock.
        atomic(directory / 'meta.json', json.dumps(meta, indent=2) + '\n')


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
        finalize(directory)
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
