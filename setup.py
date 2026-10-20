"""Build-time leftover guard for installs from this checkout.

Scientific effect: NONE. This file adds no runtime dependency and changes no
lookup, verification or refusal behaviour of the package.

setuptools reuses ``build/`` between builds and removes nothing from it. A
module left under ``build/lib`` by an install from another commit is copied
into the next wheel although ``src/`` does not contain it, and an import check
of the installed package still passes. Eight commands are guarded:

- ``build_py`` refuses a symlink among the package sources it would copy, or a
  symlinked directory above one, because the copy and the byte comparison
  below both follow the link and would ship its target as a file of this tree.
  It then compares the whole ``build/lib`` tree with the files it produces,
  before copying anything and again afterwards, and refuses when anything else
  is present. Every symlink under the tree is refused wherever it points,
  because the walk does not follow symlinks but the wheel staging step
  dereferences them (a Windows junction counts as a symlink throughout); a
  hard-linked file is refused as well, since its bytes are shared with another
  path. The run rewrites every file it produces (setuptools would
  otherwise skip a destination that is newer than its source), and afterwards
  each produced module's bytes are compared with its source, so bytes left at a
  path this run writes are replaced, never shipped. Bytecode counts as produced
  only when this run recompiles it (``--compile`` or ``-O`` with bytecode
  writing enabled); under ``python -B`` or ``PYTHONDONTWRITEBYTECODE`` setuptools
  skips the compile step, so a cache file found under ``build/lib`` is refused.
  A dry run writes nothing, so the comparison after the run is skipped there;
  the leftover check before it still applies.
- ``bdist_wheel`` refuses a leftover anywhere under the shared bdist base
  (``build/bdist.<platform>``, where the wheel, egg, dumb and rpm staging
  trees live; an interrupted build leaves one, and the next build archives
  whatever it holds) and under its own staging directory, refuses a
  pre-generated ``--dist-info-dir`` holding anything its own metadata
  conversion would not produce (the directory is copied into the wheel as
  is), and repeats the ``build/lib`` comparison, so ``--skip-build`` cannot
  bypass it. With ``--skip-build`` nothing is rebuilt, so the byte comparison
  runs there instead, every expected output must be present as a regular file,
  and bytecode, which nothing recompiles, is refused.
- ``install_lib`` applies the same comparison to the directory it copies from
  (its ``--build-dir``, by default ``build/lib``), whether or not it rebuilt
  it, which covers the legacy ``install``, ``install_lib`` and ``bdist_egg``
  commands with and without ``--skip-build``.
- ``bdist_egg``, ``bdist_dumb`` and ``bdist_rpm`` refuse a leftover under the
  shared bdist base and their own staging trees the same way; the legacy
  archives are assembled from whatever those trees hold.
- ``egg_info`` regenerates ``SOURCES.txt`` from the tree and never reads a
  leftover manifest back in, so a stale entry can add a file neither to a wheel
  nor to a source distribution; any other file left beside the ones this run
  writes is refused, because ``sdist`` and a direct ``bdist_wheel`` copy the
  whole directory into the archive. The directory is checked before the
  writers run as well as after: a writer opens each metadata file by name and
  would follow a symlink, overwriting whatever it points at, so the directory
  itself and every entry in it must be a regular file with a single link; a
  hard-linked file shares its bytes with another path and would be written
  through just the same.
- ``sdist`` refuses a symlink among the files the manifest names, or a
  symlinked directory above one, before copying anything: the release tree
  would otherwise hold the link's target as a regular file. It also refuses a
  leftover release tree (``universal_law_query-0.1.0/``, kept by
  ``--keep-temp`` or an interrupted run), which setuptools would otherwise
  fill, archive whole and only then remove.

A symlinked directory above any of these trees (``build/`` above ``build/lib``
and the staging tree, ``src/`` above the egg-info directory) is refused before
anything is written, because every write under it would land wherever the link
points.

Nothing is deleted; each refusal names the leftovers and the remedy, which is
``git clean`` for the checkout's own ``build/`` and egg-info directory and
otherwise names the directory.
"""
from __future__ import annotations

import filecmp
import os
import stat
import sys
from importlib import metadata as _metadata

from setuptools import setup
# The two legacy commands live in distutils; import them through the name
# setuptools itself uses. Importing ``setuptools._distutils.…`` directly would
# load second copies of those modules and rebind the shared package's
# attributes to unpatched classes.
from distutils.command.bdist_dumb import bdist_dumb as _bdist_dumb  # noqa: I001
from distutils.command.bdist_rpm import bdist_rpm as _bdist_rpm
from setuptools.command.bdist_egg import bdist_egg as _bdist_egg
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.egg_info import egg_info as _egg_info
from setuptools.command.egg_info import manifest_maker as _manifest_maker
from setuptools.command.install_lib import install_lib as _install_lib
from setuptools.command.sdist import sdist as _sdist
from setuptools.errors import SetupError

EGG_INFO = 'src/universal_law_query.egg-info'
# Windows' reparse tag for a junction (mount point). The ``stat`` module only
# defines the name on Windows builds; the value is fixed by the platform.
_IO_REPARSE_TAG_MOUNT_POINT = getattr(stat, 'IO_REPARSE_TAG_MOUNT_POINT', 0xA0000003)
REMEDY = 'git clean -fdX -- build ' + EGG_INFO


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _relative(path: str) -> str:
    try:
        relative = os.path.relpath(path)
    except ValueError:  # another drive on Windows: no relative form exists
        relative = os.path.abspath(path)
    return relative.replace(os.sep, '/')


def _alias(path: str) -> str | None:
    """``'symlink'`` or ``'junction'`` when ``path`` points somewhere else, else None.

    A Windows junction is a directory reparse point that ``os.path.islink``
    does not report; Python 3.12 has ``os.path.isjunction``, and older
    interpreters expose the reparse tag on ``os.lstat``.
    """
    if os.path.islink(path):
        return 'symlink'
    isjunction = getattr(os.path, 'isjunction', None)
    if isjunction is not None:
        return 'junction' if isjunction(path) else None
    try:
        tag = getattr(os.lstat(path), 'st_reparse_tag', 0)
    except OSError:
        return None
    return 'junction' if tag == _IO_REPARSE_TAG_MOUNT_POINT else None


def _unexpected(tree: str, produced: set[str], empty_dirs: bool = False) -> list[str]:
    """Files under ``tree`` that are not in ``produced``, every symlink or
    junction, every hard-linked file, and with ``empty_dirs`` every empty
    directory below the tree itself."""
    found = []
    kind = _alias(tree)
    if kind:
        return [_relative(tree) + ' (' + kind + ')']
    if not os.path.isdir(tree):
        return found
    for dirpath, dirnames, filenames in os.walk(tree):
        if empty_dirs and dirpath != tree and not dirnames and not filenames:
            found.append(_relative(dirpath) + ' (empty directory)')
        for name in dirnames:
            kind = _alias(os.path.join(dirpath, name))
            if kind:
                found.append(_relative(os.path.join(dirpath, name)) + ' (' + kind + ')')
        for name in filenames:
            path = os.path.join(dirpath, name)
            kind = _alias(path)
            if kind:
                found.append(_relative(path) + ' (' + kind + ')')
            elif os.stat(path).st_nlink > 1:
                found.append(_relative(path) + ' (hard link)')
            elif _canonical(path) not in produced:
                found.append(_relative(path))
    return sorted(found)


def _remedy(tree: str) -> str:
    """The checkout's own build/ and egg-info are cleaned by git; another directory is named."""
    relative = _relative(tree)
    for cleaned in ('build', EGG_INFO):
        if relative == cleaned or relative.startswith(cleaned + '/'):
            return REMEDY
    return ('remove the named files under ' + relative
            + ' yourself; it is outside the checkout\'s build/, so ' + REMEDY + ' does not reach it')


def _refuse(unexpected: list[str], tree: str) -> None:
    if unexpected:
        raise SetupError(
            'REFUSED: stale build output not produced from this source tree: '
            + ', '.join(unexpected)
            + '. Remove build leftovers before installing: ' + _remedy(tree))


def _under(tree: str, path: str, build_lib: str) -> str:
    """``path``, produced under ``build_lib``, relocated under ``tree``."""
    return os.path.join(tree, os.path.relpath(path, build_lib))


def _source_pairs(build_py_command, tree: str | None = None) -> list[tuple[str, str]]:
    """(source, output) for every module and data file the build copies, with
    the outputs under ``tree`` (by default the build's own ``build_lib``)."""
    build_lib = build_py_command.build_lib
    tree = build_lib if tree is None else tree
    pairs = []
    for package, module, module_file in build_py_command.find_all_modules():
        pairs.append((module_file, build_py_command.get_module_outfile(tree, package.split('.'), module)))
    for _package, src_dir, build_dir, filenames in build_py_command.data_files:
        for filename in filenames:
            pairs.append((os.path.join(src_dir, filename), _under(tree, os.path.join(build_dir, filename), build_lib)))
    return pairs


def _symlinked_paths(paths) -> list[str]:
    """Each of ``paths`` that is a symlink or junction, and every such directory above one."""
    found = set()
    for source in paths:
        path = os.path.normpath(source)
        while path and path != os.path.dirname(path):
            kind = _alias(path)
            if kind:
                found.add(_relative(path) + ' (' + kind + ')')
            path = os.path.dirname(path)
    return sorted(found)


def _symlinked_sources(build_py_command) -> list[str]:
    """Package sources, and directories above them, that are symlinks."""
    return _symlinked_paths(source for source, _output in _source_pairs(build_py_command))


def _symlinked_parents(path: str) -> list[str]:
    """Directories above a relative ``path`` that are symlinks; a write under
    ``path`` would land wherever they point. An absolute path, configured
    deliberately, is taken as given."""
    found = []
    if os.path.isabs(path):
        return found
    parent = os.path.dirname(os.path.normpath(path))
    while parent and parent != os.path.dirname(parent):
        kind = _alias(parent)
        if kind:
            found.append(_relative(parent) + ' (' + kind + ')')
        parent = os.path.dirname(parent)
    return found


def _egg_info_leftovers(tree: str, written: set[str]) -> list[str]:
    """Everything in the egg-info directory that is not a regular file with a
    name this run writes: a symlink anywhere (a writer would follow it and
    overwrite its target), a directory, or a file no writer produces."""
    found = _symlinked_parents(tree)
    kind = _alias(tree)
    if kind:
        return sorted(found + [_relative(tree) + ' (' + kind + ')'])
    if not os.path.isdir(tree):
        return sorted(found)
    for name in sorted(os.listdir(tree)):
        path = os.path.join(tree, name)
        kind = _alias(path)
        if kind:
            found.append(_relative(path) + ' (' + kind + ')')
        elif not os.path.isfile(path):
            found.append(_relative(path) + ' (not a regular file)')
        elif os.stat(path).st_nlink > 1:
            found.append(_relative(path) + ' (hard link)')
        elif name not in written:
            found.append(_relative(path))
    return sorted(found)


def _refuse_sources(symlinked: list[str]) -> None:
    if symlinked:
        raise SetupError(
            'REFUSED: symlinked source, which would ship the link\'s target rather than a file of '
            'this source tree: ' + ', '.join(symlinked)
            + '. Replace the symlink with a regular file before installing.')


def _differing_outputs(build_py_command, tree: str | None = None) -> list[str]:
    """Produced module and data paths that are missing, not regular files, or
    whose bytes are not this source tree's."""
    found = []
    for source, output in _source_pairs(build_py_command, tree):
        if _alias(output):
            continue  # already reported by the tree walk
        if not os.path.exists(output):
            found.append(_relative(output) + ' (missing)')
        elif not os.path.isfile(output):
            found.append(_relative(output) + ' (not a regular file)')
        elif not filecmp.cmp(source, output, shallow=False):
            found.append(_relative(output) + ' (bytes differ from ' + _relative(source) + ')')
    return found


def _guard_build_lib(build_py_command, compare_bytes: bool = False, recompiles: bool = True,
                     tree: str | None = None) -> None:
    """Refuse a symlinked source, then anything under the output tree (by
    default build/lib) that is not this source tree's output.

    Bytecode is admitted only when this run rewrites it: ``recompiles`` is
    false when nothing is rebuilt (``--skip-build``), and setuptools skips the
    compile step under ``python -B`` or ``PYTHONDONTWRITEBYTECODE``. With
    ``compare_bytes`` each produced module's and data file's bytes are also
    checked against its source, and every expected output must be present.
    ``tree`` names another directory holding the same layout, such as the one
    ``install_lib --build-dir`` copies from.
    """
    build_lib = build_py_command.build_lib
    tree = build_lib if tree is None else tree
    _refuse_sources(_symlinked_sources(build_py_command))
    admit_bytecode = recompiles and not sys.dont_write_bytecode
    produced = {_canonical(_under(tree, path, build_lib))
                for path in build_py_command.get_outputs(include_bytecode=admit_bytecode)}
    unexpected = sorted(_symlinked_parents(tree) + _unexpected(tree, produced))
    if compare_bytes:
        unexpected = sorted(unexpected + _differing_outputs(build_py_command, tree))
    _refuse(unexpected, tree)


def _guard_skipped_build(command, tree: str | None = None) -> None:
    """A command that ships a build tree without rebuilding it compares the bytes it has."""
    _guard_build_lib(command.get_finalized_command('build_py'), compare_bytes=True, recompiles=False, tree=tree)


def _dist_info_leftovers(tree: str, distribution) -> list[str]:
    """Entries of a pre-generated dist-info directory that this build's own
    metadata conversion would not produce, plus every alias or hard link.

    ``bdist_wheel --dist-info-dir`` copies the directory into the wheel as is.
    The conversion keeps the egg-info writers' files except ``PKG-INFO`` (which
    becomes ``METADATA``), ``requires.txt`` and ``SOURCES.txt``, and places the
    distribution's license files under ``licenses/``.
    """
    written = {entry.name for entry in _metadata.entry_points(group='egg_info.writers')}
    written -= {'PKG-INFO', 'requires.txt', 'SOURCES.txt'}
    written |= {'METADATA', 'WHEEL', 'RECORD'}
    licenses = {os.path.normpath(path).replace(os.sep, '/')
                for path in (distribution.metadata.license_files or ())}
    found = _symlinked_parents(tree)
    kind = _alias(tree)
    if kind:
        return sorted(found + [_relative(tree) + ' (' + kind + ')'])
    if not os.path.isdir(tree):
        return sorted(found + [_relative(tree) + ' (missing)'])
    for dirpath, dirnames, filenames in os.walk(tree):
        inside = os.path.relpath(dirpath, tree).replace(os.sep, '/')
        for name in dirnames:
            path = os.path.join(dirpath, name)
            kind = _alias(path)
            if kind:
                found.append(_relative(path) + ' (' + kind + ')')
            elif not (inside == os.curdir and name == 'licenses'):
                found.append(_relative(path) + ' (directory)')
        for name in filenames:
            path = os.path.join(dirpath, name)
            kind = _alias(path)
            if kind:
                found.append(_relative(path) + ' (' + kind + ')')
            elif os.stat(path).st_nlink > 1:
                found.append(_relative(path) + ' (hard link)')
            elif inside == os.curdir:
                if name not in written:
                    found.append(_relative(path))
            elif inside == 'licenses':
                if name not in licenses:
                    found.append(_relative(path))
            else:
                found.append(_relative(path))
    return sorted(found)


def _guard_staging(command, staging_dir: str) -> None:
    """Refuse any leftover under the shared bdist base (``build/bdist.<platform>``),
    where the wheel, egg, dumb and rpm staging trees live, and under the
    command's own staging directory when it was configured elsewhere."""
    base = command.get_finalized_command('bdist').bdist_base
    for tree in (base, staging_dir):
        _refuse(sorted(_symlinked_parents(tree) + _unexpected(tree, set(), empty_dirs=True)), tree)


class build_py(_build_py):
    """Refuse build output that this source tree did not produce."""

    def run(self) -> None:
        _guard_build_lib(self)
        # Rewrite every output: a leftover at a produced path that is newer than
        # its source would otherwise be kept as "up to date" and shipped.
        self.force = True
        super().run()
        # A dry run writes nothing, so there is nothing to compare; the
        # leftover check still runs.
        _guard_build_lib(self, compare_bytes=not self.dry_run)


class bdist_wheel(_bdist_wheel):
    """Refuse a leftover staging tree, and re-check build/lib even with --skip-build."""

    def run(self) -> None:
        _guard_staging(self, self.bdist_dir)
        if self.dist_info_dir:
            # Pre-generated metadata is copied into the wheel as is, so it must
            # hold only what this build's own conversion would produce.
            _refuse(_dist_info_leftovers(self.dist_info_dir, self.distribution), self.dist_info_dir)
        if self.skip_build:
            _guard_skipped_build(self)
        else:
            # The build rewrites build/lib next and checks it again itself.
            _guard_build_lib(self.get_finalized_command('build_py'))
        super().run()


class bdist_egg(_bdist_egg):
    """Refuse a leftover egg staging tree; the legacy archive is assembled from whatever it holds."""

    def run(self) -> None:
        _guard_staging(self, self.bdist_dir)
        super().run()


class bdist_dumb(_bdist_dumb):
    """Refuse a leftover dumb staging tree; the archive is the pseudo-installation tree as found."""

    def run(self) -> None:
        _guard_staging(self, self.bdist_dir)
        super().run()


class bdist_rpm(_bdist_rpm):
    """Refuse a leftover rpm build tree under the bdist base before rpmbuild sees it."""

    def run(self) -> None:
        _guard_staging(self, self.rpm_base)
        super().run()


class install_lib(_install_lib):
    """Validate the directory this command copies from (--build-dir, by default build/lib)."""

    def install(self):
        # Runs after build(): bytecode a build in this run wrote is admitted;
        # under --skip-build nothing recompiles it. A dry run copies nothing.
        _guard_build_lib(self.get_finalized_command('build_py'), compare_bytes=not self.dry_run,
                         recompiles=not self.skip_build, tree=self.build_dir)
        return super().install()


class _fresh_manifest_maker(_manifest_maker):
    """Build SOURCES.txt from the tree; a leftover manifest is never read back."""

    def read_manifest(self) -> None:
        return None


class egg_info(_egg_info):
    """Regenerate the manifest, and refuse any leftover beside the files this run writes."""

    def find_sources(self) -> None:
        manifest_filename = os.path.join(self.egg_info, 'SOURCES.txt')
        mm = _fresh_manifest_maker(self.distribution)
        mm.ignore_egg_info_dir = getattr(self, 'ignore_egg_info_in_manifest', False)
        mm.manifest = manifest_filename
        mm.run()
        self.filelist = mm.filelist

    def run(self) -> None:
        written = {entry.name for entry in _metadata.entry_points(group='egg_info.writers')}
        written.add('SOURCES.txt')
        # Before the writers run: each opens its file by name and would follow a
        # symlink, overwriting the target, so nothing may be written until the
        # directory is known to hold only regular files this run rewrites. sdist
        # grafts the whole directory and a direct bdist_wheel copies it into the
        # dist-info, so a file no writer produces is a leftover with a path into
        # the archive; the check is repeated afterwards.
        _refuse(_egg_info_leftovers(self.egg_info, written), self.egg_info)
        super().run()
        _refuse(_egg_info_leftovers(self.egg_info, written), self.egg_info)


class sdist(_sdist):
    """Refuse a leftover release tree; setuptools would fill it, archive it whole and only then remove it."""

    def make_release_tree(self, base_dir, files) -> None:
        # Every manifest entry is copied into the tree (setuptools disables hard
        # links here) and then archived, so a symlink among them, or above one,
        # would ship its target as a regular file.
        _refuse_sources(_symlinked_paths(files))
        _refuse(_unexpected(base_dir, set()), base_dir)
        super().make_release_tree(base_dir, files)


setup(cmdclass={'build_py': build_py, 'bdist_wheel': bdist_wheel, 'bdist_egg': bdist_egg,
                'bdist_dumb': bdist_dumb, 'bdist_rpm': bdist_rpm, 'install_lib': install_lib,
                'egg_info': egg_info, 'sdist': sdist})
