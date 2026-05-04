# Release Signing and Provenance

CivicRecords AI consumes the canonical CivicSuite release-provenance gate from
`civiccore.release_provenance`. The local `scripts/verify-release-provenance.py`
wrapper exists only so repo workflows have a stable command.

GitHub release pages can show a "Verified" badge for the target commit even
when the release tag itself is lightweight or unsigned. Treat that badge as a
commit signal only. The strengthened gate verifies the tag ref, tag object,
target commit, committer identity, and release tree before any release assets
are published.

## v1.4.10 Defect Statement

Current public artifact: `v1.4.10`

Defect an outside auditor can verify:

- GitHub tag ref `refs/tags/v1.4.10` points directly at commit
  `d50b9ee75f5e0ce29fddfb22e5e53c4943c041b0`.
- The target commit is GitHub-verified and uses the GitHub web-flow identity.
- The release tag is lightweight, so there is no verified annotated tag object.
- Therefore v1.4.10 fails the strengthened release provenance bar.

Reproducer:

```bash
python scripts/verify-release-provenance.py v1.4.10 --repo CivicSuite/civicrecords-ai
```

Expected output:

```text
FAIL: v1.4.10 is a lightweight tag pointing at commit d50b9ee75f5e0ce29fddfb22e5e53c4943c041b0; create a signed annotated release tag instead.
```

This release is part of the Tier 1 live-surface correction window. Do not delete
or recreate it without explicit chat authorization for that specific release.
