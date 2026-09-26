from __future__ import annotations
import hashlib,os,subprocess,sys,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from universal_law_query import stub_verify as v
class StubVerifyTests(unittest.TestCase):
    def row(self,payload=b'data'):return {'key':'x','repository':'Math-','visibility':'public','commit':'1'*40,'path':'frontiers/x.py','bytes':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}
    def test_validate_row_rejects_mutable_commit(self):
        row=self.row();row['commit']='main'
        with self.assertRaises(SystemExit):v.validate_row(row)
    def test_fetch_match_via_injected_fetch(self):
        row=self.row()
        with mock.patch.object(v,'load_candidates',return_value=[row]),mock.patch.object(v,'fetch',return_value=b'data'):self.assertEqual(v.main([]),0)
    def test_skip_env(self):
        with mock.patch.dict(os.environ,{'QUERY_STUB_VERIFY':'0'}):self.assertEqual(v.main([]),0)
    def test_root_wrapper_reexports_api(self):
        code='import verify_portable_stubs as v; print(all(hasattr(v,n) for n in ("load_candidates","validate_row","fetch_raw","check_math_tip_drift","main")))'
        p=subprocess.run([sys.executable,'-B','-S','-c',code],cwd=ROOT,capture_output=True,text=True,timeout=10);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout.strip(),'True')
if __name__=='__main__':unittest.main()
