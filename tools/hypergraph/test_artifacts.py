"""Repo-agnostic artifact-scan tests (synthetic tree; run in any repo). Organization only: credit 0, OBL OPEN."""
import importlib.util, sys
from pathlib import Path
import pytest

pytest.importorskip("hyperdb")
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("math_hypergraph", HERE / "math_hypergraph.py")
mh = importlib.util.module_from_spec(spec); sys.modules["math_hypergraph"] = mh; spec.loader.exec_module(mh)

SPEC = {"unit_depth": 2, "artifacts": {"review": ["*REVIEW*.md"], "source": ["*PROOF*.md"],
                                      "formal": ["*.lean"], "impl": ["*.py"]}}


def _tree(tmp_path):
    for rel in ("frontiers/a/PROOF.md", "frontiers/a/A.lean", "frontiers/a/run.py", "frontiers/a/REVIEW_x.md",
                "frontiers/b/deep/B.lean", "frontiers/b/notes.txt", ".lake/pkg/X.lean", "top.py"):
        p = tmp_path / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("x")
    return tmp_path


def test_artifact_hyperedges(tmp_path):
    hg = mh.HypergraphDB()
    n = mh.add_artifacts(hg, "Math-", _tree(tmp_path), SPEC)
    assert n == 3  # frontiers/a, frontiers/b, (root); .lake skipped
    assert all(v.startswith("Math-:") for v in hg.all_v)
    roles = {hg.e(e)["unit"]: sorted(hg.e(e)["roles"].values()) for e in hg.all_e}
    assert roles["frontiers/a"] == ["formal", "impl", "review", "source", "unit"]
    assert roles["frontiers/b"] == ["formal", "unit"]
    assert not any("X.lean" in v or "notes.txt" in v for v in hg.all_v)
    assert mh.validate(hg) == []
    assert all(hg.e(e)["credit"] == 0 and hg.e(e)["obl"] == "OPEN" for e in hg.all_e)


def test_missing_repo_skipped(capsys):
    cfg = {"repos": {"ghost": {"checkout": "external/__no_such_repo__", "artifacts": SPEC["artifacts"]}}}
    hg, G, skipped = mh.build(None, None, None, cfg, ["ghost"])
    assert skipped == ["ghost"] and hg.num_v == 0
    assert "skip ghost" in capsys.readouterr().err


def test_unknown_repo_rejected():
    with pytest.raises(KeyError):
        mh.build(None, None, None, {"repos": {}}, ["nope"])


def test_config_paths_relative():
    cfg = mh.load_config()
    for spec in cfg["repos"].values():
        for k in ("checkout", "ledger", "graph", "report"):
            if k in spec:
                assert not Path(spec[k]).is_absolute() and ".." not in Path(spec[k]).parts


def test_specific_patterns_beat_review_catchall(tmp_path):
    for rel in ("reviews/r1/check.py", "reviews/r1/L.lean", "reviews/r1/notes.md"):
        p = tmp_path / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_text("x")
    import json
    cfg = json.loads((HERE / "inputs.json").read_text())["repos"]["Math-"]
    hg = mh.HypergraphDB()
    mh.add_artifacts(hg, "Math-", tmp_path, cfg)
    roles = {k: r for e in hg.all_e for k, r in hg.e(e)["roles"].items()}
    assert roles["Math-:impl:reviews/r1/check.py"] == "impl"
    assert roles["Math-:formal:reviews/r1/L.lean"] == "formal"
    assert roles["Math-:src:reviews/r1/notes.md"] == "review"


def test_resolve_paths():
    assert mh._resolve("Math-", "u/x", "main:architecture/a.json") == ("main", "architecture/a.json")
    assert mh._resolve("Math-", "u/x", "replay.py") == ("Math-", "u/x/replay.py")
    assert mh._resolve("Math-", "u/x", "u/x/C7/P.md") == ("Math-", "u/x/C7/P.md")
    cfg = {"repos": {"Math-": {"root_dirs": ["frontiers"]}}}
    assert mh._resolve("Math-", "u/x", "frontiers/y/P.md", cfg) == ("Math-", "frontiers/y/P.md")
    assert mh._resolve("Math-", "u/x", "C7/P.md", cfg) == ("Math-", "u/x/C7/P.md")
    assert mh._resolve("nochk", "u/x", "C7/P.md") == ("nochk", "u/x/C7/P.md")


def test_export_manifest_includes_readme(tmp_path):
    hg = mh.HypergraphDB(); hg.add_v("m:unit:a", {"type": "unit"})
    mh.export(hg, {}, tmp_path, {}, [], [])
    import json
    man = json.loads((tmp_path / "MANIFEST.json").read_text())
    assert "README.md" in man["files"]
    assert man["files"]["README.md"] == mh._sha(tmp_path / "README.md")
