# Query — exact-source research lookup

`research_query.py` is a standard-library, read-only CLI. It queries the curated catalog in `meta-framework`, reports the exact commit/path/hash and scope, and optionally verifies local payload bytes. It does not access the network, execute retrieved code, edit repositories, determine scientific acceptance or claim the catalog is current.

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

Code, tests, outputs, the full-price replay runner and the selected coefficient Drive replica use the same key stem with `-code`, `-tests`, `-output`, `-replay` or `-drive-replica` suffixes. The public catalog currently holds 22 artifacts; this tool never treats a catalog hit as theorem acceptance.

With sibling checkouts:

```sh
python -B -S research_query.py --registry ../meta-framework/registry.json --key side24-coefficient
python -B -S research_query.py --registry ../meta-framework/registry.json --key rn-fixed-remote-window
python -B -S research_query.py --registry ../meta-framework/registry.json --verify --workspace ..
```

Omit `--key` and `--verify` to list repository roles and available keys. An unknown key is refused rather than guessed. Verification requires the exact listed payloads; a later legitimate edit also fails the old hash and needs a new reviewed catalog entry.

Local engineering controls (no sibling checkout required):

```sh
python -B -S -m unittest -v test_research_query.py
```

The twenty cross-repository federation controls remain in `trial/federation/test_federation.py`.

The tool rejects duplicate keys, malformed identities, mutable refs, path traversal, symlink payloads and entries marked private. The public catalog is manually source-reviewed; these checks do not independently discover actual GitHub visibility or prevent a malicious catalog from lying. Private `sandbox` artifacts are excluded from this route, not copied or fetched.

Main campaign61 and the actual source-linked reviews remain the place for current scientific discussion. This executable tool supersedes the earlier empty-by-design shell; it does not create another claim-status database.
