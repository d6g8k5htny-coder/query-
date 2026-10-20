"""Installed-module provenance controls for installs from this checkout.

Scientific effect: NONE. These controls exercise packaging only.

Every case installs from a temporary copy of the checkout's tracked and
untracked-but-not-ignored files, so the real checkout's ``build/`` and
``egg-info`` directories are never read or written. The contaminated cases
plant leftovers the way an earlier build leaves them (files, bytecode and
symlinks under the copy's ``build/lib/``, a wheel staging tree under
``build/bdist.*/wheel/``, a stale egg-info manifest or an extra egg-info file,
symlinks in or at the egg-info directory, a symlinked ``build/``, an sdist
release tree, a symlink among the package sources), then require the
build to refuse rather than install them, or the manifest to be regenerated
rather than read back. The post-run byte comparison inside ``build_py`` is
covered only indirectly: ``force`` already rewrites every output, and the
``--skip-build`` cases exercise the comparison itself.
"""
from __future__ import annotations

import importlib.util
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


def setup_with_preamble(checkout: Path, preamble: str, *args: str) -> subprocess.CompletedProcess:
    # Runs setup.py in-process after ``preamble``, for conditions this host
    # cannot create (a Windows junction), simulated where setup.py observes them.
    code = (preamble + '\nimport runpy, sys\nsys.argv = ' + repr(['setup.py', *args])
            + "\nrunpy.run_path('setup.py', run_name='__main__')\n")
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return subprocess.run([sys.executable, '-c', code], cwd=checkout, env=env,
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


def egg_staging_dir(checkout: Path) -> Path:
    # bdist_egg stages under the same bdist base as bdist_wheel (``build/bdist.<platform>/egg``).
    return wheel_staging_dir(checkout).parent / 'egg'


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


def release_tree_name(checkout: Path) -> str:
    # The directory sdist stages the archive in (``<name>-<version>``), asked of
    # setuptools itself.
    result = direct_setup(checkout, '--fullname')
    if result.returncode != 0 or not result.stdout.strip():
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout.strip().splitlines()[-1]


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
        # Resolved, so that expectations derived from these paths match the
        # cwd-relative paths setup.py reports even when the temporary directory
        # itself sits behind a symlink.
        self.base = Path(self.tmp.name).resolve()
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
        # An empty leftover directory is refused with the same message rather
        # than failing later, when the dist-info copy finds it in the way.
        staged.unlink()
        empty = staged.parent.parent / (PACKAGE + '-0.1.0.dist-info')
        empty.mkdir()
        result = self.wheel()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'an empty staging directory must be refused as a leftover')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn(empty.relative_to(self.checkout).as_posix() + ' (empty directory)', output)
        self.assertIn(staged.parent.relative_to(self.checkout).as_posix() + ' (empty directory)', output)
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])

    def test_stale_bdist_egg_staging_tree_is_refused(self):
        # The legacy egg is assembled from build/bdist.<platform>/egg, which a
        # --keep-temp or interrupted run leaves behind with whatever it held.
        staged = egg_staging_dir(self.checkout) / PACKAGE / 'stage_stale.py'
        staged.parent.mkdir(parents=True)
        staged.write_text('STAGE_STALE = True\n', encoding='utf-8')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_egg', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'the egg build must fail closed on a staging leftover')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn(staged.relative_to(self.checkout).as_posix(), output)
        self.assertIn('git clean -fdX -- build src/universal_law_query.egg-info', output)
        self.assertEqual(sorted(dist.glob('*.egg')) if dist.exists() else [], [])
        self.assertTrue(staged.is_file(), 'the leftover is reported, not deleted')
        # A clean egg build holds exactly the tracked package files.
        shutil.rmtree(egg_staging_dir(self.checkout).parent)
        result = direct_setup(self.checkout, 'bdist_egg', '--dist-dir', str(dist))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        eggs = sorted(dist.glob('*.egg'))
        self.assertEqual(len(eggs), 1, eggs)
        self.assertEqual(wheel_package_files(eggs[0]), tracked_source_files())

    def test_stale_bdist_dumb_and_rpm_staging_trees_are_refused(self):
        # Every bdist command stages under build/bdist.<platform>; the dumb
        # archive is that pseudo-installation tree as found, and rpmbuild works
        # from the rpm tree, so a leftover under the shared base is refused by
        # each of them before anything is assembled.
        base = wheel_staging_dir(self.checkout).parent
        staged = base / 'dumb' / 'private' / 'stale.txt'
        staged.parent.mkdir(parents=True)
        staged.write_text('STALE\n', encoding='utf-8')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_dumb', '--format', 'zip', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'the dumb build must fail closed on a staging leftover')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn(staged.relative_to(self.checkout).as_posix(), output)
        self.assertEqual(sorted(dist.glob('*')) if dist.exists() else [], [])
        self.assertTrue(staged.is_file(), 'the leftover is reported, not deleted')
        # The same leftover blocks the other bdist commands, which share the base.
        result = direct_setup(self.checkout, 'bdist_rpm', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(staged.relative_to(self.checkout).as_posix(), output)
        self.assertNotIn('rpmbuild', output, 'the refusal must come before rpmbuild is involved')
        result = self.wheel()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(staged.relative_to(self.checkout).as_posix(), result.stdout + result.stderr)
        # A clean dumb build is not refused.
        shutil.rmtree(base)
        result = direct_setup(self.checkout, 'bdist_dumb', '--format', 'zip', '--dist-dir', str(dist))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(len(sorted(dist.glob('*.zip'))), 1)

    def test_windows_junctions_are_treated_as_symlinks(self):
        # A Windows junction is not reported by os.path.islink; Python 3.12+
        # reports it through os.path.isjunction and every supported version
        # through the reparse tag on os.lstat. Neither exists here, so both are
        # simulated for one real directory: an empty build/lib/<package> that
        # a junction to an outside directory would look like, and that build_py
        # would otherwise write every module into.
        junction = self.checkout / 'build' / 'lib' / PACKAGE
        junction.mkdir(parents=True)
        target = os.path.normcase(os.path.abspath(junction))
        via_isjunction = ('import os\n_t = ' + repr(target) + '\n'
                          'os.path.isjunction = lambda p: os.path.normcase(os.path.abspath(p)) == _t\n')
        via_reparse_tag = (
            'import os\n_t = ' + repr(target) + '\n_real = os.lstat\n'
            'class _S:\n'
            '    def __init__(self, r):\n'
            '        self._r = r\n'
            '        self.st_reparse_tag = 0xA0000003\n'
            '    def __getattr__(self, n):\n'
            '        return getattr(self._r, n)\n'
            'def _lstat(p, *a, **k):\n'
            '    r = _real(p, *a, **k)\n'
            '    if isinstance(p, str) and os.path.normcase(os.path.abspath(p)) == _t:\n'
            '        return _S(r)\n'
            '    return r\n'
            'os.lstat = _lstat\n'
            "if hasattr(os.path, 'isjunction'):\n"
            '    del os.path.isjunction\n')
        for preamble in (via_isjunction, via_reparse_tag):
            result = setup_with_preamble(self.checkout, preamble, 'build_py')
            output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, 'a junction must be refused like a symlink')
            self.assertIn('REFUSED: stale build output', output)
            self.assertIn('build/lib/' + PACKAGE + ' (junction)', output)
            self.assertEqual(sorted(junction.iterdir()), [], 'nothing may be written through the junction')
        # A junction among the package sources is refused before any copy.
        shutil.rmtree(self.checkout / 'build')
        source = os.path.normcase(os.path.abspath(self.checkout / SOURCE_DIR))
        result = setup_with_preamble(
            self.checkout, via_isjunction.replace(repr(target), repr(source)), 'build_py')
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('REFUSED: symlinked source', output)
        self.assertIn('src/' + PACKAGE + ' (junction)', output)
        self.assertFalse((self.checkout / 'build' / 'lib' / PACKAGE).exists())
        # Without any simulated junction the same direct build is accepted.
        result = setup_with_preamble(self.checkout, 'import os', 'build_py')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_pre_generated_dist_info_is_validated(self):
        # ``bdist_wheel --dist-info-dir`` copies the given directory into the
        # wheel as is (pip's build hook passes the one it generated), so it must
        # hold only what this build's own metadata conversion would produce.
        meta = self.base / 'meta'
        meta.mkdir()
        generated = direct_setup(self.checkout, 'dist_info', '--output-dir', str(meta))
        self.assertEqual(generated.returncode, 0, generated.stdout + generated.stderr)
        dist_infos = sorted(meta.glob('*.dist-info'))
        self.assertEqual(len(dist_infos), 1, dist_infos)
        dist_info = dist_infos[0]
        self.assertTrue((dist_info / 'METADATA').is_file())
        planted = dist_info / 'private.txt'
        planted.write_text('private\n', encoding='utf-8')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_wheel', '--dist-info-dir', str(dist_info), '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a pre-generated dist-info with an extra file must be refused')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn(os.path.relpath(planted, self.checkout).replace(os.sep, '/'), output)
        self.assertEqual(sorted(dist.glob('*.whl')) if dist.exists() else [], [])
        self.assertTrue(planted.is_file(), 'the leftover is reported, not deleted')
        # The directory as generated is accepted, and the wheel carries exactly it.
        planted.unlink()
        result = direct_setup(self.checkout, 'bdist_wheel', '--dist-info-dir', str(dist_info), '--dist-dir', str(dist))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        wheels = sorted(dist.glob('*.whl'))
        self.assertEqual(len(wheels), 1, wheels)
        self.assertEqual(wheel_package_files(wheels[0]), tracked_source_files())
        with zipfile.ZipFile(wheels[0]) as archive:
            shipped = sorted(name.split('/', 1)[1] for name in archive.namelist()
                             if name.startswith(dist_info.name + '/'))
        self.assertNotIn('private.txt', shipped)
        self.assertIn('METADATA', shipped)

    def test_hard_linked_build_outputs_are_refused(self):
        # A hard link at a produced path shares its bytes with another file.
        # setuptools' copy unlinks the destination before writing, so the other
        # file is not written through, but the tree is still not this build's
        # output; like a symlink it is refused before anything is copied.
        outside = self.base / 'outside.py'
        outside.write_text('OUTSIDE = True\n', encoding='utf-8')
        linked = self.checkout / 'build' / 'lib' / PACKAGE / 'catalog.py'
        linked.parent.mkdir(parents=True)
        try:
            os.link(outside, linked)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'hard links are not available here: {error}')
        result = self.wheel()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a hard-linked build output must be refused')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('build/lib/' + PACKAGE + '/catalog.py (hard link)', output)
        self.assertEqual(outside.read_text(encoding='utf-8'), 'OUTSIDE = True\n')
        self.assertEqual(os.stat(outside).st_nlink, 2, 'the link is reported, not removed')
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])

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
        self.assertTrue((build_lib / 'cli.py').is_symlink(), 'the symlink is reported, not replaced')
        self.assertEqual(victim.read_text(encoding='utf-8'), 'ORIGINAL = True\n')

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

    def test_bytecode_is_refused_when_byte_compiling_is_disabled(self):
        # Under ``python -B`` or PYTHONDONTWRITEBYTECODE setuptools skips the
        # compile step of ``build_py --compile``, so a cache file found at an
        # expected path was written by something else and would be shipped as is.
        planted = Path(importlib.util.cache_from_source(
            str(self.checkout / 'build' / 'lib' / PACKAGE / 'catalog.py'), optimization=''))
        planted.parent.mkdir(parents=True)
        planted.write_bytes(b'PLANTED BYTECODE')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'build_py', '--compile', 'bdist_wheel', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'bytecode nothing recompiles must not be admitted')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn(planted.relative_to(self.checkout).as_posix(), output)
        self.assertEqual(sorted(dist.glob('*.whl')) if dist.exists() else [], [])
        self.assertEqual(planted.read_bytes(), b'PLANTED BYTECODE', 'the leftover is reported, not deleted')

    def test_skip_build_after_a_compile_build_refuses_the_bytecode(self):
        # Bytecode counts as produced only within the run that writes it. A
        # later --skip-build wheel recompiles nothing and cannot vouch for the
        # cache files it finds, so it refuses them; rebuild without --compile.
        built = direct_build_py(self.checkout, '--compile')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        pycs = sorted((self.checkout / 'build' / 'lib' / PACKAGE / '__pycache__').glob('*.pyc'))
        self.assertTrue(pycs, 'the compile step must have written bytecode under build/lib')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_wheel', '--skip-build', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a skipped build must not ship bytecode it cannot vouch for')
        self.assertIn('REFUSED: stale build output', output)
        for pyc in pycs:
            self.assertIn(pyc.relative_to(self.checkout).as_posix(), output)
        self.assertEqual(sorted(dist.glob('*.whl')) if dist.exists() else [], [])

    def test_direct_bdist_wheel_skip_build_refuses_missing_or_irregular_outputs(self):
        # With nothing built, --skip-build would archive a wheel without the
        # package; an expected output that is absent, or present but not a
        # regular file, is refused.
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_wheel', '--skip-build', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a skipped build with no build output must be refused')
        self.assertIn('REFUSED: stale build output', output)
        for name in tracked_source_files():
            if name.endswith('.py'):
                self.assertIn('build/lib/' + PACKAGE + '/' + name + ' (missing)', output)
        self.assertEqual(sorted(dist.glob('*.whl')) if dist.exists() else [], [])
        built = direct_setup(self.checkout, 'build_py')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        irregular = self.checkout / 'build' / 'lib' / PACKAGE / 'cli.py'
        irregular.unlink()
        irregular.mkdir()
        result = direct_setup(self.checkout, 'bdist_wheel', '--skip-build', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a directory at a module path must be refused')
        self.assertIn('build/lib/' + PACKAGE + '/cli.py (not a regular file)', output)
        self.assertEqual(sorted(dist.glob('*.whl')) if dist.exists() else [], [])

    def test_leftover_egg_info_files_are_refused(self):
        # The manifest maker grafts the whole egg-info directory into an sdist,
        # and a direct bdist_wheel copies it into the dist-info, so a file that
        # no writer of this run produces has a path into the archive.
        egg_info = self.checkout / 'src' / 'universal_law_query.egg-info'
        egg_info.mkdir()
        leftover = egg_info / 'private_notes.txt'
        leftover.write_text('private\n', encoding='utf-8')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'sdist', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'an sdist must not carry a leftover egg-info file')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('src/universal_law_query.egg-info/private_notes.txt', output)
        self.assertIn('git clean -fdX -- build src/universal_law_query.egg-info', output)
        self.assertEqual(sorted(dist.glob('*.tar.gz')) if dist.exists() else [], [])
        result = self.wheel()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a wheel build regenerates the same egg-info and must refuse too')
        self.assertIn('src/universal_law_query.egg-info/private_notes.txt', output)
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])
        self.assertTrue(leftover.is_file(), 'the leftover is reported, not deleted')

    def test_reused_sdist_release_tree_is_refused(self):
        # setuptools fills the release tree, archives it whole and removes it
        # only afterwards, so a tree kept by --keep-temp or an interrupted run
        # would publish whatever it still holds.
        release_tree = self.checkout / release_tree_name(self.checkout)
        release_tree.mkdir()
        leftover = release_tree / 'private.txt'
        leftover.write_text('private\n', encoding='utf-8')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'sdist', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'an sdist must not archive a leftover release tree')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn(release_tree.name + '/private.txt', output)
        self.assertIn('under ' + release_tree.name, output)
        self.assertEqual(sorted(dist.glob('*.tar.gz')) if dist.exists() else [], [])
        self.assertTrue(leftover.is_file(), 'the leftover is reported, not deleted')
        # An empty directory holds nothing to publish and is not a leftover.
        leftover.unlink()
        result = direct_setup(self.checkout, 'sdist', '--dist-dir', str(dist))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        clean = self.base / 'clean'
        clean.mkdir()
        copy_checkout(clean)
        reference = direct_setup(clean, 'sdist', '--dist-dir', str(self.base / 'clean_dist'))
        self.assertEqual(reference.returncode, 0, reference.stdout + reference.stderr)
        self.assertEqual(sdist_members(dist), sdist_members(self.base / 'clean_dist'))

    def test_symlinked_package_sources_are_refused(self):
        # The copy follows a symlink in src/, and the byte comparison follows it
        # too, so the link's target would ship as a module of this tree. Every
        # symlinked source, and every symlinked directory above one, is refused
        # before anything is copied.
        private = self.base / 'private.py'
        private.write_text('PRIVATE = True\n', encoding='utf-8')
        leak = self.checkout / SOURCE_DIR / 'leak.py'
        try:
            os.symlink(private, leak)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'symlinks are not available here: {error}')
        result = self.wheel()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a symlinked source must be refused')
        self.assertIn('REFUSED: symlinked source', output)
        self.assertIn('src/' + PACKAGE + '/leak.py (symlink)', output)
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])
        self.assertFalse((self.checkout / 'build' / 'lib' / PACKAGE / 'leak.py').exists(),
                         'nothing may be copied before the refusal')
        self.assertTrue(leak.is_symlink(), 'the symlink is reported, not replaced')
        leak.unlink()
        # A skipped build compares bytes through the link and would find them
        # equal; the link itself is refused.
        built = direct_setup(self.checkout, 'build_py')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        catalog = self.checkout / SOURCE_DIR / 'catalog.py'
        copy = self.base / 'catalog_copy.py'
        shutil.copy2(catalog, copy)
        catalog.unlink()
        os.symlink(copy, catalog)
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'bdist_wheel', '--skip-build', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'equal bytes behind a symlink are still not this tree\'s')
        self.assertIn('src/' + PACKAGE + '/catalog.py (symlink)', output)
        self.assertEqual(sorted(dist.glob('*.whl')) if dist.exists() else [], [])
        catalog.unlink()
        shutil.copy2(copy, catalog)
        # A symlinked package directory is refused through the modules under it.
        outside = self.base / 'outside_pkg'
        outside.mkdir()
        (outside / '__init__.py').write_text('OUTSIDE = True\n', encoding='utf-8')
        os.symlink(outside, self.checkout / SOURCE_DIR / 'sub', target_is_directory=True)
        result = direct_setup(self.checkout, 'build_py')
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a symlinked package directory must be refused')
        self.assertIn('REFUSED: symlinked source', output)
        self.assertIn('src/' + PACKAGE + '/sub (symlink)', output)
        self.assertFalse((self.checkout / 'build' / 'lib' / PACKAGE / 'sub').exists())

    def test_symlinked_sdist_inputs_are_refused(self):
        # The manifest names more than the package sources (tests, docs, the
        # wrappers); each entry is copied or hard-linked into the release tree
        # and archived, so a symlink among them would ship its target.
        private = self.base / 'private_test.py'
        private.write_text('PRIVATE = True\n', encoding='utf-8')
        leak = self.checkout / 'tests' / 'test_leak.py'
        try:
            os.symlink(private, leak)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'symlinks are not available here: {error}')
        dist = self.base / 'dist'
        result = direct_setup(self.checkout, 'sdist', '--dist-dir', str(dist))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a symlinked sdist input must be refused')
        self.assertIn('REFUSED: symlinked source', output)
        self.assertIn('tests/test_leak.py (symlink)', output)
        self.assertEqual(sorted(dist.glob('*.tar.gz')) if dist.exists() else [], [])
        self.assertFalse((self.checkout / release_tree_name(self.checkout)).exists(),
                         'nothing may be copied before the refusal')
        self.assertTrue(leak.is_symlink(), 'the link is reported, not replaced')

    def test_hard_linked_egg_info_entries_are_refused_before_anything_is_written(self):
        # A hard link is a regular file by every test but shares its bytes with
        # another path, so a writer opening it by name overwrites that path too.
        outside = self.base / 'outside'
        outside.mkdir()
        secret = outside / 'secret.txt'
        secret.write_text('SECRET\n', encoding='utf-8')
        egg_info = self.checkout / 'src' / 'universal_law_query.egg-info'
        egg_info.mkdir()
        try:
            os.link(secret, egg_info / 'SOURCES.txt')
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'hard links are not available here: {error}')
        result = direct_setup(self.checkout, 'egg_info')
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a hard-linked metadata file must be refused')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('src/universal_law_query.egg-info/SOURCES.txt (hard link)', output)
        self.assertEqual(secret.read_text(encoding='utf-8'), 'SECRET\n', 'nothing may be written through the link')
        self.assertFalse((egg_info / 'PKG-INFO').exists(), 'no writer may run before the refusal')
        result = direct_setup(self.checkout, 'sdist', '--dist-dir', str(self.base / 'dist'))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(secret.read_text(encoding='utf-8'), 'SECRET\n')

    def test_dry_run_build_is_not_refused_for_writing_nothing(self):
        # ``--dry-run`` writes nothing by design, so the post-run comparison
        # has nothing to compare and is skipped; the leftover check still runs.
        result = direct_setup(self.checkout, '--dry-run', 'build_py')
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn('REFUSED', output)
        self.assertFalse((self.checkout / 'build').exists(), 'a dry run must write nothing')
        plant_leftovers(self.checkout)
        result = direct_setup(self.checkout, '--dry-run', 'build_py')
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'leftovers are refused on a dry run as well')
        self.assertIn('REFUSED: stale build output', output)

    def test_install_lib_skip_build_validates_the_directory_it_copies_from(self):
        # ``install_lib --build-dir`` copies from the named directory, so that
        # directory, not the default build/lib, is what must hold exactly this
        # tree's outputs.
        built = direct_setup(self.checkout, 'build_py')
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        elsewhere = self.checkout / 'elsewhere'
        (elsewhere / PACKAGE).mkdir(parents=True)
        (elsewhere / PACKAGE / 'stale.py').write_text('STALE = True\n', encoding='utf-8')
        result = direct_setup(self.checkout, 'install_lib', '--skip-build', '--build-dir', 'elsewhere',
                              '--install-dir', str(self.target))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'the copied-from directory must be validated')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('elsewhere/' + PACKAGE + '/stale.py', output)
        self.assertIn('elsewhere/' + PACKAGE + '/__init__.py (missing)', output)
        self.assertIn('under elsewhere', output)
        self.assertEqual(installed_files(self.target), [], 'nothing may be installed after a refusal')
        # Without --skip-build the build rewrites build/lib, but the copy still
        # comes from the named directory, which must be validated just the same.
        result = direct_setup(self.checkout, 'install_lib', '--build-dir', 'elsewhere',
                              '--install-dir', str(self.target))
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'the copied-from directory must be validated after a build too')
        self.assertIn('elsewhere/' + PACKAGE + '/stale.py', output)
        self.assertEqual(installed_files(self.target), [])
        result = direct_setup(self.checkout, 'install_lib', '--skip-build', '--build-dir', 'build/lib',
                              '--install-dir', str(self.target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(installed_files(self.target), tracked_source_files())

    def test_symlinked_egg_info_entries_are_refused_before_anything_is_written(self):
        # egg_info's writers open each metadata file by name and follow a
        # symlink, so a link planted under a writer's name would have its
        # target overwritten before any later check. The directory is checked
        # first, and the directory itself may not be a link either.
        outside = self.base / 'outside'
        outside.mkdir()
        secret = outside / 'secret.txt'
        secret.write_text('SECRET\n', encoding='utf-8')
        egg_info = self.checkout / 'src' / 'universal_law_query.egg-info'
        egg_info.mkdir()
        try:
            os.symlink(secret, egg_info / 'SOURCES.txt')
            os.symlink(secret, egg_info / 'top_level.txt')
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'symlinks are not available here: {error}')
        result = direct_setup(self.checkout, 'egg_info')
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a symlinked metadata file must be refused')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('src/universal_law_query.egg-info/SOURCES.txt (symlink)', output)
        self.assertIn('src/universal_law_query.egg-info/top_level.txt (symlink)', output)
        self.assertIn('git clean -fdX -- build src/universal_law_query.egg-info', output)
        self.assertEqual(secret.read_text(encoding='utf-8'), 'SECRET\n', 'nothing may be written through the link')
        self.assertTrue((egg_info / 'SOURCES.txt').is_symlink(), 'the link is reported, not replaced')
        self.assertFalse((egg_info / 'PKG-INFO').exists(), 'no writer may run before the refusal')
        result = self.wheel()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'the wheel build regenerates the same egg-info and must refuse too')
        self.assertIn('src/universal_law_query.egg-info/SOURCES.txt (symlink)', output)
        self.assertEqual(secret.read_text(encoding='utf-8'), 'SECRET\n')
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])
        # The egg-info directory itself as a symlink: nothing may be written
        # into the link's target.
        shutil.rmtree(egg_info)
        os.symlink(outside, egg_info, target_is_directory=True)
        result = direct_setup(self.checkout, 'egg_info')
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a symlinked egg-info directory must be refused')
        self.assertIn('src/universal_law_query.egg-info (symlink)', output)
        self.assertEqual(sorted(path.name for path in outside.iterdir()), ['secret.txt'],
                         'nothing may be written into the link target')
        self.assertTrue(egg_info.is_symlink(), 'the link is reported, not replaced')

    def test_symlinked_build_directory_is_refused(self):
        # Every write under build/ lands wherever a symlinked build/ points, so
        # a symlinked directory above build/lib or the staging tree is refused
        # before anything is written.
        outside = self.base / 'outside_build'
        outside.mkdir()
        try:
            os.symlink(outside, self.checkout / 'build', target_is_directory=True)
        except (OSError, NotImplementedError) as error:
            self.skipTest(f'symlinks are not available here: {error}')
        result = self.wheel()
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'a symlinked build directory must be refused')
        self.assertIn('REFUSED: stale build output', output)
        self.assertIn('build (symlink)', output)
        self.assertIn('git clean -fdX -- build src/universal_law_query.egg-info', output)
        self.assertEqual(sorted(outside.iterdir()), [], 'nothing may be written through the link')
        self.assertEqual(sorted(self.wheels.glob('*.whl')), [])
        self.assertTrue((self.checkout / 'build').is_symlink(), 'the link is reported, not replaced')
        result = direct_setup(self.checkout, 'build_py')
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, 'the direct build must refuse the same link')
        self.assertIn('build (symlink)', output)
        self.assertEqual(sorted(outside.iterdir()), [])

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
