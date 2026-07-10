# CivicSunshine — Compliance & Regulatory Analysis

**50-State AI Regulatory Viability Assessment**

*Version 0.1 — April 2026*

---

## Executive Finding

CivicSunshine is deployable in all 50 states. No state has enacted a law that prohibits government agencies from using AI as an internal search, retrieval, and workflow assistance tool for open records processing. The product sits in the "staff productivity tool" category, not the "automated decision-making" category. Maintaining that classification requires specific architectural decisions documented in this analysis.

---

## Colorado (Home State — Deepest Analysis)

### The Colorado AI Act (CAIA / SB 24-205)

Colorado has the most aggressive comprehensive AI law in the United States. The CAIA was signed May 17, 2024. Its effective date has been delayed twice — from February 1, 2026 to June 30, 2026 — and the Governor's AI Policy Working Group released a proposed repeal-and-replace bill in March 2026. If enacted, the revised law would not take effect until January 1, 2027.

The CAIA defines a high-risk AI system as one that "when deployed, makes, or is a substantial factor in making, a consequential decision" with material effect on the provision or denial of: education, employment, essential government services, healthcare, housing, insurance, or legal services.

**"Government services" is explicitly in scope.** This is the provision that requires the most careful analysis for CivicSunshine.

### Why CivicSunshine Is Not a High-Risk System Under CAIA

The CAIA regulates systems that *make or substantially factor into consequential decisions about consumers.* CivicSunshine does not make decisions about consumers. It:

- Searches for documents responsive to a records request.
- Flags content that *may* be exempt from disclosure.
- Drafts response language for human review.
- Tracks deadlines and workflow status.

At no point does the system decide whether to grant or deny a request, what to redact, or what to release. Every output is a recommendation or draft presented to a human staff member who makes the actual decision. The system is analogous to a search engine or document management tool, not a decision-making system.

However, this classification depends on architectural enforcement, not just policy:

1. **No auto-redaction.** The system must never autonomously redact content. Every exemption flag must require affirmative human action to apply.
2. **No auto-denial.** The system must never generate a denial or partial-denial response without human initiation and approval.
3. **No auto-release.** No document may be transmitted to a requester without explicit human authorization.
4. **Clear labeling.** All AI-generated content (draft responses, exemption flags, search summaries) must be visually distinct and labeled as AI-generated drafts requiring review.

If any of these constraints are relaxed — for instance, if a future feature allows bulk auto-redaction of PII — the system would likely cross into "high-risk" territory under CAIA and trigger impact assessment, disclosure, and consumer appeal requirements.

### CAIA Compliance Features to Build Regardless

Even though CivicSunshine is likely outside CAIA's high-risk scope, building the following features positions the product for compliance if scope expands or if deploying cities choose to treat the system as high-risk as a precaution:

- **Impact assessment template:** Pre-built document that a city can complete to satisfy CAIA's impact assessment requirements if they elect to treat the system as high-risk.
- **Public disclosure template:** A statement cities can publish describing their use of AI in records processing, satisfying CAIA's deployer transparency requirements.
- **Audit trail:** Complete logging of all AI interactions, satisfying CAIA's documentation and attorney general inspection requirements.
- **Consumer notification template:** Language cities can include in response letters disclosing that AI-assisted search was used in locating responsive documents.

### Colorado Open Records Act (CORA) Considerations

CORA itself does not address AI use. It requires government bodies to produce responsive public records within three working days, with certain exemptions. Key CORA implications for CivicSunshine:

- **AI interactions are likely public records under CORA.** Search queries, AI-generated results, draft responses, and exemption flags created within the system may themselves be subject to CORA requests. The system's audit log must be designed with this in mind — it must be exportable and producible.
- **CORA does not require agencies to create new records.** The system should not be presented as creating new analytical documents in response to requests. It searches existing records and assists staff in organizing responses.
- **CORA exemptions must be applied by humans.** The system's exemption detection engine must be clearly positioned as a flagging tool, not an adjudicator. Staff must independently evaluate each flag against the applicable CORA exemption.
- **Colorado Department of Public Safety has acknowledged the AI/CORA intersection.** CDPS notes that requests asking agencies to use AI tools to facilitate searches "frequently are not pertinent or even possible," framing AI search capability as a gap, not a prohibition. CivicSunshine fills exactly this gap.

### Colorado Municipal AI Adoption Precedent

Colorado municipalities are already adopting AI governance policies. Garfield County approved a comprehensive AI policy in late 2025 that classifies AI use into risk tiers, requires human review of all AI outputs, and prohibits entering sensitive data into public AI systems. CivicSunshine's fully local architecture directly addresses the sensitive-data prohibition that constrains cloud AI adoption in Colorado municipalities.

---

## State-by-State Regulatory Landscape

### Tier 1: States with Comprehensive AI Laws

These states have enacted broad AI governance frameworks. None prohibit AI use for internal government document search, but each has specific compliance considerations.

**Colorado** — See detailed analysis above.

**Texas (Responsible AI Governance Act, effective January 1, 2026):** Focused primarily on government applications. Prohibits AI for "restricted purposes" (encouraging self-harm, violence, CSAM, unlawful deepfakes). Does not restrict AI-assisted document search. Requires disclosure when consumers interact with AI systems. Since CivicSunshine is an internal staff tool (not consumer-facing in v1), disclosure requirements do not apply to the search interface. If the system generates response letters sent to requesters, those letters should disclose AI assistance.

**California (multiple laws, various effective dates in 2026):** California's AI Transparency Act (SB 942) requires large AI platforms to provide detection tools and watermarks for AI-generated content. This applies to platforms with over 1 million monthly users — CivicSunshine, as a single-city deployment, would not meet this threshold. California's employment-focused AI regulations (Civil Rights Department, effective October 2025) apply to hiring and employment decisions, not records management. No California law prohibits AI-assisted records search.

**New York (RAISE Act, effective January 1, 2027):** Targets frontier AI model developers with annual revenue over $500 million. Requires transparency reports and risk management frameworks. Does not apply to deployers of open-source models on local hardware. CivicSunshine is fully outside scope.

**Illinois (HB 3773, effective January 1, 2026):** Amends the state Human Rights Act to cover AI-driven discrimination in employment decisions (hiring, firing, discipline, tenure, training). Narrowly scoped to employment. Does not apply to records management tools.

**Utah (AI Policy Act, effective May 2024; SB 226, effective May 2025):** Requires disclosure when consumers interact with generative AI. Established an AI regulatory sandbox for experimentation. Does not prohibit internal government AI use. Disclosure requirement applies only to consumer-facing AI interactions.

### Tier 2: States with Targeted AI Regulations

These states have enacted narrower AI laws focused on specific use cases (deepfakes, employment, insurance, elections). None restrict AI use for internal government records search.

- **Tennessee:** ELVIS Act (AI voice cloning). No records relevance.
- **Maryland, New Jersey, Illinois, New York City:** Employment-specific AI laws regulating automated hiring tools. No records relevance.
- **Michigan:** Election integrity and deepfake protections. No records relevance.
- **Virginia:** Regulatory reduction pilot. No prohibitions on government AI use.
- **Indiana, Montana, multiple others:** Task forces and study commissions. No enacted restrictions.

### Tier 3: States with No Comprehensive AI Legislation

The majority of states — approximately 35 — have not enacted comprehensive AI governance legislation as of April 2026. Many have introduced bills, created study commissions, or passed narrow measures (deepfake disclosure, AI in insurance). None have enacted laws that would prohibit a local government from deploying an internal AI search tool for records management.

---

## Federal Regulatory Environment

### Executive Order 14365 (December 11, 2025)

President Trump's executive order "Ensuring a National Policy Framework for Artificial Intelligence" signals intent to preempt state AI laws deemed inconsistent with federal deregulatory policy. The order directed the Secretary of Commerce to identify "burdensome" state AI laws by mid-March 2026 and established an AI Litigation Task Force to challenge state laws.

**Impact on CivicSunshine:** Minimal. The executive order targets state laws regulating AI development and commercial deployment. It does not create any prohibition on government agencies using AI internally. If federal preemption reduces the compliance burden of state AI laws like CAIA, that is a net positive for CivicSunshine adoption. However, governors in Colorado, California, and New York have publicly stated the order will not stop enforcement of their state laws. The prudent approach is to continue designing for full state-law compliance.

### No Federal Law Prohibits Government AI Use for Records

There is no federal statute that prohibits government agencies from using AI tools for internal records search and management. The federal FOIA framework is separate from state open records laws, and federal agencies (including the State Department, DOJ, and CDC) are already actively testing AI tools for FOIA processing. MITRE's FOIA Assistant prototype, funded by the federal government, is specifically designed for this purpose.

---

## Compliance Architecture Requirements

Based on the regulatory analysis, the following features must be treated as hard requirements in the product architecture — not optional, not Phase 2, not "nice to have."

### 1. Human-in-the-Loop (Architectural Enforcement)

Every state and municipal AI policy reviewed requires human oversight for any AI output that affects the public. This must be enforced at the application layer, not just the UI layer.

**Implementation:**
- No API endpoint that produces a final, releasable document without a human approval step.
- Exemption flags are stored as recommendations with a status field (flagged / reviewed / accepted / rejected) — the system cannot proceed past "flagged" without human action.
- Response letters are generated as drafts in a review queue. The "send" or "finalize" action requires authenticated human authorization.
- The system must not offer a "batch approve" or "auto-process" mode for exemption decisions or response generation.

### 2. Comprehensive Audit Logging

AI interactions in government systems are public records in most jurisdictions. The audit log is not a debugging tool — it is a legal compliance requirement.

**Implementation:**
- Every search query, every AI-generated result, every exemption flag, every draft response, every user action must be logged with timestamp, user identity, and session context.
- Logs must be append-only and tamper-evident (hash-chained or similar).
- Logs must be exportable in standard formats (CSV, JSON) for production in response to records requests or attorney general inquiries.
- Log retention period must be configurable per city to match their records retention schedule. Default: 3 years minimum (aligns with CAIA's assessment retention requirement).
- Logs must distinguish between AI-generated content and human-authored content.

### 3. Transparency and Disclosure Templates

Cities need ready-to-use compliance documents. The product should ship with:

- **Public AI Use Disclosure:** A one-page statement cities can publish on their website describing their use of CivicSunshine, what it does, what it does not do, and how human oversight is maintained.
- **Response Letter Disclosure Language:** A paragraph cities can include in records response letters: "This office used an AI-assisted search tool to locate potentially responsive documents. All results were reviewed by [staff member name/title] before inclusion in this response. The AI tool did not make any decisions regarding the release, redaction, or withholding of records."
- **CAIA Impact Assessment Template:** Pre-filled where possible, with blanks for city-specific information, enabling Colorado cities to document their risk assessment even if they determine the system is not "high-risk."
- **AI Governance Policy Template:** A model policy document cities can adapt, based on the GovAI Coalition templates and existing municipal AI policies (Boston, San Jose, Bellevue, Garfield County CO). Covers acceptable use, data classification, risk tiers, training requirements, and oversight responsibilities.

### 4. Data Sovereignty Documentation

The product's fully local architecture is its strongest compliance feature. This must be documented and verifiable.

**Implementation:**
- Installation verification script that confirms no outbound network connections exist (or only allowlisted connections) and that all data stores are local.
- Architecture documentation with a clear data flow diagram showing where data lives and where it does not go.
- A "Data Residency Attestation" document that a city IT director can sign and file, confirming that all data processed by the system remains on city-owned infrastructure.
- No telemetry, no analytics, no crash reporting that transmits data off the machine. This must be verifiable in the source code.

### 5. Exemption Detection Auditability

If the exemption detection engine's flags influence staff decisions (which they will), the system needs to demonstrate that the flagging is not systematically biased.

**Implementation:**
- Dashboard showing exemption flag acceptance/rejection rates by category, department, and time period.
- Ability to export flag accuracy data for external review.
- Configuration interface where authorized staff can adjust exemption rules without code changes, with all changes logged.
- Documentation of the exemption rule sources (state statutes, city-specific rules) with version tracking.

### 6. Model Transparency

Cities and their attorneys will want to know what model is running and what it was trained on.

**Implementation:**
- Admin panel displays current model name, version, parameter count, license, and a link to the model card.
- The system does not fine-tune models on city data unless explicitly configured to do so by IT staff. Default: retrieval-augmented generation only, no fine-tuning.
- If fine-tuning is enabled, the system documents what data was used, when, and by whom.
- No proprietary or closed-source models are used by default. The recommended model stack is fully open-weight and Apache 2.0 / MIT licensed.

---

## Risk Matrix

| Risk | Severity | Likelihood | Mitigation |
|---|---|---|---|
| CAIA classifies system as "high-risk" | Medium | Low | Human-in-the-loop architecture; no autonomous decisions; impact assessment template |
| AI-generated response contains error | High | Medium | Mandatory human review; clear draft labeling; audit trail |
| Audit log is itself subject to CORA request | Medium | High | Export-ready logging; retention policy configuration; log format documentation |
| Exemption flags exhibit systematic bias | High | Low | Auditability dashboard; human override required; configurable rules engine |
| City attorney rejects product on precautionary grounds | Medium | Medium | Compliance documentation package; governance policy template; data residency attestation |
| Federal preemption creates uncertainty | Low | Medium | Design for strictest state standard (Colorado); federal deregulation only reduces burden |
| State enacts new law restricting government AI | Medium | Low | Modular architecture allows disabling specific features; transparency features satisfy most disclosure requirements |
| Resident files CORA request for "all AI interactions" | Medium | High | Audit log is the response; export tooling is pre-built; retention schedule is documented |

---

## Regulatory Monitoring Requirements

The product team should track the following regulatory developments:

1. **Colorado CAIA repeal-and-replace bill** — Expected to be introduced during the 2026 legislative session. May narrow or expand the definition of "high-risk" and "consequential decision." The working group's March 2026 draft replaces audit requirements with a transparency framework, which would be favorable for CivicSunshine.

2. **Federal AI preemption** — The Commerce Department's evaluation of "burdensome" state AI laws was due by mid-March 2026. The DOJ AI Litigation Task Force may challenge state laws. If successful, this reduces compliance complexity but does not change the product's compliance posture (design for the strictest standard).

3. **State legislative sessions (2026-2027)** — Over 1,200 AI-related bills were introduced across all 50 states in 2025 alone, with 145 enacted. The 2026 sessions will produce more. Monitor for any bills specifically targeting government AI use in records management or public-facing services.

4. **Municipal AI policy adoption** — Cities are rapidly adopting internal AI governance policies. The product's compliance documentation should be updated to reference the most current model policies from the GovAI Coalition, NACo, ICMA, and NLC.

5. **NIST AI Risk Management Framework updates** — Multiple state laws and municipal policies reference NIST AI RMF. The product's documentation should maintain alignment with current NIST guidance.

---

## Appendix: Key Reference Documents

- Colorado AI Act (SB 24-205): https://leg.colorado.gov/bills/sb24-205
- Colorado AI Act Wikipedia (status tracker): https://en.wikipedia.org/wiki/Colorado_AI_Act
- IAPP US State AI Governance Legislation Tracker: https://iapp.org/resources/article/us-state-ai-governance-legislation-tracker
- CDT: AI in Local Government (municipal policy analysis): https://cdt.org/insights/ai-in-local-government-how-counties-cities-are-advancing-ai-governance/
- MRSC: AI Policies and Resources for Local Governments: https://mrsc.org/explore-topics/technology/it/artificial-intelligence
- ICMA: AI in Your Municipality: https://icma.org/articles/pm-magazine/ai-your-municipality-implementation-and-governance
- GovAI Coalition Templates: https://govaicoalition.org
- NIST AI Risk Management Framework: https://www.nist.gov/artificial-intelligence/ai-risk-management-framework
- Colorado Open Records Act (CORA): C.R.S. § 24-72-201 to 206
- Colorado Freedom of Information Coalition Guide: https://coloradofoic.org/open-government-guide/
- Garfield County AI Policy (example municipal policy): https://www.postindependent.com/news/garfield-county-adopts-first-policy-governing-artificial-intelligence-use-by-employees/
