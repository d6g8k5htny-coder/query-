"""Build-time leftover guard for installs from this checkout.

Scientific effect: NONE. This file adds no runtime dependency and changes no
lookup, verification or refusal behaviour of the package.

setuptools reuses ``build/lib`` between builds and removes nothing from it. A
module left there by an install from another commit is copied into the next
wheel although ``src/`` does not contain it, and an import check of the
installed package still passes. This ``build_py`` compares the whole
``build_lib`` tree with the files it has just produced and refuses to continue
when anything else is present. Bytecode written by the same run (``--compile``
or ``-O``) counts as produced; that admission is by cache path, so a file
already at a path this run would write is accepted even when the byte-compile
step leaves its bytes in place (the pip path writes no bytecode and refuses
such a file). Nothing is deleted; the refusal names the leftovers and the
documented remedy.
"""
from __future__ import annotations

import os

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py
from setuptools.errors import SetupError

REMEDY = 'git clean -fdX -- build src/universal_law_query.egg-info'


def _canonical(path: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


class build_py(_build_py):
    """Refuse build output that this source tree did not produce."""

    def run(self) -> None:
        super().run()
        produced = {_canonical(path) for path in self.get_outputs(include_bytecode=True)}
        stale = []
        for dirpath, _dirnames, filenames in os.walk(self.build_lib):
            for name in filenames:
                path = os.path.join(dirpath, name)
                if _canonical(path) not in produced:
                    stale.append(os.path.relpath(path).replace(os.sep, '/'))
        if stale:
            raise SetupError(
                'REFUSED: stale build output not produced from this source tree: '
                + ', '.join(sorted(stale))
                + '. Remove build leftovers before installing: ' + REMEDY)


setup(cmdclass={'build_py': build_py})
