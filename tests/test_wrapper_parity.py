from __future__ import annotations
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'src';WRAPPER=ROOT/'research_query.py'
class WrapperParity(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);(self.root/'Math-').mkdir();(self.root/'Math-/proof.txt').write_bytes(b'candidate\n')
        self.registry=self.root/'catalog.json';self.registry.write_text(json.dumps({'schema_version':1,'scientific_status_authority':False,'repositories':{'Math-':{'full_name':'d6g8k5htny-coder/Math-','visibility':'public'}},'artifacts':[{'key':'p','repository':'Math-','path':'proof.txt','commit':'0'*40,'visibility':'public','bytes':10,'sha256':hashlib.sha256(b'candidate\n').hexdigest(),'scope':'synthetic'}]}))
    def run_wrapper(self,*args):return subprocess.run([sys.executable,'-B','-S',str(WRAPPER),'--registry',str(self.registry),*args],capture_output=True,text=True,timeout=10)
    def run_module(self,*args):
        env=dict(os.environ,PYTHONPATH=str(SRC));return subprocess.run([sys.executable,'-B','-S','-m','universal_law_query.cli','--registry',str(self.registry),*args],capture_output=True,text=True,env=env,timeout=10)
    def test_wrapper_exists_and_matches_module(self):
        for args in [(),('--key','p'),('--verify','--workspace',str(self.root)),('--key','missing')]:
            a=self.run_wrapper(*args);b=self.run_module(*args);self.assertEqual((a.returncode,a.stdout,a.stderr),(b.returncode,b.stdout,b.stderr),args)
    def test_wrapper_reexports_legacy_api(self):
        code='import research_query as q; print(all(hasattr(q,n) for n in ("CatalogError","load_catalog","lookup","verify","main")))'
        p=subprocess.run([sys.executable,'-B','-S','-c',code],cwd=ROOT,capture_output=True,text=True,timeout=10);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout.strip(),'True')
if __name__=='__main__':unittest.main()
