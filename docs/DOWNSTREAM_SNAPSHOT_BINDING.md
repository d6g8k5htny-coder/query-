# Downstream snapshot identity

The active `portable/CANDIDATE_DOWNSTREAM_GATE_STUBS.json` describes one recorded Math snapshot. Its `math_tip` must be a lowercase 40-hex commit string, and every artifact whose `repository` is `Math-` must use that exact `commit`. Byte equality at a different commit does not satisfy this declaration.

The canonical verifier preflights the whole downstream bundle before candidate rows are returned or deduplicated, and before the direct tip-check path performs any remote fetch. Refusals identify `math_tip`; they are distinct from `TIP_DRIFT`, which reports changed live bytes.

The rule is scoped to this named bundle. Other candidate bundles and the standalone RN stub retain their existing per-row commit identities. Non-Math rows retain their existing identity rules. A coherent historical snapshot remains a valid recorded identity; neither the current Math commit nor a minimum date is hardcoded. The existing empty-bundle behavior is preserved when its declared tip is valid. Frozen history files are outside active discovery.

## Verification and limits

The checkout-only regression module `tests/test_stub_verify_snapshot.py` exercises both public entry paths, a second-row mismatch before any fetch, duplicate-key hiding, malformed tip declarations independent of row comparisons, and positive compatibility cases. Its synthetic references establish string/association behavior, not real commit existence. Existing wrong-byte and wrong-length controls remain separate.

Test-first evidence: tests-only head `5b9eae7b7ad2cd1cb45f093bd9f55087102b1a8e`, hosted run [38074388202](https://github.com/d6g8k5htny-coder/query-/actions/runs/38074388202), tested merge `b07128dfc9921d02505700616dc3fb94dcc8dcca`: 38 legacy tests passed; package discovery ran 74 methods and had 50 expected missing-refusal assertion failures, with no test errors. The production fix follows that observed RED. Current final verification and nonauthor disposition belong to [PR37](https://github.com/d6g8k5htny-coder/query-/pull/37).

Run the existing complete legacy and package commands in AGENTS.md, then both portable verifier commands in the existing hosted workflow. The custom source archive retains its five-module/15-method subset; this new checkout regression module does not change archive membership. No runtime dependency is added.

Pinned-byte verification authenticates bytes at declared commits. The optional tip check still compares sequential reads of floating `main` against those byte identities; it does not authenticate an observed atomic live snapshot. Direct tip checking alone does not establish the declared commit's existence. Internal injected loader seams intentionally bypass on-disk discovery and are not evidence that a real bundle was validated.

Scientific effect is NONE. Snapshot consistency, byte identity, hosted CI and a registered handoff are engineering evidence, not catalog integration, theorem acceptance or proof completion.

Authorship: OpenAI/Codex root01a0bbb5, delegated for Dylan Roy; source-exposed, organizational-independence credit0. No personal human review is claimed.
