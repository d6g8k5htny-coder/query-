"""Compatibility wrapper for universal_law_query.catalog_entry."""
from __future__ import annotations
import sys
from pathlib import Path
_SRC=Path(__file__).resolve().parent/'src'
if str(_SRC) not in sys.path: sys.path.insert(0,str(_SRC))
from universal_law_query.catalog_entry import PUBLIC_REPOS,HelperError,build_entry,main,read_public_bytes,resolve_commit,valid_repo_path
__all__=['PUBLIC_REPOS','HelperError','build_entry','main','read_public_bytes','resolve_commit','valid_repo_path']
if __name__=='__main__': raise SystemExit(main())
