# Browser QA - CivicRecords AI v1.4.10 docs

Date: 2026-05-03

Scope:
- Rendered `docs/index.html` after updating release/download surfaces from v1.4.9 to v1.4.10.
- Confirmed the landing page source references `v1.4.10`, the v1.4.10 installer/download paths, and preserves the CivicCore v0.22.0 datasource source-list status projection copy.
- Captured desktop and mobile evidence with Chrome headless.

Evidence:
- Desktop screenshot: `docs/screenshots/browser-qa-v1410-docs-desktop.png`
- Mobile screenshot: `docs/screenshots/browser-qa-v1410-docs-mobile.png`

Viewport checks:
- Desktop: `1440x1100`
- Mobile: `390x1200`

Console/page-error check:
- `docs/index.html` has no page script execution path; Chrome headless produced screenshots without JavaScript page errors.
