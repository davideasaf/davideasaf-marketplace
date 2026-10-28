import json
import os
from pathlib import Path
import subprocess
import tempfile
import signal
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/ask.sh'
FAKE = r'''#!/usr/bin/env python3
import json, os, pathlib, subprocess, sys, time
if '--version' in sys.argv: print('codex-fixture 1.0'); sys.exit(0)
p=pathlib.Path(os.environ['FIXTURE'])
a=sys.argv[1:]
(p/'invocation.json').write_text(json.dumps({'args':a,'prompt':sys.stdin.read()}))
mode=os.environ.get('RESPONSE','success')
if mode=='slow':
 child=subprocess.Popen(['sleep','60'])
 (p/'pids.json').write_text(json.dumps([os.getpid(),child.pid]))
 time.sleep(60)
text='   \n' if mode=='empty' else 'DONE: fixture answer'
if mode!='no-answer': pathlib.Path(a[a.index('-o')+1]).write_text(text)
print(json.dumps({'type':'thread.started','thread_id':'fixture-thread'}))
print(json.dumps({'type':'turn.failed','error':{'message':'fixture failure'}}) if mode=='error' else json.dumps({'type':'turn.completed','usage':{'input_tokens':3,'output_tokens':4}}))
'''


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.bin=self.root/'bin'; self.bin.mkdir()
        self.provider=self.bin/'codex'; self.provider.write_text(FAKE); self.provider.chmod(0o755)
        ioreg=self.bin/'ioreg'; ioreg.write_text('#!/bin/sh\necho "CGSSessionScreenIsLocked = No"\n'); ioreg.chmod(0o755)
        self.env=dict(os.environ,PATH=str(self.bin)+':'+os.environ['PATH'],
                      ASK_CODEX_BIN=str(self.provider),ASK_RUN_ROOT=str(self.root/'runs'),FIXTURE=str(self.root))
        for key in ['ASK_ALLOW_LAUNCHCTL','FABLE_ORCHESTRATOR_ISOLATION_JSON']:
            self.env.pop(key,None)

    def tearDown(self):
        if (self.root/'pids.json').exists():
            for pid in json.loads((self.root/'pids.json').read_text()):
                try: os.kill(pid,signal.SIGKILL)
                except ProcessLookupError: pass
        self.temp.cleanup()
    def run_script(self,*args,response='success'):
        return subprocess.run(['bash',str(SCRIPT),*args],env=dict(self.env,RESPONSE=response),
                              capture_output=True,text=True,timeout=15)
    def invocation(self): return json.loads((self.root/'invocation.json').read_text())
    def run_dir(self): return next((self.root/'runs/codex').iterdir())

    def test_case_insensitive_alias_and_repeatable_passthrough(self):
        result=self.run_script('ask','--model','AsTrA','--image','/tmp/one image.png',
                               '--image','/tmp/two.png','--config','feature=true',
                               '--config','label="two words"','question')
        self.assertEqual(result.returncode,0,result.stderr)
        args=self.invocation()['args']
        self.assertEqual(args[args.index('-m')+1],'gpt-6-astra')
        self.assertIn('--image=/tmp/one image.png',args)
        self.assertIn('--image=/tmp/two.png',args)
        self.assertIn('feature=true',args)
        self.assertIn('label="two words"',args)

    def test_relative_project_directory_is_resolved_once(self):
        project=self.root/'project'; project.mkdir()
        result=subprocess.run(['bash',str(SCRIPT),'ask','question','project'],cwd=self.root,
                              env=self.env,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        actual=Path(json.loads((self.run_dir()/'meta.json').read_text())['project_dir'])
        self.assertTrue(actual.is_absolute() and actual.samefile(project))

    def test_computer_use_settings_and_mission_reference(self):
        result=self.run_script('ask','--computer-use','inspect window')
        self.assertEqual(result.returncode,0,result.stderr)
        call=self.invocation(); args=call['args']
        self.assertEqual(args[args.index('-s')+1],'danger-full-access')
        self.assertIn('model_reasoning_effort="max"',args)
        self.assertIn('## Mission',call['prompt'])
        self.assertTrue(call['prompt'].endswith('inspect window'))
        meta=json.loads((self.run_dir()/'meta.json').read_text())
        self.assertTrue(meta['computer_use'])
        self.assertEqual(meta['outcome'],'DONE')

    def test_explicit_effort_wins_in_either_flag_order(self):
        for options in [('--effort','xhigh','--computer-use'),('--computer-use','--effort','max')]:
            with self.subTest(options=options):
                result=self.run_script('ask',*options,'inspect window')
                self.assertEqual(result.returncode,0,result.stderr)
                expected='xhigh' if options[0]=='--effort' else 'max'
                self.assertIn('model_reasoning_effort="'+expected+'"',self.invocation()['args'])

    def test_missing_mission_reference_prevents_launch(self):
        import shutil
        isolated=self.root/'skill'; shutil.copytree(SCRIPT.parents[1],isolated)
        preamble=isolated/'references/computer-use-mission.md'
        preamble.unlink(missing_ok=True)
        result=subprocess.run(['bash',str(isolated/'scripts/ask.sh'),'ask','--computer-use','inspect'],
                              env=self.env,capture_output=True,text=True,timeout=10)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('computer-use-mission.md',result.stderr)
        self.assertFalse((self.root/'invocation.json').exists())

    def test_empty_and_events_only_outputs_fail(self):
        for mode in ['empty','no-answer']:
            with self.subTest(response=mode):
                result=self.run_script('ask','question',response=mode)
                self.assertNotEqual(result.returncode,0)
                result=self.run_script('result','latest')
                self.assertNotEqual(result.returncode,0)

    def test_error_text_cannot_be_retrieved_as_success(self):
        self.assertNotEqual(self.run_script('ask','question',response='error').returncode,0)
        self.assertNotEqual(self.run_script('result','latest').returncode,0)
        self.assertNotEqual(self.run_script('wait','latest','--timeout','1').returncode,0)

    def test_reply_reuses_thread_settings_in_managed_mode(self):
        result=self.run_script('ask','--computer-use','--model','luna','--effort','max','inspect')
        self.assertEqual(result.returncode,0,result.stderr)
        result=self.run_script('reply','latest','--wait','continue with this scope')
        self.assertEqual(result.returncode,0,result.stderr)
        call=self.invocation(); args=call['args']
        self.assertEqual(args[:2],['exec','resume'])
        self.assertIn('fixture-thread',args)
        self.assertEqual(args[args.index('-m')+1],'gpt-6-luna')
        self.assertIn('model_reasoning_effort="max"',args)
        self.assertNotIn('-s',args)
        self.assertEqual(call['prompt'],'continue with this scope')
        self.assertEqual(result.stdout.strip(),'DONE: fixture answer')

    def test_preflight_is_read_only_and_reports_missing_support(self):
        self.env['CODEX_CONFIG']=str(self.root/'missing-config.toml')
        result=self.run_script('preflight',str(self.root))
        self.assertNotEqual(result.returncode,0)
        self.assertIn('NOT READY',result.stdout)
        self.assertFalse((self.root/'invocation.json').exists())

    def test_isolated_auth_cleanup_is_preserved(self):
        source=self.root/'source-auth.json'; source.write_text('{"fixture":true}')
        self.env.update(FABLE_ORCHESTRATOR_ISOLATION_JSON='{}',FABLE_ORCHESTRATOR_AUTH_SOURCE=str(source))
        result=self.run_script('ask','question')
        self.assertEqual(result.returncode,0,result.stderr)
        meta=json.loads((self.run_dir()/'meta.json').read_text())
        self.assertFalse((Path(meta['codex_home'])/'auth.json').exists())
        self.assertTrue(source.exists())
        self.assertTrue((self.run_dir()/'auth-removed').exists())

    def test_isolated_auth_cleanup_without_explicit_run_root(self):
        source=self.root/'source-auth.json'; source.write_text('{"fixture":true}')
        self.env.pop('ASK_RUN_ROOT')
        self.env.update(HOME=str(self.root), FABLE_ORCHESTRATOR_ISOLATION_JSON='{}',
                        FABLE_ORCHESTRATOR_AUTH_SOURCE=str(source))
        result=self.run_script('ask','question')
        self.assertEqual(result.returncode,0,result.stderr)
        run=next((self.root/'.cache/ask-runs/codex').iterdir())
        meta=json.loads((run/'meta.json').read_text())
        self.assertFalse((Path(meta['codex_home'])/'auth.json').exists())
        self.assertTrue((run/'auth-removed').exists())

    def test_cancel_stops_provider_and_descendant(self):
        with (self.root/'stdout').open('w') as stdout, (self.root/'stderr').open('w') as stderr:
            proc=subprocess.Popen(['bash',str(SCRIPT),'run','question'],
                                  env=dict(self.env,RESPONSE='slow'),stdout=stdout,stderr=stderr)
            try:
                deadline=time.monotonic()+8
                while not (self.root/'pids.json').exists() and time.monotonic()<deadline:
                    time.sleep(.05)
                self.assertTrue((self.root/'pids.json').exists())
                result=self.run_script('cancel','latest')
                self.assertEqual(result.returncode,0,result.stderr)
                proc.wait(timeout=8)
                for pid in json.loads((self.root/'pids.json').read_text()):
                    ps=subprocess.run(['ps','-p',str(pid),'-o','stat='],capture_output=True,text=True)
                    self.assertTrue(not ps.stdout.strip() or ps.stdout.strip().startswith('Z'),f'process {pid} survived')
                self.assertEqual(json.loads((self.run_dir()/'meta.json').read_text())['status'],'cancelled')
            finally:
                if proc.poll() is None: proc.kill(); proc.wait()


if __name__=='__main__': unittest.main()
