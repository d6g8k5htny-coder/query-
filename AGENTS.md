# Agent entry — `query-`

Read-only lookup and local byte verification against the meta-framework catalog.

## Always

- **Coordinate with peer models before each eng action** (meta open PRs, trial `MULTI_AGENT_WAKE_*.json`, [`portable/PEER_HANDOFF.json`](portable/PEER_HANDOFF.json), local Task agents). Do not wait on Dylan for re-approval or next-step answers.
- Coordinate via [`main`](https://github.com/d6g8k5htny-coder/main) campaign work and the [`governance-`](https://github.com/d6g8k5htny-coder/governance-) working contract.
- Prefer exact source identities (commit/path/hash) over mutable labels.
- Scientific effect: **NONE**. Never flip `lemma_closed` / prizes / premises.
- Cross-repo eng tests and Path C live in [`d6g8k5htny-coder/trial`](https://github.com/d6g8k5htny-coder/trial).
- CLI is stdlib-only (`research_query.py`); federation controls live under trial `federation/`.
- Keep `research_query.py` byte-identical to the pinned trial/meta federation hashes unless those pins are updated in the same change set.
- Use `catalog_entry_helper.py` for candidate public identities; do not treat stubs as catalog landings or acceptance.
- Do not race open meta-framework catalog PRs, Math- mesoscopic drafts, or google-drive replica PRs; record decisions in `PEER_HANDOFF.json`.

## Never

- Duplicate scientific-status registers here.
- Publish private `sandbox` material.
- Ask Dylan for re-approval of autonomy already granted.
- Change `research_query.py` casually; meta-framework catalog CI and trial `federation/replay.py` pin its exact bytes.

## Start here

1. This repository’s [README](README.md)
2. [`governance-` working contract](https://github.com/d6g8k5htny-coder/governance-)
3. [`trial` multi-agent access](https://github.com/d6g8k5htny-coder/trial/blob/main/docs/MULTI_AGENT_ACCESS.md) (Cloud Agent env deps live on trial `.cursor/environment.json`)
