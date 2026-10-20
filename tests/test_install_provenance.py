"""Installed-module provenance controls for installs from this checkout.

Scientific effect: NONE. These controls exercise packaging only.

Every case installs from a temporary copy of the checkout's tracked and
untracked-but-not-ignored files, so the real checkout's ``build/`` and
``egg-info`` directories are never read or written. The contaminated cases
plant files under the copy's ``build/lib/`` the way an install from another
commit leaves them, then require the build to refuse rather than install them.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
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
        # A SOURCES.txt left by an earlier build is read back when no revision
        # control plugin is present. The package ships no package data, so no
        # manifest entry may add a file to the installed package.
        egg_info = self.checkout / 'src' / 'universal_law_query.egg-info'
        egg_info.mkdir()
        (self.checkout / SOURCE_DIR / 'stale_data.txt').write_text('stale data\n', encoding='utf-8')
        (egg_info / 'SOURCES.txt').write_text(
            'README.md\npyproject.toml\nsrc/universal_law_query/__init__.py\n'
            'src/universal_law_query/stale_data.txt\n', encoding='utf-8')
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(installed_files(self.target), tracked_source_files())

    def test_second_clean_install_after_a_first_is_not_refused(self):
        # The guard must not mistake this build's own earlier output for leftovers.
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        shutil.rmtree(self.target)
        self.target.mkdir()
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(installed_files(self.target), tracked_source_files())

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
