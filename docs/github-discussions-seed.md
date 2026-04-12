# GitHub Discussions — Seed Content

## Announcements (Pin this)

### Welcome to CivicRecords AI

Hey everyone! 👋

CivicRecords AI is an open-source, locally-hosted AI system that helps municipal staff respond to open records requests (FOIA, CORA, and state equivalents). Every piece of data stays on your city's own hardware — no cloud, no subscriptions, no vendor lock-in.

**Current status:** v0.1.0 — feature-complete MVP with:
- Hybrid AI search (semantic + keyword) across ingested city documents
- Records request tracking with statutory deadline management
- Exemption detection (PII regex + state-specific keyword rules + optional LLM)
- Human-in-the-loop enforcement — the system suggests, staff decides
- Hash-chained audit logging for compliance
- Cross-platform: Windows, macOS, Linux via Docker

**What's next:**
- Community feedback on the UI/UX
- Additional state exemption rules (currently CO, TX, CA, NY, FL)
- Performance testing on larger document sets
- shadcn/ui component library upgrade

We built this because no open-source tool exists for the *responder* side of open records at the municipal level. If you're a city clerk, records officer, or civic technologist — we'd love to hear from you.

— Scott

---

## Q&A

### How do I install CivicRecords AI?

**Q:** What do I need to get CivicRecords AI running on my city's server?

**A:** You need a machine with Docker installed (Windows 10/11, macOS, or Linux). The recommended spec is 8+ cores, 32GB+ RAM, and 1TB SSD — a ~$1000 desktop.

Installation is one command:
- **Windows:** `powershell -ExecutionPolicy Bypass -File install.ps1`
- **Mac/Linux:** `bash install.sh`

The script installs Docker if needed, sets up all 7 services, and creates your admin account. Full details in the README.

---

### Does this work without internet access?

**Q:** Our city network doesn't allow outbound connections from internal servers. Can CivicRecords AI run air-gapped?

**A:** Yes — that's a core design requirement. The system runs entirely locally with no outbound connections. The `verify-sovereignty.sh` script (or `verify-sovereignty.ps1` on Windows) confirms no data leaves your network. The only time you need internet is the initial Docker image pull and Ollama model download during installation.

---

### What LLM models are supported?

**Q:** The docs mention Gemma 4 as the recommended model. Can I use something else?

**A:** CivicRecords AI is model-agnostic. It works with any model available through Ollama:
- **Gemma 4 26B** — recommended for multimodal document understanding
- **Gemma 3 4B** — lighter alternative for smaller hardware
- **Llama 3, Mistral, Qwen** — also work for search and synthesis

The embedding model (nomic-embed-text) is separate from the chat model and runs on minimal resources. You can swap models in the admin panel without code changes.

---

## Ideas / Feature Requests

### Batch exemption review workflow

One thing I've been thinking about: when a request has 50+ flagged exemptions across dozens of documents, reviewing them one by one is tedious. Would a batch review interface make sense? Something like:

- Group flags by category (all SSN flags together, all law enforcement flags together)
- "Accept all in category" with a single confirmation
- Still requires human click — but organized by type rather than document order

Would this be useful for your workflow? What other exemption review patterns would help?

---

### Public-facing request portal

The current system is internal staff-only. But many cities have public portals where citizens can submit and track their records requests. Should we add:

- A public submission form (no login required)
- Request status tracking with a reference number
- Automated acknowledgment emails with deadline info

This would be a significant addition. Interested to hear if cities would use it.

---

## General

### Welcome — tell us about your use case

If you're checking out CivicRecords AI, we'd love to hear:

1. **What's your role?** City clerk? Records officer? IT staff? Journalist? Civic technologist?
2. **How do you currently handle open records requests?** Manual search? Commercial software? Spreadsheets?
3. **What's your biggest pain point?** Volume? Deadlines? Finding responsive documents? Exemption review?
4. **What would make this tool useful for you?**

No pressure — just trying to understand who finds this project and what they need. Every response helps us prioritize the roadmap.
