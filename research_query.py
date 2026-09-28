"""Compatibility wrapper for the canonical universal_law_query package."""
from __future__ import annotations
import sys
from pathlib import Path

_SRC=Path(__file__).resolve().parent/'src'
if str(_SRC) not in sys.path:
    sys.path.insert(0,str(_SRC))

from universal_law_query.catalog import CatalogError, load_catalog, lookup, unique, valid_path, verify
from universal_law_query.cli import main

__all__=['CatalogError','load_catalog','lookup','unique','valid_path','verify','main']

if __name__=='__main__':
    raise SystemExit(main())
