# Agent entry — `query-`

Read-only lookup and local byte verification against the meta-framework catalog.

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

## Verify

```bash
python -B -S -m unittest -v test_research_query.py test_catalog_entry_helper.py test_verify_portable_stubs.py
python -B -S -m unittest discover -s tests -p 'test_*.py' -v
```

## Never

- Duplicate scientific-status registers here.
- Treat catalog lookup as acceptance.
- Ask Dylan for repeated approval of already authorized architecture work.
- Change wrapper behavior without parity tests.
