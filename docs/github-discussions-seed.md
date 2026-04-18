# GitHub Discussions — Seed Content for CivicRecords AI
# v1.1+ · April 2026
#
# Instructions for seeding:
#   gh discussion create --repo scottconverse/civicrecords-ai --category "Announcements" --title "..." --body "..."
#   (Repeat for each post below. Pin the Announcements post after creating it.)
#
# Categories to enable in GitHub Settings → Discussions:
#   Announcements, Q&A, Ideas, Show and Tell, General
# ─────────────────────────────────────────────────────────────────────────────


## ── ANNOUNCEMENTS ────────────────────────────────────────────────────────────
## Category: Announcements
## Action: PIN THIS POST after creating it

### Title: Welcome to CivicRecords AI — v1.1+ is here

---

Hello, and welcome to the CivicRecords AI community.

CivicRecords AI is an open-source, locally-hosted AI system built for American cities responding to public records requests — FOIA, CORA, and their state equivalents. Everything runs on a single machine inside your network. No cloud. No vendor lock-in. Resident data never leaves the building.

**What v1.1 delivers:**

- **AI-powered hybrid search** — natural language queries across all ingested city documents (semantic + keyword, pgvector + PostgreSQL full-text, normalized scores, optional LLM summary)
- **Records request lifecycle** — 10-status workflow from intake to fulfillment with deadline tracking, messaging, fee management, and AI-drafted response letters
- **Exemption detection** — PII patterns (SSN, phone, email, credit card) + statutory keyword matching across all 50 states and DC (180 rules). Every flag requires human confirmation — no auto-redaction
- **Universal connector framework** — File system, REST API (API key / Bearer / OAuth2 / Basic auth; page/offset/cursor pagination), and ODBC (SQL databases via pyodbc) connectors with per-source cron scheduling
- **Sync failure tracking & circuit breaker** — per-record failure tracking, two-layer retry, automatic circuit breaker after 5 consecutive full-run failures, live health status on every source card
- **Department access controls** — staff scoped to their department; admins see all
- **Compliance by design** — hash-chained audit logs, human-in-the-loop enforcement at every transition, 5 compliance templates (AI Use Disclosure, CAIA Impact Assessment, AI Governance Policy, Response Letter Disclosure, Data Residency Attestation)
- **Guided onboarding** — 3-phase wizard gets a new city to production in under an hour

**Current status:** Active development. All core workflows are production-ready. The public-facing requester portal is on the v1.2 roadmap.

**Quick links:**
- [README](../README.md) — quick start and feature overview
- [User Manual](civicrecords-ai-manual.pdf) — staff operations guide + IT reference + architecture
- [Installation](https://github.com/scottconverse/civicrecords-ai#install) — one command on Windows, macOS, or Linux
- [CHANGELOG](../CHANGELOG.md) — full history of every release

If you're a city clerk, records officer, IT administrator, or civic technologist — we're glad you're here. Ask anything, share what you're working on, and tell us what would make this tool more useful for your city.

— Scott


## ── Q&A ──────────────────────────────────────────────────────────────────────
## Category: Q&A

### Title: How do I install CivicRecords AI on our city's server?

**Q:** What hardware and software do we need? What does the install process look like?

**A:**

**Minimum requirements:**
- 8 CPU cores (16 recommended), 32 GB RAM (64 GB recommended), 50 GB free disk space
- Docker Desktop (Windows 10/11 or macOS 13+) or Docker Engine (Ubuntu 20.04+, Debian 11+)
- No internet connection required after initial setup

**Installation — three steps:**

*Windows:*
```powershell
git clone https://github.com/scottconverse/civicrecords-ai.git
cd civicrecords-ai
.\install.ps1
```

*Linux / macOS:*
```bash
git clone https://github.com/scottconverse/civicrecords-ai.git
cd civicrecords-ai
bash install.sh
```

*Then open your browser:* `http://localhost:8080`

The installer starts 7 Docker services: frontend, backend API, Celery worker, Celery beat scheduler, PostgreSQL 17 + pgvector, Redis 7.2, and Ollama (local LLM). First startup pulls the Ollama model — that's the only internet download required.

Full configuration options (SMTP, GPU, custom ports) are in the `.env` file the installer creates. The [IT Admin section of the User Manual](civicrecords-ai-manual.pdf) covers every option.

---

### Title: Does CivicRecords AI work without an internet connection?

**Q:** Our network policy blocks outbound connections from internal servers. Can this run air-gapped after installation?

**A:**

Yes — air-gapped operation is a core design requirement, not an afterthought.

After the initial setup (which pulls Docker images and the Ollama model), the system requires zero internet connectivity. All LLM inference runs locally via Ollama. All document storage is in the local PostgreSQL instance. No telemetry, no usage reporting, no "phone home" behavior of any kind.

The repo includes a `verify-sovereignty.sh` / `verify-sovereignty.ps1` script that runs `netstat` and confirms no outbound connections are active during normal operation. You can run it and show the output to your network security team.

The only exception: if you're hosting the landing page via GitHub Pages, that's a static HTML file served by GitHub — entirely separate from the application. The application itself is LAN-only.

---

### Title: A data source is showing "Circuit Open" — what does that mean and how do I fix it?

**Q:** One of our data sources went red and says "Circuit Open." Syncing stopped. What happened and how do I recover?

**A:**

Circuit Open means the system tried to sync this source 5 times in a row and failed every time. Rather than keep hammering a broken connection (which wastes worker resources and fills up the failure log), it automatically pauses the source and sends an admin notification.

**What to check first:**
1. **Credentials** — Did an API key expire? Did a password change? Open the source settings and re-test the connection.
2. **Network** — Is the source system accessible from the server? Try pinging it or hitting the URL from the server itself.
3. **Source system** — Is the remote system (database, REST API, file share) actually up and running?

**How to recover:**
1. Fix the underlying issue (step 1–3 above)
2. Open the source in the Data Sources page
3. Click **Unpause →**
4. The next scheduled sync (or a manual "Sync Now") will run with a grace threshold of 2 — meaning it only takes 2 failures (instead of 5) to trip the circuit breaker again, so you get fast feedback if the problem isn't actually fixed

**Viewing failed records:**
Click **View failures** on the source card to see which specific records failed and why. You can retry individual records, bulk-retry all of them, or dismiss records you don't want to ingest.

If you need more help diagnosing, the sync run log shows exactly what happened on each run. Check `docker compose logs worker` for the raw error messages.

---

### Title: What LLM models are supported? Do we need a GPU?

**Q:** The docs mention Gemma 4. Can we use a different model? And what if our server doesn't have a GPU?

**A:**

CivicRecords AI is model-agnostic — it works with any model available through Ollama. A few options depending on your hardware:

| Model | Use case | RAM required |
|---|---|---|
| Gemma 4 26B (recommended) | Multimodal, handles scanned PDFs | 32 GB |
| Gemma 3 4B | Lighter; text-only documents | 8 GB |
| Mistral 7B | Good for search synthesis | 16 GB |
| nomic-embed-text | Embeddings only (always needed) | 2 GB |

The embedding model (`nomic-embed-text`) runs separately from the chat model and uses minimal resources. Even if you run a smaller chat model, embedding quality stays consistent.

**GPU:** Optional, but recommended for production use. Ollama auto-detects:
- NVIDIA (CUDA) on Linux and Windows
- AMD (ROCm) on Linux
- AMD/Intel (DirectML) on Windows

Without a GPU, inference falls back to CPU and will be noticeably slower — fine for evaluation, slower for production with many concurrent requests or large documents.

You can switch models at any time in the Admin panel → Model Registry without reinstalling anything.

---

### Title: How does department scoping work for staff users?

**Q:** We have multiple departments using the system. Will a police department clerk see finance department records?

**A:**

No — department scoping is enforced at the API layer, not just the UI.

When a staff user (or liaison/reviewer role) belongs to a department, every API request they make is filtered to their department's records, requests, and data sources. They cannot see other departments' data even by crafting a direct API call.

Admin-role users see everything across all departments.

Here's how to set it up:
1. Create departments in **Admin → Departments**
2. Assign each user to a department when creating their account (or edit existing users)
3. Assign each data source to a department in the source settings

Unassigned sources and requests are visible to admins only. If you have sources that everyone should see, you can leave them unassigned — admins will manage them.

---

## ── IDEAS / FEATURE REQUESTS ─────────────────────────────────────────────────
## Category: Ideas

### Title: Public-facing requester portal — what would you need?

The current system is internal staff-only. Staff receive requests through whatever channel the city uses (email, phone, paper counter) and enter them manually.

A logical next step is a public portal where residents and journalists can:
- Submit requests without calling or emailing
- Get an acknowledgment with a reference number and expected timeline
- Check the status of their request without having to contact staff

This is on the v1.2 roadmap. Before we design it, I'd like to understand what cities actually need:

- Would you use a public portal, or does your city prefer the current channel model?
- What information should requesters be able to see? Just status, or more detail?
- Should requesters receive automated email notifications when status changes?
- Any concerns about exposing a public endpoint given the air-gapped design goal?

If you're currently running CivicRecords AI or evaluating it, your input here would directly shape what gets built.

---

### Title: Additional connector types — what does your city need?

The connector framework currently ships with file system, REST API, and ODBC/SQL connectors. What record systems does your city use that would benefit from a built-in connector?

The roadmap includes:
- **IMAP email** (ingesting email archives)
- **SMB/NFS** (Windows file shares with proper auth)
- **SharePoint** (Microsoft Graph API + Azure AD)

But I'm more interested in what's on your actual infrastructure list. A few questions:
- What's your city's primary document management system?
- Are you running on-prem Microsoft environments (Active Directory, SharePoint, Exchange)?
- Do you use any specific municipal software vendors (Tyler Technologies, Granicus, etc.) with API access?
- What's the #1 system you'd want connected that isn't currently supported?

---

## ── SHOW AND TELL ────────────────────────────────────────────────────────────
## Category: Show and Tell

### Title: Our first production deployment — Police Department records request workflow

We stood up CivicRecords AI for a mid-sized city's police department records office. Here's what the workflow looks like in practice after two weeks of use.

**Setup:**
- Dell PowerEdge R550 (16 cores, 64 GB RAM, 2 TB NVMe) — existing hardware
- Running Ubuntu 22.04 with Docker Engine
- Connected to a file share containing 8 years of incident reports, contracts, and correspondence (~180,000 documents, 2.3 TB)
- ODBC connector to their Records Management System (Tyler New World)

**Ingestion:**
- Initial ingest: 6 days running continuously (large document set, OCR-heavy for scanned PDFs)
- Incremental sync: ~4 hours/night for new documents
- Failure rate: about 0.3% of records on first pass — mostly corrupt PDFs that were already corrupted before ingest

**Search quality:**
Staff describe it as "finding in 30 seconds what used to take 45 minutes." The hybrid search handles police-specific terminology well, and the AI summaries have been useful for quickly determining whether a document is responsive before opening it.

**Exemption detection:**
The built-in law enforcement exemption rules catch most of what they need. They've added 3 custom keyword rules for state-specific language that the built-in rules missed.

**What's working well:** The audit trail has been valuable — supervisors can see exactly what was searched, what was flagged, and who made what decision.

**What could be better:** Bulk document review when a request spans hundreds of documents is still time-consuming. Looking forward to any batch review improvements.

Happy to answer questions about the deployment or what it looks like day-to-day.

---

## ── GENERAL ──────────────────────────────────────────────────────────────────
## Category: General

### Title: Welcome — tell us who you are and what you're working on

If you found CivicRecords AI, we'd love to hear about you and your situation. No pressure — just trying to understand who the community is and what they need.

A few questions to start:

1. **What's your role?** City clerk? Records officer? IT staff? Journalist? Civic technologist? Open-source contributor?

2. **What city or organization are you with?** (No need to be specific if you prefer not to — "mid-sized Midwest city" is fine.)

3. **How do you currently handle open records requests?** Manual search through file shares? Commercial software (Laserfiche, DocuWare, etc.)? Spreadsheets and email? Something else?

4. **What's your biggest pain point in the current process?** Volume of requests? Finding responsive documents across multiple systems? Exemption review? Deadline management? Getting through review and approval?

5. **What would make CivicRecords AI useful for your city?** Or what's blocking you from trying it?

Every response helps us understand where to focus and what to build next. This is a small open-source project trying to solve a real problem for real cities — your perspective matters more than any feature vote.

---

### Title: How to get help and contribute

**Getting help:**

The best place for questions is the [Q&A category](../../discussions?category=q-a) in this Discussions board. I check it regularly and try to respond within a day or two.

For bugs, please open an [Issue](../../issues) with:
- Your OS and Docker version
- The specific error message or unexpected behavior
- Steps to reproduce (if possible)

**Contributing:**

Pull requests are welcome. The [CONTRIBUTING.md](../../blob/master/CONTRIBUTING.md) file covers:
- Development environment setup (Python 3.12 venv + Node 20)
- Running the test suite (423 backend tests, 5 frontend tests)
- Code standards (typed Python, strict TypeScript, conventional commits)
- How to write a good PR description

The [Canonical Spec](docs/UNIFIED-SPEC.md) is the source of truth for what the system is designed to do. If you're proposing a significant feature, it helps to read the relevant spec sections first — particularly §17 which documents architectural decisions and the rationale behind them.

**What we most need help with:**
- Additional state exemption rule coverage (currently strong on CO/CA/TX/NY/FL, lighter on smaller states)
- Accessibility testing on assistive technology (screen readers, keyboard-only navigation)
- Performance testing on large document sets (1M+ documents)
- Documentation improvements, especially for non-technical city staff

Thanks for being here.
