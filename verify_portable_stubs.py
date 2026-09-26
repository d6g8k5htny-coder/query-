"""Compatibility wrapper for universal_law_query.stub_verify."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
_SRC=ROOT/'src'
if str(_SRC) not in sys.path: sys.path.insert(0,str(_SRC))
from universal_law_query import stub_verify as _impl
PUBLIC_REPOS=_impl.PUBLIC_REPOS
REPO_ROOT=_impl.REPO_ROOT
validate_row=_impl.validate_row
load_candidates=_impl.load_candidates
fetch_raw=_impl.fetch_raw
fetch=_impl.fetch

def check_math_tip_drift(root=None):
    return _impl.check_math_tip_drift(root,fetch_raw_fn=lambda *args,**kwargs: fetch_raw(*args,**kwargs))

def main(argv=None):
    return _impl.main(argv,load_candidates_fn=lambda: load_candidates(),fetch_fn=lambda row: fetch(row),check_tip_fn=lambda: check_math_tip_drift())

__all__=['ROOT','PUBLIC_REPOS','REPO_ROOT','check_math_tip_drift','fetch','fetch_raw','load_candidates','main','validate_row']
if __name__=='__main__': raise SystemExit(main())
