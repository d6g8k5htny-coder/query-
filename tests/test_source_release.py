from __future__ import annotations
import hashlib,json,os,re,shutil,subprocess,tarfile,tempfile,unittest
from unittest import mock
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
    def test_archive_retains_public_metadata_without_admitting_other_root_files(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            repo = self.make_repo(base)
            public_files = {
                'CITATION.cff': b'cff-version: 1.2.0\n',
                'SUPPORT.md': b'Public support routes.\n',
                'SECURITY.md': b'Security reporting routes.\n',
                'MANIFEST.in': b'include CITATION.cff SUPPORT.md SECURITY.md\n',
            }
            for name, content in public_files.items():
                (repo / name).write_bytes(content)
            (repo / 'private-notes.md').write_text('Do not distribute.\n')
            subprocess.run(['git', 'add', '.'], cwd=repo, check=True)
            subprocess.run(['git', 'commit', '-qm', 'metadata fixture'], cwd=repo, check=True)
            out = base / 'source.tar.gz'
            build_source_archive(repo, out, 1700000000)
            with tarfile.open(out, 'r:gz') as tf:
                for name, content in public_files.items():
                    self.assertIn(name, tf.getnames())
                    self.assertEqual(tf.extractfile(name).read(), content)
                self.assertNotIn('private-notes.md', tf.getnames())
    def test_symlink_license_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);repo=self.make_repo(base);outside=base/'outside';outside.write_text('fake');(repo/'LICENSE').symlink_to(outside);subprocess.run(['git','add','LICENSE'],cwd=repo,check=True);subprocess.run(['git','commit','-qm','license'],cwd=repo,check=True)
            with self.assertRaisesRegex(ValueError,'symlink'):build_source_archive(repo,base/'x.tar.gz',1700000000)
    def test_output_inside_repo_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            repo=self.make_repo(Path(td))
            with self.assertRaises(ValueError):build_source_archive(repo,repo/'bad.tar.gz',1700000000)

# Independent contract: do not derive these expectations from the builder.
ARCHIVE_ROOT_FILES = (
    'AGENTS.md', 'CITATION.cff', 'LICENSE', 'MANIFEST.in',
    'README.md', 'SECURITY.md', 'SUPPORT.md', 'pyproject.toml',
    'research_query.py', 'catalog_entry_helper.py', 'verify_portable_stubs.py',
)
ARCHIVE_PACKAGE_FILES = tuple('src/universal_law_query/' + name for name in (
    '__init__.py', 'catalog.py', 'catalog_entry.py', 'cli.py', 'stub_verify.py',
))
ARCHIVE_TEST_FILES = tuple('tests/' + name for name in (
    'test_catalog.py', 'test_catalog_entry.py', 'test_cli.py',
    'test_stub_verify.py', 'test_wrapper_parity.py',
))
ARCHIVE_PAYLOADS = frozenset(ARCHIVE_ROOT_FILES + ARCHIVE_PACKAGE_FILES + ARCHIVE_TEST_FILES)
GENERATED_FILES = frozenset(('BUILD_INFO.json', 'SOURCE_MANIFEST.json'))
OFFLINE_METHODS = {
    'test_catalog.CatalogTests': (
        'test_changed_bytes_are_refused', 'test_duplicate_json_key_is_refused',
        'test_lookup_and_verify', 'test_path_traversal_and_private_artifacts_refused',
        'test_unknown_key_fails_closed',
    ),
    'test_catalog_entry.CatalogEntryTests': (
        'test_build_entry', 'test_refuse_sandbox_traversal_symlink_and_mutable_commit',
        'test_root_wrapper_reexports_helper_api',
    ),
    'test_cli.CliTests': ('test_module_list_lookup_verify_and_refusal',),
    'test_stub_verify.StubVerifyTests': (
        'test_fetch_match_via_injected_fetch', 'test_root_wrapper_reexports_api',
        'test_skip_env', 'test_validate_row_rejects_mutable_commit',
    ),
    'test_wrapper_parity.WrapperParity': (
        'test_wrapper_exists_and_matches_module', 'test_wrapper_reexports_legacy_api',
    ),
}
EXPECTED_METHOD_IDS = sorted(cls + '.' + method for cls, methods in OFFLINE_METHODS.items() for method in methods)

# These new children explicitly choose their own normal/-O mode. Existing
# selected-test child commands are left unchanged (they use -B -S, not -O).
PACKAGE_PROBE = r'''
import importlib, importlib.util, json, os, sys
from pathlib import Path
root = Path.cwd().resolve()
mode, action, target, forbidden = sys.argv[1:]
print('PROBE_OPTIMIZE=' + str(sys.flags.optimize), file=sys.stderr, flush=True)
def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)
require(sys.flags.optimize == int(mode), 'OPTIMIZATION_MODE')
require(os.environ.get('QUERY_STUB_VERIFY') == '1', 'POSITIVE_ENVIRONMENT')
require(all(name not in os.environ for name in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE')), 'INHERITED_PYTHON_ENVIRONMENT')
sys.path.insert(0, str(root / 'src'))
require(not any(Path(p or '.').resolve().is_relative_to(Path(forbidden)) for p in sys.path), 'SOURCE_PATH_LEAK')
require(importlib.util.find_spec('query_source_only_sentinel') is None, 'SOURCE_SENTINEL_LEAK')
package = importlib.import_module('universal_law_query')
if action == 'root':
    init = root / 'src/universal_law_query/__init__.py'
    require(init.is_file() and not init.is_symlink(), 'PACKAGE_ROOT_REGULAR_INITIALIZER')
    require(package.__file__ is not None and Path(package.__file__).resolve() == init, 'PACKAGE_ROOT_FILE')
    require(package.__spec__.origin is not None and Path(package.__spec__.origin).resolve() == init, 'PACKAGE_ROOT_ORIGIN')
    require(all(hasattr(package, name) for name in ('CatalogError', 'load_catalog', 'lookup', 'verify')), 'PACKAGE_ROOT_EXPORTS')
    for name in ('catalog', 'catalog_entry', 'cli', 'stub_verify'):
        importlib.import_module('universal_law_query.' + name)
    for name in ('research_query', 'catalog_entry_helper', 'verify_portable_stubs'):
        importlib.import_module(name)
else:
    importlib.import_module(target)
require([Path(p).resolve() for p in package.__path__] == [root / 'src/universal_law_query'], 'PACKAGE_SEARCH_LOCATION')
origins = {}
for name, module in tuple(sys.modules.items()):
    if name.startswith('universal_law_query') or name in ('research_query', 'catalog_entry_helper', 'verify_portable_stubs'):
        if name == 'universal_law_query' and action == 'namespace':
            require(module.__file__ is None and module.__spec__.origin is None, 'EXPECTED_NAMESPACE_PACKAGE')
            continue
        origin = getattr(module, '__file__', None)
        require(origin is not None and Path(origin).resolve().is_relative_to(root), 'PRODUCT_ORIGIN: ' + name)
        origins[name] = str(Path(origin).resolve().relative_to(root))
print(json.dumps({'optimize': sys.flags.optimize, 'action': action, 'origins': origins, 'namespace': package.__file__ is None}, sort_keys=True))
'''

# Use unittest's same discovery CLI with exit=False so the actual outer process
# can report its collection, result, and separate synthetic/skip fixture output.
SUBSET_RUNNER = r'''
import contextlib, importlib.util, io, json, os, sys, unittest
from pathlib import Path
expected_mode = int(sys.argv[1])
forbidden = Path(sys.argv[2])
if any(name in os.environ for name in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE')):
    raise RuntimeError('INHERITED_PYTHON_ENVIRONMENT')
if importlib.util.find_spec('query_source_only_sentinel') is not None:
    raise RuntimeError('SOURCE_SENTINEL_LEAK')
if sys.flags.optimize != expected_mode or os.environ.get('QUERY_STUB_VERIFY') != '1':
    raise RuntimeError('OUTER_MODE_OR_POSITIVE_ENVIRONMENT')
class RecordingResult(unittest.TextTestResult):
    def startTest(self, test):
        super().startTest(test)
        self.outputs[test.id()] = ''
        self.capture = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.capture)
        self.redirect.__enter__()
    def stopTest(self, test):
        self.redirect.__exit__(None, None, None)
        self.outputs[test.id()] = self.capture.getvalue()
        super().stopTest(test)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outputs = {}
program = unittest.main(module=None, argv=['unittest', 'discover', '-s', 'tests', '-p', 'test_*.py', '-v'],
                        testRunner=unittest.TextTestRunner(resultclass=RecordingResult, verbosity=2), exit=False)
result = program.result
if any(Path(p or '.').resolve().is_relative_to(forbidden) for p in sys.path):
    raise RuntimeError('SOURCE_PATH_LEAK')
origins = {name: str(Path(module.__file__).resolve()) for name, module in tuple(sys.modules.items())
           if name.startswith('universal_law_query') and getattr(module, '__file__', None)}
report = {'optimize': sys.flags.optimize, 'ids': sorted(result.outputs), 'run': result.testsRun,
          'failures': len(result.failures), 'errors': len(result.errors), 'skipped': len(result.skipped),
          'expected_failures': len(result.expectedFailures), 'unexpected_successes': len(result.unexpectedSuccesses),
          'outputs': result.outputs, 'origins': origins}
print(json.dumps(report, sort_keys=True))
raise SystemExit(not result.wasSuccessful())
'''


HELP_RUNNER = r'''
import contextlib, io, json, runpy, sys
output = io.StringIO()
sys.argv = ['research_query.py', '--help']
with contextlib.redirect_stdout(output):
    try:
        runpy.run_path('research_query.py', run_name='__main__')
    except SystemExit as exit_status:
        if exit_status.code != 0:
            raise
print(json.dumps({'optimize': sys.flags.optimize, 'help': output.getvalue()}))
'''


class ExtractedPackageContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'source-checkout'
        self.repo.mkdir()
        tracked = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '-z']).decode().split('\0')
        self.source_bytes = {}
        for name in filter(None, tracked):
            source = ROOT / name
            self.assertTrue(source.is_file() and not source.is_symlink(), name)
            raw = source.read_bytes()
            self.source_bytes[name] = raw
            dest = self.repo / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(raw)
        # A source-only import sentinel is tracked but is not an archive member.
        (self.repo / 'query_source_only_sentinel.py').write_text('SOURCE_ONLY = True\n')
        # This inert fixture-only marker must not revive the obsolete allowlist entry.
        (self.repo / 'OWNER_STOP.md').write_text('Excluded archive fixture marker.\n')
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'test')
        self.git('add', '.')
        self.git('commit', '-qm', 'authenticated source fixture')
        self.assertEqual(self.git('status', '--porcelain'), '')
        for name, raw in self.source_bytes.items():
            committed = subprocess.check_output(['git', '-C', str(self.repo), 'show', 'HEAD:' + name])
            self.assertEqual(committed, raw, name)
        self.archive = self.base / 'source.tar.gz'
        # The complete-checkout contract opts into producer-side membership.
        self.result = build_source_archive(self.repo, self.archive, 1700000000, strict_members=True)
        self.extracted = self.base / 'extracted'
        self.extracted.mkdir()

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def extract_verified(self):
        with tarfile.open(self.archive, 'r:gz') as archive:
            members = archive.getmembers()
            names = [member.name for member in members]
            self.assertEqual(len(names), len(set(names)), 'duplicate archive members')
            self.assertEqual(set(names), ARCHIVE_PAYLOADS | GENERATED_FILES,
                             'exact archive membership: missing=' + repr(sorted((ARCHIVE_PAYLOADS | GENERATED_FILES) - set(names))) +
                             '; extra=' + repr(sorted(set(names) - (ARCHIVE_PAYLOADS | GENERATED_FILES))))
            for member in members:
                self.assertTrue(member.isfile(), member.name)
                self.assertEqual((member.mode, member.uid, member.gid, member.uname, member.gname, member.mtime),
                                 (0o644, 0, 0, '', '', 1700000000))
            manifest_raw = archive.extractfile('SOURCE_MANIFEST.json').read()
            manifest = json.loads(manifest_raw)
            rows = manifest['files']
            self.assertEqual([row['path'] for row in rows], sorted(ARCHIVE_PAYLOADS))
            self.assertEqual(manifest['commit'], self.git('rev-parse', 'HEAD'))
            self.assertFalse(manifest['scientific_status_authority'])
            self.assertTrue(manifest['release_eligible'])
            self.assertEqual(self.result['file_count'], 21)
            self.assertEqual(self.result['manifest_sha256'], hashlib.sha256(manifest_raw).hexdigest())
            self.assertEqual(self.result['archive_sha256'], hashlib.sha256(self.archive.read_bytes()).hexdigest())
            build = json.load(archive.extractfile('BUILD_INFO.json'))
            self.assertEqual(build['commit'], manifest['commit'])
            self.assertEqual(build['source_date_epoch'], 1700000000)
            for row in rows:
                raw = archive.extractfile(row['path']).read()
                self.assertEqual(raw, self.source_bytes[row['path']], row['path'])
                self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']))
            # Extraction occurs only after every member is an expected regular file.
            archive.extractall(self.extracted, **({'filter': 'data'} if hasattr(tarfile, 'data_filter') else {}))
        self.verify_extraction(self.extracted)
        self.assertFalse(self.extracted.is_relative_to(self.repo))
        self.assertFalse(self.extracted.is_relative_to(ROOT))

    def verify_extraction(self, root):
        paths = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() or p.is_symlink()}
        self.assertEqual(paths, ARCHIVE_PAYLOADS | GENERATED_FILES, 'extracted membership')
        manifest = json.loads((root / 'SOURCE_MANIFEST.json').read_text())
        self.assertEqual([row['path'] for row in manifest['files']], sorted(ARCHIVE_PAYLOADS))
        for row in manifest['files']:
            path = root / row['path']
            self.assertFalse(path.is_symlink(), row['path'])
            raw = path.read_bytes()
            self.assertEqual((len(raw), hashlib.sha256(raw).hexdigest()), (row['bytes'], row['sha256']))

    def clean_env(self):
        env = dict(os.environ)
        for name in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE'):
            env.pop(name, None)
        env['QUERY_STUB_VERIFY'] = '1'
        return env

    def child(self, root, optimized, *args):
        flags = ['-B', '-O', '-S'] if optimized else ['-B', '-S']
        return subprocess.run([sys.executable, *flags, *args], cwd=root, env=self.clean_env(),
                              capture_output=True, text=True, timeout=60)

    def probe(self, root, optimized, action='root', target=''):
        result = self.child(root, optimized, '-c', PACKAGE_PROBE, str(int(optimized)), action, target, str(self.repo))
        self.assertIn('PROBE_OPTIMIZE=' + str(int(optimized)) + '\n', result.stderr)
        return result

    def test_exact_archive_members_manifest_and_hashes(self):
        self.extract_verified()

    def test_extracted_help_and_exact_offline_subset_in_both_modes(self):
        self.extract_verified()
        # Prove inherited source paths, optimization and the skip switch cannot
        # turn the positive fixtures into a false pass.
        with mock.patch.dict(os.environ, {'PYTHONPATH': str(self.repo), 'PYTHONHOME': str(self.repo),
                                         'PYTHONOPTIMIZE': '2', 'QUERY_STUB_VERIFY': '0'}):
            for optimized in (False, True):
                with self.subTest(optimized=optimized):
                    probe = self.probe(self.extracted, optimized)
                    self.assertEqual(probe.returncode, 0, probe.stderr)
                    self.assertEqual(json.loads(probe.stdout)['optimize'], int(optimized))
                    help_run = self.child(self.extracted, optimized, '-c', HELP_RUNNER)
                    self.assertEqual(help_run.returncode, 0, help_run.stderr)
                    help_report = json.loads(help_run.stdout)
                    self.assertEqual(help_report['optimize'], int(optimized))
                    self.assertIn('--registry', help_report['help'])
                    subset = self.child(self.extracted, optimized, '-c', SUBSET_RUNNER, str(int(optimized)), str(self.repo))
                    self.assertEqual(subset.returncode, 0, subset.stderr)
                    report = json.loads(subset.stdout)
                    self.assertEqual(report['optimize'], int(optimized))
                    self.assertEqual(report['ids'], EXPECTED_METHOD_IDS)
                    self.assertEqual(report['run'], 15)
                    for key in ('failures', 'errors', 'skipped', 'expected_failures', 'unexpected_successes'):
                        self.assertEqual(report[key], 0, key)
                    positive = report['outputs']['test_stub_verify.StubVerifyTests.test_fetch_match_via_injected_fetch']
                    self.assertEqual(json.loads(positive)['verified'], ['x'])
                    skipped = report['outputs']['test_stub_verify.StubVerifyTests.test_skip_env']
                    self.assertEqual(skipped.strip(), 'SKIPPED_STUB_VERIFY')
                    self.assertTrue(report['origins'])
                    for origin in report['origins'].values():
                        self.assertTrue(Path(origin).is_relative_to(self.extracted), origin)
                    print('EXTRACTED_SUBSET ' + json.dumps({'optimize': report['optimize'], 'ids': report['ids'],
                          'run': 15, 'failures': 0, 'errors': 0, 'skipped': 0,
                          'help_optimize': help_report['optimize'], 'package_probe_optimize': json.loads(probe.stdout)['optimize'],
                          'synthetic_verified': ['x'], 'deliberate_skip': skipped.strip()}, sort_keys=True))
        self.verify_extraction(self.extracted)

    def test_omissions_fail_membership_and_consuming_probes(self):
        self.extract_verified()
        wrappers = ('research_query.py', 'catalog_entry_helper.py', 'verify_portable_stubs.py')
        required = wrappers + ARCHIVE_PACKAGE_FILES + ARCHIVE_TEST_FILES
        for index, name in enumerate(required):
            with self.subTest(omitted=name):
                omitted = self.base / ('omitted-' + str(index))
                shutil.copytree(self.extracted, omitted)
                (omitted / name).unlink()
                with self.assertRaisesRegex(AssertionError, 'extracted membership'):
                    self.verify_extraction(omitted)
                if name not in wrappers + ARCHIVE_PACKAGE_FILES:
                    continue  # Their contract is membership, not product import.
                for optimized in (False, True):
                    if name.endswith('/__init__.py'):
                        negative = self.probe(omitted, optimized)
                        self.assertNotEqual(negative.returncode, 0)
                        self.assertIn('PACKAGE_ROOT_REGULAR_INITIALIZER', negative.stderr)
                        namespace = self.probe(omitted, optimized, 'namespace', 'universal_law_query.cli')
                        self.assertEqual(namespace.returncode, 0, namespace.stderr)
                        observed = json.loads(namespace.stdout)
                        self.assertTrue(observed['namespace'])
                        self.assertEqual(observed['optimize'], int(optimized))
                    else:
                        module = Path(name).stem
                        target = module if name in wrappers else 'universal_law_query.' + module
                        negative = self.probe(omitted, optimized, 'import', target)
                        self.assertNotEqual(negative.returncode, 0)
                        self.assertIn('ModuleNotFoundError', negative.stderr)
                        self.assertIn(target, negative.stderr)
                print('OMISSION_CONTROL ' + json.dumps({'omitted': name, 'membership_rejected': True,
                      'probe_modes': [0, 1], 'namespace_submodule_survives': name.endswith('/__init__.py')}, sort_keys=True))


# LICENSE is the one optional member; every other curated name is mandatory.
MANDATORY_PAYLOADS = ARCHIVE_PAYLOADS - {'LICENSE'}


class StrictMembers(unittest.TestCase):
    """Producer-side membership for the complete package archive (query-#29).

    The fixture holds synthetic text under every curated name, and nothing in it
    is imported. Expected names come from the independent constants above, not
    from the builder.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.repo = self.base / 'complete-checkout'
        for name in sorted(ARCHIVE_PAYLOADS):
            path = self.repo / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('synthetic ' + name + '\n')
        (self.repo / 'pyproject.toml').write_text('[project]\nname="universal-law-query"\nversion="0.1.0"\n')
        self.git('init', '-q')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'test')
        self.git('config', 'core.safecrlf', 'false')
        self.commit('complete fixture')
        # Its parent directory does not exist, so a refusal can be shown to create nothing.
        self.out = self.base / 'out' / 'archive.tar.gz'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args], text=True).strip()

    def commit(self, message):
        self.git('add', '-A')
        self.git('commit', '-qm', message)
        self.assertEqual(self.git('status', '--porcelain'), '')

    def members(self, archive):
        with tarfile.open(archive, 'r:gz') as tf:
            return set(tf.getnames())

    def refusal(self, missing, unexpected):
        return re.escape('archive membership refused: missing=' + repr(missing) + '; unexpected=' + repr(unexpected)) + '$'

    def assert_refused_before_output(self, pattern):
        with self.assertRaisesRegex(ValueError, pattern):
            build_source_archive(self.repo, self.out, 1700000000, strict_members=True)
        self.assertFalse(self.out.parent.exists(), 'a refusal must not create the output directory')
        existing = self.base / 'existing.tar.gz'
        existing.write_bytes(b'sentinel')
        with self.assertRaisesRegex(ValueError, pattern):
            build_source_archive(self.repo, existing, 1700000000, strict_members=True)
        self.assertEqual(existing.read_bytes(), b'sentinel', 'a refusal must not truncate an existing output')

    def test_complete_checkout_strict_and_default_calls_agree(self):
        default = self.base / 'default.tar.gz'
        strict = self.base / 'strict.tar.gz'
        result_default = build_source_archive(self.repo, default, 1700000000)
        result_strict = build_source_archive(self.repo, strict, 1700000000, strict_members=True)
        self.assertEqual(default.read_bytes(), strict.read_bytes())
        self.assertEqual(result_default, result_strict)
        self.assertEqual(self.members(strict), ARCHIVE_PAYLOADS | GENERATED_FILES)
        self.assertEqual((result_strict['file_count'], result_strict['release_eligible']), (21, True))

    def test_strict_without_license_is_complete_but_not_eligible(self):
        self.git('rm', '-q', 'LICENSE')
        self.commit('no license')
        result = build_source_archive(self.repo, self.out, 1700000000, strict_members=True)
        self.assertEqual(self.members(self.out), MANDATORY_PAYLOADS | GENERATED_FILES)
        self.assertEqual((result['file_count'], result['release_eligible']), (20, False))

    def test_strict_refuses_each_missing_mandatory_member_before_output(self):
        self.assertEqual(len(MANDATORY_PAYLOADS), 20)
        for name in sorted(MANDATORY_PAYLOADS):
            with self.subTest(missing=name):
                self.git('rm', '-q', name)
                self.commit('delete ' + name)
                try:
                    self.assert_refused_before_output(self.refusal([name], []))
                finally:
                    self.git('reset', '-q', '--hard', 'HEAD~1')

    def test_strict_refuses_directory_substitutes(self):
        cases = (
            ('SUPPORT.md', ['SUPPORT.md']),
            ('src/universal_law_query/__init__.py', ['src/universal_law_query/__init__.py']),
            # Optional when absent, never when something else sits under its name.
            ('LICENSE', []),
        )
        for name, missing in cases:
            with self.subTest(substituted=name):
                self.git('rm', '-q', name)
                (self.repo / name).mkdir()
                (self.repo / name / 'replacement.txt').write_text('synthetic descendant\n')
                self.commit('directory at ' + name)
                try:
                    self.assert_refused_before_output(self.refusal(missing, [name + '/replacement.txt']))
                finally:
                    self.git('reset', '-q', '--hard', 'HEAD~1')

    def test_near_name_sibling_is_never_selected(self):
        (self.repo / 'SUPPORT.md.extra').write_text('synthetic sibling\n')
        self.commit('near-name sibling')
        result = build_source_archive(self.repo, self.out, 1700000000, strict_members=True)
        self.assertEqual(self.members(self.out), ARCHIVE_PAYLOADS | GENERATED_FILES)
        self.assertEqual(result['file_count'], 21)

    def test_strict_refuses_the_partial_legacy_fixture(self):
        partial = SourceRelease().make_repo(self.base / 'partial')
        with self.assertRaisesRegex(ValueError, r"^archive membership refused: missing=\[.*'CITATION\.cff'.*\]; unexpected=\[\]$"):
            build_source_archive(partial, self.out, 1700000000, strict_members=True)
        self.assertFalse(self.out.parent.exists())
        # The five original tests keep reaching this fixture through the default call.
        self.assertFalse(build_source_archive(partial, self.base / 'partial.tar.gz', 1700000000)['release_eligible'])

    def test_strict_keeps_the_symlink_refusal_for_license(self):
        outside = self.base / 'outside-license'
        outside.write_text('not the license\n')
        self.git('rm', '-q', 'LICENSE')
        (self.repo / 'LICENSE').symlink_to(outside)
        self.commit('license symlink')
        with self.assertRaisesRegex(ValueError, r'^symlink payload refused: LICENSE$'):
            build_source_archive(self.repo, self.out, 1700000000, strict_members=True)
        self.assertFalse(self.out.parent.exists())

    def test_default_call_stays_permissive_about_a_missing_member(self):
        # Compatibility boundary recorded in query-#29: only strict_members=True refuses.
        self.git('rm', '-q', 'SUPPORT.md')
        self.commit('delete SUPPORT.md')
        result = build_source_archive(self.repo, self.out, 1700000000)
        self.assertEqual((result['file_count'], result['release_eligible']), (20, True))
        self.assertNotIn('SUPPORT.md', self.members(self.out))

    def test_strict_binds_payload_bytes_to_the_commit_despite_index_hints(self):
        for hint in ('assume-unchanged', 'skip-worktree'):
            with self.subTest(hint=hint):
                self.git('update-index', '--' + hint, 'README.md')
                try:
                    # A hinted file whose bytes are still the commit's is a positive control.
                    unchanged = self.base / ('hinted-' + hint + '.tar.gz')
                    result = build_source_archive(self.repo, unchanged, 1700000000, strict_members=True)
                    self.assertEqual(result['file_count'], 21)
                    (self.repo / 'README.md').write_text('altered behind the index hint\n')
                    self.assertEqual(self.git('status', '--porcelain'), '', 'the hint must hide the change from status')
                    self.assert_refused_before_output(r'^payload differs from its committed blob: README\.md$')
                finally:
                    self.git('update-index', '--no-' + hint, 'README.md')
                    self.git('checkout', '--', 'README.md')
                self.assertEqual(self.git('status', '--porcelain'), '')

    def test_strict_refuses_bytes_changed_by_checkout_normalization(self):
        # Deliberate choice: working bytes that are not the committed blob are refused, never normalized.
        (self.repo / '.gitattributes').write_text('SUPPORT.md text eol=crlf\n')
        (self.repo / 'SUPPORT.md').write_bytes(b'synthetic SUPPORT.md\r\n')
        self.commit('crlf working copy, lf blob')
        committed = subprocess.check_output(['git', '-C', str(self.repo), 'cat-file', 'blob', 'HEAD:SUPPORT.md'])
        self.assertEqual(committed, b'synthetic SUPPORT.md\n')
        self.assertEqual((self.repo / 'SUPPORT.md').read_bytes(), b'synthetic SUPPORT.md\r\n')
        self.assert_refused_before_output(r'^payload differs from its committed blob: SUPPORT\.md$')

    def replace_named_commit_with_pending_changes(self):
        """Commit the pending changes, then let HEAD name the earlier commit while a replacement ref substitutes the new one."""
        named = self.git('rev-parse', 'HEAD')
        self.commit('replacement commit')
        self.git('replace', named, self.git('rev-parse', 'HEAD'))
        # HEAD names the original commit again, while index and working tree hold the replacement.
        self.git('reset', '-q', '--soft', named)
        self.assertEqual(self.git('rev-parse', 'HEAD'), named)
        self.assertEqual(self.git('status', '--porcelain'), '', 'the replacement must leave status clean')
        return named

    def test_strict_reads_the_named_commit_despite_a_replacement_ref(self):
        (self.repo / 'README.md').write_text('replacement bytes\n')
        named = self.replace_named_commit_with_pending_changes()
        self.assertEqual(self.git('cat-file', 'blob', named + ':README.md'), 'replacement bytes')
        self.assertEqual(self.git('--no-replace-objects', 'cat-file', 'blob', named + ':README.md'), 'synthetic README.md')
        self.assert_refused_before_output(r'^payload differs from its committed blob: README\.md$')

    def test_strict_takes_membership_from_the_named_commit(self):
        # The replacement drops the optional LICENSE, so the checkout looks complete without it.
        self.git('rm', '-q', 'LICENSE')
        named = self.replace_named_commit_with_pending_changes()
        self.assertEqual(self.git('ls-files', '--', 'LICENSE'), '')
        self.assertTrue(self.git('--no-replace-objects', 'ls-tree', named, 'LICENSE').startswith('100644 blob '))
        self.assert_refused_before_output(
            re.escape("commit and checkout disagree on members: commit only=['LICENSE']; checkout only=[]") + '$')

    def test_strict_refuses_a_symlink_entry_checked_out_as_a_regular_file(self):
        # With core.symlinks=false Git materializes a mode-120000 entry as a plain file holding the target.
        self.git('config', 'core.symlinks', 'false')
        self.git('rm', '-q', 'LICENSE')
        target = subprocess.run(['git', '-C', str(self.repo), 'hash-object', '-w', '--stdin'],
                                input=b'outside-license', capture_output=True, check=True).stdout.decode().strip()
        self.git('update-index', '--add', '--cacheinfo', '120000,' + target + ',LICENSE')
        (self.repo / 'LICENSE').write_bytes(b'outside-license')
        self.commit('symlink entry, regular working file')
        self.assertTrue(self.git('ls-tree', 'HEAD', 'LICENSE').startswith('120000 blob '))
        self.assertFalse((self.repo / 'LICENSE').is_symlink())
        self.assert_refused_before_output(r'^not a regular file in the commit: LICENSE$')

if __name__=='__main__':unittest.main()
