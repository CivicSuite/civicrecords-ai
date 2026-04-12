import re
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentChunk
from app.models.exemption import ExemptionFlag, ExemptionRule, FlagStatus, RuleType


# Built-in PII patterns (always active regardless of state rules)
BUILTIN_PII_RULES = [
    {"category": "PII - SSN", "pattern": r"\b\d{3}-\d{2}-\d{4}\b", "confidence": 0.95},
    {"category": "PII - SSN (no dashes)", "pattern": r"\b\d{9}\b", "confidence": 0.6},
    {"category": "PII - Phone", "pattern": r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b", "confidence": 0.8},
    {"category": "PII - Email", "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "confidence": 0.85},
    {"category": "PII - Credit Card", "pattern": r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "confidence": 0.9},
    {"category": "PII - Date of Birth", "pattern": r"\b(?:DOB|Date of Birth|born)\s*:?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", "confidence": 0.85},
]


@dataclass
class FlagResult:
    category: str
    matched_text: str
    confidence: float
    rule_id: uuid.UUID | None = None
    rule_type: str = "regex"


def scan_text_with_regex(text: str, pattern: str) -> list[str]:
    """Find all matches of a regex pattern in text."""
    try:
        return re.findall(pattern, text, re.IGNORECASE)
    except re.error:
        return []


def scan_text_with_keywords(text: str, keywords: str) -> list[str]:
    """Find keyword matches. Keywords are comma-separated."""
    matches = []
    text_lower = text.lower()
    for kw in keywords.split(","):
        kw = kw.strip().lower()
        if kw and kw in text_lower:
            # Extract surrounding context
            idx = text_lower.index(kw)
            start = max(0, idx - 30)
            end = min(len(text), idx + len(kw) + 30)
            matches.append(text[start:end].strip())
    return matches


def scan_chunk_builtin(text: str) -> list[FlagResult]:
    """Scan text with built-in PII rules."""
    flags = []
    for rule in BUILTIN_PII_RULES:
        matches = scan_text_with_regex(text, rule["pattern"])
        for match in matches:
            flags.append(FlagResult(
                category=rule["category"],
                matched_text=match if len(match) < 200 else match[:200],
                confidence=rule["confidence"],
                rule_id=None,
                rule_type="regex",
            ))
    return flags


async def scan_chunk_with_rules(
    session: AsyncSession,
    text: str,
    state_code: str | None = None,
) -> list[FlagResult]:
    """Scan text with database-configured rules for a state."""
    flags = scan_chunk_builtin(text)

    if state_code:
        result = await session.execute(
            select(ExemptionRule).where(
                ExemptionRule.enabled.is_(True),
                ExemptionRule.state_code == state_code,
                ExemptionRule.rule_type.in_([RuleType.REGEX, RuleType.KEYWORD]),
            )
        )
        rules = result.scalars().all()

        for rule in rules:
            if rule.rule_type == RuleType.REGEX:
                matches = scan_text_with_regex(text, rule.rule_definition)
            elif rule.rule_type == RuleType.KEYWORD:
                matches = scan_text_with_keywords(text, rule.rule_definition)
            else:
                continue

            for match in matches:
                flags.append(FlagResult(
                    category=rule.category,
                    matched_text=match if len(match) < 200 else match[:200],
                    confidence=0.8,
                    rule_id=rule.id,
                    rule_type=rule.rule_type.value,
                ))

    return flags


async def scan_request_documents(
    session: AsyncSession,
    request_id: uuid.UUID,
    state_code: str | None = None,
) -> list[ExemptionFlag]:
    """Scan all document chunks attached to a request for exemptions."""
    from app.models.request import RequestDocument

    # Get all attached document IDs
    result = await session.execute(
        select(RequestDocument.document_id).where(
            RequestDocument.request_id == request_id
        )
    )
    doc_ids = [r[0] for r in result.fetchall()]

    if not doc_ids:
        return []

    # Get all chunks for these documents
    result = await session.execute(
        select(DocumentChunk).where(DocumentChunk.document_id.in_(doc_ids))
    )
    chunks = result.scalars().all()

    created_flags = []
    for chunk in chunks:
        flag_results = await scan_chunk_with_rules(session, chunk.content_text, state_code)

        for fr in flag_results:
            # Check for duplicate flags on same chunk + category
            existing = await session.execute(
                select(ExemptionFlag).where(
                    ExemptionFlag.chunk_id == chunk.id,
                    ExemptionFlag.request_id == request_id,
                    ExemptionFlag.category == fr.category,
                    ExemptionFlag.matched_text == fr.matched_text,
                )
            )
            if existing.scalar_one_or_none():
                continue

            flag = ExemptionFlag(
                chunk_id=chunk.id,
                rule_id=fr.rule_id,
                request_id=request_id,
                category=fr.category,
                matched_text=fr.matched_text,
                confidence=fr.confidence,
                status=FlagStatus.FLAGGED,
            )
            session.add(flag)
            created_flags.append(flag)

    await session.commit()
    return created_flags
