from __future__ import annotations
import json,subprocess,tarfile,tempfile,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from build_source_release import build_source_archive
class SourceRelease(unittest.TestCase):
    def make_repo(self,base:Path)->Path:
        repo=base/'repo';(repo/'src/universal_law_query').mkdir(parents=True);(repo/'tests').mkdir()
        (repo/'pyproject.toml').write_text('[project]\nname="universal-law-query"\nversion="0.1.0"\n');(repo/'README.md').write_text('readme\n');(repo/'AGENTS.md').write_text('agents\n')
        (repo/'research_query.py').write_text('pass\n');(repo/'catalog_entry_helper.py').write_text('pass\n');(repo/'verify_portable_stubs.py').write_text('pass\n');(repo/'src/universal_law_query/__init__.py').write_text('__all__=[]\n');(repo/'tests/test_x.py').write_text('pass\n')
        subprocess.run(['git','init','-q'],cwd=repo,check=True);subprocess.run(['git','config','user.email','test@example.com'],cwd=repo,check=True);subprocess.run(['git','config','user.name','test'],cwd=repo,check=True);subprocess.run(['git','add','.'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','fixture'],cwd=repo,check=True);return repo
    def test_archive_is_deterministic_and_public_package_scoped(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);repo=self.make_repo(base);a=base/'a.tar.gz';b=base/'b.tar.gz';ra=build_source_archive(repo,a,1700000000);rb=build_source_archive(repo,b,1700000000);self.assertEqual(a.read_bytes(),b.read_bytes());self.assertEqual(ra['archive_sha256'],rb['archive_sha256'])
            with tarfile.open(a,'r:gz') as tf:
                names=tf.getnames();self.assertIn('SOURCE_MANIFEST.json',names);self.assertIn('BUILD_INFO.json',names);self.assertFalse(any('.git' in n or '__pycache__' in n or n.startswith('sandbox') for n in names));manifest=json.load(tf.extractfile('SOURCE_MANIFEST.json'));self.assertFalse(manifest['scientific_status_authority']);self.assertFalse(manifest['release_eligible']);self.assertEqual(manifest['distribution'],'universal-law-query')
    def test_gitignored_untracked_file_is_not_packed(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);repo=self.make_repo(base);(repo/'.gitignore').write_text('src/ignored_secret.py\n');subprocess.run(['git','add','.gitignore'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','ignore'],cwd=repo,check=True);(repo/'src/ignored_secret.py').write_text('SECRET');out=base/'x.tar.gz';build_source_archive(repo,out,1700000000)
            with tarfile.open(out,'r:gz') as tf:self.assertNotIn('src/ignored_secret.py',tf.getnames())
    def test_symlink_license_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);repo=self.make_repo(base);outside=base/'outside';outside.write_text('fake');(repo/'LICENSE').symlink_to(outside);subprocess.run(['git','add','LICENSE'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','license'],cwd=repo,check=True)
            with self.assertRaisesRegex(ValueError,'symlink'):build_source_archive(repo,base/'x.tar.gz',1700000000)
    def test_output_inside_repo_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            repo=self.make_repo(Path(td))
            with self.assertRaises(ValueError):build_source_archive(repo,repo/'bad.tar.gz',1700000000)
if __name__=='__main__':unittest.main()
