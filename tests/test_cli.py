from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile,unittest,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'src'
class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'Math-').mkdir();(self.root/'Math-/proof.txt').write_bytes(b'candidate\n')
        self.registry=self.root/'catalog.json';self.registry.write_text(json.dumps({'schema_version':1,'scientific_status_authority':False,'repositories':{'Math-':{'full_name':'d6g8k5htny-coder/Math-','visibility':'public'}},'artifacts':[{'key':'p','repository':'Math-','path':'proof.txt','commit':'0'*40,'visibility':'public','bytes':10,'sha256':hashlib.sha256(b'candidate\n').hexdigest(),'scope':'synthetic'}]}))
    def run_module(self,*args):
        env=dict(os.environ,PYTHONPATH=str(SRC));return subprocess.run([sys.executable,'-B','-S','-m','universal_law_query.cli','--registry',str(self.registry),*args],capture_output=True,text=True,env=env,timeout=10)
    def test_module_list_lookup_verify_and_refusal(self):
        p=self.run_module();self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['keys'],['p'])
        p=self.run_module('--key','p');self.assertEqual(p.returncode,0,p.stderr);self.assertTrue(json.loads(p.stdout)['catalog_is_not_acceptance'])
        p=self.run_module('--verify','--workspace',str(self.root));self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['verified'],['p'])
        p=self.run_module('--key','missing');self.assertEqual(p.returncode,2);self.assertIn('UNKNOWN_KEY',p.stderr);self.assertNotIn('Traceback',p.stderr)
if __name__=='__main__':unittest.main()
