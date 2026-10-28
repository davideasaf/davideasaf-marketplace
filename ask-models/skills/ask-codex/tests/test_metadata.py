import fcntl
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest


class MetadataTest(unittest.TestCase):
    def test_terminal_publication_obeys_the_shared_metadata_lock(self):
        wrapper=Path(__file__).resolve().parents[1]/'scripts/ask.sh'
        definitions=wrapper.read_text().split('\nif [[ $# -eq 0 ]]; then')[0]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'meta.json').write_text('{"status":"running","child_pid":12345}')
            script=root/'terminal.sh'
            script.write_text(definitions+'\nwrite_terminal_status "$1" done "" 0\n')
            with (root/'.metadata.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX)
                proc=subprocess.Popen(['bash',str(script),str(root)],
                                      env=dict(os.environ,ASK_RUN_ROOT=str(root/'runs')),
                                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                try:
                    time.sleep(.3)
                    self.assertIsNone(proc.poll(),'terminal writer bypassed the shared lock')
                    self.assertEqual(json.loads((root/'meta.json').read_text())['status'],'running')
                finally:
                    fcntl.flock(lock,fcntl.LOCK_UN)
                    stdout,stderr=proc.communicate(timeout=5)
            self.assertEqual(proc.returncode,0,stderr)
            self.assertEqual(json.loads((root/'meta.json').read_text())['child_pid'],12345)
            self.assertEqual(json.loads((root/'meta.json').read_text())['status'],'done')


if __name__=='__main__': unittest.main()
