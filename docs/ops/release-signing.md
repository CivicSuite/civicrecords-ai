# Release Signing and Provenance

CivicRecords AI consumes the canonical CivicSuite release-provenance gate from
`civiccore.release_provenance`. The local `scripts/verify-release-provenance.py`
wrapper exists only so repo workflows have a stable command.

GitHub release pages can show a "Verified" badge for the target commit even
when the release tag itself is lightweight or unsigned. Treat that badge as a
commit signal only. Under the strengthened model, the Git tag is a release
pointer and the trust artifact is the Sigstore-signed `release-attestation.json`
plus `release-attestation.json.bundle`.

The active release workflow now runs CivicCore's adversarial provenance fixtures
before any build, builds the unsigned Windows installer, writes a checksum,
generates a schema-version-1 release attestation, signs it with GitHub Actions
OIDC via cosign, and verifies the attestation before the GitHub Release is
published. Existing releases are not modified by this wiring.

## Verification Shape

For a post-baseline release, auditors verify the release with the exact repo and
tag identity:

```bash
cosign verify-blob release-attestation.json \
  --bundle release-attestation.json.bundle \
  --certificate-identity "https://github.com/CivicSuite/civicrecords-ai/.github/workflows/release.yml@refs/tags/<tag>" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

sha256sum -c CivicRecordsAI-<version>-Setup.exe.sha256
python scripts/verify-release-provenance.py <tag> \
  --repo CivicSuite/civicrecords-ai \
  --attestation release-attestation.json \
  --bundle release-attestation.json.bundle \
  --artifacts-dir .
```

## v1.4.10 CO-4 Ledger Statement

Historical pre-gate artifact: `v1.4.10`

Defect an outside auditor can verify:

- GitHub tag ref `refs/tags/v1.4.10` points directly at commit
  `d50b9ee75f5e0ce29fddfb22e5e53c4943c041b0`.
- The target commit is GitHub-verified and uses the GitHub web-flow identity.
- The release tag is lightweight, so there is no verified annotated tag object.
- Therefore v1.4.10 fails the strengthened release provenance bar.
- CO-4 records this release as `pre_gate_no_attestation_do_not_promote` in
  [`docs/ops/tier1-retrofit-ledger.md`](tier1-retrofit-ledger.md). No public
  release notes, tags, or assets were changed by that decision.

Reproducer:

```bash
python scripts/verify-release-provenance.py v1.4.10 --repo CivicSuite/civicrecords-ai
```

Expected output:

```text
FAIL: Live release verification requires --attestation and --bundle under the Sigstore attestation provenance model.
```

Do not delete or recreate this release, edit its release notes, attach retrofit
attestation assets, mirror it, or promote it as an attested provenance baseline
without a future explicit release-class authorization and a new ledger entry.
