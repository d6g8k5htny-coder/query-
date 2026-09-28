from __future__ import annotations
import subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class InstallContract(unittest.TestCase):
    def test_local_package_installs_without_runtime_dependencies(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'site';target.mkdir()
            p=subprocess.run([sys.executable,'-m','pip','install','--quiet','--no-deps','--no-build-isolation','--target',str(target),str(ROOT)],capture_output=True,text=True,timeout=60);self.assertEqual(p.returncode,0,p.stderr)
            q=subprocess.run([sys.executable,'-c','import universal_law_query; print(universal_law_query.__name__)'],env={'PYTHONPATH':str(target)},capture_output=True,text=True,timeout=10);self.assertEqual(q.returncode,0,q.stderr);self.assertEqual(q.stdout.strip(),'universal_law_query')
if __name__=='__main__':unittest.main()
