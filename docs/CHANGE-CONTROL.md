# CivicRecords AI — Change Control Register

**Canonical Spec:** `docs/UNIFIED-SPEC.md` (Unified Design Specification v2.0, April 12, 2026)

Every intentional deviation from the canonical spec is recorded here with rationale and approval status. This document is the audit trail for scope decisions. If a feature is in the canonical spec but not in the code, it must either appear in the reconciliation backlog or have an entry here explaining why.

---

## Format

| Field | Description |
|-------|-------------|
| **ID** | Sequential identifier (CC-001, CC-002, etc.) |
| **Date** | Date the decision was made |
| **Canonical Spec Says** | What the spec requires (section reference) |
| **Actual Decision** | What the team is doing instead |
| **Rationale** | Why the deviation is justified |
| **Approved By** | Who authorized this deviation |
| **Status** | Approved / Pending / Rejected |

---

## Change Register

*No approved changes yet. This register was established on 2026-04-13 as part of a process correction after the development team was found to be working from a superseded spec document. All deviations from the canonical spec identified during the reconciliation (Step 3) will be logged here for formal review and approval.*

---

## Pending Decisions (to be resolved during reconciliation)

These items were identified as potential intentional deviations but have NOT been approved. They are listed here so they can be formally reviewed:

| ID | Canonical Spec Says | Proposed Deviation | Rationale (draft) | Status |
|----|--------------------|--------------------|-------------------|--------|
| CC-001 | Tier 2 NER/NLP redaction via Ollama or spaCy [v1.1] (Section 12.7) | Defer beyond v1.1 | Deploying NER-based automated redaction detection may push the system from "staff productivity tool" to "automated decision-making" under Colorado CAIA (SB 24-205), risking high-risk classification. Needs legal review. | **Pending** |
| CC-002 | Tier 3 Visual AI — faces/plates in video, OCR for scanned docs, speech-to-text [v2.0] (Section 12.7) | Keep as v2.0, no change proposed | Listed here for tracking. No deviation — canonical spec already places this at v2.0. | **No action needed** |
| CC-003 | RPA bridge as last-resort connector [v2.0] (Section 12.4) | Keep as v2.0, no change proposed | Listed here for tracking. No deviation — canonical spec already places this at v2.0. | **No action needed** |
| CC-004 | Active Discovery Engine with network scanning [v1.1] (Section 12.3) | No decision yet | Significant security implications for municipal networks. Needs IT security review before implementation scope is finalized. | **Pending** |
| CC-005 | Version numbering: canonical spec uses phase-based naming (Phase 0-4), repo used semver (v1.0.0, v1.0.1, v1.1.0) | Reconcile during Step 3 | The repo's version numbers (v1.0.0, v1.1.0) don't correspond to the canonical spec's phases. Either version numbers need to be walked back, or the canonical spec's v1.0 scope needs to be formally reduced. Decision required. | **Pending** |

---

## Process

1. Any intentional deviation from the canonical spec requires an entry in this register.
2. Entries start as **Pending** until reviewed and approved by the project owner.
3. "Not in the spec" is never an acceptable justification for removing a feature. If a feature is being deferred or cut, the rationale must reference a concrete concern (regulatory, technical, resource, or user research).
4. Approved entries become the authoritative record for that decision. The canonical spec is NOT modified — this register documents where and why the implementation diverges.
5. During code reviews, reviewers should check that any spec deviation has a corresponding entry here.
