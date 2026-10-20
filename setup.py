"""Build-time leftover guard for installs from this checkout.

Scientific effect: NONE. This file adds no runtime dependency and changes no
lookup, verification or refusal behaviour of the package.

setuptools reuses ``build/`` between builds and removes nothing from it. A
module left under ``build/lib`` by an install from another commit is copied
into the next wheel although ``src/`` does not contain it, and an import check
of the installed package still passes. Three commands are guarded:

- ``build_py`` compares the whole ``build/lib`` tree with the files it
  produces, before copying anything and again afterwards, and refuses when
  anything else is present. Every symlink under the tree is refused wherever it
  points, because the walk does not follow symlinks but the wheel staging step
  dereferences them. The run rewrites every file it produces (setuptools would
  otherwise skip a destination that is newer than its source), and afterwards
  each produced module's bytes are compared with its source, so bytes left at a
  path this run writes are replaced, never shipped. Bytecode written by the same
  run (``--compile`` or ``-O``) counts as produced and is recompiled.
- ``bdist_wheel`` refuses a leftover staging tree under ``build/bdist.*/wheel``
  (an interrupted build leaves one, and the next build archives whatever it
  holds) and repeats the ``build/lib`` comparison, so ``--skip-build`` cannot
  bypass it; with ``--skip-build`` nothing is rebuilt, so the byte comparison
  runs there instead.
- ``egg_info`` regenerates ``SOURCES.txt`` from the tree and never reads a
  leftover manifest back in, so a stale entry can add a file neither to a wheel
  nor to a source distribution.

Nothing is deleted; each refusal names the leftovers and the remedy, which is
``git clean`` for the checkout's own ``build/`` and otherwise names the
configured directory.
"""
from __future__ import annotations

import filecmp
import os

from setuptools import setup
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.egg_info import egg_info as _egg_info
from setuptools.command.egg_info import manifest_maker as _manifest_maker
from setuptools.errors import SetupError

REMEDY = 'git clean -fdX -- build src/universal_law_query.egg-info'


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _relative(path: str) -> str:
    return os.path.relpath(path).replace(os.sep, '/')


def _unexpected(tree: str, produced: set[str]) -> list[str]:
    """Files under ``tree`` that are not in ``produced``, and every symlink."""
    found = []
    if os.path.islink(tree):
        return [_relative(tree) + ' (symlink)']
    if not os.path.isdir(tree):
        return found
    for dirpath, dirnames, filenames in os.walk(tree):
        for name in dirnames:
            if os.path.islink(os.path.join(dirpath, name)):
                found.append(_relative(os.path.join(dirpath, name)) + ' (symlink)')
        for name in filenames:
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                found.append(_relative(path) + ' (symlink)')
            elif _canonical(path) not in produced:
                found.append(_relative(path))
    return sorted(found)


def _remedy(tree: str) -> str:
    """The checkout's own build/ is cleaned by git; another directory is named."""
    try:
        relative = os.path.relpath(tree)
    except ValueError:  # another drive on Windows
        relative = None
    if relative is not None and (relative == 'build' or relative.startswith('build' + os.sep)):
        return REMEDY
    return ('remove the named files under ' + _relative(tree)
            + ' yourself; it is outside the checkout\'s build/, so ' + REMEDY + ' does not reach it')


def _refuse(unexpected: list[str], tree: str) -> None:
    if unexpected:
        raise SetupError(
            'REFUSED: stale build output not produced from this source tree: '
            + ', '.join(unexpected)
            + '. Remove build leftovers before installing: ' + _remedy(tree))


def _differing_outputs(build_py_command) -> list[str]:
    """Produced module and data paths whose bytes are not this source tree's."""
    pairs = []
    for package, module, module_file in build_py_command.find_all_modules():
        output = build_py_command.get_module_outfile(build_py_command.build_lib, package.split('.'), module)
        pairs.append((module_file, output))
    for _package, src_dir, build_dir, filenames in build_py_command.data_files:
        for filename in filenames:
            pairs.append((os.path.join(src_dir, filename), os.path.join(build_dir, filename)))
    found = []
    for source, output in pairs:
        if os.path.isfile(output) and not filecmp.cmp(source, output, shallow=False):
            found.append(_relative(output) + ' (bytes differ from ' + _relative(source) + ')')
    return found


def _guard_build_lib(build_py_command, compare_bytes: bool = False) -> None:
    produced = {_canonical(path) for path in build_py_command.get_outputs(include_bytecode=True)}
    unexpected = _unexpected(build_py_command.build_lib, produced)
    if compare_bytes:
        unexpected = sorted(unexpected + _differing_outputs(build_py_command))
    _refuse(unexpected, build_py_command.build_lib)


class build_py(_build_py):
    """Refuse build output that this source tree did not produce."""

    def run(self) -> None:
        _guard_build_lib(self)
        # Rewrite every output: a leftover at a produced path that is newer than
        # its source would otherwise be kept as "up to date" and shipped.
        self.force = True
        super().run()
        _guard_build_lib(self, compare_bytes=True)


class bdist_wheel(_bdist_wheel):
    """Refuse a leftover staging tree, and re-check build/lib even with --skip-build."""

    def run(self) -> None:
        _refuse(_unexpected(self.bdist_dir, set()), self.bdist_dir)
        # Without --skip-build the build rewrites build/lib next; with it, the
        # bytes already there are what gets shipped, so compare them now.
        _guard_build_lib(self.get_finalized_command('build_py'), compare_bytes=bool(self.skip_build))
        super().run()


class _fresh_manifest_maker(_manifest_maker):
    """Build SOURCES.txt from the tree; a leftover manifest is never read back."""

    def read_manifest(self) -> None:
        return None


class egg_info(_egg_info):
    def find_sources(self) -> None:
        manifest_filename = os.path.join(self.egg_info, 'SOURCES.txt')
        mm = _fresh_manifest_maker(self.distribution)
        mm.ignore_egg_info_dir = getattr(self, 'ignore_egg_info_in_manifest', False)
        mm.manifest = manifest_filename
        mm.run()
        self.filelist = mm.filelist


setup(cmdclass={'build_py': build_py, 'bdist_wheel': bdist_wheel, 'egg_info': egg_info})
