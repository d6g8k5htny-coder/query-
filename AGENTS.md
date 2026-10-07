# Agent entry — `query-`

Read-only lookup and local byte verification against the meta-framework catalog.

The 27 September 2026 owner stop is no longer in effect (Dylan Roy, 7 October 2026: remove the stop file; no agent needs to stop). Do not exit because of that historical stop.

## Canonical code

- Package: `src/universal_law_query/`
- Compatibility wrappers: `research_query.py`, `catalog_entry_helper.py`, `verify_portable_stubs.py`
- Package tests: `tests/`
- Legacy compatibility tests: root `test_*.py`
- Deterministic source dry-run builder: `scripts/build_source_release.py`

Wrappers may only add local `src/`, re-export compatibility symbols and delegate. Do not reintroduce business logic into root wrappers.

## Always

- Coordinate via current GitHub issues/PRs and the governance working contract.
- Prefer exact commit/path/hash identities.
- Scientific effect: NONE. Never flip theorem/prize/premise status.
- Runtime dependencies remain zero unless a reviewed architecture change says otherwise.
- Do not import `universal_law_control` or `universal_law_math`.
- Keep public/private boundaries fail-closed; never publish sandbox material.
- Run both package and legacy compatibility tests before integration.
- A source archive dry run is not publication; no release while the repository lacks an existing license file.

## Verify in the full checkout

```bash
python -B -S -m unittest -v test_research_query.py test_catalog_entry_helper.py test_verify_portable_stubs.py
python -B -S -m unittest discover -s tests -p 'test_*.py' -v
```

The commands above retain all checkout controls, including the source builder,
dated peer-handoff fixtures and the local pip installation test. Full discovery
requires Git, checkout fixture inputs and an existing supported build backend.
For an offline install-control run, verify pip, setuptools>=77.0.3 and wheel
first, and set PIP_NO_INDEX=1 and PIP_DISABLE_PIP_VERSION_CHECK=1. The existing
test uses --no-deps, --no-build-isolation and a temporary local target; do not
retrieve missing build tools or infer an installed-console result from it.

## Verify an extracted custom package archive

Extract outside the checkout. Python>=3.11 and local symlink creation are needed.
The archive contains 21 payloads (11 public root members, five package files and
five test modules) plus SOURCE_MANIFEST.json and BUILD_INFO.json.

```bash
env -u PYTHONPATH -u PYTHONHOME -u PYTHONOPTIMIZE QUERY_STUB_VERIFY=1 python -B -S research_query.py --help
env -u PYTHONPATH -u PYTHONHOME -u PYTHONOPTIMIZE QUERY_STUB_VERIFY=1 python -B -S -m unittest discover -s tests -p 'test_*.py' -v
```

This offline subset is exactly test_catalog, test_catalog_entry, test_cli,
test_stub_verify and test_wrapper_parity: 15 fixture-based methods. Repeat with
-B -O -S for the optimized outer runner; existing test children retain their
own normal -B -S commands. Positive verification uses QUERY_STUB_VERIFY=1;
the deliberate skip fixture and synthetic verified keys are not live coverage.

Source-builder, dated peer and installation tests, legacy root tests, Git and
portable inputs remain checkout-only. The builder's regression checks exact
members/hashes, extracted origins and omissions; an absent __init__.py fails
membership/package-root checks even though namespace submodule imports can work.
A supplied catalog/workspace, installation, and real portable fetch/tip coverage
are separate capabilities. Wrapper presence alone establishes none of them.
The builder's release_eligible is LICENSE presence after its guards, not test
success, release permission or scientific authority. The custom archive and
setuptools source distributions have separate membership contracts.

## Never

- Duplicate scientific-status registers here.
- Treat catalog lookup as acceptance.
- Ask Dylan for repeated approval of already authorized architecture work.
- Change wrapper behavior without parity tests.
