[![Universal Law — mathematics, evidence and verification](https://raw.githubusercontent.com/d6g8k5htny-coder/main/6168a1efc42dc6eabae3ce91623d6e16d3c92fd6/docs/site/brand/banner.svg)](https://d6g8k5htny-coder.github.io/main/site/)

# Query — exact-source research lookup

Look up exactly where a published Universal Law research artifact lives and verify that local bytes match its pinned source identity. The package is standard-library at runtime, read-only, and has **no scientific-status authority**: it reports commit/path/hash/scope metadata from the curated `meta-framework` catalog and does not determine theorem acceptance.

[Citation](CITATION.cff) · [Help](SUPPORT.md) · [Security](SECURITY.md) · [MIT license](LICENSE)

## Try it from source

You need Git and Python 3.11 or newer. This first check needs no catalog,
installation, or private Drive access; after cloning, it runs offline.

```bash
git clone https://github.com/d6g8k5htny-coder/query-.git
cd query-
python -B -S research_query.py --help
```

For a real lookup, clone the public catalog as a sibling checkout:

```bash
git clone https://github.com/d6g8k5htny-coder/meta-framework.git ../meta-framework
python -B -S research_query.py --registry ../meta-framework/registry.json --key side24-coefficient
```

The catalog supplies the pinned source identities. Record the catalog commit
along with the query commit when reproducing a lookup.

## Installation is a separate capability

To install the command in your Python environment from this checkout:

```bash
python -m pip install --no-deps .
universal-law-query --registry ../meta-framework/registry.json --key side24-coefficient
```

The package has no runtime dependencies. Installation may download build tools;
the setuptools build backend requires version 77.0.3 or newer for SPDX license
metadata. Offline installation with `--no-build-isolation` requires those build
tools to be installed already. These commands install local source, not a
claimed PyPI release.

The canonical implementation lives in `src/universal_law_query/`. Historical root commands — `research_query.py`, `catalog_entry_helper.py`, and `verify_portable_stubs.py` — remain thin compatibility wrappers so existing `python -B -S` workflows continue to work.

The wrapper and package CLI are parity-tested for stdout, stderr, exit status, lookup, verification and refusal paths.

## Pinned identities and non-theorem boundary

- Portable pin sets are in:
  - `portable/CANDIDATE_DOWNSTREAM_GATE_STUBS.json`
  - `portable/CANDIDATE_PUBLIC_REPLAY_STUBS.json`
  - `portable/RN_FIXED_REMOTE_REPLAY_STUB.json`
- `verify_portable_stubs.py` enforces exact byte identity (`commit`, `path`, `bytes`, `sha256`) for public artifacts.
- `--check-math-tip` reports TIP_DRIFT when current `Math-` default-tip bytes diverge from the pinned downstream-gate stubs. It compares bytes, not tip commit equality: documentation-only Math commits can leave this check green while the recorded `math_tip` needs an identity refresh.
- Scientific effect is **NONE**: this repository does not change theorem status, prize disposition, `lemma_closed`, or acceptance registers.

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

## Full-checkout engineering controls

```bash
python -B -S -m unittest -v test_research_query.py test_catalog_entry_helper.py test_verify_portable_stubs.py
python -B -S -m unittest discover -s tests -p 'test_*.py' -v
python -B -S verify_portable_stubs.py
python -B -S verify_portable_stubs.py --check-math-tip
```

These commands are for the full Git checkout. The older root tests remain as
compatibility controls; package tests are the canonical implementation tests.
Full discovery also runs the source-builder, dated peer-handoff and installation
controls. It needs Git, the tracked checkout inputs, portable fixture JSON and
already available pip/build tools; it is not the archive's stdlib-only subset.
The real portable verification commands additionally need public network access.

For an offline run of the existing installation control, first verify that pip,
setuptools>=77.0.3 and wheel are already available, then set PIP_NO_INDEX=1 and
PIP_DISABLE_PIP_VERSION_CHECK=1 for the checkout test commands. The control uses
--no-deps, --no-build-isolation and a temporary local target. Missing build tools
are a missing capability, not permission to download them during an offline run.

## Extracted package archive: offline help and unit subset

The custom source archive supports Python 3.11+ help and exactly five offline
fixture-test modules (15 methods). Extract it outside the source checkout and
run from that extracted directory; local symlink creation is needed by one
refusal fixture. No catalog, installation or network is needed for these checks:

```bash
env -u PYTHONPATH -u PYTHONHOME -u PYTHONOPTIMIZE QUERY_STUB_VERIFY=1 python -B -S research_query.py --help
env -u PYTHONPATH -u PYTHONHOME -u PYTHONOPTIMIZE QUERY_STUB_VERIFY=1 python -B -S -m unittest discover -s tests -p 'test_*.py' -v
```

Repeat with `-B -O -S` for an optimized outer runner. The selected tests keep
their own normal `-B -S` child commands; an optimized outer run is not an
optimized-child claim. QUERY_STUB_VERIFY=1 makes the positive mocked-fetch
fixture run; the suite separately tests the deliberate skip switch. Synthetic
`verified` results and the skip message are not live portable coverage.

The explicit payload contains 11 public root files, the five package files
and only these five test modules:
`test_catalog.py`, `test_catalog_entry.py`, `test_cli.py`, `test_stub_verify.py`
and `test_wrapper_parity.py`. Together they are 21 payloads, plus the generated
SOURCE_MANIFEST.json and BUILD_INFO.json.

The archive intentionally excludes the source builder, its tests, dated
peer-handoff tests/data, installation tests, root compatibility tests and
portable candidates. Do not use archive-wide discovery as evidence that the
full checkout suite passed. The checkout-side archive regression verifies exact
members and hashes, extracted product origins, source-path isolation and
required-member omissions, including the initializer's package-root contract.

Lookup with `--registry` needs a separately supplied public catalog; local byte
verification also needs the catalog's corresponding workspace files. Record
those inputs' identities separately. A portable-verifier wrapper without its
candidate inputs does not establish coverage, even if it reports an empty
verified list. Installation and installed-console verification remain separate
from these offline source checks.

## Candidate public catalog stubs

`catalog_entry_helper.py` remains a compatibility wrapper for `universal_law_query.catalog_entry`. It refuses sandbox repositories, symlinks, unsafe paths and mutable commits. A printed stub is not catalog integration or theorem acceptance.

Portable candidates remain under `portable/`; the verifier checks exact public bytes at declared commits. Private `sandbox` material is never fetched or published.

## Source publication dry run

`scripts/build_source_release.py` is a checkout-only API: it needs a clean Git
HEAD/index and tracked selected inputs, and its output must be outside the
checkout. It builds the package archive described above with normalized metadata
and embedded `SOURCE_MANIFEST.json` / `BUILD_INFO.json`, preserving tracked-only
selection and public-file/symlink guards.

In both modes the builder reads the repository at the checkout it is given. Its
Git commands run without the inherited variables that select another repository,
work tree, index or object store (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`
and the others listed in the script), so such a variable cannot put another
repository's commit into the manifest. The recorded `commit` is the commit that
HEAD resolves to: a HEAD that names an annotated tag records the tagged commit,
and a HEAD that leads to no commit is refused.

For the complete package archive, call
`build_source_archive(repo, output, epoch, strict_members=True)`. Strict mode
compares the selected names with the curated lists and refuses before anything
is written when a required member is missing, or when a selected path is not a
listed name (for example a directory standing where a listed file should be).
LICENSE alone is optional: without it the archive holds 20 payloads and
`release_eligible` is false. Strict mode also requires HEAD's own tree to hold
the same members as regular files, and every selected file to hold exactly that
blob's bytes, read with replacement refs ignored. Index hints, checkout
normalization, a replaced commit or a symlink entry checked out as a plain file
therefore cannot place other content under the recorded commit. The default
call makes none of these checks; it stays permissive so that partial fixtures
keep working, and it will write a smaller archive without an error.

The repository uses the MIT license in [`LICENSE`](LICENSE). The current
`release_eligible` field means that LICENSE is present in the selected payload
after the builder's guards; it does not mean extracted tests passed or authorize
a release. A successful dry run is neither publication nor theorem acceptance.
Standard setuptools source distributions are a separate producer: this custom
allowlist does not define their membership or establish an offline-install or
installed-console result.

Cross-repository integration controls remain in `trial`. The curated public artifact routing authority remains `meta-framework/registry.json`.
