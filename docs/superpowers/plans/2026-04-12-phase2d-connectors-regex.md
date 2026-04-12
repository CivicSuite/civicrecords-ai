# Phase 2D: Connector Framework + Tier 1 Regex Expansion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the universal connector protocol (base class + file system connector) and expand Tier 1 PII regex patterns to include credit cards, bank accounts, and driver's licenses.

**Architecture:** Connector framework uses an abstract base class with 4 operations (authenticate, discover, fetch, health_check). Each connector type is a separate implementation. The file system connector is the first concrete implementation. Tier 1 regex patterns are added to the existing exemption rules system.

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Python 3.12, re (regex)

**Working directory:** `C:\Users\scott\Desktop\Claude\civicrecords-ai\backend`

---

## Task 1: Connector Base Class

**Files:**
- Create: `backend/app/connectors/__init__.py`
- Create: `backend/app/connectors/base.py`

- [ ] **Step 1: Create the connector base class**

Create `backend/app/connectors/__init__.py` (empty).

Create `backend/app/connectors/base.py`:

```python
"""Universal Connector Protocol — Base Class.

Every connector implements 4 operations:
- authenticate(): Establish secure connection
- discover(): Enumerate available records
- fetch(): Pull specific records into standard format
- health_check(): Verify connection alive and healthy
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNREACHABLE = "unreachable"


@dataclass
class HealthCheckResult:
    status: HealthStatus
    latency_ms: int | None = None
    error_message: str | None = None
    records_available: int | None = None
    schema_hash: str | None = None
    checked_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DiscoveredRecord:
    """A record discovered in a source system."""
    source_path: str
    filename: str
    file_type: str
    file_size: int
    last_modified: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class FetchedDocument:
    """A document fetched from a source system, ready for ingestion."""
    source_path: str
    filename: str
    file_type: str
    content: bytes
    file_size: int
    metadata: dict = field(default_factory=dict)


class BaseConnector(ABC):
    """Abstract base class for all data source connectors."""

    def __init__(self, config: dict):
        """Initialize with connection configuration.
        
        Args:
            config: Connection-specific configuration (paths, credentials, etc.)
        """
        self.config = config
        self._authenticated = False

    @property
    @abstractmethod
    def connector_type(self) -> str:
        """Return the connector type identifier (e.g., 'file_system', 'smtp', 'rest_api')."""
        ...

    @abstractmethod
    async def authenticate(self) -> bool:
        """Establish connection to the source system.
        
        Returns:
            True if authentication successful, False otherwise.
        """
        ...

    @abstractmethod
    async def discover(self) -> list[DiscoveredRecord]:
        """Enumerate available records in the source system.
        
        Returns:
            List of discovered records with metadata.
        """
        ...

    @abstractmethod
    async def fetch(self, source_path: str) -> FetchedDocument:
        """Fetch a specific record from the source system.
        
        Args:
            source_path: Path/identifier of the record to fetch.
            
        Returns:
            FetchedDocument with content bytes and metadata.
        """
        ...

    @abstractmethod
    async def health_check(self) -> HealthCheckResult:
        """Check connection health.
        
        Returns:
            HealthCheckResult with status, latency, and diagnostics.
        """
        ...
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.connectors.base import BaseConnector, HealthStatus; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/connectors/
git commit -m "feat: add connector base class with 4-operation protocol

- BaseConnector ABC: authenticate, discover, fetch, health_check
- HealthCheckResult, DiscoveredRecord, FetchedDocument dataclasses
- HealthStatus enum (healthy/degraded/failed/unreachable)
- Foundation for file system, email, REST API, ODBC connectors"
```

---

## Task 2: File System Connector

**Files:**
- Create: `backend/app/connectors/file_system.py`

- [ ] **Step 1: Create the file system connector**

Create `backend/app/connectors/file_system.py`:

```python
"""File System / SMB Connector.

Connects to local or mounted file directories to discover and fetch documents.
Supports: PDF, DOCX, XLSX, CSV, TXT, HTML, EML
"""

import os
import hashlib
import time
from datetime import datetime
from pathlib import Path

from app.connectors.base import (
    BaseConnector,
    DiscoveredRecord,
    FetchedDocument,
    HealthCheckResult,
    HealthStatus,
)


SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".csv", ".txt", ".html", ".htm", ".eml",
    ".doc", ".xls", ".json", ".xml", ".rtf",
}


class FileSystemConnector(BaseConnector):
    """Connector for local file system and mounted network shares."""

    @property
    def connector_type(self) -> str:
        return "file_system"

    def __init__(self, config: dict):
        super().__init__(config)
        self.base_path = config.get("path", "")
        self.recursive = config.get("recursive", True)
        self.max_file_size = config.get("max_file_size_mb", 50) * 1024 * 1024

    async def authenticate(self) -> bool:
        """Verify the directory exists and is readable."""
        path = Path(self.base_path)
        if path.exists() and path.is_dir() and os.access(path, os.R_OK):
            self._authenticated = True
            return True
        return False

    async def discover(self) -> list[DiscoveredRecord]:
        """Scan directory for supported files."""
        if not self._authenticated:
            await self.authenticate()

        records = []
        base = Path(self.base_path)

        if self.recursive:
            files = base.rglob("*")
        else:
            files = base.glob("*")

        for file_path in files:
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            stat = file_path.stat()
            if stat.st_size > self.max_file_size:
                continue

            records.append(DiscoveredRecord(
                source_path=str(file_path),
                filename=file_path.name,
                file_type=file_path.suffix.lstrip(".").lower(),
                file_size=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
                metadata={
                    "relative_path": str(file_path.relative_to(base)),
                },
            ))

        return records

    async def fetch(self, source_path: str) -> FetchedDocument:
        """Read a file from the filesystem."""
        path = Path(source_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {source_path}")
        if not path.is_file():
            raise ValueError(f"Not a file: {source_path}")

        content = path.read_bytes()
        return FetchedDocument(
            source_path=source_path,
            filename=path.name,
            file_type=path.suffix.lstrip(".").lower(),
            content=content,
            file_size=len(content),
            metadata={
                "sha256": hashlib.sha256(content).hexdigest(),
                "last_modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
            },
        )

    async def health_check(self) -> HealthCheckResult:
        """Check if directory is accessible."""
        start = time.monotonic()
        path = Path(self.base_path)

        if not path.exists():
            return HealthCheckResult(
                status=HealthStatus.UNREACHABLE,
                error_message=f"Directory does not exist: {self.base_path}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        if not os.access(path, os.R_OK):
            return HealthCheckResult(
                status=HealthStatus.FAILED,
                error_message=f"Directory not readable: {self.base_path}",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        # Count files for records_available
        try:
            file_count = sum(
                1 for f in path.rglob("*")
                if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS
            )
        except PermissionError:
            return HealthCheckResult(
                status=HealthStatus.DEGRADED,
                error_message="Some subdirectories not readable",
                latency_ms=int((time.monotonic() - start) * 1000),
            )

        return HealthCheckResult(
            status=HealthStatus.HEALTHY,
            records_available=file_count,
            latency_ms=int((time.monotonic() - start) * 1000),
        )
```

- [ ] **Step 2: Verify import**

```bash
cd backend && python -c "from app.connectors.file_system import FileSystemConnector; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/connectors/file_system.py
git commit -m "feat: add file system connector (authenticate/discover/fetch/health_check)

- Scans directories for supported file types (PDF, DOCX, XLSX, CSV, TXT, HTML, EML)
- Recursive scanning with max file size limit
- Health check verifies directory accessibility and counts available files
- SHA-256 hash computed on fetch for deduplication"
```

---

## Task 3: Tier 1 Regex Expansion

**Files:**
- Create: `backend/app/exemptions/patterns.py`

Expand the PII detection patterns beyond the existing 6 (SSN, email, phone) to include credit cards, bank accounts, and driver's licenses.

- [ ] **Step 1: Read existing exemption rules to understand current patterns**

Read whatever files define the current regex patterns — check `app/exemptions/` directory.

- [ ] **Step 2: Create comprehensive PII patterns module**

Create `backend/app/exemptions/patterns.py`:

```python
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
```

- [ ] **Step 3: Verify import and basic test**

```bash
cd backend && python -c "
from app.exemptions.patterns import scan_text

# Test SSN
matches = scan_text('His SSN is 123-45-6789 and phone is (303) 555-1234')
for m in matches:
    print(f'{m.category}: {m.matched_text} (confidence: {m.confidence})')

# Test credit card with Luhn
matches = scan_text('Card number: 4111-1111-1111-1111')
for m in matches:
    print(f'{m.category}: {m.matched_text} (confidence: {m.confidence})')

print('OK')
"
```

- [ ] **Step 4: Run full test suite**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords python -m pytest tests/ -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/exemptions/patterns.py
git commit -m "feat: expand Tier 1 PII regex patterns

- SSN, credit card (Luhn-validated), phone, email
- Bank routing numbers (9-digit with label)
- Bank account numbers (6-17 digit with label)
- State-specific driver's license patterns (CO, CA, TX, NY, FL)
- scan_text() function returns matches with confidence scores
- Zero false negatives target; false positives acceptable"
```

---

## Summary

After Phase 2D:
- Connector base class with 4-operation protocol (authenticate/discover/fetch/health_check)
- File system connector implementation (scans directories, fetches files, health checks)
- Expanded Tier 1 PII patterns: SSN, credit card, phone, email, bank routing, bank account, driver's licenses (5 states)
- scan_text() function for PII scanning with confidence scores
