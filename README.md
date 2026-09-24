# Query — exact-source research lookup

`research_query.py` is a standard-library, read-only CLI. It queries the curated catalog in `meta-framework`, reports the exact commit/path/hash and scope, and optionally verifies local payload bytes. It does not access the network, execute retrieved code, edit repositories, determine scientific acceptance or claim the catalog is current.

With sibling checkouts:

```sh
python -B -S research_query.py --registry ../meta-framework/registry.json --key side24-coefficient
python -B -S research_query.py --registry ../meta-framework/registry.json --verify --workspace ..
```

Omit `--key` and `--verify` to list repository roles and available keys. An unknown key is refused rather than guessed. Verification requires the exact listed payloads; a later legitimate edit also fails the old hash and needs a new reviewed catalog entry.

The tool rejects duplicate keys, malformed identities, mutable refs, path traversal, symlink payloads and entries marked private. The public catalog is manually source-reviewed; these checks do not independently discover actual GitHub visibility or prevent a malicious catalog from lying. Private `sandbox` artifacts are excluded from this route, not copied or fetched.

Twenty engineering controls are maintained in `trial/federation/test_federation.py`, separate from the mathematical tests in `Math-`. Main campaign61 and the actual source-linked reviews remain the place for current scientific discussion. This executable tool supersedes the earlier empty-by-design shell; it does not create another claim-status database.
