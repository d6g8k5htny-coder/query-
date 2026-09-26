# Query — exact-source research lookup

The canonical implementation now lives in `src/universal_law_query/`. The historical root commands — `research_query.py`, `catalog_entry_helper.py`, and `verify_portable_stubs.py` — remain thin compatibility wrappers so existing `python -B -S` workflows continue to work.

The package is standard-library at runtime, read-only, and has **no scientific-status authority**. It queries the curated catalog in `meta-framework`, reports exact commit/path/hash/scope metadata, and optionally verifies local bytes. It does not determine theorem acceptance.

## Source package

```bash
python -m pip install --no-deps --no-build-isolation .
universal-law-query --registry ../meta-framework/registry.json --key side24-coefficient
```

From an uninstalled checkout, the compatibility command is still:

```bash
python -B -S research_query.py --registry ../meta-framework/registry.json --key side24-coefficient
```

The wrapper and package CLI are parity-tested for stdout, stderr, exit status, lookup, verification and refusal paths.

## Topic → exact lookup key

| Topic | Exact lookup key |
|---|---|
| SIDE24 coefficient | `side24-coefficient` |
| Quantitative lifetime density | `lifetime-remainder` |
| RN probability-to-count interface | `rn-count-interface` |
| RN fixed-remote height-window estimate | `rn-fixed-remote-window` |
| P15 original-coordinate family | `p15-realized-covers` |
| P15 unrestricted price counterexample | `p15-price-boundary` |
| P15 restricted transformed-price successor | `p15-price-budget` |
| P15 full probability range and sharp factor | `p15-full-price` |

Unknown keys are refused rather than guessed. Exact-byte verification rejects path traversal, symlink payloads, mutable refs and private catalog artifacts.

## Local engineering controls

```bash
python -B -S -m unittest -v test_research_query.py test_catalog_entry_helper.py test_verify_portable_stubs.py
python -B -S -m unittest discover -s tests -p 'test_*.py' -v
python -B -S verify_portable_stubs.py
python -B -S verify_portable_stubs.py --check-math-tip
```

The older root tests remain as compatibility controls; package tests are the canonical implementation tests.

## Candidate public catalog stubs

`catalog_entry_helper.py` remains a compatibility wrapper for `universal_law_query.catalog_entry`. It refuses sandbox repositories, symlinks, unsafe paths and mutable commits. A printed stub is not catalog integration or theorem acceptance.

Portable candidates remain under `portable/`; the verifier checks exact public bytes at declared commits. Private `sandbox` material is never fetched or published.

## Source publication dry run

`scripts/build_source_release.py` builds a deterministic package-scoped archive with normalized metadata and embedded `SOURCE_MANIFEST.json` / `BUILD_INFO.json`. The builder refuses dirty trees and outputs inside the repository. Because this repository currently has no `LICENSE` file, the generated manifest records `release_eligible: false`; no public release is authorized by the dry run.

Cross-repository integration controls remain in `trial`. The curated public artifact routing authority remains `meta-framework/registry.json`.
