from __future__ import annotations
import hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from universal_law_query.catalog import CatalogError,load_catalog,lookup,verify
class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'Math-').mkdir();(self.root/'Math-/proof.txt').write_bytes(b'candidate\n');self.catalog=self.root/'catalog.json'
        self.data={'schema_version':1,'scientific_status_authority':False,'repositories':{'Math-':{'full_name':'d6g8k5htny-coder/Math-','visibility':'public'}},'artifacts':[{'key':'p','repository':'Math-','path':'proof.txt','commit':'0'*40,'visibility':'public','bytes':10,'sha256':hashlib.sha256(b'candidate\n').hexdigest(),'scope':'synthetic not acceptance'}]}
    def load(self,data=None):self.catalog.write_text(json.dumps(self.data if data is None else data));return load_catalog(self.catalog)
    def test_lookup_and_verify(self):
        data=self.load();self.assertTrue(lookup(data,'p')['catalog_is_not_acceptance']);self.assertEqual(verify(data,self.root)['verified'],['p'])
    def test_unknown_key_fails_closed(self):
        data=self.load()
        with self.assertRaisesRegex(CatalogError,'UNKNOWN_KEY'):lookup(data,'missing')
    def test_duplicate_json_key_is_refused(self):
        self.catalog.write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(CatalogError):load_catalog(self.catalog)
    def test_path_traversal_and_private_artifacts_refused(self):
        bad=json.loads(json.dumps(self.data));bad['artifacts'][0]['path']='../x'
        with self.assertRaises(CatalogError):self.load(bad)
        bad=json.loads(json.dumps(self.data));bad['repositories']['Math-']['visibility']='private'
        with self.assertRaises(CatalogError):self.load(bad)
        # Removing the type-first repository guard must fail the API contract,
        # while the existing CLI must continue to refuse malformed input.
        cases=[('empty list',[]),('list',['Math-']),('empty object',{}),
               ('object',{'name':'Math-'}),('null',None),('true',True),
               ('false',False),('integer',0),('float',1.5),
               ('empty string',''),('unknown string','Missing-'),('missing',None)]
        for label,value in cases:
            with self.subTest(repository=label):
                bad=json.loads(json.dumps(self.data))
                if label=='missing':bad['artifacts'][0].pop('repository')
                else:bad['artifacts'][0]['repository']=value
                self.catalog.write_text(json.dumps(bad))
                before=self.catalog.read_bytes()
                try:load_catalog(self.catalog)
                except Exception as error:
                    self.assertIsInstance(error,CatalogError)
                    self.assertEqual(str(error),'unknown repository')
                else:self.fail('malformed repository was accepted')
                self.assertEqual(self.catalog.read_bytes(),before)
                result=subprocess.run([sys.executable,'-B','-S',str(ROOT/'research_query.py'),
                                       '--registry',str(self.catalog)],capture_output=True,text=True,timeout=10)
                self.assertEqual(result.returncode,2,result.stderr)
                self.assertEqual(result.stdout,'')
                self.assertEqual(result.stderr,'REFUSED: unknown repository\n')
                self.assertEqual(self.catalog.read_bytes(),before)
    def test_changed_bytes_are_refused(self):
        data=self.load();(self.root/'Math-/proof.txt').write_bytes(b'altered!!\n')
        with self.assertRaisesRegex(CatalogError,'hash mismatch'):verify(data,self.root)
if __name__=='__main__':unittest.main()
