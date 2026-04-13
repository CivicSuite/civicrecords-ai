# Colorado AI Act (SB 24-205) Impact Assessment

## CivicRecords AI — Deployer Assessment

**Deploying Entity:** {{CITY_NAME}}, {{STATE}}
**Assessment Date:** {{EFFECTIVE_DATE}}
**Prepared By:** {{CONTACT_NAME}}
**System Name:** CivicRecords AI
**System Version:** {{SYSTEM_VERSION}}

---

## 1. System Classification

### 1.1 Risk Determination

**Classification: NOT a High-Risk Artificial Intelligence System**

Under the Colorado AI Act (SB 24-205), a "high-risk artificial intelligence system" is one that makes, or is a substantial factor in making, a "consequential decision." Consequential decisions include those affecting education, employment, financial services, government services, healthcare, housing, insurance, and legal services.

### 1.2 Rationale for Non-High-Risk Classification

CivicRecords AI is classified as **not high-risk** for the following reasons:

1. **No autonomous decision-making:** CivicRecords AI does not make, and is not a substantial factor in making, any consequential decision. The system provides suggestions and draft content that must be reviewed and approved by authorized human staff before any action is taken.

2. **Advisory role only:** The system functions as a staff productivity tool that assists with document search, exemption identification, redaction suggestions, and response drafting. It does not determine whether a records request is granted, denied, or partially fulfilled.

3. **No direct impact on individuals:** The system does not evaluate, score, classify, or make determinations about individual requesters. It processes documents, not people.

4. **Human-in-the-loop enforcement:** Every output of the system passes through mandatory human review before affecting any records request outcome. Staff retain full authority to accept, modify, or reject any AI suggestion.

5. **No consequential government services determination:** Processing efficiency for records requests does not constitute a consequential decision regarding access to government services. The legal right to records is determined by statute, and the AI does not alter that right.

### 1.3 Voluntary Compliance

Despite the non-high-risk classification, {{CITY_NAME}} voluntarily adopts the following practices consistent with the spirit of the Colorado AI Act to demonstrate responsible AI governance.

## 2. Human-in-the-Loop Enforcement

The following table documents every decision point where CivicRecords AI produces output that could influence records request processing, and the corresponding human oversight requirement:

| Decision Point | AI Role | Human Role | Override Available? |
|---|---|---|---|
| Document search and retrieval | Ranks and surfaces potentially responsive documents | Staff reviews result set; may add or remove documents | Yes — staff can search manually |
| Exemption identification | Suggests applicable statutory exemptions with citations | Staff evaluates each suggestion against the actual document and statute | Yes — staff can reject all suggestions |
| Redaction proposal | Highlights document regions that may require redaction | Staff reviews every proposed redaction; approves, adjusts, or removes each one | Yes — staff can redact manually |
| Response letter drafting | Generates draft response text with statutory citations | Staff reviews, edits, and approves all language before sending | Yes — staff can draft from scratch |
| Fee calculation | Computes estimated costs based on page counts and fee schedules | Staff reviews and approves final fee amounts | Yes — staff can calculate manually |
| Request denial | Not involved | Authorized staff or city attorney makes all denial decisions | N/A — AI is excluded |
| Appeal processing | May retrieve prior correspondence for reference | Staff and/or city attorney handle all appeal determinations | N/A — AI provides reference only |

**Enforcement mechanism:** The CivicRecords AI application enforces human review through its workflow architecture. AI suggestions are presented in a review queue; no suggestion can be applied, sent, or finalized without an explicit staff approval action in the interface.

## 3. Data Governance

### 3.1 Data Sources

| Data Category | Source | Contains PII? | Retention |
|---|---|---|---|
| Municipal documents | {{CITY_NAME}} document repositories | Potentially | Per {{CITY_NAME}} retention schedule |
| Records requests | Requester submissions | Yes (contact info) | Per {{CITY_NAME}} retention schedule |
| AI model weights | Pre-trained open-source models | No | Indefinite (static, not updated from data) |
| System logs | Application audit trail | Minimal (staff IDs) | Per {{CITY_NAME}} retention schedule |

### 3.2 Data Residency

- All data is stored and processed on hardware owned by {{CITY_NAME}}, located at {{CITY_NAME}} facilities.
- No data is transmitted to external cloud services, third-party APIs, or vendor systems.
- AI models run locally; no external inference services are used.
- No telemetry or usage analytics are transmitted externally.

### 3.3 Data Subject Rights

- Requesters may ask that their request be processed without AI assistance.
- {{CITY_NAME}}'s existing records retention and destruction policies apply to all data in the system.
- No personal data is used to train, fine-tune, or update AI models.

## 4. Risk Mitigation

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| AI suggests incorrect exemption | Medium | Medium | Mandatory staff review of every exemption suggestion; audit logging of overrides |
| AI misses responsive document | Low | Medium | Staff can perform supplemental manual searches; AI search is additive, not exclusive |
| AI suggests over-redaction | Medium | Low | Staff reviews every redaction; over-redaction is visible and correctable |
| AI suggests under-redaction | Low | High | Staff reviews every redaction; training on common exemption patterns; audit trail |
| Bias in document ranking | Low | Low | Open-source model with no training on demographic data; ranking is content-based |
| Data breach via AI system | Low | High | Local deployment with no external connectivity; standard IT security controls apply |
| Staff over-reliance on AI | Medium | Medium | Training requirements; periodic manual-only processing audits; confidence scores displayed |

## 5. Ongoing Monitoring Requirements

{{CITY_NAME}} commits to the following ongoing monitoring practices:

### 5.1 Regular Review

- **Quarterly review** of AI suggestion acceptance/rejection rates to detect potential over-reliance.
- **Annual review** of this impact assessment and update as system capabilities or legal requirements change.
- **Incident review** within 30 days of any identified AI error that materially affected a records request outcome.

### 5.2 Staff Training

- All staff using CivicRecords AI must complete initial training on the system's capabilities and limitations.
- Annual refresher training on AI oversight responsibilities.
- Training records maintained by {{CONTACT_NAME}}.

### 5.3 Public Transparency

- {{CITY_NAME}} publishes an AI Use Disclosure (see companion template) describing the system and human oversight guarantees.
- Response letters include AI disclosure when AI-assisted features are used (see Response Letter Disclosure template).
- This impact assessment is available to the public upon request.

### 5.4 Audit Trail

- CivicRecords AI maintains a complete audit log of all AI suggestions, staff actions (accept/reject/modify), and final outcomes.
- Audit logs are retained per {{CITY_NAME}}'s records retention schedule.
- Logs are available for internal audit, legal review, or public records requests as applicable.

## 6. Certification

I certify that this impact assessment accurately describes {{CITY_NAME}}'s deployment and use of CivicRecords AI as of the assessment date.

**Name:** {{CONTACT_NAME}}
**Title:** {{CONTACT_TITLE}}
**Date:** {{EFFECTIVE_DATE}}

**Signature:** ___________________________

---

> **Disclaimer:** Consult your city attorney before adoption. This impact assessment template is a starting point. While CivicRecords AI is designed to fall outside the Colorado AI Act's high-risk classification, your jurisdiction should independently evaluate its obligations under applicable law.

Template provided by CivicRecords AI (Apache 2.0).
