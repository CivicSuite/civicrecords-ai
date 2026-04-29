# Browser QA - CivicRecords AI v1.4.2

Date: 2026-04-29

Target: `docs/index.html`

## Evidence

- Desktop screenshot: `docs/browser-qa-v1.4.2-desktop.png` (1440x1200, 564355 bytes)
- Mobile screenshot: `docs/browser-qa-v1.4.2-mobile.png` (390x1100, 178099 bytes)

## Checks

- Current release badge shows `v1.4.2`.
- Linux/macOS install script links point to `https://raw.githubusercontent.com/CivicSuite/civicrecords-ai/v1.4.2/install.sh`.
- Windows installer links point to `https://github.com/CivicSuite/civicrecords-ai/releases/download/v1.4.2/CivicRecordsAI-1.4.2-Setup.exe`.
- Desktop and mobile screenshots render without obvious clipping or missing primary calls to action.

## Console

The landing page is static HTML/CSS. Headless Microsoft Edge generated both screenshots successfully; no page JavaScript console collection was required for this static page.
