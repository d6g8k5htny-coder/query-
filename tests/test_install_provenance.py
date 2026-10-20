"""Installed-module provenance controls for installs from this checkout.

Scientific effect: NONE. These controls exercise packaging only.

Every case installs from a temporary copy of the checkout's tracked and
untracked-but-not-ignored files, so the real checkout's ``build/`` and
``egg-info`` directories are never read or written. The contaminated cases
plant leftovers the way an earlier build leaves them (files and symlinks under
the copy's ``build/lib/``, a wheel staging tree under ``build/bdist.*/wheel/``,
a stale egg-info manifest), then require the build to refuse rather than
install them, or the manifest to be regenerated rather than read back.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = 'universal_law_query'
SOURCE_DIR = Path('src') / PACKAGE
STALE_FILES = ('stale_leftover.py', 'stale_pkg/__init__.py')
PIP_TIMEOUT = 180


def tracked_source_files() -> list[str]:
    raw = subprocess.check_output(
        ['git', '-C', str(ROOT), 'ls-files', '-z', '--', SOURCE_DIR.as_posix()], timeout=10)
    return sorted(Path(name).relative_to(SOURCE_DIR).as_posix()
                  for name in raw.decode().split('\0') if name)


def copy_checkout(dest: Path) -> None:
    # Tracked plus untracked-but-not-ignored files: an uncommitted repair is
    # exercised, while the real checkout's ignored build/ and egg-info are not.
    raw = subprocess.check_output(
        ['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
        timeout=10)
    for name in raw.decode().split('\0'):
        if not name:
            continue
        parts = Path(name).parts
        if '__pycache__' in parts or name.endswith(('.pyc', '.pyo')):
            continue
        source = ROOT / name
        if not source.is_file() or source.is_symlink():
            continue
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def plant_leftovers(checkout: Path) -> list[Path]:
    planted = []
    for name in STALE_FILES:
        path = checkout / 'build' / 'lib' / PACKAGE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('STALE = True  # left by an install from another commit\n', encoding='utf-8')
        planted.append(path)
    return planted


def pip(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env['PIP_DISABLE_PIP_VERSION_CHECK'] = '1'
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return subprocess.run([sys.executable, '-m', 'pip', *args], env=env,
                          capture_output=True, text=True, timeout=PIP_TIMEOUT)


def direct_build_py(checkout: Path, *args: str) -> subprocess.CompletedProcess:
    # The legacy direct command path. Bytecode writing stays enabled so that the
    # build's own ``__pycache__`` output is part of what the guard inspects.
    env = {key: value for key, value in os.environ.items() if key != 'PYTHONDONTWRITEBYTECODE'}
    return subprocess.run([sys.executable, 'setup.py', 'build_py', *args], cwd=checkout, env=env,
                          capture_output=True, text=True, timeout=PIP_TIMEOUT)


def direct_setup(checkout: Path, *args: str) -> subprocess.CompletedProcess:
    # Any other legacy direct command (``bdist_wheel``, ``sdist``), without bytecode.
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return subprocess.run([sys.executable, 'setup.py', *args], cwd=checkout, env=env,
                          capture_output=True, text=True, timeout=PIP_TIMEOUT)


def wheel_staging_dir(checkout: Path) -> Path:
    # The directory bdist_wheel stages the archive in (``build/bdist.<platform>/wheel``),
    # asked of setuptools itself so the platform tag matches the build's.
    code = ('from setuptools.dist import Distribution\n'
            'from setuptools.command.bdist_wheel import bdist_wheel\n'
            'command = bdist_wheel(Distribution())\n'
            'command.finalize_options()\n'
            'print(command.bdist_dir)\n')
    raw = subprocess.check_output([sys.executable, '-c', code], cwd=checkout, text=True, timeout=60)
    return checkout / raw.strip()


def plant_stale_manifest(checkout: Path) -> Path:
    # A SOURCES.txt left by an earlier build, naming an untracked file that exists.
    egg_info = checkout / 'src' / 'universal_law_query.egg-info'
    egg_info.mkdir()
    stale = checkout / SOURCE_DIR / 'stale_data.txt'
    stale.write_text('stale data\n', encoding='utf-8')
    (egg_info / 'SOURCES.txt').write_text(
        'README.md\npyproject.toml\nsrc/universal_law_query/__init__.py\n'
        'src/universal_law_query/stale_data.txt\n', encoding='utf-8')
    return egg_info / 'SOURCES.txt'


def sdist_members(dist_dir: Path) -> list[str]:
    tarballs = sorted(dist_dir.glob('*.tar.gz'))
    if len(tarballs) != 1:
        raise AssertionError(f'expected one sdist, found {tarballs}')
    with tarfile.open(tarballs[0]) as archive:
        return sorted(name.split('/', 1)[1] for name in archive.getnames() if '/' in name)


def installed_files(target: Path) -> list[str]:
    package = target / PACKAGE
    if not package.is_dir():
        return []
    return sorted(path.relative_to(package).as_posix() for path in package.rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts)


def wheel_package_files(wheel: Path) -> list[str]:
    with zipfile.ZipFile(wheel) as archive:
        return sorted(name[len(PACKAGE) + 1:] for name in archive.namelist()
                      if name.startswith(PACKAGE + '/'))


class InstallProvenance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.checkout = self.base / 'checkout'
        self.checkout.mkdir()
        copy_checkout(self.checkout)
        self.target = self.base / 'site'
        self.target.mkdir()
        self.wheels = self.base / 'wheels'
        self.wheels.mkdir()
        self.assertFalse((self.checkout / 'build').exists(), 'copy must start without build/')
        self.assertTrue(tracked_source_files(), 'tracked package inventory must be non-empty')

    def install(self):
        return pip('install', '--quiet', '--no-deps', '--no-build-isolation',
                   '--target', str(self.target), str(self.checkout))

    def wheel(self):
        return pip('wheel', '--quiet', '--no-deps', '--no-build-isolation',
                   '--wheel-dir', str(self.wheels), str(self.checkout))

    def test_clean_copy_installs_exactly_the_tracked_package_files(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installed_files(self.target), tracked_source_files())
        probe = subprocess.run(
            [sys.executable, '-c', 'import universal_law_query, sys; print(universal_law_query.__file__)'],
            env={'PYTHONPATH': str(self.target)}, capture_output=True, text=True, timeout=10)
        self.assertEqual(probe.returncode, 0, probe.stderr)
        self.assertTrue(Path(probe.stdout.strip()).resolve().is_relative_to(self.target.resolve()))

    def test_clean_copy_wheel_holds_exactly_the_tracked_package_files(self):
        result = self.wheel()
        self.assertEqual(result.returncode, 0, result.stderr)
        wheels = sorted(self.wheels.glob('*.whl'))
        self.assertEqual(len(wheels), 1, wheels)
        self.assertEqual(wheel_package_files(wheels[0]), tracked_source_files())

    def test_stale_build_lib_leftovers_are_refused_and_not_installed(self):
        plant_leftovers(self.checkout)
        result = self.install()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'install must fail closed on build/lib leftovers')
        self.assertIn('REFUSED: stale build output', output)
        for name in STALE_FILES:
            self.assertIn('build/lib/' + PACKAGE + '/' + name, output)
        self.assertIn('git clean -fdX -- build src/universal_law_query.egg-info', output)
        self.assertEqual(installed_files(self.target), [], 'nothing may be installed after a refusal')
        # The leftovers are reported, not deleted.
        for name in STALE_FILES:
            self.assertTrue((self.checkout / 'build' / 'lib' / PACKAGE / name).is_file())

    def test_stale_build_lib_leftovers_block_the_wheel(self):
        plant_leftovers(self.checkout)
        result = self.wheel()
        self.assertNotEqual(result.returncode, 0, 'wheel build must fail closed on build/lib leftovers')
        self.assertIn('REFUSED: stale build output', result.stdout + result.stderr)
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])

    def test_stale_egg_info_manifest_cannot_add_package_data(self):
        # A SOURCES.txt left by an earlier build would be read back when no
        # revision control plugin is present. The package ships no package data,
        # so no manifest entry may add a file to the installed package.
        plant_stale_manifest(self.checkout)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installed_files(self.target), tracked_source_files())

    def test_sdist_never_reads_a_stale_manifest_back(self):
        # ``include-package-data = false`` keeps manifest entries out of a wheel
        # but not out of a source distribution, so the manifest itself must be
        # regenerated from the tree instead of accumulating leftover entries.
        clean = self.base / 'clean'
        clean.mkdir()
        copy_checkout(clean)
        reference = direct_setup(clean, 'sdist', '--dist-dir', str(self.base / 'clean_dist'))
        self.assertEqual(reference.returncode, 0, reference.stdout + reference.stderr)
        manifest = plant_stale_manifest(self.checkout)
        result = direct_setup(self.checkout, 'sdist', '--dist-dir', str(self.base / 'dist'))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        members = sdist_members(self.base / 'dist')
        self.assertEqual(members, sdist_members(self.base / 'clean_dist'))
        self.assertNotIn('src/universal_law_query/stale_data.txt', members)
        self.assertNotIn('stale_data.txt', manifest.read_text(encoding='utf-8'),
                         'the regenerated manifest must not carry the stale entry')

    def test_stale_wheel_staging_tree_is_refused(self):
        # An interrupted wheel build leaves build/bdist.<platform>/wheel behind;
        # the next build would archive whatever that tree holds.
        staged = wheel_staging_dir(self.checkout) / PACKAGE / 'stage_stale.py'
        staged.parent.mkdir(parents=True)
        staged.write_text('STAGE_STALE = True\n', encoding='utf-8')
        result = self.wheel()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'wheel build must fail closed on a staging leftover')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn(staged.relative_to(self.checkout).as_posix(), output)
        self.assertIn('git clean -fdX -- build src/universal_law_query.egg-info', output)
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])
        self.assertTrue(staged.is_file(), 'the leftover is reported, not deleted')

    def test_direct_bdist_wheel_skip_build_still_refuses_stale_build_lib(self):
        # ``--skip-build`` never runs build_py, so the wheel command must repeat
        # the inventory check itself.
        stale = self.checkout / 'build' / 'lib' / PACKAGE / 'stale.py'
        stale.parent.mkdir(parents=True)
        stale.write_text('STALE = True\n', encoding='utf-8')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_wheel', '--skip-build', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a skipped build must not bypass the guard')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('build/lib/' + PACKAGE + '/stale.py', output)
        self.assertEqual(sorted(dist.glob('*.whl')) if dist.exists() else [], [])

    def test_direct_bdist_wheel_skip_build_after_a_clean_build_is_accepted(self):
        built = direct_setup(self.checkout, 'build_py')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_wheel', '--skip-build', '--dist-dir', str(dist))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wheels = sorted(dist.glob('*.whl'))
        self.assertEqual(len(wheels), 1, wheels)
        self.assertEqual(wheel_package_files(wheels[0]), tracked_source_files())

    def test_newer_stale_bytes_at_a_produced_path_are_rewritten_not_shipped(self):
        # setuptools skips a destination that is newer than its source, so a
        # leftover module at a path this build writes would be kept as is. The
        # build rewrites every output and then compares bytes with the source.
        planted = self.checkout / 'build' / 'lib' / PACKAGE / 'catalog.py'
        planted.parent.mkdir(parents=True)
        planted.write_text('PLANTED_MARKER = True\n', encoding='utf-8')
        future = os.stat(self.checkout / SOURCE_DIR / 'catalog.py').st_mtime + 86400
        os.utime(planted, (future, future))
        result = self.wheel()
        self.assertEqual(result.returncode, 0, result.stderr)
        wheels = sorted(self.wheels.glob('*.whl'))
        self.assertEqual(len(wheels), 1, wheels)
        with zipfile.ZipFile(wheels[0]) as archive:
            shipped = archive.read(PACKAGE + '/catalog.py')
        self.assertEqual(shipped, (self.checkout / SOURCE_DIR / 'catalog.py').read_bytes())
        self.assertNotIn(b'PLANTED_MARKER', shipped)

    def test_direct_bdist_wheel_skip_build_refuses_differing_bytes(self):
        built = direct_setup(self.checkout, 'build_py')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        stale = self.checkout / 'build' / 'lib' / PACKAGE / 'catalog.py'
        stale.write_text('PLANTED_MARKER = True\n', encoding='utf-8')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_wheel', '--skip-build', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a skipped build must not ship bytes the source tree did not produce')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('build/lib/' + PACKAGE + '/catalog.py (bytes differ from src/' + PACKAGE + '/catalog.py)', output)
        self.assertEqual(sorted(dist.glob('*.whl')) if dist.exists() else [], [])

    def test_refusal_in_a_custom_build_lib_names_that_directory(self):
        # ``git clean -fdX -- build …`` only reaches the checkout's build/; a
        # refusal elsewhere must point at the directory it inspected.
        outside = self.base / 'elsewhere'
        (outside / PACKAGE).mkdir(parents=True)
        (outside / PACKAGE / 'stale.py').write_text('STALE = True\n', encoding='utf-8')
        result = direct_setup(self.checkout, 'build_py', '--build-lib', str(outside))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('REFUSED: stale build output', output)
        relative = os.path.relpath(outside, self.checkout).replace(os.sep, '/')
        self.assertIn(relative + '/' + PACKAGE + '/stale.py', output)
        self.assertIn('outside the checkout', output)
        self.assertIn('under ' + relative, output)

    def test_symlinks_under_build_lib_are_refused(self):
        # os.walk does not follow symlinks, but the wheel staging step
        # dereferences them, so a symlinked directory or file is a leftover
        # wherever it points, even at a path this build would write.
        outside = self.base / 'outside' / 'stale_pkg'
        outside.mkdir(parents=True)
        (outside / '__init__.py').write_text('OUTSIDE = True\n', encoding='utf-8')
        build_lib = self.checkout / 'build' / 'lib' / PACKAGE
        build_lib.mkdir(parents=True)
        try:
            os.symlink(outside, build_lib / 'stale_pkg', target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'symlinks are not available here: {error}')
        result = self.wheel()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a symlinked directory must be refused')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('build/lib/' + PACKAGE + '/stale_pkg (symlink)', output)
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])
        self.assertTrue((build_lib / 'stale_pkg').is_symlink(), 'the symlink is reported, not removed')
        # A symlinked file at a path this build writes is refused before the copy.
        (build_lib / 'stale_pkg').unlink()
        victim = self.base / 'victim.py'
        victim.write_text('ORIGINAL = True\n', encoding='utf-8')
        os.symlink(victim, build_lib / 'cli.py')
        result = direct_setup(self.checkout, 'build_py')
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a symlinked file must be refused')
        self.assertIn('build/lib/' + PACKAGE + '/cli.py (symlink)', output)
        self.assertEqual(victim.read_text(encoding='utf-8'), 'ORIGINAL = True\n',
                         'nothing may be written through the symlink')

    def test_second_clean_install_after_a_first_is_not_refused(self):
        # The guard must not mistake this build's own earlier output for leftovers.
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        shutil.rmtree(self.target)
        self.target.mkdir()
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(installed_files(self.target), tracked_source_files())

    def test_direct_build_py_compile_accepts_its_own_bytecode(self):
        # ``python setup.py build_py --compile`` writes ``__pycache__`` under
        # build/lib in the same run. That output is this build's, not a leftover,
        # so neither the first run nor a repeat may be refused; planted leftovers
        # are still refused on this path.
        first = direct_build_py(self.checkout, '--compile')
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        pycs = sorted((self.checkout / 'build' / 'lib' / PACKAGE / '__pycache__').glob('*.pyc'))
        self.assertTrue(pycs, 'the compile step must have written bytecode under build/lib')
        second = direct_build_py(self.checkout, '--compile')
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        plant_leftovers(self.checkout)
        third = direct_build_py(self.checkout, '--compile')
        self.assertNotEqual(third.returncode, 0, 'leftovers must still be refused on the direct path')
        output = third.stdout + third.stderr
        self.assertIn('REFUSED: stale build output', output)
        for name in STALE_FILES:
            self.assertIn('build/lib/' + PACKAGE + '/' + name, output)
        self.assertNotIn('.pyc', output, 'this build\'s own bytecode must not be named as a leftover')

    @unittest.skipUnless(os.environ.get('QUERY_INSTALL_ISOLATED') == '1',
                         'isolated build downloads setuptools; set QUERY_INSTALL_ISOLATED=1 to run')
    def test_isolated_build_also_refuses_stale_build_lib_leftovers(self):
        plant_leftovers(self.checkout)
        result = pip('install', '--quiet', '--no-deps', '--target', str(self.target), str(self.checkout))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('REFUSED: stale build output', result.stdout + result.stderr)
        self.assertEqual(installed_files(self.target), [])


if __name__ == '__main__':
    unittest.main()
