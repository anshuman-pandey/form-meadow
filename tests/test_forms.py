import copy,csv,io,tempfile,unittest
from forms import Forms,FormError,definition,csv_cell

SCHEMA={'title':'Workshop signup','fields':[{'id':'name','label':'Your name','type':'text','required':True},{'id':'email','label':'Email','type':'email'},{'id':'track','label':'Track','type':'choice','options':['Design','Code']},{'id':'consent','label':'May we contact you about this workshop?','type':'consent','required':True}]}
VALUES={'name':'Ada','email':'ada@example.com','track':'Code','consent':True}

class FormsTest(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=self.temp.name+'/db';self.store=Forms(self.path);self.key=self.store.create(SCHEMA)
 def tearDown(self):self.store.close();self.temp.cleanup()
 def test_closed_by_default_and_reopen(self):
  with self.assertRaisesRegex(FormError,'closed'):self.store.submit(self.key,1,VALUES,'one')
  self.store.set_open(self.key,True);self.store.submit(self.key,1,VALUES,'one')
  self.store.set_open(self.key,False)
  with self.assertRaisesRegex(FormError,'closed'):self.store.submit(self.key,1,VALUES,'two')
 def test_old_answers_keep_original_labels(self):
  self.store.set_open(self.key,True);self.store.submit(self.key,1,VALUES,'one')
  updated=copy.deepcopy(SCHEMA);updated['fields'][0]['label']='Preferred name'
  self.store.revise(self.key,1,updated);self.store.submit(self.key,2,VALUES,'two')
  rows=self.store.inbox(self.key);self.assertEqual(rows[0]['schema']['fields'][0]['label'],'Preferred name');self.assertEqual(rows[1]['schema']['fields'][0]['label'],'Your name')
 def test_stale_editor_does_not_overwrite(self):
  self.store.revise(self.key,1,SCHEMA)
  with self.assertRaises(FormError):self.store.revise(self.key,1,SCHEMA)
  self.assertEqual(self.store.get(self.key)['revision'],2)
 def test_stale_submission_is_rejected(self):
  self.store.set_open(self.key,True);self.store.revise(self.key,1,SCHEMA)
  with self.assertRaisesRegex(FormError,'Questions changed'):self.store.submit(self.key,1,VALUES,'one')
  self.assertEqual(self.store.inbox(self.key),[])
 def test_retry_is_idempotent_even_after_close(self):
  self.store.set_open(self.key,True);first=self.store.submit(self.key,1,VALUES,'one');self.store.set_open(self.key,False)
  self.assertEqual(self.store.submit(self.key,1,VALUES,'one'),first);self.assertEqual(len(self.store.inbox(self.key)),1)
 def test_conflicting_retry_is_rejected(self):
  self.store.set_open(self.key,True);self.store.submit(self.key,1,VALUES,'one')
  with self.assertRaises(FormError):self.store.submit(self.key,1,dict(VALUES,name='Different'),'one')
 def test_invalid_answers_do_not_write(self):
  self.store.set_open(self.key,True)
  for patch in [{'name':''},{'email':'bad'},{'track':'Other'},{'consent':False},{'consent':'true'},{'unexpected':'value'},{'name':'x'*4001}]:
   with self.subTest(patch=patch),self.assertRaises(FormError):self.store.submit(self.key,1,dict(VALUES,**patch),'one')
  self.assertEqual(self.store.inbox(self.key),[])
 def test_csv_escapes_formulas_and_retains_multiline(self):
  self.store.set_open(self.key,True);self.store.submit(self.key,1,dict(VALUES,name=' =HYPERLINK("https://example.com")\nsecond line'),'one')
  rows=list(csv.DictReader(io.StringIO(self.store.export_csv(self.key))));self.assertEqual(rows[0]['answer'],'\' =HYPERLINK("https://example.com")\nsecond line');self.assertEqual(rows[-1]['answer'],'true')
 def test_data_survives_reopen(self):
  self.store.set_open(self.key,True);self.store.submit(self.key,1,VALUES,'one');self.store.close();self.store=Forms(self.path)
  self.assertEqual(self.store.inbox(self.key)[0]['answers'],VALUES)
 def test_optional_answers_have_explicit_defaults(self):
  self.store.set_open(self.key,True);self.store.submit(self.key,1,{'name':'Ada','consent':True},'one')
  self.assertEqual(self.store.inbox(self.key)[0]['answers']['email'],'')
 def test_duplicate_field_ids_rejected(self):
  bad=copy.deepcopy(SCHEMA);bad['fields'].append(bad['fields'][0])
  with self.assertRaises(FormError):definition(bad)
 def test_invalid_schema_is_rejected_before_revision(self):
  for patch in [{'title':''},{'fields':[]},{'unknown':True}]:
   with self.assertRaises(FormError):self.store.revise(self.key,1,dict(SCHEMA,**patch))
  self.assertEqual(self.store.get(self.key)['revision'],1)
 def test_csv_prefixes(self):
  for value in ['=1','+1','-1','@x','\tdata','\ntext','  =1','\u00a0=1']:
   self.assertTrue(csv_cell(value).startswith("'"))
 def test_revision_requires_positive_integer(self):
  for revision in [True,1.0,'1',0,-1]:
   with self.assertRaises(FormError):self.store.revise(self.key,revision,SCHEMA)
   with self.assertRaises(FormError):self.store.submit(self.key,revision,VALUES,'one')
 def test_cross_connection_stale_edit_and_state(self):
  other=Forms(self.path)
  try:
   self.store.revise(self.key,1,SCHEMA)
   with self.assertRaises(FormError):other.revise(self.key,1,SCHEMA)
   self.store.set_open(self.key,True);other.submit(self.key,2,VALUES,'one')
   self.assertEqual(len(self.store.inbox(self.key)),1)
  finally:other.close()
