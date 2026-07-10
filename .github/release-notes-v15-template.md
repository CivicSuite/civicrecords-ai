
## Verify release provenance

```bash
cosign verify-blob release-attestation.json \
  --bundle release-attestation.json.bundle \
  --certificate-identity "https://github.com/${REPO}/.github/workflows/release.yml@refs/tags/${TAG}" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

sha256sum -c CivicSunshine-${VERSION}-Setup.exe.sha256
sha256sum -c SHA256SUMS.txt
python scripts/verify-release-provenance.py "${TAG}" \
  --repo "${REPO}" \
  --attestation release-attestation.json \
  --bundle release-attestation.json.bundle \
  --artifacts-dir .
```

## Cleanroom rehearsal

Cleanroom rehearsal: PASSED in workflow run ${WORKFLOW_RUN_ID}.
Verified clean install of ${WHEEL_URL} from cold caches at ${CLEANROOM_TIMESTAMP}.
