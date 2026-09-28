from __future__ import annotations
import hashlib,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from universal_law_query.catalog_entry import HelperError,build_entry
class CatalogEntryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.payload=self.root/'x.py';self.payload.write_bytes(b'candidate\n')
    def test_build_entry(self):
        row=build_entry(file_path=self.payload,repository='Math-',repo_path='frontiers/x.py',key='x',scope='synthetic',commit='1'*40);self.assertEqual(row['bytes'],10);self.assertEqual(row['sha256'],hashlib.sha256(b'candidate\n').hexdigest());self.assertTrue(row['catalog_is_not_acceptance'])
    def test_refuse_sandbox_traversal_symlink_and_mutable_commit(self):
        cases=[dict(repository='sandbox',repo_path='x.py',commit='1'*40),dict(repository='Math-',repo_path='../x.py',commit='1'*40),dict(repository='Math-',repo_path='x.py',commit='main')]
        for kw in cases:
            with self.assertRaises(HelperError):build_entry(file_path=self.payload,key='x',scope='s',**kw)
        target=self.root/'t';target.write_bytes(b'candidate\n');link=self.root/'link';link.symlink_to(target)
        with self.assertRaises(HelperError):build_entry(file_path=link,repository='Math-',repo_path='link',key='x',scope='s',commit='1'*40)
    def test_root_wrapper_reexports_helper_api(self):
        code='import catalog_entry_helper as h; print(all(hasattr(h,n) for n in ("HelperError","build_entry","main")))'
        p=subprocess.run([sys.executable,'-B','-S','-c',code],cwd=ROOT,capture_output=True,text=True,timeout=10);self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(p.stdout.strip(),'True')
if __name__=='__main__':unittest.main()
