# tools/hypergraph (query- companion) — organization only, NOT A RESULT

credit 0 · OBL OPEN · no flags. Same pinned package as d6g8k5htny-coder/main `tools/hypergraph` (main#579);
this copy scans **query-** (checkout `.`) and, when present, read-only checkouts of main, Math- under `external/`.
Vertex keys are `<repo>:<type>:<id>`. Absent/private repos are skipped with a message.

## Run locally (Python 3.11/3.12)
```
pip install -r tools/hypergraph/requirements.txt
pytest tools/hypergraph
python -m tools.hypergraph.math_hypergraph validate | gaps | repos
python -m tools.hypergraph.math_hypergraph export /tmp/hg-bundle --repos all --png
# optional: git clone --depth 1 https://github.com/d6g8k5htny-coder/<repo> external/<repo>
```
Edit `inputs.json` to change which globs count as source / review / formal / impl / spec / test.

## GitHub Actions — `.github/workflows/math-hypergraph.yml`
Runs on PRs/pushes to `main` touching the tool or query-'s artifacts, and via workflow_dispatch. Checks out the other public
repos read-only, installs pins on Python 3.12, runs pytest, `validate`, `gaps`, and uploads the all-repo export
(JSON, PNG, README, MANIFEST) as the `math-hypergraph` artifact. `contents: read`, no secrets, 10-minute timeout, not required.
The committed-output `build --check` gate lives in main, which owns the ledger.
