## About this release

CivicRecords AI is an open-source, locally-hosted AI system for municipal open-records request processing. Every deployment is a sovereign instance owned by the city — no cloud, no telemetry, no outbound data transfer.

**Windows installer is UNSIGNED by design.** On first run, Windows SmartScreen will show "Windows protected your PC — Unknown publisher." To proceed: click **More info** → **Run anyway**, then confirm UAC. See [installer/windows/README.md](../blob/master/installer/windows/README.md) for the full remediation walkthrough.

## Release provenance

Post-baseline releases include `release-attestation.json` and
`release-attestation.json.bundle`. The Git tag is a release pointer; the
Sigstore-signed attestation is the trust artifact. Verify the attestation with
the exact `CivicSuite/civicrecords-ai` workflow identity printed in the release
notes and then verify the installer checksum sidecar.

## Downloads

- **Windows double-click installer:** `CivicRecordsAI-<version>-Setup.exe` (bundled with `.sha256` checksum sidecar for `Get-FileHash` verification).
- **Linux / macOS guided-script install:** clone the repo at this tag and run `./install.sh` — see [README.md](../blob/master/README.md) and [USER-MANUAL.md](../blob/master/USER-MANUAL.md) for prerequisites and a step-by-step walkthrough.

Cross-platform native installer parity is explicit follow-on work, not shipped in this release.

## Docs

- [README](../blob/master/README.md) · [USER-MANUAL](../blob/master/USER-MANUAL.md) · [Canonical spec](../blob/master/docs/UNIFIED-SPEC.md) · [CHANGELOG](../blob/master/CHANGELOG.md)

---

## What's in this release
