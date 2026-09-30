# Downstream-gate source identity successor — 30 September 2026

The [active candidate bundle](CANDIDATE_DOWNSTREAM_GATE_STUBS.json) now records
seven exact public files at Math- commit
`de54d1da2f6cdde59df3c34bb50ecd85c25ca333`. Six differ from the previous
snapshot; `SCOPE.md` is byte-identical. This updates lookup identities only.

The [previous bundle](history/DOWNSTREAM_GATE_STUBS_d6628da.json) is preserved
unchanged: 4,623 bytes, SHA256
`4046357b30c56e911a8aea14515611201d4dbe3f7b9f16b99b61d4e10fccf828`,
originally at query- commit `a9f19e04377c5d95f4d8ea2d22bd6bc128ba5ef6`.
Its Math- source was `d6628da09384728992dcbe6e921cc28ba85aebb0`.
The history subdirectory is outside the active candidate-file discovery glob.

## Why the bytes changed

- [Math #126](https://github.com/d6g8k5htny-coder/Math-/pull/126), merged at
  `82247833b5dd58e04291d55353b52938d73ec614`, bound the D1 reconciliation's
  component sources into the graph and reverse-impact checks. Its
  [final technical review](https://github.com/d6g8k5htny-coder/Math-/pull/126#pullrequestreview-5346076059)
  records the source-binding repair and 71-test gate. This accounts for the
  README and replay-runner changes, plus graph, result and test changes.
- [Math #151](https://github.com/d6g8k5htny-coder/Math-/pull/151), merged at
  `ec6db8c5ccc47d2aaabd827cbe6d70d44b2f97d2`, integrated the scoped D5 graph
  update, corrected generated reporting, and repaired the witness note. Its
  [successor integration review](https://github.com/d6g8k5htny-coder/Math-/pull/151#pullrequestreview-5359927297)
  retains the existing analytic boundaries. This accounts for the checker,
  graph, result and test changes.

The seven source identities were compared with pinned public bytes and the
upstream `SOURCE_FILES.json`. Normal and optimized checker output matched the
stored result, retaining `lemma_closed: false` and `scientific_effect: NONE`.
The original query tip check correctly refused six mismatches; the successor
matches all seven source files. This is source verification, not a new proof
review or scientific-status transition.

The bundle's `aligned_to_meta_pr` and `aligned_to_meta_head` remain historical
provenance. They do **not** assert that this successor is integrated into the
live catalog. `PEER_HANDOFF.json`, the 28 September offer and the other replay
pin files are unchanged. No stopped background process is resumed.

To check the recorded public bytes and compare them with the current Math-
default branch:

```sh
python -B -S verify_portable_stubs.py
python -B -S verify_portable_stubs.py --check-math-tip
```

Later source changes may correctly trigger drift again. Check their actual
scope and review records before producing another identity successor.
