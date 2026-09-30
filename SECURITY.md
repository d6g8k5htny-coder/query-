# Security reporting

Relevant problems include reading outside the requested workspace, following
symlink payloads, exposing private catalog entries, accepting mutable source
identities where pinned identities are required, or executing catalog content.

If GitHub shows **Report a vulnerability** on this repository's Security tab,
use that private reporting route. Otherwise, open a [public issue](https://github.com/d6g8k5htny-coder/query-/issues/new)
requesting a private contact route, with only a non-sensitive description.
Do not post credentials, private source bytes, or an exploit containing private
paths. A dedicated private inbox and response-time guarantee are not currently
advertised by this project.

Include the affected full commit, Python version, platform, expected boundary,
and a minimal reproducer when it is safe to share. Ordinary installation or
lookup questions belong in [support](SUPPORT.md).

Please reproduce against the current default branch when practical and identify
older affected commits. This project does not advertise a maintained security
release series. Source verification checks identity and scope; it is not a
security audit of the retrieved mathematical artifact.
