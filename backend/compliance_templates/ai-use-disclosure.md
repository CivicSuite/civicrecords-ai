# Public Disclosure: Use of Artificial Intelligence in Records Management

**{{CITY_NAME}}, {{STATE}}**
**Effective Date: {{EFFECTIVE_DATE}}**

---

## 1. System Description

{{CITY_NAME}} utilizes CivicSunshine, an open-source records management assistance tool, to support staff in processing public records requests submitted under applicable open records laws. CivicSunshine runs entirely on locally owned and operated hardware within {{CITY_NAME}}'s facilities. No data leaves {{CITY_NAME}}'s network.

### What CivicSunshine Does

- **Document search and retrieval:** Assists staff in locating responsive documents across municipal repositories by analyzing request language and matching it against indexed records.
- **Exemption identification:** Flags portions of responsive documents that may contain information subject to statutory exemptions (e.g., personally identifiable information, attorney-client privilege, law enforcement sensitive data).
- **Redaction assistance:** Suggests redaction regions on documents based on identified exemptions. All suggested redactions are presented to staff for review before application.
- **Response drafting:** Generates draft response letters that cite applicable statutes, summarize responsive documents, and include required disclosures. All drafts are reviewed and edited by staff before release.
- **Cost estimation:** Calculates estimated fees based on page counts, labor time, and applicable fee schedules.

### What CivicSunshine Does NOT Do

- **CivicSunshine does not make final decisions.** Every action suggested by the AI — including exemption determinations, redactions, response language, and fee calculations — requires explicit human review and approval before taking effect.
- **CivicSunshine does not deny or grant requests.** All decisions to fulfill, partially fulfill, or deny a records request are made by authorized {{CITY_NAME}} staff.
- **CivicSunshine does not communicate directly with requesters.** All correspondence is reviewed, edited as necessary, and sent by {{CITY_NAME}} personnel.
- **CivicSunshine does not learn from or retain personal data.** The system does not use requester information or request content to update its models.

## 2. Human Oversight Guarantees

{{CITY_NAME}} maintains the following human oversight requirements for all AI-assisted records processing:

| Decision Point | AI Role | Human Role |
|---|---|---|
| Exemption determination | Suggests applicable exemptions with statutory citations | Staff reviews, accepts, modifies, or rejects each suggestion |
| Document redaction | Proposes redaction regions | Staff verifies every redaction before application |
| Response letter content | Drafts response language | Staff reviews and edits all language before release |
| Request denial | Not involved in denial decisions | Authorized staff or city attorney makes all denial decisions |
| Fee calculation | Computes estimates from fee schedule | Staff reviews and approves final fee amounts |
| Appeal handling | May retrieve prior correspondence | Staff and/or city attorney handle all appeals |

No records request response is sent without a qualified staff member reviewing the complete output and explicitly approving release.

## 3. Data Sovereignty

All data processed by CivicSunshine remains within {{CITY_NAME}}'s physical and logical control at all times:

- The system runs on hardware owned and maintained by {{CITY_NAME}}.
- No data is transmitted to cloud services, third-party servers, or external APIs.
- All AI models run locally — no external inference calls are made.
- {{CITY_NAME}} retains full ownership of all data, models, and outputs.
- The system includes no telemetry, analytics, or usage reporting that transmits data externally.

## 4. Software Transparency

CivicSunshine is open-source software licensed under the Apache License 2.0. The source code is publicly available for inspection, audit, and independent review. {{CITY_NAME}} welcomes public scrutiny of the tools used in records management.

## 5. Contact Information

For questions about {{CITY_NAME}}'s use of AI in records management, or to request records without AI assistance, contact:

**{{CONTACT_NAME}}**
{{CONTACT_TITLE}}
{{CITY_NAME}}, {{STATE}}
Email: {{CONTACT_EMAIL}}
Phone: {{CONTACT_PHONE}}

Any requester may ask that their records request be processed without AI assistance. {{CITY_NAME}} will honor such requests, though processing times may be longer.

---

> **Disclaimer:** Consult your city attorney before adoption. This disclosure template is a starting point and should be adapted to your jurisdiction's specific legal requirements, policies, and operational context.

Template provided by CivicSunshine (Apache 2.0).
