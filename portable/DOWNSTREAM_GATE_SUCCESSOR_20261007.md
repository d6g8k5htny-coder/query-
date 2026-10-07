# Downstream-gate source identity successor — 7 October 2026

The [active candidate bundle](CANDIDATE_DOWNSTREAM_GATE_STUBS.json) records
the same seven public key/path associations at the single Math- snapshot
`7d2f62500ad6effba2bbdf6f3b89b0826408dc4a`. Six files are byte-identical to
the preceding snapshot; only `run_validation.py` changed. This is reviewed
source-identity maintenance. Scientific effect: **NONE**.

## Preserved history and exact source identity

The [preceding bundle](history/DOWNSTREAM_GATE_STUBS_de54d1da.json) is the
complete, unchanged active bundle from Query commit
`aeffebc0ab984ff218b6f07d6f2a999ef4c6ca96`: 4,640 bytes, SHA-256
`3484254f34efe57820b19a9b80e533b2fb0ce3c8b4d5a34c2ab55f6bbbfe8db5`,
Git blob `b454e4fbbf81487ac1419186a6c5f6a7df06f55c`. Its recorded Math
snapshot is `de54d1da2f6cdde59df3c34bb50ecd85c25ca333`; all seven retained
identities are historically correct. The older
[d6628da bundle](history/DOWNSTREAM_GATE_STUBS_d6628da.json) and
[30 September note](DOWNSTREAM_GATE_SUCCESSOR_20260930.md) remain unchanged.
Neither history bundle enters the nonrecursive active candidate-file glob.

All paths below are under `frontiers/downstream_gate_20260925/` in public
`d6g8k5htny-coder/Math-`. Complete immutable native source bodies at both
snapshots were independently decoded and checked by length, SHA-256 and Git
blob identity. Their seven entries agree with each snapshot's upstream
manifest. The current
[SOURCE_FILES.json](https://github.com/d6g8k5htny-coder/Math-/blob/7d2f62500ad6effba2bbdf6f3b89b0826408dc4a/frontiers/downstream_gate_20260925/SOURCE_FILES.json)
is blob `c42e11304ae6e605343b365f80a127646840d290`.

| File | Current bytes | SHA-256 | Change from retained snapshot |
|---|---:|---|---|
| README.md | 4025 | `13fc1accebebd6017f34b0e5473bf6338f2604948c25a002051b5f0620fc327a` | None |
| SCOPE.md | 2218 | `c7b5bb0ec34f53395b96ae24edceb3b5b0a3451caf7df6205b924d40e9e9fd84` | None |
| hard_gate.py | 26735 | `a78f3e25f3b0cfe113e618a4c31a7a25d7f22af638c46dec1ecba221fa333ac8` | None |
| test_hard_gate.py | 23161 | `c444e6c347da680aff5bef7f43900e45d52a0cc45081fb7b4def45266d97aac1` | None |
| RESULTS.json | 7095 | `0b95624e08e3eff7ca386a68534960b89ef63b10312ad5120159c0e29961264a` | None |
| run_validation.py | 10454 | `ec1d3315b0c21f4608ab7b824f45d7d6e1041555f62e77feeec2bacaa8e5a9f5` | Reviewed timeout-evidence repair |
| GRAPH.json | 38753 | `8822e9618678321a342d69cd0b8ae6552de1b5d578c331de5072b2892ee9dd09` | None |

The preceding runner was 7,517 bytes, SHA-256
`276e69c2b29e012c386db615ed64e24badf3726a9f122fd9d77776a9c4f00711`,
blob `58c2b5e855272d11df627d472fd09274ff14fcc6`. The successor runner is
blob `fcf6480529d6b521628e2635e7c1e271ecfa39a4`.

## Actual changed semantics and corrected review

[Math #263](https://github.com/d6g8k5htny-coder/Math-/pull/263), authored by
OpenAI/Codex `preserve_validation_timeout_evidence`, repaired a real failure
path: `execute()` previously let `TimeoutExpired` escape before preserving
partial output. It now attempts to save raw stdout/stderr bytes, including
invalid or incomplete UTF-8, and per-invocation timeout metadata. Optional
clock, cwd and persistence diagnostics do not replace the original timeout.
Unavailable, nonfinite or negative elapsed time is null with an explanation;
the supplied cwd is retained without failure-path filesystem resolution.
The same timeout is re-raised, including when the final REPORT write fails.

A timeout still cannot count as successful mutant rejection, complete a mode
or continue to later commands. The 30-second `execute()` timeout, 71-test /
24-mutant contract and completed-command acceptance checks are unchanged.
Static comparison here confirms the expected-test constant, mutant mapping
and complete four-statement acceptance tail are unchanged. The separate
15-second checker subprocess remains outside `execute()`; this repair is not
an overall deadline or universal timeout-evidence facility. Timing remains
best-effort wrapper elapsed time, potentially including evidence writes,
and supported timeout streams remain bytes or None.

The original
[AMEND 5403519405](https://github.com/d6g8k5htny-coder/Math-/pull/263#pullrequestreview-5403519405)
on `cdaaf62433430757e3899948b2d59bde6471df76` found clock/cwd failure masking
and nonfinite JSON. Its failed candidate and original failure evidence remain
history. The corrected
[PASS 5403547268](https://github.com/d6g8k5htny-coder/Math-/pull/263#pullrequestreview-5403547268)
covers exact head `20acca8030672a474f19ae9cd3de72736ac30ff1`, tree
`95d0d4f3958505a1849d6b8d79dc9282dbf1eedb`, against refreshed base
`bbe85e270f2c8b747f2d5d9477c86e86e323fe15`, and explicitly binds the current
10,454-byte runner. This was a separate nonauthor OpenAI/Codex engineering
reviewer, source-exposed and same provider/account: organizational-independence
credit **0**. Its 15 author, 15 retained reviewer and six additional reviewer
controls passed in both modes. Those are attributed historical executions,
not tests freshly rerun for this Query identity update. Its master receipt
inspection was not a second master execution or mathematical review.

## Landing and reused execution evidence

The reviewed runner is byte-identical at the reviewed head, landed commit
`af43e809184699007c230db1da94e94147776634` and the recorded current snapshot.
Math #263 merged on 4 October 2026 at 00:11:13 UTC. Native Git objects bind
both the PR-tested merge `d55f96f5fcf5b5888ebc887000f428351c14111b` and the
landed merge to the reviewed tree above and ordered parents
`bbe85e270f2c8b747f2d5d9477c86e86e323fe15`,
`20acca8030672a474f19ae9cd3de72736ac30ff1`.

The existing [PR run 37163440777](https://github.com/d6g8k5htny-coder/Math-/actions/runs/37163440777)
and [landed push run 37164160146](https://github.com/d6g8k5htny-coder/Math-/actions/runs/37164160146)
are completed SUCCESS. The source-bound log reconciliation in
[BQ47](https://github.com/d6g8k5htny-coder/main/issues/275#issuecomment-6037891570)
identifies replay jobs 111321457416 / 111323551093 and aggregate jobs
111321942554 / 111324054476, with actual checkouts at the tested/landed merges
respectively. It records both 71-test/24-mutant modes, `passed=true`,
`sources_unchanged=true`, the exact current runner digest,
`promotion_permission=false` and `scientific_effect=NONE`.
These original receipts are reused with attribution. No new local Math
master/proof replay, whole-current-tree Math execution, Lean execution or
theorem acceptance is claimed by this update.

## Query verification and scope limits

The original [Query run 37617405288](https://github.com/d6g8k5htny-coder/query-/actions/runs/37617405288)
correctly verified ten immutable pins and then refused
`TIP_DRIFT downstream-hard-gate-replay`. Its failure is preserved, not waived
or relabelled transient. Before these edits, bounded offline calls to the
unchanged Query verifier reproduced that exact refusal using authenticated
current runner bytes while all ten historical immutable pins passed, in
normal and optimized Python modes. The fixture's current-byte supplier is
bound to the named immutable snapshot; it is not a fresh live HTTP tip check.

The existing hosted workflow still must pass both pinned verification and
`--check-math-tip` on the actual new candidate/tested merge. That latter
command performs sequential floating `main` fetches; its reported
`math_tip_recorded` is the bundle's pin, not an observed atomic upstream
commit. A successful floating comparison does not prove an atomic seven-file
snapshot. Later genuine drift requires source/review reconciliation before
another successor, rather than blind rehashing or weakening the gate.

The active bundle retains seven unique keys and the complete active discovery
remains ten unique keys. All scopes, public visibility and repository
associations, `scientific_status_authority=false`, and historical
`aligned_to_meta_pr` / `aligned_to_meta_head` provenance are preserved. The
latter fields do not assert live catalog integration. PEER_HANDOFF, the
other replay bundles, verifier, tests, workflow, scientific flags and
Cursor-specific owner-stop records are unchanged. No stopped process is
resumed and no scientific or catalog authority is acquired.

This separate three-file successor requires nonauthor review and guarded
integration. Query #24's four-file archive candidate is a separate scope:
only after this successor lands may its authorized integrator refresh it,
retain its reviewed source blobs and rerun applicable checks. Because its
generated BUILD_INFO and SOURCE_MANIFEST embed HEAD, that refreshed candidate
needs recomputed archive/manifest identities; the older frozen hashes remain
historical. No archive/package publication is authorized by this note.
