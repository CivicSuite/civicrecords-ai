# CivicRecords AI CO-4 Browser QA Evidence

Date: 2026-05-05

Scope: `docs/index.html` after CO-4 Tier 1 retrofit ledger copy and CivicCore v0.22.1 baseline updates.

## Viewports

- Desktop: 1280 x 900, screenshot `docs/browser-qa-co4-tier1-ledger-desktop.png`
- Mobile: 390 x 844, screenshot `docs/browser-qa-co4-tier1-ledger-mobile.png`

## Rendered States

- Success state: checked on desktop and mobile.
- Loading state: not applicable; static documentation page has no asynchronous loading path.
- Empty state: not applicable; static documentation page has no data-backed empty condition.
- Error state: not applicable; static documentation page has no user-triggered error condition.
- Partial/degraded state: not applicable; page has no runtime service or progressive data dependency.

## Results

### Desktop
- Page title: CivicRecords AI — Open-Source AI for Municipal Open Records
- Main heading: CivicRecords AI
- Required copy present: true
- Stale correction-window copy: not present
- Browser console messages: none
- Page errors: none
- Horizontal overflow: false
- Body text contrast ratio on white sections: 10.31
- Hero release-note contrast ratio on blue section: 8.19
- Nav link contrast ratio on blue section: 7.84
- Image count / empty alts: 3 / 0
- Keyboard traversal sample: a CivicRecords AI outline=auto/1px ; a Features outline=auto/1px ; a Tech Stack outline=auto/1px ; a Docs outline=auto/1px ; a GitHub outline=auto/1px ; a 🐈 GitHub Repository outline=auto/3px ; a ⬇ Download Installer (Linux / macOS) outline=auto/3px ; a ⬇ Download Installer (Windows) outline=auto/3px ; a 🗎 User Manual outline=auto/3px ; a 📄 README outline=auto/3px ; a 🐈
        GitHub Repository
        CivicSuite/ci outline=auto/1px ; a ⬇
        Download Installer
        Linux & macOS outline=auto/1px
### Mobile
- Page title: CivicRecords AI — Open-Source AI for Municipal Open Records
- Main heading: CivicRecords AI
- Required copy present: true
- Stale correction-window copy: not present
- Browser console messages: none
- Page errors: none
- Horizontal overflow: false
- Body text contrast ratio on white sections: 10.31
- Hero release-note contrast ratio on blue section: 8.19
- Nav link contrast ratio on blue section: 7.84
- Image count / empty alts: 3 / 0
- Keyboard traversal sample: a CivicRecords AI outline=auto/1px ; a 🐈 GitHub Repository outline=auto/3px ; a ⬇ Download Installer (Linux / macOS) outline=auto/3px ; a ⬇ Download Installer (Windows) outline=auto/3px ; a 🗎 User Manual outline=auto/3px ; a 📄 README outline=auto/3px ; a 🐈
        GitHub Repository
        CivicSuite/ci outline=auto/1px ; a ⬇
        Download Installer
        Linux & macOS outline=auto/1px ; a ⬇
        Download Installer
        Windows · Set outline=auto/1px ; a 🗎
        User Manual
        Staff + IT + Archit outline=auto/1px ; a 📄
        README
        Quick start & feature ov outline=auto/1px ; a 📖 Complete Manual (Online) → outline=auto/3px

Result: PASS
