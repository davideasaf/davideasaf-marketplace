import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

WRAPPER = Path(__file__).with_name('ask.sh')
FAKE = '''#!/usr/bin/env python3
import json,os,pathlib,subprocess,sys,time
root=pathlib.Path(os.environ['FIXTURE_ROOT']); mode=os.environ['FIXTURE_MODE']
(root/'argv.json').write_text(json.dumps(sys.argv[1:])); (root/'stdin.txt').write_text(sys.stdin.read())
if mode=='permission':
 for value in ['Denied by policy',None,42,[]]:
  print(json.dumps({'type':'system','subtype':'permission_denied','message':value}))
if mode=='error':
 print(json.dumps({'type':'result','is_error':True,'result':'fixture error'})); sys.exit(42)
if mode=='empty': sys.exit(0)
if mode=='partial':
 print(json.dumps({'type':'stream_event','event':{'delta':{'text':'partial'}}})); sys.exit(0)
if mode in ['gate','hang','descendant']:
 print(json.dumps({'type':'system','session_id':'fixture-session'}),flush=True)
 if mode=='descendant':
  code="import pathlib,time,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); p=pathlib.Path("+repr(str(root/'descendant.heartbeat'))+")"+chr(10)+"while True:"+chr(10)+" p.write_text(str(time.monotonic())); time.sleep(.03)"
  subprocess.Popen([sys.executable,'-c',code])
 while not (root/'release').exists():
  (root/'heartbeat').write_text(str(time.monotonic())); time.sleep(.03)
print(json.dumps({'type':'assistant','message':{'model':'fixture-provider-model'}}))
print(json.dumps({'type':'result','is_error':False,'result':'READY\\nSecond line\\nFinal line','session_id':'fixture-session','total_cost_usd':0.01}))
'''


class LifecycleTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'bin').mkdir()
        fake = self.root/'bin/claude'; fake.write_text(FAKE); fake.chmod(0o755)
        self.env = {**os.environ, 'ASK_RUN_ROOT':str(self.root/'runs'), 'FIXTURE_ROOT':str(self.root),
                    'PATH':str(self.root/'bin')+':'+os.environ['PATH'], 'FIXTURE_MODE':'success'}
        self.runs=[]

    def tearDown(self):
        for rid in self.runs:
            self.call('cancel',rid)
        self.tmp.cleanup()

    def call(self,*args):
        return subprocess.run(['bash',str(WRAPPER),*args],env=self.env,capture_output=True,text=True,timeout=10)

    def start(self,mode='success',*options):
        self.env['FIXTURE_MODE']=mode
        started=self.call('start',*options,'Return READY.',str(self.root))
        self.assertEqual(started.returncode,0,started.stderr)
        rid=next(l.split('=',1)[1] for l in started.stdout.splitlines() if l.startswith('RUN_ID='))
        self.runs.append(rid)
        return rid,self.root/'runs/claude'/rid

    def test_success_and_immediate_cached_result(self):
        rid,d=self.start()
        waited=self.call('wait',rid)
        self.assertEqual(waited.returncode,0,waited.stderr)
        self.assertEqual(waited.stdout,'READY\nSecond line\nFinal line\n')
        cached=self.call('result',rid)
        self.assertEqual(cached.returncode,0,cached.stderr)
        self.assertEqual(cached.stdout,waited.stdout)
        meta=json.loads((d/'meta.json').read_text())
        self.assertEqual(meta['status'],'done'); self.assertEqual(meta['response_model'],'fixture-provider-model')
        self.assertEqual(meta['session_id'],'fixture-session'); self.assertEqual(meta['cost_usd'],.01)

    def test_non_object_system_messages_do_not_crash_finalization(self):
        rid,d=self.start('permission')
        waited=self.call('wait',rid,'--timeout','3')
        self.assertEqual(waited.returncode,0,waited.stderr)
        self.assertEqual(waited.stdout,'READY\nSecond line\nFinal line\n')
        self.assertTrue((d/'supervisor.done').exists())
        self.assertEqual(self.call('result',rid).returncode,0)
        self.assertEqual(json.loads((d/'meta.json').read_text())['response_model'],'fixture-provider-model')
        self.assertNotIn('Traceback',(d/'supervisor.log').read_text())

    def test_error_exit_propagates_in_wait_result_and_ask(self):
        rid,d=self.start('error')
        self.assertEqual(self.call('wait',rid).returncode,42)
        self.assertEqual(self.call('result',rid).returncode,42)
        self.assertEqual(json.loads((d/'meta.json').read_text())['status'],'failed')
        self.assertEqual(self.call('ask','Return READY.',str(self.root)).returncode,42)

    def test_empty_and_partial_are_failed(self):
        for mode in ['empty','partial']:
            with self.subTest(mode=mode):
                rid,d=self.start(mode)
                self.assertNotEqual(self.call('wait',rid).returncode,0)
                self.assertNotEqual(self.call('result',rid).returncode,0)
                self.assertEqual(json.loads((d/'meta.json').read_text())['status'],'failed')

    def test_poll_timeout_then_release(self):
        rid,d=self.start('gate')
        self.assertIn('running',self.call('status',rid).stdout)
        self.assertEqual(self.call('result',rid).returncode,2)
        self.assertEqual(self.call('wait',rid,'--timeout','1').returncode,124)
        self.assertFalse((d/'exit_code').exists())
        (self.root/'release').touch()
        self.assertEqual(self.call('wait',rid,'--timeout','3').returncode,0)
        self.assertEqual(self.call('result',rid).returncode,0)

    def test_cancel_stops_child_and_descendant_and_preserves_status(self):
        rid,d=self.start('descendant')
        heartbeat=self.root/'descendant.heartbeat'
        deadline=time.monotonic()+3
        while not heartbeat.exists() and time.monotonic()<deadline: time.sleep(.03)
        self.assertTrue(heartbeat.exists())
        self.assertEqual(self.call('cancel',rid).returncode,0)
        a=heartbeat.read_text(); parent=(self.root/'heartbeat').read_text(); time.sleep(.2)
        self.assertEqual(heartbeat.read_text(),a); self.assertEqual((self.root/'heartbeat').read_text(),parent)
        self.assertEqual(self.call('wait',rid).returncode,130)
        self.assertEqual(self.call('result',rid).returncode,130)
        self.call('status',rid)
        self.assertEqual(json.loads((d/'meta.json').read_text())['status'],'cancelled')

    def test_model_aliases_and_literal_safe_controls(self):
        for alias,expected in [('opus','claude-opus-5-5'),('fable','claude-fable-5-2'),('fable-5.1','claude-fable-5-1'),('sonnet','claude-sonnet-5-5'),('sonnet-5.5','claude-sonnet-5-5')]:
            with self.subTest(alias=alias):
                rid,d=self.start('success','--model',alias,'--safe-mode','--tools','','--strict-mcp-config','--no-session-persistence','--permission-prompts','none','--permission-mode','dontAsk','--max-budget-usd','0.10','--effort','low','--system-prompt','literal $(false) `false`')
                self.assertEqual(self.call('wait',rid).returncode,0)
                args=json.loads((self.root/'argv.json').read_text())
                self.assertEqual(args[args.index('--model')+1],expected)
                self.assertEqual(args[args.index('--tools')+1],'')
                self.assertEqual(args[args.index('--system-prompt')+1],'literal $(false) `false`')

    def test_unsupported_or_bypass_options_fail_before_launch(self):
        for options in [('--sandbox','workspace-write'),('--permission-mode','bypassPermissions'),('--tools',)]:
            self.assertNotEqual(self.call('start',*options).returncode,0)
        self.assertFalse((self.root/'argv.json').exists())

    def test_resume_options_pass_through(self):
        rid,d=self.start('success','--resume','fixture-session','--fork-session','--session-id','fixture-new-session')
        self.assertEqual(self.call('wait',rid).returncode,0)
        args=json.loads((self.root/'argv.json').read_text())
        self.assertEqual(args[args.index('--resume')+1],'fixture-session')
        self.assertIn('--fork-session',args)


if __name__=='__main__': unittest.main()
