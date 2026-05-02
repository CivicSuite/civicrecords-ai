# Browser QA - CivicRecords AI v1.4.6

Date: 2026-05-02

- Desktop screenshot: `docs/browser-qa-v1.4.6-desktop.png`
- Mobile screenshot: `docs/browser-qa-v1.4.6-mobile.png`
- Browser command: Google Chrome headless against `file:///C:/Users/scott/OneDrive/Desktop/Claude/civicrecords-ai/docs/index.html`.
- Visible checks: current release badge shows `v1.4.6`, public installer links point to `v1.4.6`, the page renders without visible clipping at desktop and mobile widths, and the unsigned Windows installer warning remains present in the install guidance.
- Console/runtime note: headless Chrome wrote both screenshots successfully. The first file-existence check raced the screenshot write, then both screenshots were confirmed on disk.
