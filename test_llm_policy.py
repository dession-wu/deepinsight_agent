import importlib.util,tempfile,pathlib,unittest,concurrent.futures,os
from unittest.mock import patch
path=pathlib.Path(__file__).parent / 'llm_policy.py'
spec=importlib.util.spec_from_file_location('policy',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class PolicyTest(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.l=m.Ledger(pathlib.Path(self.tmp.name)/'quota.sqlite')
 def tearDown(self):self.tmp.cleanup()
 def test_concurrent_limit(self):
  def call(i):
   try:self.l.reserve('alice',str(i),'hash');return True
   except m.HTTPException:return False
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:self.assertEqual(sum(ex.map(call,range(8))),3)
  self.assertEqual(self.l.status('alice')['remaining'],0)
 def test_release_success_replay_isolation(self):
  self.l.reserve('alice','1','hash');self.l.finish('alice','1',False);self.assertEqual(self.l.status('alice')['remaining'],3)
  self.l.reserve('alice','1','hash');self.l.finish('alice','1',True,'result');self.assertEqual(self.l.reserve('alice','1','hash'),'result')
  self.assertEqual(self.l.status('bob')['remaining'],3)
  with self.assertRaises(m.HTTPException):self.l.reserve('alice','1','different')
 def test_failclosed_personal_priority(self):
  with self.assertRaises(m.HTTPException):m.scoped_credentials(('bailian','fake'),self.l)
  token=m.SCOPE.set({'owner':'alice','id':'op','fingerprint':'hash'})
  try:
   with patch.object(m,'operator_key',side_effect=AssertionError('must not load operator')):self.assertEqual(m.scoped_credentials(('bailian','fake'),self.l),('bailian','fake'))
   self.assertEqual(self.l.status('alice')['used'],0)
   with patch.object(m,'operator_key',return_value=None):
    with self.assertRaises(m.HTTPException):m.scoped_credentials(None,self.l)
   self.assertEqual(self.l.status('alice')['reserved'],0)
  finally:m.SCOPE.reset(token)
 def test_dead_worker_recovery(self):
  self.l.reserve('alice','1','hash')
  with patch.object(m,'process_alive',return_value=False):self.l.recover()
  self.assertEqual(self.l.status('alice')['remaining'],3)
 def test_live_worker_not_released(self):
  self.l.reserve('alice','1','hash');self.l.recover();self.assertEqual(self.l.status('alice')['reserved'],1)
 def test_personal_validation_mock(self):
  import sys,types
  from unittest.mock import MagicMock
  client=MagicMock();client.__enter__.return_value=client
  client.chat.completions.create.return_value.choices=[types.SimpleNamespace(message=types.SimpleNamespace(content='OK'))]
  factory=MagicMock(return_value=client)
  with patch.dict(sys.modules,{'openai':types.SimpleNamespace(OpenAI=factory)}):
   m.validate_personal_key('bailian','not-a-real-key')
   args=client.chat.completions.create.call_args.kwargs
   self.assertEqual(args['model'],'qwen3.7-flash');self.assertEqual(args['extra_body'],{'enable_thinking':False})
   self.assertEqual(self.l.status('alice')['remaining'],3)
   client.chat.completions.create.side_effect=RuntimeError('upstream')
   with self.assertRaises(m.HTTPException):m.validate_personal_key('bailian','not-a-real-key')
 def test_operator_key_environment_precedence_and_missing_default(self):
  with patch.dict(m.os.environ,{'BAILIAN_API_KEY':'fake-env-key','BAILIAN_API_KEY_FILE':'unused'},clear=True),patch.object(m,'Path',side_effect=AssertionError('must not read file')):
   self.assertEqual(m.operator_key(),'fake-env-key')
  with patch.dict(m.os.environ,{},clear=True),patch.object(m.Path,'is_file',return_value=False):
   self.assertIsNone(m.operator_key())
if __name__=='__main__':unittest.main()
