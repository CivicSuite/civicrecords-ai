"""Tier 1 PII Detection Patterns (RegEx).

Deterministic, rule-based detection of structured PII.
Zero false negatives target on test corpus.
False positives acceptable and expected.
"""

import re
from dataclasses import dataclass


@dataclass
class PIIPattern:
    name: str
    category: str
    pattern: re.Pattern
    description: str
    confidence: float  # 0.0-1.0, base confidence for matches


# Social Security Numbers
SSN_PATTERN = PIIPattern(
    name="ssn",
    category="PII - SSN",
    pattern=re.compile(
        r'\b(\d{3}[-\s]?\d{2}[-\s]?\d{4})\b'
    ),
    description="Social Security Number (XXX-XX-XXXX and variants)",
    confidence=0.95,
)

# Credit Card Numbers (Luhn-validated)
def _luhn_check(number: str) -> bool:
    """Validate credit card number using Luhn algorithm."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


CREDIT_CARD_PATTERN = PIIPattern(
    name="credit_card",
    category="PII - Credit Card",
    pattern=re.compile(
        r'\b([3-6]\d{3}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{0,4})\b'
    ),
    description="Credit card number (Visa, MC, Amex, Discover — Luhn validated)",
    confidence=0.90,
)

# Phone Numbers
PHONE_PATTERN = PIIPattern(
    name="phone",
    category="PII - Phone",
    pattern=re.compile(
        r'\b(\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})\b'
    ),
    description="US phone number with area code",
    confidence=0.85,
)

# Email Addresses
EMAIL_PATTERN = PIIPattern(
    name="email",
    category="PII - Email",
    pattern=re.compile(
        r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
    ),
    description="Email address",
    confidence=0.95,
)

# Bank Account / Routing Numbers
BANK_ROUTING_PATTERN = PIIPattern(
    name="bank_routing",
    category="PII - Bank Account",
    pattern=re.compile(
        r'\b((?:routing|aba|transit)[\s#:]*\d{9})\b',
        re.IGNORECASE,
    ),
    description="Bank routing/ABA/transit number (9 digits with label)",
    confidence=0.90,
)

BANK_ACCOUNT_PATTERN = PIIPattern(
    name="bank_account",
    category="PII - Bank Account",
    pattern=re.compile(
        r'\b((?:account|acct)[\s#:]*\d{6,17})\b',
        re.IGNORECASE,
    ),
    description="Bank account number (6-17 digits with label)",
    confidence=0.85,
)

# Driver's License Numbers (state-specific patterns for pilot states)
DRIVERS_LICENSE_PATTERNS = {
    "CO": PIIPattern(
        name="dl_colorado",
        category="PII - Driver License",
        pattern=re.compile(r'\b(\d{2}-\d{3}-\d{4})\b'),
        description="Colorado driver's license (XX-XXX-XXXX)",
        confidence=0.80,
    ),
    "CA": PIIPattern(
        name="dl_california",
        category="PII - Driver License",
        pattern=re.compile(r'\b([A-Z]\d{7})\b'),
        description="California driver's license (A1234567)",
        confidence=0.75,
    ),
    "TX": PIIPattern(
        name="dl_texas",
        category="PII - Driver License",
        pattern=re.compile(r'\b(\d{8})\b'),
        description="Texas driver's license (8 digits)",
        confidence=0.60,  # Lower confidence — 8 digits is common
    ),
    "NY": PIIPattern(
        name="dl_new_york",
        category="PII - Driver License",
        pattern=re.compile(r'\b(\d{3}\s?\d{3}\s?\d{3})\b'),
        description="New York driver's license (XXX XXX XXX)",
        confidence=0.70,
    ),
    "FL": PIIPattern(
        name="dl_florida",
        category="PII - Driver License",
        pattern=re.compile(r'\b([A-Z]\d{12})\b'),
        description="Florida driver's license (A + 12 digits)",
        confidence=0.85,
    ),
}

# All universal patterns (not state-specific)
UNIVERSAL_PATTERNS = [
    SSN_PATTERN,
    CREDIT_CARD_PATTERN,
    PHONE_PATTERN,
    EMAIL_PATTERN,
    BANK_ROUTING_PATTERN,
    BANK_ACCOUNT_PATTERN,
]


@dataclass
class PIIMatch:
    pattern_name: str
    category: str
    matched_text: str
    start: int
    end: int
    confidence: float


def scan_text(text: str, state_code: str | None = None) -> list[PIIMatch]:
    """Scan text for PII patterns.

    Args:
        text: Text to scan.
        state_code: Optional state code to include state-specific DL patterns.

    Returns:
        List of PII matches found.
    """
    matches = []

    for pii in UNIVERSAL_PATTERNS:
        for m in pii.pattern.finditer(text):
            # Special handling for credit cards — Luhn validation
            if pii.name == "credit_card":
                card_num = re.sub(r'[\s-]', '', m.group(1))
                if not _luhn_check(card_num):
                    continue

            matches.append(PIIMatch(
                pattern_name=pii.name,
                category=pii.category,
                matched_text=m.group(1),
                start=m.start(1),
                end=m.end(1),
                confidence=pii.confidence,
            ))

    # State-specific DL patterns
    if state_code and state_code.upper() in DRIVERS_LICENSE_PATTERNS:
        dl = DRIVERS_LICENSE_PATTERNS[state_code.upper()]
        for m in dl.pattern.finditer(text):
            matches.append(PIIMatch(
                pattern_name=dl.name,
                category=dl.category,
                matched_text=m.group(1),
                start=m.start(1),
                end=m.end(1),
                confidence=dl.confidence,
            ))

    return matches
