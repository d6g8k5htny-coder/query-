"""Build-time leftover guard for installs from this checkout.

Scientific effect: NONE. This file adds no runtime dependency and changes no
lookup, verification or refusal behaviour of the package.

setuptools reuses ``build/`` between builds and removes nothing from it. A
module left under ``build/lib`` by an install from another commit is copied
into the next wheel although ``src/`` does not contain it, and an import check
of the installed package still passes. Nine commands are guarded:

- ``build_py`` refuses a symlink among the package sources it would copy, or a
  symlinked directory above one, because the copy and the byte comparison
  below both follow the link and would ship its target as a file of this tree.
  It then compares the whole ``build/lib`` tree with the files it produces,
  before copying anything and again afterwards, and refuses when anything else
  is present. Every symlink under the tree is refused wherever it points,
  because the walk does not follow symlinks but the wheel staging step
  dereferences them (a Windows junction counts as a symlink throughout, and no
  walk descends into one); a
  hard-linked file is refused as well, since its bytes are shared with another
  path. The run rewrites every file it produces (setuptools would
  otherwise skip a destination that is newer than its source), and afterwards
  each produced module's bytes are compared with its source, so bytes left at a
  path this run writes are replaced, never shipped. Bytecode counts as produced
  only when this run recompiles it (``--compile`` or ``-O`` with bytecode
  writing enabled); under ``python -B`` or ``PYTHONDONTWRITEBYTECODE`` setuptools
  skips the compile step, so a cache file found under ``build/lib`` is refused.
  A dry run writes nothing, so the comparison after the run is skipped there;
  the leftover check before it still applies. An editable build copies
  nothing (the install runs from ``src/``), so there is nothing to guard.
- ``bdist_wheel`` refuses a leftover anywhere in its own staging tree (by
  default ``build/bdist.<platform>/wheel``; an interrupted build leaves one,
  and the next build archives whatever it holds), refuses a
  pre-generated ``--dist-info-dir`` that differs in any name or byte from this
  build's own metadata, which a separate ``dist_info`` run of this script
  regenerates for the comparison (the directory is copied into the wheel as
  is), and repeats the ``build/lib`` comparison, so ``--skip-build`` cannot
  bypass it. With ``--skip-build`` nothing is rebuilt, so the byte comparison
  runs there instead, every expected output must be present as a regular file,
  and bytecode, which nothing recompiles, is refused.
- ``editable_wheel`` applies the same ``--dist-info-dir`` comparison; pip's
  editable install passes the metadata it generated, and the command copies it
  into the editable wheel as is.
- ``install_lib`` applies the same comparison to the directory it copies from
  (its ``--build-dir``, by default ``build/lib``), whether or not it rebuilt
  it, which covers the legacy ``install``, ``install_lib`` and ``bdist_egg``
  commands with and without ``--skip-build``. Bytecode is admitted only in
  ``build/lib`` after this run recompiled it there; in another directory
  nothing recompiled it, and the copy keeps a cache file newer than its source.
- ``bdist_egg`` and ``bdist_dumb`` refuse a leftover in their own staging
  trees the same way; the legacy archives are assembled from whatever those
  trees hold. ``bdist_rpm`` refuses one in its rpm tree, except the spec and
  source archive that every run rewrites (forced) and a successful run leaves
  behind with empty directories. Each command reads only its own tree, so a
  sibling's tree under ``build/bdist.<platform>`` blocks nothing else. A tree
  that an earlier command of the same run kept (``bdist`` keeps one between
  two formats of a command) is that run's own output and is admitted.
- ``egg_info`` regenerates ``SOURCES.txt`` from the tree and never reads a
  leftover manifest back in, so a stale entry can add a file neither to a wheel
  nor to a source distribution; any other file left beside the ones this run
  writes is refused, because ``sdist`` and a direct ``bdist_wheel`` copy the
  whole directory into the archive. The directory is checked before the
  writers run as well as after: a writer opens each metadata file by name and
  would follow a symlink, overwriting whatever it points at, so the directory
  itself and every entry in it must be a regular file with a single link; a
  hard-linked file shares its bytes with another path and would be written
  through just the same. A symlink among the files the manifest names, or a
  symlinked directory above one, is refused when the manifest is built: the
  metadata conversion reads ``README.md`` into ``METADATA`` and copies the
  license files into the wheel, following any link.
- ``sdist`` refuses a symlink among the files the manifest names, or a
  symlinked directory above one, before copying anything: the release tree
  would otherwise hold the link's target as a regular file. It also refuses a
  leftover release tree (``universal_law_query-0.1.0/``, kept by
  ``--keep-temp`` or an interrupted run), which setuptools would otherwise
  fill, archive whole and only then remove.

A symlinked directory above any of these trees (``build/`` above ``build/lib``
and the staging tree, ``src/`` above the egg-info directory) is refused before
anything is written, because every write under it would land wherever the link
points. A tree named with a trailing separator or ``.`` is checked as the link
it names, and one reached through ``..`` after a symlinked directory is refused
as well. The output directory (``dist/`` or ``--dist-dir``) is taken as given.

Nothing is deleted; each refusal names the leftovers and the remedy, which is
``git clean`` for the checkout's own ``build/`` and egg-info directory and
otherwise names the directory.
"""
from __future__ import annotations

import filecmp
import os
import stat
import subprocess
import sys
import tempfile
from importlib import metadata as _metadata

from setuptools import setup
# setuptools has no bdist_dumb of its own and runs distutils' command; import
# it through the name setuptools itself uses. Importing
# ``setuptools._distutils.…`` directly would load a second copy of that module
# and rebind the shared package's attributes to unpatched classes.
from distutils.command.bdist_dumb import bdist_dumb as _bdist_dumb  # noqa: I001
from setuptools.command.bdist_egg import bdist_egg as _bdist_egg
from setuptools.command.bdist_rpm import bdist_rpm as _bdist_rpm
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.editable_wheel import editable_wheel as _editable_wheel
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
SETUP_SCRIPT = os.path.abspath(__file__)


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
    interpreters expose the reparse tag on ``os.lstat``. A trailing separator
    or ``.`` would make the system follow the link, so it is dropped first.
    """
    path = os.path.normpath(path)
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
        for name in list(dirnames):
            kind = _alias(os.path.join(dirpath, name))
            if kind:
                found.append(_relative(os.path.join(dirpath, name)) + ' (' + kind + ')')
                dirnames.remove(name)  # os.walk would descend into a Windows junction
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
            + ', '.join(sorted(set(unexpected)))
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
    ``path`` would land wherever they point. Each directory is taken as
    written, since ``..`` after a symlinked one leaves the link's target and
    normalizing would hide it. An absolute path, configured deliberately, is
    taken as given."""
    found = []
    if os.path.isabs(path):
        return found
    parent = os.path.dirname(path)
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


def _interpreter_flags() -> list[str]:
    """The running interpreter's isolation options, for a child run of this script."""
    options = (('isolated', '-I'), ('ignore_environment', '-E'), ('no_user_site', '-s'),
               ('no_site', '-S'), ('safe_path', '-P'), ('dont_write_bytecode', '-B'))
    return [option for flag, option in options if getattr(sys.flags, flag, False)]


def _fresh_dist_info(workdir: str) -> str:
    """This build's own dist-info directory, regenerated by a separate
    ``dist_info`` run of this script into the empty ``workdir``."""
    command = [sys.executable, *_interpreter_flags(), SETUP_SCRIPT, '-q', 'dist_info', '--output-dir', workdir]
    try:
        result = subprocess.run(command, cwd=os.path.dirname(SETUP_SCRIPT), capture_output=True, text=True,
                                errors='replace')
    except OSError as error:
        raise SetupError('REFUSED: could not regenerate this build\'s metadata to compare with '
                         '--dist-info-dir: ' + str(error)) from error
    produced = [name for name in os.listdir(workdir) if name.endswith('.dist-info')]
    if result.returncode != 0 or len(produced) != 1:
        raise SetupError('REFUSED: could not regenerate this build\'s metadata to compare with '
                         '--dist-info-dir: ' + (result.stderr.strip()[-2000:] or 'no dist-info produced'))
    return os.path.join(workdir, produced[0])


def _entries(tree: str) -> tuple[set[str], set[str]]:
    """Relative paths of the directories and of the files under ``tree``, as spelled on disk."""
    dirs, files = set(), set()
    for dirpath, dirnames, filenames in os.walk(tree):
        inside = os.path.relpath(dirpath, tree)
        dirs.update(os.path.normpath(os.path.join(inside, name)) for name in dirnames)
        files.update(os.path.normpath(os.path.join(inside, name)) for name in filenames)
        # Reported as entries; os.walk would descend into a Windows junction.
        dirnames[:] = [name for name in dirnames if not _alias(os.path.join(dirpath, name))]
    return dirs, files


def _dist_info_mismatches(tree: str, reference: str) -> list[str]:
    """Every way a pre-generated dist-info directory differs from ``reference``,
    this build's own: an alias or hard link, a non-regular file, an entry the
    reference lacks, bytes that differ, or a reference file that is missing.
    Names are compared exactly, so a case variant counts as another entry."""
    found = _symlinked_parents(tree)
    kind = _alias(tree)
    if kind:
        return sorted(found + [_relative(tree) + ' (' + kind + ')'])
    if not os.path.isdir(tree):
        return sorted(found + [_relative(tree) + ' (missing)'])
    expected_dirs, expected_files = _entries(reference)
    dirs, files = _entries(tree)
    for entry in sorted(dirs):
        path = os.path.join(tree, entry)
        kind = _alias(path)
        if kind:
            found.append(_relative(path) + ' (' + kind + ')')
        elif entry not in expected_dirs:
            found.append(_relative(path) + ' (not in this build\'s metadata)')
    for entry in sorted(files):
        path = os.path.join(tree, entry)
        kind = _alias(path)
        if kind:
            found.append(_relative(path) + ' (' + kind + ')')
        elif not os.path.isfile(path):
            found.append(_relative(path) + ' (not a regular file)')
        elif os.stat(path).st_nlink > 1:
            found.append(_relative(path) + ' (hard link)')
        elif entry not in expected_files:
            found.append(_relative(path) + ' (not in this build\'s metadata)')
        elif not filecmp.cmp(os.path.join(reference, entry), path, shallow=False):
            found.append(_relative(path) + ' (bytes differ from this build\'s metadata)')
    for entry in sorted(expected_files - files):
        found.append(_relative(os.path.join(tree, entry)) + ' (missing)')
    return sorted(found)


def _refuse_dist_info(mismatches: list[str]) -> None:
    if mismatches:
        raise SetupError(
            'REFUSED: pre-generated metadata does not match this build\'s own: ' + ', '.join(mismatches)
            + '. Regenerate it from this checkout (setup.py dist_info) or build without --dist-info-dir.')


def _guard_dist_info(dist_info_dir: str | None) -> None:
    """A given ``--dist-info-dir`` is copied into the wheel as is, so it must
    match, in names and bytes, what this build's own conversion produces; a
    separate run regenerates that for the comparison."""
    if dist_info_dir:
        with tempfile.TemporaryDirectory() as workdir:
            _refuse_dist_info(_dist_info_mismatches(os.fspath(dist_info_dir), _fresh_dist_info(workdir)))


# Files of staging trees that an earlier command of this same run kept
# (``bdist`` keeps the tree between two formats of one command): this run's
# own output, not leftovers.
_KEPT_STAGING: set[str] = set()


def _guard_staging(staging_dir: str, rewritten: frozenset[str] = frozenset(), empty_dirs: bool = True) -> None:
    """Refuse any leftover in a command's own staging tree, which the command
    archives (or, for rpm, hands to rpmbuild) as found. A sibling command's
    tree under the same ``build/bdist.<platform>`` is never read. Files that an
    earlier command of this same run kept, and ``rewritten`` files that the
    command overwrites on every run, are admitted."""
    _refuse(sorted(_symlinked_parents(staging_dir)
                   + _unexpected(staging_dir, _KEPT_STAGING | rewritten, empty_dirs=empty_dirs)), staging_dir)


def _remember_kept(command, staging_dir: str) -> None:
    """After a command that keeps its staging tree, admit that tree's files to
    later commands of this run."""
    if getattr(command, 'keep_temp', False) and os.path.isdir(staging_dir):
        for dirpath, _dirnames, filenames in os.walk(staging_dir):
            _KEPT_STAGING.update(_canonical(os.path.join(dirpath, name)) for name in filenames)


class build_py(_build_py):
    """Refuse build output that this source tree did not produce."""

    def run(self) -> None:
        if self.editable_mode:
            # An editable build copies nothing (the install runs from src/),
            # so there is no build tree to guard.
            return super().run()
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
        _guard_staging(self.bdist_dir)
        _guard_dist_info(self.dist_info_dir)
        if self.skip_build:
            _guard_skipped_build(self)
        else:
            # The build rewrites build/lib next and checks it again itself.
            _guard_build_lib(self.get_finalized_command('build_py'))
        super().run()
        _remember_kept(self, self.bdist_dir)


class editable_wheel(_editable_wheel):
    """Validate a pre-generated dist-info; pip's editable flow passes the one it generated."""

    def run(self) -> None:
        # Before the run: it writes WHEEL into the given directory, then copies
        # the directory into the wheel as is.
        _guard_dist_info(self.dist_info_dir)
        super().run()


class bdist_egg(_bdist_egg):
    """Refuse a leftover egg staging tree; the legacy archive is assembled from whatever it holds."""

    def run(self) -> None:
        _guard_staging(self.bdist_dir)
        super().run()
        _remember_kept(self, self.bdist_dir)


class bdist_dumb(_bdist_dumb):
    """Refuse a leftover dumb staging tree; the archive is the pseudo-installation tree as found."""

    def run(self) -> None:
        _guard_staging(self.bdist_dir)
        super().run()
        _remember_kept(self, self.bdist_dir)


class bdist_rpm(_bdist_rpm):
    """Refuse a leftover in the rpm build tree before rpmbuild sees it."""

    def run(self) -> None:
        # Every run rewrites the spec and the source archive that rpmbuild
        # reads, and a successful run leaves both behind with empty
        # directories; the copy is forced, so an existing archive newer than
        # the new one is not kept. Anything else in the tree is a leftover.
        self.force = True
        archive = self.distribution.get_fullname() + ('.tar.bz2' if self.use_bzip2 else '.tar.gz')
        rewritten = frozenset({
            _canonical(os.path.join(self.rpm_base, 'SPECS', self.distribution.get_name() + '.spec')),
            _canonical(os.path.join(self.rpm_base, 'SOURCES', archive))})
        _guard_staging(self.rpm_base, rewritten, empty_dirs=False)
        super().run()
        _remember_kept(self, self.rpm_base)


class install_lib(_install_lib):
    """Validate the directory this command copies from (--build-dir, by default build/lib)."""

    def install(self):
        # Runs after build(): bytecode a build in this run wrote is admitted,
        # but only in build/lib, the tree that build recompiled; under
        # --skip-build nothing recompiles it. A dry run copies nothing.
        build_py = self.get_finalized_command('build_py')
        recompiled = not self.skip_build and _canonical(self.build_dir) == _canonical(build_py.build_lib)
        _guard_build_lib(build_py, compare_bytes=not self.dry_run, recompiles=recompiled, tree=self.build_dir)
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
        # The metadata conversion reads README.md into METADATA and copies the
        # license files into the wheel, following any symlink, so every file
        # the manifest names must be a file of this tree, as for an sdist.
        _refuse_sources(_symlinked_paths(self.filelist.files))

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


setup(cmdclass={'build_py': build_py, 'bdist_wheel': bdist_wheel, 'editable_wheel': editable_wheel,
                'bdist_egg': bdist_egg, 'bdist_dumb': bdist_dumb, 'bdist_rpm': bdist_rpm,
                'install_lib': install_lib, 'egg_info': egg_info, 'sdist': sdist})
