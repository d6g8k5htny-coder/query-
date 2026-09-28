# Proposal: public master workspace (`universal-law-workspace`)

Scientific effect: **NONE**. This proposal is packaging/routing only, not theorem acceptance.

## 1) Repository and branch policy

- In-scope public repos (owner `d6g8k5htny-coder`): `main`, `Math-`, `query-`, `trial`, `governance-`, `meta-framework`, `google-drive`.
- Out of scope unless later approved: private sandbox.
- Default refs in workspace must track each repository default branch tip.
- Named PR branches may be included only as explicit opt-in refs; no blind merge of historical refs.
- If two trees disagree, keep both and record the disagreement in a conflict ledger; do not collapse to one winner.

## 2) Proposed workspace layout

```text
/README.md
/repos/main/              # git submodule (or subtree) of d6g8k5htny-coder/main @ default tip
/repos/Math-/             # git submodule (or subtree) of d6g8k5htny-coder/Math- @ default tip
/repos/query-/            # git submodule (or subtree) of d6g8k5htny-coder/query- @ default tip
/repos/trial/             # git submodule (or subtree) of d6g8k5htny-coder/trial @ default tip
/repos/governance-/       # git submodule (or subtree) of d6g8k5htny-coder/governance- @ default tip
/repos/meta-framework/    # git submodule (or subtree) of d6g8k5htny-coder/meta-framework @ default tip
/repos/google-drive/      # git submodule (or subtree) of d6g8k5htny-coder/google-drive @ default tip
/branches/query-pr13/     # optional named lane: query- PR #13 head
/branches/query-pr14/     # optional named lane: query- PR #14 head
/branches/meta-pr6/       # optional named lane: meta-framework PR #6 head
/branches/google-drive-pr3/ # optional named lane: google-drive PR #3 head
/CONFLICT_LEDGER.json     # required when path/content conflicts exist
/BYTE_IDENTITY_MANIFEST.jsonl
```

Recommendation: use submodules for exact upstream identity preservation; use subtree only when a fully vendored copy is explicitly required.

## 3) Initial curated named branches/PRs

Include only these non-default lanes at workspace bootstrap:

- `query-` PR #13 (`chatgpt/src-migration-20260925`)
- `query-` PR #14 (`copilot/fix-github-actions-job`)
- `meta-framework` PR #6 (`cursor/catalog-drive-parents-5cb8`)
- `google-drive` PR #3 (`cursor/rn-fixed-remote-drive-replica-7827`)

Everything else remains available upstream but excluded from the initial workspace import.

## 4) Conflict ledger contract (fail-closed)

When the same logical artifact exists in multiple repos/branches and differs, record an entry instead of overwriting:

```json
{
  "logical_key": "example-key",
  "left": {"repo":"Math-","ref":"main","path":"...","blob_sha":"...","sha256":"..."},
  "right":{"repo":"main","ref":"main","path":"...","blob_sha":"...","sha256":"..."},
  "resolution":"kept-both",
  "kept_paths":["repos/Math-/...","repos/main/..."],
  "notes":"no winner selected"
}
```

## 5) Byte-identity recording contract

For every copied/vendored file (when not using submodule pointers), record:

- source repository
- source ref/commit
- source path
- source git blob SHA
- SHA256 of bytes in workspace copy

No private tokens, `.env` values, Actions secrets, or private experiment dumps may be copied.
