import os,sys,tempfile,pathlib,unittest,types,importlib
from unittest.mock import patch
class ApiTests(unittest.TestCase):
 def test_operation_flow(self):
  from fastapi.testclient import TestClient
  with tempfile.TemporaryDirectory() as directory:
   with patch.dict(os.environ,{'ACCOUNT_DATA_DIR':directory,'BAILIAN_API_KEY':'fake-operator-test'}):
    sys.path.insert(0,str(pathlib.Path(__file__).parent))
    api=importlib.import_module('api')
    with api.db() as conn:conn.execute("INSERT INTO users(id,email,name,password) VALUES('test-user','test@example.invalid','test','mock-not-password')")
    with TestClient(api.app) as client:
     self.assertEqual(client.post('/analyze',json={'query':'test'}).status_code,401)
     account={'id':'test-user','key':None,'provider':'bailian'}
     class Engine:
      def chat(self,*args):return 'mock research output'
     class Thread:
      def __init__(self,target,args,**kwargs):self.target=target;self.args=args
      def start(self):self.target(*self.args)
     with patch.object(api,'user',return_value=account),patch.object(api.threading,'Thread',Thread),patch.dict(sys.modules,{'main':types.SimpleNamespace(DeepInsightEngine=Engine),'openai':types.SimpleNamespace(OpenAI=lambda **kwargs:object())}):
      self.assertTrue(client.get('/health').json()['llm_available'])
      for i in range(3):self.assertEqual(client.post('/analyze',json={'query':'test'},headers={'Idempotency-Key':str(i)}).status_code,200)
      self.assertEqual(api.LEDGER.status('test-user')['used'],3)
      self.assertFalse(client.get('/health').json()['llm_available'])
      self.assertEqual(client.post('/analyze',json={'query':'test'},headers={'Idempotency-Key':'0'}).status_code,200)
      self.assertEqual(client.post('/analyze',json={'query':'different'},headers={'Idempotency-Key':'0'}).status_code,409)
      self.assertEqual(client.post('/analyze',json={'query':'test'},headers={'Idempotency-Key':'4'}).status_code,409)
      self.assertEqual(api.LEDGER.status('test-user')['used'],3)
     # Dead personal-key worker must be released without touching live workers.
     with api.db() as conn:
      conn.execute("INSERT INTO tasks(id,user_id,query,status,created_at) VALUES('interrupted','test-user','mock','running','test')")
      conn.execute("INSERT INTO task_workers VALUES('interrupted',99999999)")
     with patch.object(api,'process_alive',return_value=False):api.recover_interrupted_tasks()
     with api.db() as conn:self.assertEqual(conn.execute("SELECT status FROM tasks WHERE id='interrupted'").fetchone()[0],'failed')
if __name__=='__main__':unittest.main()
