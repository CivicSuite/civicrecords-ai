# Browser QA - CivicRecords AI v1.4.7

Date: 2026-05-02

Scope:
- Rendered `docs/index.html` after the CivicCore v0.20.0 startup config validation consumer update.
- Confirmed the landing page source references `v1.4.7` release links and preserves unsigned Windows installer warning language.
- Captured desktop and mobile evidence with Chrome headless.

Evidence:
- Desktop screenshot: `docs/browser-qa-v1.4.7-desktop.png`
- Mobile screenshot: `docs/browser-qa-v1.4.7-mobile.png`

Viewport checks:
- Desktop: `1440x1100`
- Mobile: `390x1200`

Console/page-error check:
- The static docs page has no application JavaScript execution path; Chrome headless rendered both screenshots without JavaScript page errors.
