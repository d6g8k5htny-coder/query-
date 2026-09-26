"""Compatibility wrapper for universal_law_query.stub_verify."""
from __future__ import annotations
import sys
from pathlib import Path
_SRC=Path(__file__).resolve().parent/'src'
if str(_SRC) not in sys.path: sys.path.insert(0,str(_SRC))
from universal_law_query.stub_verify import PUBLIC_REPOS,REPO_ROOT,check_math_tip_drift,fetch,fetch_raw,load_candidates,main,validate_row
__all__=['PUBLIC_REPOS','REPO_ROOT','check_math_tip_drift','fetch','fetch_raw','load_candidates','main','validate_row']
if __name__=='__main__': raise SystemExit(main())
