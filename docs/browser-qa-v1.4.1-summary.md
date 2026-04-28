# Browser QA — CivicRecords AI v1.4.1

Date: 2026-04-28

Target: `docs/index.html`

## Evidence

- Desktop screenshot: `docs/browser-qa-v1.4.1-desktop.png` (1440x1200, 564232 bytes)
- Mobile screenshot: `docs/browser-qa-v1.4.1-mobile.png` (390x1100, 178053 bytes)

## Checks

- Current release badge shows `v1.4.1`.
- Linux/macOS install script links point to `https://raw.githubusercontent.com/CivicSuite/civicrecords-ai/v1.4.1/install.sh`.
- Windows installer links point to `https://github.com/CivicSuite/civicrecords-ai/releases/download/v1.4.1/CivicRecordsAI-1.4.1-Setup.exe`.
- Desktop and mobile screenshots render without obvious clipping or missing primary calls to action.

## Console

The landing page is static HTML/CSS. Headless Microsoft Edge generated both screenshots successfully; no page JavaScript console collection was required for this static page.
