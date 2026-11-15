import http.client,json,tempfile,threading,unittest
from server import make_server,MAX_BODY

SCHEMA={'title':'Workshop','fields':[{'id':'name','label':'Name','type':'text','required':True}]}
TOKEN='synthetic-test-token-not-a-secret-'*2

class AccessTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.server=make_server(self.temp.name+'/db',TOKEN,0);self.thread=threading.Thread(target=self.server.serve_forever);self.thread.start()
 def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.temp.cleanup()
 def req(self,path,data=None,owner=False,headers=None):
  h={'Content-Type':'application/json'}
  if owner:h['Authorization']='Bearer '+TOKEN
  h.update(headers or {});c=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
  c.request('GET' if data is None else 'POST',path,None if data is None else json.dumps(data),h);r=c.getresponse();raw=r.read();status=r.status;c.close()
  return status,json.loads(raw) if r.getheader('Content-Type')=='application/json' else raw.decode()
 def create(self):return self.req('/api/owner/forms',SCHEMA,True)[1]['id']
 def test_owner_routes_never_public(self):
  key=self.create()
  for path in ['/api/owner/forms',f'/api/owner/forms/{key}/inbox',f'/api/owner/forms/{key}/csv']:
   self.assertEqual(self.req(path)[0],401)
  self.assertEqual(self.req('/api/owner/forms',SCHEMA)[0],401)
 def test_separate_respondent_lifecycle_and_export(self):
  key=self.create();route=f'/api/forms/{key}';admin=f'/api/owner/forms/{key}'
  self.assertEqual(self.req(route)[0],410)
  self.assertEqual(self.req(admin+'/open',{'open':True},True)[0],200)
  status,form=self.req(route);self.assertEqual(status,200);self.assertNotIn('responses',form)
  answer={'revision':1,'answers':{'name':'=1+1'},'request_key':'one'}
  status,receipt=self.req(route+'/submit',answer);self.assertEqual(status,201)
  self.assertEqual(self.req(route+'/submit',answer)[1],receipt)
  inbox=self.req(admin+'/inbox',owner=True)[1]['responses'];self.assertEqual(len(inbox),1)
  self.assertIn("'=1+1",self.req(admin+'/csv',owner=True)[1])
  self.assertEqual(self.req(admin+'/delete-response',{'id':receipt['receipt']},True)[0],200)
  self.assertEqual(self.req(admin+'/inbox',owner=True)[1]['responses'],[])
 def test_origin_host_and_token_rejection(self):
  for h in [{'Host':'evil.example'},{'Origin':'https://evil.example'}]:self.assertEqual(self.req('/api/owner/forms',owner=True,headers=h)[0],403)
  self.assertEqual(self.req('/api/owner/forms',headers={'Authorization':'Bearer wrong'})[0],401)
 def test_validation_does_not_write(self):
  key=self.create();admin=f'/api/owner/forms/{key}';self.req(admin+'/open',{'open':True},True)
  status,_=self.req(f'/api/forms/{key}/submit',{'revision':1,'answers':{},'request_key':'one'})
  self.assertEqual(status,400);self.assertEqual(self.req(admin+'/inbox',owner=True)[1]['responses'],[])
 def test_oversized_request_rejected_before_read(self):
  self.assertEqual(self.req('/api/owner/forms',{},True,{'Content-Length':str(MAX_BODY+1)})[0],413)
 def test_public_cannot_revise_or_delete(self):
  key=self.create()
  self.assertEqual(self.req(f'/api/owner/forms/{key}/revise',{'revision':1,'schema':SCHEMA})[0],401)
  self.assertEqual(self.req(f'/api/forms/{key}/inbox')[0],404)
 def test_submission_rate_limit(self):
  # Invalid submissions also consume the bounded attempt budget.
  for i in range(60):self.req('/api/forms/'+'x'*22+'/submit',{})
  self.assertEqual(self.req('/api/forms/'+'x'*22+'/submit',{})[0],429)
 def test_weak_owner_key_rejected(self):
  with self.assertRaises(ValueError):make_server(self.temp.name+'/other','short',0)
