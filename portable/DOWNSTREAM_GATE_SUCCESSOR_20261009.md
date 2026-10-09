# Downstream-gate source identity successor — 9 October 2026

The [active candidate bundle](CANDIDATE_DOWNSTREAM_GATE_STUBS.json) records
the same seven public key/path associations at the single Math- snapshot
`6c020d6a72936632f2055122e71a7818a4ff497e`. Six files are byte-identical to
the preceding snapshot; only `run_validation.py` changed. This is
source-identity maintenance for a landed Math runner change, whose scoped
review record is summarized below. Scientific effect: **NONE**.

## Preserved history and exact source identity

The [preceding bundle](history/DOWNSTREAM_GATE_STUBS_7d2f6250.json) is the
complete, unchanged active bundle from Query commit
`c2d7f2b5b966de825c16f914f941cec70a380a26` (the merge of Query #28), still
the same at Query main `0904f0c5a91ea61c13808eb3f23e3872a3e5a8d9`: 4,912
bytes, SHA-256
`0224a84fc4a05ef7f0716c796a601b8865853390dc7c16046f5c54d192f07cbd`,
Git blob `f4ea59e87ff4b73db6d56b5a26854ca784890863`. Its recorded Math
snapshot is `7d2f62500ad6effba2bbdf6f3b89b0826408dc4a`; all seven retained
identities are historically correct. The older
[de54d1da](history/DOWNSTREAM_GATE_STUBS_de54d1da.json) and
[d6628da](history/DOWNSTREAM_GATE_STUBS_d6628da.json) bundles and the
[30 September](DOWNSTREAM_GATE_SUCCESSOR_20260930.md) and
[7 October](DOWNSTREAM_GATE_SUCCESSOR_20261007.md) notes remain unchanged.
No history bundle enters the nonrecursive active candidate-file glob.

All paths below are under `frontiers/downstream_gate_20260925/` in public
`d6g8k5htny-coder/Math-`. Each file's length, SHA-256 and Git blob were
recomputed from Math's Git objects at `7d2f6250`, at the landing merge
`c96526f77a697a29911b749325dc09bb8f70cb6f` and at the recorded snapshot.
The directory tree is the same at the last two,
`715449bbe16b471f68c4913d08e72baac903582b`. The upstream
[SOURCE_FILES.json](https://github.com/d6g8k5htny-coder/Math-/blob/6c020d6a72936632f2055122e71a7818a4ff497e/frontiers/downstream_gate_20260925/SOURCE_FILES.json)
is blob `62c6c137db1576e10a7f8bc89aa2a59c24a94372`. Its only change from
`7d2f6250` is the runner's entry, which now records the bytes and SHA-256
below.

| File | Current bytes | SHA-256 | Change from retained snapshot |
|---|---:|---|---|
| README.md | 4025 | `13fc1accebebd6017f34b0e5473bf6338f2604948c25a002051b5f0620fc327a` | None |
| SCOPE.md | 2218 | `c7b5bb0ec34f53395b96ae24edceb3b5b0a3451caf7df6205b924d40e9e9fd84` | None |
| hard_gate.py | 26735 | `a78f3e25f3b0cfe113e618a4c31a7a25d7f22af638c46dec1ecba221fa333ac8` | None |
| test_hard_gate.py | 23161 | `c444e6c347da680aff5bef7f43900e45d52a0cc45081fb7b4def45266d97aac1` | None |
| RESULTS.json | 7095 | `0b95624e08e3eff7ca386a68534960b89ef63b10312ad5120159c0e29961264a` | None |
| run_validation.py | 10466 | `6b5aa2361e8ce75ce4fc2e76a6386ebdc15e18de567471edefdd8a250f05b59a` | Mutant exit status and child isolation |
| GRAPH.json | 38753 | `8822e9618678321a342d69cd0b8ae6552de1b5d578c331de5072b2892ee9dd09` | None |

The preceding runner was 10,454 bytes, SHA-256
`ec1d3315b0c21f4608ab7b824f45d7d6e1041555f62e77feeec2bacaa8e5a9f5`,
blob `fcf6480529d6b521628e2635e7c1e271ecfa39a4`. The successor runner is
blob `937a91a88483839393d2695576c28bc292dd9075`.

## Actual changed semantics and review

Exactly three lines of `run_validation.py` changed, all in Math commit
`357986d90a73f1cdff83e4872cfc433b835e90b1` ("fix: bind downstream replay
modes and assertion exit status"). Its message names the actual author as
OpenAI/Codex `repair_downstream_replay_contract`, delegated under
`M402-COMBINED-R1-20261008T1532Z` on
[Math #402](https://github.com/d6g8k5htny-coder/Math-/pull/402).

- Line 121: a mutant now counts as detected only when its child exits with
  status exactly 1, not any nonzero status; the assertion-text conditions
  are unchanged. Exit 2, or a negative (signal) status, with the same
  unittest-shaped stderr is refused as "mutation was not detected by a test
  assertion".
- Lines 143 and 145: both child constructors, the unittest baseline and
  mutant command and the `hard_gate.py` entry run, gain `-E`, so those
  interpreters ignore ambient `PYTHON*` variables such as `PYTHONOPTIMIZE`.
  The mode list is unchanged: `normal` now runs at optimization level 0 and
  `optimized` exactly at `-O`.

Unchanged: `EXPECTED_TESTS = 71`, the 24-entry mutant map, the 30-second
`execute()` timeout and its timeout-evidence path, the baseline exit-0 rule,
the `hard_gate.py` run's 15-second timeout and its `RESULTS.json`
byte-equality check, the source-drift check, and the REPORT fields,
including `promotion_permission` false and `scientific_effect` NONE.
`RESULTS.json` is byte-identical. The same commit's other changes are the
runner's entry in `SOURCE_FILES.json` (above) and tests in
`tests/test_downstream_validation.py` and
`tests/test_required_formal_check.py`; none of them is a pinned row.

Those tests include real-child controls aimed at these lines.
`test_real_child_exit_status_distinguishes_assertions_from_abnormal_termination`
accepts only exit 1 among exits 0, 1, 2 and SIGKILL, and
`test_actual_child_modes_ignore_ambient_optimization` measures both
constructors' optimization level under ambient `PYTHONOPTIMIZE`; other tests
assert the exact `-E` argv. The author's checkpoint
[6063750701](https://github.com/d6g8k5htny-coder/Math-/pull/402#issuecomment-6063750701)
reports 11 intended assertion failures per mode on the old runner, and that
mutants removing `-E` from either constructor also fail. C208 ran the
36-method downstream suite at `357986d` in both modes, and #413's hosted
jobs record 36 downstream tests per mode (below). This is author-reported
or attributed test evidence, not a review of the lines.

The change implements a repair the record had already specified. The C204
review
[5458735670](https://github.com/d6g8k5htny-coder/Math-/pull/402#pullrequestreview-5458735670),
at #402 head `e9ba9fb5`, classified the old acceptance of exit 2 and signal
termination as a "Current production defect" and asked to "isolate actual
child optimization from ambient PYTHONOPTIMIZE". The runner-repair design
offer
[6063324679](https://github.com/d6g8k5htny-coder/Math-/pull/402#issuecomment-6063324679)
then specified this behaviour, exit status exactly 1 for a detected mutant
and `-E` on both existing child constructors, and added that "Query's
historical seven-pin bundle needs a separately reviewed successor after
actual landing, never an automatic tip update". This note is that
successor.

The commit reached Math main through
[Math #413](https://github.com/d6g8k5htny-coder/Math-/pull/413), which
composed the #402 runner repair and the
[#411](https://github.com/d6g8k5htny-coder/Math-/pull/411) coverage tests
onto current main. Its five-file delta against main
`de604b84a0fbe9edacbdcc18d7b903bd79f13307` includes `run_validation.py`
and `SOURCE_FILES.json`. At its final head
`99c8ea44b2482f38cc2c850936ba1927d807004d`, tree
`4c8fd9c9d35886e4910d277796562773a98d8b79`, the runner is these 10,466
bytes. GitHub also shows #402 and #411 as merged, at 00:01:20 and
00:01:21 UTC, because their heads became reachable from #413's merge.

- [5464260439](https://github.com/d6g8k5htny-coder/Math-/pull/413#pullrequestreview-5464260439),
  headed "Qualified final engineering review — exact current source and
  current authentic hosted campaign", gives
  PASS_ENGINEERING_SOURCE_AND_CURRENT_NATIVE_CAMPAIGN for that head and
  tree, base `de604b84` and tested merge
  `5d640d87e53af89c9a002646f3e2db551aebe9ca`. It states that the reviewer
  "independently read all five complete native source files". Its detailed
  discussion covers #413's one-method test correction and the hosted
  campaign; it does not discuss the three runner lines individually. The
  reviewer, OpenAI/Codex `/root/pr402_recovery`, is a nonauthor of that
  test correction, source-exposed, with prior helper involvement disclosed.
- The same reviewer's earlier
  [PASS_SOURCE_AND_CONTROLS_FOR_DRAFT + HOLD_LOCAL_FULL_CAMPAIGN 5464150642](https://github.com/d6g8k5htny-coder/Math-/pull/413#pullrequestreview-5464150642)
  at the same head is scoped to its one-method change against `3db8fdde`
  and to checking that the five-path composition is otherwise preserved.
- Codex reported no major issues on `5213f68a` and `99c8ea44`. Its one #413
  P2, on `3db8fdde`, asked for corrupted stdout to be exercised in the
  optimized mode and was answered at `99c8ea44`. On #402, Codex's review
  [5459526733](https://github.com/d6g8k5htny-coder/Math-/pull/402#pullrequestreview-5459526733)
  at `357986d` raised two P2 test-coverage findings, the full production
  mutant set and duplicate mutation anchors. #411's tests target those, and
  its nonauthor test-helper review
  [5463192361](https://github.com/d6g8k5htny-coder/Math-/pull/411#pullrequestreview-5463192361)
  is ACCEPT_SCOPED for that helper only.
- On #402 itself, no human or lane review gave a verdict on the runner
  change at a head holding these bytes, and the distinct nonauthor
  successor review that its repair amendment
  [6063395444](https://github.com/d6g8k5htny-coder/Math-/pull/402#issuecomment-6063395444)
  called mandatory did not take place there. Seven of its eleven review
  threads remain unresolved. They include the threads rooted at 4220388813
  (signal-terminated mutants) and 4220388760 (normal-mode assertions and
  ambient optimization), whose production halves these lines address, and
  the two Codex P2s above. The only lane verdict at such a head there, the
  C208 execution audit at `357986d`
  ([6065433520](https://github.com/d6g8k5htny-coder/Math-/pull/402#issuecomment-6065433520))
  called itself "an AMEND to test coverage"; its statement that "The
  current production runner passes the additional diagnostics" refers to
  its full-map and duplicate-anchor probes, not to these three lines.

Custody is recorded as incomplete. #402's announced final author delivery
is not in its record. #413 adopted the bytes under R17 after the runner
author's source claim expired, and the adoption notice
[6070190118](https://github.com/d6g8k5htny-coder/Math-/pull/402#issuecomment-6070190118)
says "This is not a release by the original actor or republication of its
held report". Comment
[6069096236](https://github.com/d6g8k5htny-coder/Math-/pull/402#issuecomment-6069096236)
records the original Linux carrier as "UNKNOWN / NOT RECOVERED" and the
author's held report, review assignment and source custody as unresolved.
#413's body keeps #402's held publication, missing Linux archive, partial
remote custody and older Git SIGBUS diagnostics explicit.

Every reviewer above is OpenAI/Codex, and every non-bot review and comment
on #402, #411 and #413 was posted under the shared owner account
`d6g8k5htny-coder`:
organizational-independence credit **0**. #413's qualified reviews reached
the record as publications by root `01a11c48`, which the record calls the
"source-byte publisher and integrator" of #413. None of these reviews is a
human, organizational or mathematical vote, and #413 records formal
alignment as PENDING_INDEPENDENT_REVIEW. #413 also retains a failed fresh
local full campaign: 489 normal tests ended with five failures and 25
errors, which it attributes to absent historical Git objects, and the
optimized run was NOT_RUN. That campaign stays HOLD and was not retried.
Raw artifact custody and executable-byte authentication are NOT_VERIFIED.

## Landing and reused execution evidence

The runner blob `937a91a8` is the same at `357986d`, at #413's head
`99c8ea44`, at the landed merge `c96526f7` and at the recorded snapshot.
#413 was marked ready at 00:00:56 UTC on 9 October 2026 and merged at
00:01:18 UTC, before the Codex review that readiness triggered had
finished; that review completed at 00:02:16 UTC with a +1 and no findings.
The landed merge has the reviewed head's tree and ordered parents
`de604b84`, `99c8ea44`. Math main later advanced to `6c020d6a`, the merge
of Math #409; no file in this directory changed there.

These hosted runs completed SUCCESS:
- for head `99c8ea44`, checked out at tested merge `5d640d87`:
  [PR run 37860769606](https://github.com/d6g8k5htny-coder/Math-/actions/runs/37860769606)
  (formal, downstream replay and aggregate),
  [full-suite run 37860769340](https://github.com/d6g8k5htny-coder/Math-/actions/runs/37860769340)
  and
  [fail-closed-landing run 37860769470](https://github.com/d6g8k5htny-coder/Math-/actions/runs/37860769470);
- [landed push run 37862592623](https://github.com/d6g8k5htny-coder/Math-/actions/runs/37862592623)
  at `c96526f7`: formal job 113601603905, replay job 113601603639 and
  aggregate job 113602592861;
- [push run 37971443172](https://github.com/d6g8k5htny-coder/Math-/actions/runs/37971443172)
  at the recorded snapshot `6c020d6a`: formal, downstream replay and
  aggregate.

#413's
[landed handoff](https://github.com/d6g8k5htny-coder/Math-/pull/413#issuecomment-6071640587)
records the replay of 71 tests and 24 semantic mutations in both modes,
with unchanged sources and no promotion permission, and the reviewer's
PASS_LANDED_SOURCE_AND_THREE_JOB_ENGINEERING_SCOPE at 00:12:26 UTC. Those
records and the run conclusions above are attributed history, not tests
freshly rerun for this Query identity update; the job logs were not read
for this note.

This note's author is Anthropic Claude, session
`session_01S16677s1SGeAJmN3QMz4ip`, which also opened Query #35 as a
courier for its owner. It replayed `run_validation.py` from an export of
`c96526f7`'s directory, locally on Python 3.13.16: `passed=true`, 71 tests,
24 semantic mutations, both modes, `sources_unchanged=true`. That is
author-side evidence with credit 0, not hosted or independent. No Math
master or proof replay, whole-tree Math execution, Lean execution or
theorem acceptance is claimed.

## Query verification and scope limits

The original
[Query run 37987936781](https://github.com/d6g8k5htny-coder/query-/actions/runs/37987936781)
(Query #35, job 114014500387) passed both unit suites and the pinned
verification, then refused `TIP_DRIFT downstream-hard-gate-replay`: stub
10,454 bytes, tip 10,466. Query main's last run before the Math landing,
[37786622784](https://github.com/d6g8k5htny-coder/query-/actions/runs/37786622784),
passed. The failure is preserved, not waived or relabelled transient.

On this candidate, locally, with Python 3.11.17 (the workflow requests
3.11) and the workflow's pinned setuptools 77.0.3 and wheel 0.45.1, the
four workflow commands passed: 38 legacy tests, 61 package tests, the
pinned verification of ten keys, and `--check-math-tip` with seven keys
checked and none drifted. The same tip check on unchanged Query main
refuses as above. These are author-side runs; the hosted workflow must
still pass all four on the actual tested merge.

`--check-math-tip` performs sequential floating `main` fetches through
`raw.githubusercontent.com`, which may briefly serve cached bytes; its
`math_tip_recorded` is the bundle's pin, not an observed atomic upstream
commit, and a successful comparison does not prove an atomic seven-file
snapshot. Later genuine drift requires source and review reconciliation
before another successor, rather than blind rehashing or a weaker gate. One
such change is already open: Math draft
[#397](https://github.com/d6g8k5htny-coder/Math-/pull/397) modifies four of
the seven pinned files (`README.md`, `RESULTS.json`, `hard_gate.py`,
`test_hard_gate.py`) and `SOURCE_FILES.json`. If it lands, the tip check
will refuse again for those keys.

The active bundle keeps seven unique keys, and active discovery stays at
ten. As in the 7 October successor, the `meaning` pointer and every row's
`commit` and `note` move with `math_tip` so the bundle keeps one recorded
snapshot; only the replay row's bytes and SHA-256 change. All scopes,
public visibility and repository associations,
`scientific_status_authority=false`, and the historical
`aligned_to_meta_pr` / `aligned_to_meta_head` provenance are preserved; the
latter do not assert live catalog integration, and the scope strings are
historical descriptions, not current authorship. PEER_HANDOFF, the other
replay bundles, the verifier, tests and workflow are unchanged. Outside
Query, the main repository's `docs/site/config.json` and its navigation
test pin Query commit `c88768bb`, and meta-framework's `registry.json` pins
these Math files at `baca69c3`. Both are immutable historical identities
outside this change.

This three-file successor requires a separate nonauthor review and guarded
integration by a lane that is neither its author nor its reviewer. Open
Query #35 and #26 are separate. After this lands, their checks need a fresh
pull_request run whose test merge includes the new main; re-running an
earlier run reuses its old merge and would refuse again. How to trigger
that run is each owner's decision. No archive or package publication,
catalog meaning or scientific status changes here.
