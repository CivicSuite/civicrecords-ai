# Sub-Project 2: Ingestion Pipeline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the two-track document ingestion pipeline that consumes files from configured sources, extracts text, chunks content, generates embeddings via Ollama, and stores vectors in pgvector — making documents searchable for Sub-Project 3.

**Architecture:** Two-track ingestion: Fast Track uses lightweight Python parsers (pdfplumber, python-docx, openpyxl, etc.) for structured documents. LLM Track sends scanned/image documents to Ollama's multimodal endpoint for text extraction, with Tesseract as fallback. Both tracks produce text chunks that get embedded via nomic-embed-text through Ollama and stored in pgvector. Celery workers handle async processing. An admin API + dashboard UI shows ingestion status.

**Tech Stack:**
- pdfplumber (MIT), python-docx (MIT), openpyxl (MIT), beautifulsoup4 (MIT) — document parsers
- Pillow (MIT-like), pytesseract (Apache 2.0) — image handling and OCR fallback
- httpx — Ollama API client for embeddings and multimodal inference
- Celery + Redis — async task processing (existing)
- PostgreSQL + pgvector — vector storage (existing)
- SQLAlchemy + Alembic — ORM and migrations (existing)
- React + shadcn/ui — ingestion dashboard (existing frontend shell)

---

## File Structure

```
backend/
├── app/
│   ├── models/
│   │   ├── document.py          # DataSource, Document, DocumentChunk models
│   │   └── __init__.py          # Updated: re-export new models
│   ├── schemas/
│   │   └── document.py          # Pydantic schemas for data sources, documents, chunks
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── parsers/
│   │   │   ├── __init__.py      # Parser registry + detect_parser()
│   │   │   ├── base.py          # Abstract base parser
│   │   │   ├── pdf.py           # PDF parser (pdfplumber)
│   │   │   ├── docx.py          # DOCX parser (python-docx)
│   │   │   ├── xlsx.py          # XLSX parser (openpyxl)
│   │   │   ├── csv_parser.py    # CSV parser (stdlib)
│   │   │   ├── email.py         # Email parser (stdlib email/mailbox)
│   │   │   ├── html.py          # HTML parser (beautifulsoup4)
│   │   │   └── text.py          # Plain text / Markdown parser
│   │   ├── chunker.py           # Text chunking engine
│   │   ├── embedder.py          # Ollama embedding client
│   │   ├── llm_extractor.py     # LLM Track: multimodal text extraction
│   │   ├── pipeline.py          # Orchestrates: detect → parse → chunk → embed → store
│   │   └── tasks.py             # Celery tasks: ingest_file, ingest_source, schedule
│   ├── datasources/
│   │   ├── __init__.py
│   │   └── router.py            # Data source CRUD + ingestion trigger endpoints
│   └── documents/
│       ├── __init__.py
│       └── router.py            # Document listing, status, chunk viewing endpoints
├── alembic/
│   └── versions/
│       └── 002_documents.py     # Migration: data_sources, documents, document_chunks
└── tests/
    ├── test_parsers.py          # Parser unit tests
    ├── test_chunker.py          # Chunker unit tests
    ├── test_embedder.py         # Embedder tests (mocked Ollama)
    ├── test_pipeline.py         # Pipeline integration tests
    ├── test_datasources.py      # Data source API tests
    └── test_documents.py        # Document API tests

frontend/
└── src/
    └── pages/
        ├── DataSources.tsx      # Data source configuration page
        └── Ingestion.tsx        # Ingestion status dashboard
```

---

## Task 1: Database Models and Migration

**Files:**
- Create: `backend/app/models/document.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/schemas/document.py`
- Create: `backend/alembic/versions/002_documents.py`

- [ ] **Step 1: Create backend/app/models/document.py**

```python
import enum
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Index, Integer,
    String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.user import Base


class SourceType(str, enum.Enum):
    UPLOAD = "upload"
    DIRECTORY = "directory"
    # Future: database, email, sharepoint, rest_api


class IngestionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), unique=True)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type")
    )
    connection_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    schedule_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_ingestion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("data_sources.id"), index=True
    )
    source_path: Mapped[str] = mapped_column(Text)
    filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(50))
    file_hash: Mapped[str] = mapped_column(String(64), index=True)
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    ingestion_status: Mapped[IngestionStatus] = mapped_column(
        Enum(IngestionStatus, name="ingestion_status"),
        default=IngestionStatus.PENDING,
    )
    ingestion_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    __table_args__ = (
        Index("ix_documents_source_hash", "source_id", "file_hash"),
    )


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    content_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list | None] = mapped_column(Vector(768), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_chunks_doc_index", "document_id", "chunk_index"),
    )
```

- [ ] **Step 2: Update backend/app/models/__init__.py**

```python
from app.models.audit import AuditLog
from app.models.document import DataSource, Document, DocumentChunk, IngestionStatus, SourceType
from app.models.service_account import ServiceAccount
from app.models.user import Base, User, UserRole

__all__ = [
    "Base", "User", "UserRole", "ServiceAccount", "AuditLog",
    "DataSource", "Document", "DocumentChunk", "IngestionStatus", "SourceType",
]
```

- [ ] **Step 3: Create backend/app/schemas/document.py**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.document import IngestionStatus, SourceType


class DataSourceCreate(BaseModel):
    name: str
    source_type: SourceType
    connection_config: dict = {}
    schedule_minutes: int | None = None


class DataSourceRead(BaseModel):
    id: uuid.UUID
    name: str
    source_type: SourceType
    connection_config: dict
    schedule_minutes: int | None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    last_ingestion_at: datetime | None

    model_config = {"from_attributes": True}


class DataSourceUpdate(BaseModel):
    name: str | None = None
    connection_config: dict | None = None
    schedule_minutes: int | None = None
    is_active: bool | None = None


class DocumentRead(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_path: str
    filename: str
    file_type: str
    file_hash: str
    file_size: int
    ingestion_status: IngestionStatus
    ingestion_error: str | None
    chunk_count: int
    ingested_at: datetime | None

    model_config = {"from_attributes": True}


class DocumentChunkRead(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content_text: str
    token_count: int
    page_number: int | None

    model_config = {"from_attributes": True}


class IngestionStats(BaseModel):
    total_sources: int
    active_sources: int
    total_documents: int
    documents_by_status: dict[str, int]
    total_chunks: int
```

- [ ] **Step 4: Create migration backend/alembic/versions/002_documents.py**

```python
"""Document ingestion tables: data_sources, documents, document_chunks

Revision ID: 002
Revises: 001
Create Date: 2026-04-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    source_type = postgresql.ENUM("upload", "directory", name="source_type", create_type=True)
    source_type.create(op.get_bind(), checkfirst=True)

    ingestion_status = postgresql.ENUM(
        "pending", "processing", "completed", "failed",
        name="ingestion_status", create_type=True,
    )
    ingestion_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "data_sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("source_type", sa.Enum("upload", "directory", name="source_type", create_type=False), nullable=False),
        sa.Column("connection_config", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("schedule_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_ingestion_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("filename", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingestion_status", sa.Enum("pending", "processing", "completed", "failed", name="ingestion_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("ingestion_error", sa.Text(), nullable=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"])
    op.create_index("ix_documents_source_hash", "documents", ["source_id", "file_hash"])

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("document_id", sa.UUID(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_chunks_doc_index", "document_chunks", ["document_id", "chunk_index"])


def downgrade() -> None:
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("data_sources")
    op.execute("DROP TYPE IF EXISTS ingestion_status")
    op.execute("DROP TYPE IF EXISTS source_type")
```

- [ ] **Step 5: Add new dependencies to backend/pyproject.toml**

Add to the `dependencies` list:

```
    "pdfplumber>=0.11.0",
    "python-docx>=1.1.0",
    "openpyxl>=3.1.0",
    "beautifulsoup4>=4.12.0",
    "Pillow>=11.0.0",
    "pytesseract>=0.3.10",
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/document.py backend/app/models/__init__.py \
  backend/app/schemas/document.py backend/alembic/versions/002_documents.py \
  backend/pyproject.toml
git commit -m "feat: document ingestion models, schemas, and migration"
```

---

## Task 2: Parser Framework and Text Parsers

**Files:**
- Create: `backend/app/ingestion/__init__.py`
- Create: `backend/app/ingestion/parsers/__init__.py`
- Create: `backend/app/ingestion/parsers/base.py`
- Create: `backend/app/ingestion/parsers/text.py`
- Create: `backend/app/ingestion/parsers/pdf.py`
- Create: `backend/app/ingestion/parsers/docx.py`
- Create: `backend/app/ingestion/parsers/xlsx.py`
- Create: `backend/app/ingestion/parsers/csv_parser.py`
- Create: `backend/app/ingestion/parsers/email.py`
- Create: `backend/app/ingestion/parsers/html.py`
- Create: `backend/tests/test_parsers.py`

- [ ] **Step 1: Create backend/app/ingestion/__init__.py**

```python
# Ingestion pipeline package
```

- [ ] **Step 2: Create backend/app/ingestion/parsers/base.py**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParsedPage:
    """A single page/section of extracted text."""
    text: str
    page_number: int | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    """Result of parsing a document."""
    pages: list[ParsedPage]
    metadata: dict = field(default_factory=dict)
    file_type: str = ""

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages if p.text.strip())

    @property
    def total_chars(self) -> int:
        return sum(len(p.text) for p in self.pages)


class BaseParser(ABC):
    """Abstract base for document parsers."""

    supported_extensions: list[str] = []

    @abstractmethod
    def parse(self, file_path: Path) -> ParseResult:
        """Parse a file and return extracted text with metadata."""
        ...

    def can_parse(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.supported_extensions
```

- [ ] **Step 3: Create backend/app/ingestion/parsers/text.py**

```python
from pathlib import Path

from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult


class TextParser(BaseParser):
    supported_extensions = [".txt", ".md", ".log", ".cfg", ".ini", ".json", ".xml", ".yaml", ".yml"]

    def parse(self, file_path: Path) -> ParseResult:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        return ParseResult(
            pages=[ParsedPage(text=text, page_number=1)],
            metadata={"encoding": "utf-8"},
            file_type=file_path.suffix.lower().lstrip("."),
        )
```

- [ ] **Step 4: Create backend/app/ingestion/parsers/pdf.py**

```python
from pathlib import Path

import pdfplumber

from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult


class PdfParser(BaseParser):
    supported_extensions = [".pdf"]

    def parse(self, file_path: Path) -> ParseResult:
        pages = []
        metadata = {}

        with pdfplumber.open(file_path) as pdf:
            metadata = {
                "page_count": len(pdf.pages),
                "pdf_info": pdf.metadata or {},
            }
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                pages.append(ParsedPage(text=text, page_number=i))

        # Check if this is a scanned PDF (mostly empty text)
        total_text = sum(len(p.text.strip()) for p in pages)
        if metadata.get("page_count", 0) > 0 and total_text < 50 * metadata["page_count"]:
            metadata["likely_scanned"] = True

        return ParseResult(pages=pages, metadata=metadata, file_type="pdf")
```

- [ ] **Step 5: Create backend/app/ingestion/parsers/docx.py**

```python
from pathlib import Path

from docx import Document as DocxDocument

from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult


class DocxParser(BaseParser):
    supported_extensions = [".docx"]

    def parse(self, file_path: Path) -> ParseResult:
        doc = DocxDocument(str(file_path))

        paragraphs = []
        for para in doc.paragraphs:
            if para.text.strip():
                paragraphs.append(para.text)

        # Extract tables as text
        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                rows.append(" | ".join(cells))
            if rows:
                paragraphs.append("\n".join(rows))

        full_text = "\n\n".join(paragraphs)

        metadata = {
            "paragraph_count": len(doc.paragraphs),
            "table_count": len(doc.tables),
        }
        if doc.core_properties:
            if doc.core_properties.author:
                metadata["author"] = doc.core_properties.author
            if doc.core_properties.title:
                metadata["title"] = doc.core_properties.title

        return ParseResult(
            pages=[ParsedPage(text=full_text, page_number=1)],
            metadata=metadata,
            file_type="docx",
        )
```

- [ ] **Step 6: Create backend/app/ingestion/parsers/xlsx.py**

```python
from pathlib import Path

from openpyxl import load_workbook

from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult


class XlsxParser(BaseParser):
    supported_extensions = [".xlsx", ".xls"]

    def parse(self, file_path: Path) -> ParseResult:
        wb = load_workbook(str(file_path), read_only=True, data_only=True)
        pages = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if any(c.strip() for c in cells):
                    rows.append(" | ".join(cells))

            if rows:
                text = f"Sheet: {sheet_name}\n" + "\n".join(rows)
                pages.append(ParsedPage(text=text, page_number=None, metadata={"sheet": sheet_name}))

        wb.close()
        return ParseResult(
            pages=pages,
            metadata={"sheet_count": len(wb.sheetnames)},
            file_type="xlsx",
        )
```

- [ ] **Step 7: Create backend/app/ingestion/parsers/csv_parser.py**

```python
import csv
from pathlib import Path

from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult


class CsvParser(BaseParser):
    supported_extensions = [".csv", ".tsv"]

    def parse(self, file_path: Path) -> ParseResult:
        delimiter = "\t" if file_path.suffix.lower() == ".tsv" else ","

        rows = []
        with open(file_path, newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter=delimiter)
            for row in reader:
                rows.append(" | ".join(row))

        text = "\n".join(rows)
        return ParseResult(
            pages=[ParsedPage(text=text, page_number=1)],
            metadata={"row_count": len(rows), "delimiter": delimiter},
            file_type="csv",
        )
```

- [ ] **Step 8: Create backend/app/ingestion/parsers/email.py**

```python
import email
from email import policy
from pathlib import Path

from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult


class EmailParser(BaseParser):
    supported_extensions = [".eml"]

    def parse(self, file_path: Path) -> ParseResult:
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)

        parts = []
        headers = f"From: {msg.get('from', '')}\nTo: {msg.get('to', '')}\nDate: {msg.get('date', '')}\nSubject: {msg.get('subject', '')}\n"
        parts.append(headers)

        # Extract body
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    body = part.get_content()
                    if isinstance(body, str):
                        parts.append(body)
        else:
            body = msg.get_content()
            if isinstance(body, str):
                parts.append(body)

        text = "\n\n".join(parts)
        metadata = {
            "from": msg.get("from", ""),
            "to": msg.get("to", ""),
            "subject": msg.get("subject", ""),
            "date": msg.get("date", ""),
        }

        return ParseResult(
            pages=[ParsedPage(text=text, page_number=1)],
            metadata=metadata,
            file_type="eml",
        )
```

- [ ] **Step 9: Create backend/app/ingestion/parsers/html.py**

```python
from pathlib import Path

from bs4 import BeautifulSoup

from app.ingestion.parsers.base import BaseParser, ParsedPage, ParseResult


class HtmlParser(BaseParser):
    supported_extensions = [".html", ".htm"]

    def parse(self, file_path: Path) -> ParseResult:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        title = soup.title.string if soup.title else None

        return ParseResult(
            pages=[ParsedPage(text=text, page_number=1)],
            metadata={"title": title} if title else {},
            file_type="html",
        )
```

- [ ] **Step 10: Create backend/app/ingestion/parsers/__init__.py**

The parser registry: auto-detects which parser to use based on file extension.

```python
from pathlib import Path

from app.ingestion.parsers.base import BaseParser, ParseResult
from app.ingestion.parsers.csv_parser import CsvParser
from app.ingestion.parsers.docx import DocxParser
from app.ingestion.parsers.email import EmailParser
from app.ingestion.parsers.html import HtmlParser
from app.ingestion.parsers.pdf import PdfParser
from app.ingestion.parsers.text import TextParser
from app.ingestion.parsers.xlsx import XlsxParser

_PARSERS: list[BaseParser] = [
    PdfParser(),
    DocxParser(),
    XlsxParser(),
    CsvParser(),
    EmailParser(),
    HtmlParser(),
    TextParser(),  # Last — catches .txt, .md, etc.
]

# File extensions that the LLM Track should handle (scanned/image docs)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"}


def detect_parser(file_path: Path) -> BaseParser | None:
    """Return the appropriate parser for a file, or None if unsupported."""
    for parser in _PARSERS:
        if parser.can_parse(file_path):
            return parser
    return None


def is_image_file(file_path: Path) -> bool:
    """Check if a file should be processed by the LLM Track."""
    return file_path.suffix.lower() in IMAGE_EXTENSIONS


__all__ = ["detect_parser", "is_image_file", "ParseResult", "BaseParser"]
```

- [ ] **Step 11: Create backend/tests/test_parsers.py**

```python
import tempfile
from pathlib import Path

import pytest

from app.ingestion.parsers import detect_parser, is_image_file
from app.ingestion.parsers.text import TextParser
from app.ingestion.parsers.csv_parser import CsvParser
from app.ingestion.parsers.html import HtmlParser


def test_text_parser():
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
        f.write("Hello world\n\nThis is a test document.")
        f.flush()
        parser = TextParser()
        result = parser.parse(Path(f.name))
        assert "Hello world" in result.full_text
        assert result.total_chars > 0
        assert len(result.pages) == 1


def test_csv_parser():
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False, encoding="utf-8") as f:
        f.write("name,age,city\nAlice,30,Denver\nBob,25,Boulder\n")
        f.flush()
        parser = CsvParser()
        result = parser.parse(Path(f.name))
        assert "Alice" in result.full_text
        assert "Denver" in result.full_text
        assert result.metadata["row_count"] == 3


def test_html_parser():
    with tempfile.NamedTemporaryFile(suffix=".html", mode="w", delete=False, encoding="utf-8") as f:
        f.write("<html><head><title>Test</title></head><body><p>Hello HTML</p><script>var x=1;</script></body></html>")
        f.flush()
        parser = HtmlParser()
        result = parser.parse(Path(f.name))
        assert "Hello HTML" in result.full_text
        assert "var x=1" not in result.full_text  # Script removed
        assert result.metadata.get("title") == "Test"


def test_detect_parser_txt():
    parser = detect_parser(Path("test.txt"))
    assert parser is not None
    assert isinstance(parser, TextParser)


def test_detect_parser_pdf():
    parser = detect_parser(Path("report.pdf"))
    assert parser is not None


def test_detect_parser_unknown():
    parser = detect_parser(Path("file.xyz123"))
    assert parser is None


def test_is_image_file():
    assert is_image_file(Path("scan.jpg")) is True
    assert is_image_file(Path("photo.png")) is True
    assert is_image_file(Path("doc.pdf")) is False
    assert is_image_file(Path("file.txt")) is False
```

- [ ] **Step 12: Commit**

```bash
git add backend/app/ingestion/ backend/tests/test_parsers.py
git commit -m "feat: parser framework with 7 file type parsers and tests"
```

---

## Task 3: Chunking Engine

**Files:**
- Create: `backend/app/ingestion/chunker.py`
- Create: `backend/tests/test_chunker.py`

- [ ] **Step 1: Create backend/app/ingestion/chunker.py**

Splits text into overlapping chunks suitable for embedding. Uses sentence-aware splitting.

```python
import re
from dataclasses import dataclass


@dataclass
class Chunk:
    text: str
    index: int
    page_number: int | None = None
    token_count: int = 0


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving sentence boundaries."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    page_number: int | None = None,
) -> list[Chunk]:
    """Split text into overlapping chunks by token count.

    Uses sentence-aware splitting: never breaks mid-sentence.
    chunk_size and chunk_overlap are in estimated tokens.
    """
    if not text.strip():
        return []

    sentences = split_into_sentences(text)
    if not sentences:
        return []

    chunks = []
    current_sentences: list[str] = []
    current_tokens = 0
    chunk_index = len(chunks)

    for sentence in sentences:
        sentence_tokens = estimate_tokens(sentence)

        if current_tokens + sentence_tokens > chunk_size and current_sentences:
            # Emit current chunk
            chunk_text_str = " ".join(current_sentences)
            chunks.append(Chunk(
                text=chunk_text_str,
                index=len(chunks),
                page_number=page_number,
                token_count=estimate_tokens(chunk_text_str),
            ))

            # Keep overlap: walk backwards from end until we have enough overlap tokens
            overlap_sentences: list[str] = []
            overlap_tokens = 0
            for s in reversed(current_sentences):
                if overlap_tokens + estimate_tokens(s) > chunk_overlap:
                    break
                overlap_sentences.insert(0, s)
                overlap_tokens += estimate_tokens(s)

            current_sentences = overlap_sentences
            current_tokens = overlap_tokens

        current_sentences.append(sentence)
        current_tokens += sentence_tokens

    # Emit final chunk
    if current_sentences:
        chunk_text_str = " ".join(current_sentences)
        chunks.append(Chunk(
            text=chunk_text_str,
            index=len(chunks),
            page_number=page_number,
            token_count=estimate_tokens(chunk_text_str),
        ))

    return chunks


def chunk_pages(
    pages: list[dict],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[Chunk]:
    """Chunk multiple pages, preserving page number attribution.

    pages: list of {"text": str, "page_number": int | None}
    """
    all_chunks: list[Chunk] = []
    for page in pages:
        page_chunks = chunk_text(
            text=page["text"],
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            page_number=page.get("page_number"),
        )
        # Re-index to be globally sequential
        for chunk in page_chunks:
            chunk.index = len(all_chunks)
            all_chunks.append(chunk)
    return all_chunks
```

- [ ] **Step 2: Create backend/tests/test_chunker.py**

```python
from app.ingestion.chunker import chunk_text, chunk_pages, estimate_tokens


def test_estimate_tokens():
    assert estimate_tokens("hello world") > 0
    assert estimate_tokens("a" * 400) == 100


def test_chunk_text_single_chunk():
    """Short text that fits in one chunk."""
    text = "Hello world. This is a test."
    chunks = chunk_text(text, chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0].text == text
    assert chunks[0].index == 0


def test_chunk_text_multiple_chunks():
    """Long text that should produce multiple chunks."""
    sentences = [f"Sentence number {i} has some content." for i in range(50)]
    text = " ".join(sentences)
    chunks = chunk_text(text, chunk_size=100, chunk_overlap=20)
    assert len(chunks) > 1
    # Indices should be sequential
    for i, chunk in enumerate(chunks):
        assert chunk.index == i
    # All original content should be present across chunks
    full_reconstructed = " ".join(c.text for c in chunks)
    for s in sentences:
        assert s in full_reconstructed


def test_chunk_text_overlap():
    """Chunks should overlap: last sentence(s) of chunk N appear in chunk N+1."""
    sentences = [f"Sentence {i} with enough words to count." for i in range(20)]
    text = " ".join(sentences)
    chunks = chunk_text(text, chunk_size=50, chunk_overlap=15)
    if len(chunks) >= 2:
        # Some text from end of chunk 0 should appear in chunk 1
        last_words_chunk0 = chunks[0].text.split()[-3:]
        assert any(w in chunks[1].text for w in last_words_chunk0)


def test_chunk_text_empty():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_chunk_pages():
    pages = [
        {"text": "Page one content here.", "page_number": 1},
        {"text": "Page two has different content.", "page_number": 2},
    ]
    chunks = chunk_pages(pages, chunk_size=500)
    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert chunks[1].page_number == 2
    assert chunks[0].index == 0
    assert chunks[1].index == 1


def test_chunk_pages_preserves_page_number():
    """When a page produces multiple chunks, all keep the page number."""
    long_text = " ".join([f"Sentence {i} on this page." for i in range(30)])
    pages = [{"text": long_text, "page_number": 5}]
    chunks = chunk_pages(pages, chunk_size=50)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.page_number == 5
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ingestion/chunker.py backend/tests/test_chunker.py
git commit -m "feat: sentence-aware text chunking engine with overlap"
```

---

## Task 4: Ollama Embedding Client

**Files:**
- Create: `backend/app/ingestion/embedder.py`
- Create: `backend/tests/test_embedder.py`

- [ ] **Step 1: Create backend/app/ingestion/embedder.py**

```python
import httpx

from app.config import settings

DEFAULT_MODEL = "nomic-embed-text"


async def embed_text(text: str, model: str = DEFAULT_MODEL) -> list[float]:
    """Generate an embedding vector for a text string via Ollama."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": model, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        # Ollama returns {"embeddings": [[...vector...]]}
        embeddings = data.get("embeddings", [])
        if embeddings and len(embeddings) > 0:
            return embeddings[0]
        raise ValueError(f"No embedding returned from Ollama for model {model}")


async def embed_batch(texts: list[str], model: str = DEFAULT_MODEL) -> list[list[float]]:
    """Generate embeddings for a batch of texts.

    Ollama's /api/embed supports batch input.
    """
    if not texts:
        return []

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/embed",
            json={"model": model, "input": texts},
        )
        resp.raise_for_status()
        data = resp.json()
        embeddings = data.get("embeddings", [])
        if len(embeddings) != len(texts):
            raise ValueError(
                f"Expected {len(texts)} embeddings, got {len(embeddings)}"
            )
        return embeddings


async def check_model_available(model: str = DEFAULT_MODEL) -> bool:
    """Check if the embedding model is available in Ollama."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                return any(model in m for m in models)
    except Exception:
        pass
    return False
```

- [ ] **Step 2: Create backend/tests/test_embedder.py**

```python
import pytest
from unittest.mock import AsyncMock, patch

from app.ingestion.embedder import embed_text, embed_batch, check_model_available


@pytest.mark.asyncio
async def test_embed_text_calls_ollama():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3] * 256]}

    with patch("app.ingestion.embedder.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await embed_text("test text")
        assert len(result) == 768
        instance.post.assert_called_once()


@pytest.mark.asyncio
async def test_embed_batch_calls_ollama():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = lambda: None
    mock_response.json.return_value = {
        "embeddings": [[0.1] * 768, [0.2] * 768]
    }

    with patch("app.ingestion.embedder.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.post.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await embed_batch(["text 1", "text 2"])
        assert len(result) == 2
        assert len(result[0]) == 768


@pytest.mark.asyncio
async def test_embed_batch_empty():
    result = await embed_batch([])
    assert result == []


@pytest.mark.asyncio
async def test_check_model_available():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [{"name": "nomic-embed-text:latest"}]
    }

    with patch("app.ingestion.embedder.httpx.AsyncClient") as mock_client:
        instance = AsyncMock()
        instance.get.return_value = mock_response
        instance.__aenter__ = AsyncMock(return_value=instance)
        instance.__aexit__ = AsyncMock(return_value=False)
        mock_client.return_value = instance

        result = await check_model_available("nomic-embed-text")
        assert result is True
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ingestion/embedder.py backend/tests/test_embedder.py
git commit -m "feat: Ollama embedding client with batch support and tests"
```

---

## Task 5: LLM Track — Multimodal Text Extraction

**Files:**
- Create: `backend/app/ingestion/llm_extractor.py`

- [ ] **Step 1: Create backend/app/ingestion/llm_extractor.py**

The LLM Track: sends images/scanned PDFs to Ollama's multimodal model for text extraction. Falls back to Tesseract OCR if no multimodal model is available.

```python
import base64
import subprocess
from pathlib import Path

import httpx

from app.config import settings

MULTIMODAL_MODEL = "gemma4:e4b"
OCR_PROMPT = "Extract all text from this image. Return only the extracted text, no commentary."


async def extract_text_multimodal(image_path: Path, model: str = MULTIMODAL_MODEL) -> str:
    """Send an image to Ollama's multimodal model for text extraction."""
    image_bytes = image_path.read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json={
                "model": model,
                "prompt": OCR_PROMPT,
                "images": [image_b64],
                "stream": False,
            },
        )
        if resp.status_code == 200:
            return resp.json().get("response", "")
        raise RuntimeError(f"Ollama multimodal failed: {resp.status_code} {resp.text}")


def extract_text_tesseract(image_path: Path) -> str:
    """Fallback: use Tesseract OCR for text extraction."""
    try:
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        return pytesseract.image_to_string(img)
    except ImportError:
        raise RuntimeError("pytesseract or Pillow not installed — cannot use Tesseract fallback")
    except Exception as e:
        raise RuntimeError(f"Tesseract OCR failed: {e}")


async def extract_text_from_image(
    image_path: Path,
    prefer_multimodal: bool = True,
    model: str = MULTIMODAL_MODEL,
) -> str:
    """Extract text from an image using multimodal LLM (preferred) or Tesseract (fallback)."""
    if prefer_multimodal:
        try:
            return await extract_text_multimodal(image_path, model)
        except Exception:
            pass  # Fall through to Tesseract

    return extract_text_tesseract(image_path)


async def extract_text_from_scanned_pdf(
    pdf_path: Path,
    prefer_multimodal: bool = True,
    model: str = MULTIMODAL_MODEL,
) -> list[dict]:
    """Extract text from a scanned PDF by converting pages to images.

    Returns list of {"text": str, "page_number": int}.
    """
    from PIL import Image
    import io

    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError("pdfplumber required for scanned PDF processing")

    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            # Convert page to image
            img = page.to_image(resolution=200)
            img_bytes = io.BytesIO()
            img.original.save(img_bytes, format="PNG")
            img_bytes.seek(0)

            # Save to temp file for processing
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(img_bytes.read())
                tmp_path = Path(tmp.name)

            text = await extract_text_from_image(tmp_path, prefer_multimodal, model)
            pages.append({"text": text, "page_number": i})

            # Cleanup temp file
            tmp_path.unlink(missing_ok=True)

    return pages
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/ingestion/llm_extractor.py
git commit -m "feat: LLM Track multimodal text extraction with Tesseract fallback"
```

---

## Task 6: Ingestion Pipeline Orchestrator

**Files:**
- Create: `backend/app/ingestion/pipeline.py`
- Create: `backend/tests/test_pipeline.py`

- [ ] **Step 1: Create backend/app/ingestion/pipeline.py**

The main orchestrator: takes a file, detects type, parses, chunks, embeds, stores.

```python
import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.chunker import chunk_pages, Chunk
from app.ingestion.embedder import embed_batch
from app.ingestion.parsers import detect_parser, is_image_file, ParseResult
from app.ingestion.llm_extractor import extract_text_from_image, extract_text_from_scanned_pdf
from app.models.document import Document, DocumentChunk, IngestionStatus


def compute_file_hash(file_path: Path) -> str:
    """SHA-256 hash of file contents."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()


async def ingest_file(
    session: AsyncSession,
    file_path: Path,
    source_id: uuid.UUID,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    embed_model: str = "nomic-embed-text",
) -> Document:
    """Ingest a single file: parse → chunk → embed → store.

    Returns the Document record.
    """
    file_hash = compute_file_hash(file_path)
    file_size = file_path.stat().st_size

    # Check for duplicate (same source + same hash = already ingested)
    existing = await session.execute(
        select(Document).where(
            Document.source_id == source_id,
            Document.file_hash == file_hash,
        )
    )
    if existing.scalar_one_or_none():
        # File unchanged, skip
        return existing.scalar_one_or_none()

    # Create document record
    doc = Document(
        source_id=source_id,
        source_path=str(file_path),
        filename=file_path.name,
        file_type=file_path.suffix.lower().lstrip("."),
        file_hash=file_hash,
        file_size=file_size,
        ingestion_status=IngestionStatus.PROCESSING,
    )
    session.add(doc)
    await session.flush()

    try:
        # Step 1: Parse
        pages_data = []
        if is_image_file(file_path):
            # LLM Track: image file
            text = await extract_text_from_image(file_path)
            pages_data = [{"text": text, "page_number": 1}]
        else:
            parser = detect_parser(file_path)
            if parser is None:
                raise ValueError(f"No parser for file type: {file_path.suffix}")

            result = parser.parse(file_path)

            # Check if scanned PDF
            if result.metadata.get("likely_scanned") and result.file_type == "pdf":
                pages_data = await extract_text_from_scanned_pdf(file_path)
            else:
                pages_data = [
                    {"text": p.text, "page_number": p.page_number}
                    for p in result.pages
                ]

            doc.metadata_ = result.metadata

        # Step 2: Chunk
        chunks = chunk_pages(pages_data, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        if not chunks:
            doc.ingestion_status = IngestionStatus.COMPLETED
            doc.chunk_count = 0
            doc.ingested_at = datetime.now(timezone.utc)
            await session.commit()
            return doc

        # Step 3: Embed
        texts = [c.text for c in chunks]
        embeddings = await embed_batch(texts, model=embed_model)

        # Step 4: Store chunks
        for chunk, embedding in zip(chunks, embeddings):
            db_chunk = DocumentChunk(
                document_id=doc.id,
                chunk_index=chunk.index,
                content_text=chunk.text,
                embedding=embedding,
                token_count=chunk.token_count,
                page_number=chunk.page_number,
            )
            session.add(db_chunk)

        doc.ingestion_status = IngestionStatus.COMPLETED
        doc.chunk_count = len(chunks)
        doc.ingested_at = datetime.now(timezone.utc)
        await session.commit()

    except Exception as e:
        doc.ingestion_status = IngestionStatus.FAILED
        doc.ingestion_error = str(e)[:2000]
        await session.commit()
        raise

    return doc


async def ingest_directory(
    session: AsyncSession,
    directory: Path,
    source_id: uuid.UUID,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    embed_model: str = "nomic-embed-text",
) -> dict:
    """Ingest all supported files in a directory.

    Returns stats: {"processed": int, "skipped": int, "failed": int, "errors": list}
    """
    from app.ingestion.parsers import IMAGE_EXTENSIONS

    supported_extensions = set()
    from app.ingestion.parsers import _PARSERS
    for p in _PARSERS:
        supported_extensions.update(p.supported_extensions)
    supported_extensions.update(IMAGE_EXTENSIONS)

    stats = {"processed": 0, "skipped": 0, "failed": 0, "errors": []}

    for file_path in sorted(directory.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in supported_extensions:
            stats["skipped"] += 1
            continue

        try:
            await ingest_file(
                session=session,
                file_path=file_path,
                source_id=source_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                embed_model=embed_model,
            )
            stats["processed"] += 1
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append({"file": str(file_path), "error": str(e)})

    return stats
```

- [ ] **Step 2: Create backend/tests/test_pipeline.py**

```python
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_compute_file_hash():
    from app.ingestion.pipeline import compute_file_hash

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test content")
        f.flush()
        hash1 = compute_file_hash(Path(f.name))
        assert len(hash1) == 64  # SHA-256 hex

    # Same content = same hash
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write("test content")
        f.flush()
        hash2 = compute_file_hash(Path(f.name))
        assert hash1 == hash2


@pytest.mark.asyncio
async def test_ingest_file_txt(client):
    """Integration test: ingest a text file through the full pipeline."""
    from tests.conftest import test_session_maker
    from app.ingestion.pipeline import ingest_file
    from app.models.document import DataSource, IngestionStatus, SourceType
    import uuid

    # Mock the embedder since Ollama isn't running in tests
    mock_embeddings = [[0.1] * 768]

    with patch("app.ingestion.pipeline.embed_batch", new_callable=AsyncMock) as mock_embed:
        mock_embed.return_value = mock_embeddings

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("This is a test document for ingestion.")
            f.flush()
            file_path = Path(f.name)

        async with test_session_maker() as session:
            # Create a data source first
            source = DataSource(
                name=f"test-source-{uuid.uuid4().hex[:8]}",
                source_type=SourceType.UPLOAD,
                created_by=uuid.uuid4(),  # Fake user ID for test
            )
            session.add(source)
            await session.flush()

            doc = await ingest_file(
                session=session,
                file_path=file_path,
                source_id=source.id,
            )

            assert doc.ingestion_status == IngestionStatus.COMPLETED
            assert doc.chunk_count >= 1
            assert doc.filename == file_path.name
            assert doc.file_type == "txt"
            mock_embed.assert_called_once()
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ingestion/pipeline.py backend/tests/test_pipeline.py
git commit -m "feat: ingestion pipeline orchestrator with parse → chunk → embed → store"
```

---

## Task 7: Celery Tasks for Async Ingestion

**Files:**
- Create: `backend/app/ingestion/tasks.py`
- Modify: `backend/app/worker.py`

- [ ] **Step 1: Create backend/app/ingestion/tasks.py**

```python
import asyncio
import uuid
from pathlib import Path

from app.worker import celery_app
from app.database import async_session_maker
from app.ingestion.pipeline import ingest_file, ingest_directory
from app.audit.logger import write_audit_log


def _run_async(coro):
    """Helper to run async code in Celery sync tasks."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(name="civicrecords.ingest_file", bind=True, max_retries=2)
def task_ingest_file(
    self,
    file_path: str,
    source_id: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    embed_model: str = "nomic-embed-text",
    user_id: str | None = None,
):
    """Celery task: ingest a single file."""

    async def _ingest():
        async with async_session_maker() as session:
            doc = await ingest_file(
                session=session,
                file_path=Path(file_path),
                source_id=uuid.UUID(source_id),
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                embed_model=embed_model,
            )
            await write_audit_log(
                session=session,
                action="ingest_file",
                resource_type="document",
                resource_id=str(doc.id),
                user_id=uuid.UUID(user_id) if user_id else None,
                details={
                    "filename": doc.filename,
                    "status": doc.ingestion_status.value,
                    "chunks": doc.chunk_count,
                },
            )
            return {"document_id": str(doc.id), "status": doc.ingestion_status.value}

    try:
        return _run_async(_ingest())
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(name="civicrecords.ingest_source", bind=True)
def task_ingest_source(
    self,
    source_id: str,
    user_id: str | None = None,
):
    """Celery task: ingest all files from a data source."""

    async def _ingest():
        async with async_session_maker() as session:
            from sqlalchemy import select
            from app.models.document import DataSource
            from datetime import datetime, timezone

            source = await session.get(DataSource, uuid.UUID(source_id))
            if not source:
                return {"error": "Source not found"}

            config = source.connection_config
            directory = Path(config.get("path", ""))
            if not directory.is_dir():
                return {"error": f"Directory not found: {directory}"}

            stats = await ingest_directory(
                session=session,
                directory=directory,
                source_id=source.id,
            )

            source.last_ingestion_at = datetime.now(timezone.utc)
            await session.commit()

            await write_audit_log(
                session=session,
                action="ingest_source",
                resource_type="data_source",
                resource_id=source_id,
                user_id=uuid.UUID(user_id) if user_id else None,
                details=stats,
            )

            return stats

    return _run_async(_ingest())
```

- [ ] **Step 2: Update backend/app/worker.py to import tasks**

```python
from celery import Celery

from app.config import settings

celery_app = Celery(
    "civicrecords",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(name="civicrecords.health")
def health_check():
    """Simple health check task."""
    return {"status": "ok"}


# Import tasks so Celery discovers them
import app.ingestion.tasks  # noqa: F401, E402
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/ingestion/tasks.py backend/app/worker.py
git commit -m "feat: Celery tasks for async file and source ingestion"
```

---

## Task 8: Data Source and Document API Endpoints

**Files:**
- Create: `backend/app/datasources/__init__.py`
- Create: `backend/app/datasources/router.py`
- Create: `backend/app/documents/__init__.py`
- Create: `backend/app/documents/router.py`
- Create: `backend/tests/test_datasources.py`
- Create: `backend/tests/test_documents.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Create backend/app/datasources/router.py**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.logger import write_audit_log
from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.document import DataSource, Document, DocumentChunk, IngestionStatus, SourceType
from app.models.user import User, UserRole
from app.schemas.document import (
    DataSourceCreate, DataSourceRead, DataSourceUpdate, IngestionStats,
)

router = APIRouter(prefix="/datasources", tags=["datasources"])


@router.post("/", response_model=DataSourceRead, status_code=201)
async def create_datasource(
    data: DataSourceCreate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    existing = await session.execute(
        select(DataSource).where(DataSource.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Name already taken")

    source = DataSource(
        name=data.name,
        source_type=data.source_type,
        connection_config=data.connection_config,
        schedule_minutes=data.schedule_minutes,
        created_by=user.id,
    )
    session.add(source)
    await session.commit()
    await session.refresh(source)

    await write_audit_log(
        session=session,
        action="create_datasource",
        resource_type="data_source",
        resource_id=str(source.id),
        user_id=user.id,
        details={"name": data.name, "type": data.source_type.value},
    )

    return source


@router.get("/", response_model=list[DataSourceRead])
async def list_datasources(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    result = await session.execute(
        select(DataSource).order_by(DataSource.created_at.desc())
    )
    return result.scalars().all()


@router.patch("/{source_id}", response_model=DataSourceRead)
async def update_datasource(
    source_id: uuid.UUID,
    data: DataSourceUpdate,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.ADMIN)),
):
    source = await session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    if data.name is not None:
        source.name = data.name
    if data.connection_config is not None:
        source.connection_config = data.connection_config
    if data.schedule_minutes is not None:
        source.schedule_minutes = data.schedule_minutes
    if data.is_active is not None:
        source.is_active = data.is_active

    await session.commit()
    await session.refresh(source)
    return source


@router.post("/{source_id}/ingest")
async def trigger_ingestion(
    source_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Trigger ingestion for a data source. Runs async via Celery."""
    source = await session.get(DataSource, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Data source not found")

    from app.ingestion.tasks import task_ingest_source
    task = task_ingest_source.delay(
        source_id=str(source_id),
        user_id=str(user.id),
    )

    return {"task_id": task.id, "status": "queued"}


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Upload a single file for ingestion."""
    import tempfile
    from pathlib import Path

    # Save uploaded file to temp location
    with tempfile.NamedTemporaryFile(
        delete=False, suffix=f"_{file.filename}"
    ) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    # Find or create an "uploads" data source
    result = await session.execute(
        select(DataSource).where(
            DataSource.name == "_uploads",
            DataSource.source_type == SourceType.UPLOAD,
        )
    )
    upload_source = result.scalar_one_or_none()
    if not upload_source:
        upload_source = DataSource(
            name="_uploads",
            source_type=SourceType.UPLOAD,
            created_by=user.id,
        )
        session.add(upload_source)
        await session.flush()

    from app.ingestion.tasks import task_ingest_file
    task = task_ingest_file.delay(
        file_path=tmp_path,
        source_id=str(upload_source.id),
        user_id=str(user.id),
    )

    return {"task_id": task.id, "filename": file.filename, "status": "queued"}


@router.get("/stats", response_model=IngestionStats)
async def ingestion_stats(
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    """Get ingestion statistics."""
    total_sources = (await session.execute(
        select(func.count(DataSource.id))
    )).scalar() or 0

    active_sources = (await session.execute(
        select(func.count(DataSource.id)).where(DataSource.is_active.is_(True))
    )).scalar() or 0

    total_documents = (await session.execute(
        select(func.count(Document.id))
    )).scalar() or 0

    total_chunks = (await session.execute(
        select(func.count(DocumentChunk.id))
    )).scalar() or 0

    # Documents by status
    status_counts = {}
    for status in IngestionStatus:
        count = (await session.execute(
            select(func.count(Document.id)).where(
                Document.ingestion_status == status
            )
        )).scalar() or 0
        status_counts[status.value] = count

    return IngestionStats(
        total_sources=total_sources,
        active_sources=active_sources,
        total_documents=total_documents,
        documents_by_status=status_counts,
        total_chunks=total_chunks,
    )
```

- [ ] **Step 2: Create backend/app/datasources/__init__.py**

```python
from app.datasources.router import router as datasources_router

__all__ = ["datasources_router"]
```

- [ ] **Step 3: Create backend/app/documents/router.py**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_role
from app.database import get_async_session
from app.models.document import Document, DocumentChunk, IngestionStatus
from app.models.user import User, UserRole
from app.schemas.document import DocumentRead, DocumentChunkRead

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/", response_model=list[DocumentRead])
async def list_documents(
    source_id: uuid.UUID | None = None,
    status: IngestionStatus | None = None,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    stmt = select(Document).order_by(Document.ingested_at.desc().nulls_last())

    if source_id:
        stmt = stmt.where(Document.source_id == source_id)
    if status:
        stmt = stmt.where(Document.ingestion_status == status)

    stmt = stmt.offset(offset).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentRead)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    doc = await session.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.get("/{document_id}/chunks", response_model=list[DocumentChunkRead])
async def list_chunks(
    document_id: uuid.UUID,
    limit: int = Query(default=50, le=500),
    offset: int = 0,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(require_role(UserRole.STAFF)),
):
    result = await session.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()
```

- [ ] **Step 4: Create backend/app/documents/__init__.py**

```python
from app.documents.router import router as documents_router

__all__ = ["documents_router"]
```

- [ ] **Step 5: Update backend/app/main.py — add new routers**

Add after the admin router include:

```python
from app.datasources import datasources_router
from app.documents import documents_router

app.include_router(datasources_router)
app.include_router(documents_router)
```

- [ ] **Step 6: Create backend/tests/test_datasources.py**

```python
import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_datasource(client: AsyncClient, admin_token: str):
    resp = await client.post(
        "/datasources/",
        json={
            "name": f"test-source-{uuid.uuid4().hex[:8]}",
            "source_type": "directory",
            "connection_config": {"path": "/data/test"},
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["source_type"] == "directory"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_datasource_requires_admin(client: AsyncClient, staff_token: str):
    resp = await client.post(
        "/datasources/",
        json={"name": "test", "source_type": "upload"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_list_datasources(client: AsyncClient, admin_token: str):
    await client.post(
        "/datasources/",
        json={
            "name": f"list-test-{uuid.uuid4().hex[:8]}",
            "source_type": "upload",
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    resp = await client.get(
        "/datasources/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


@pytest.mark.asyncio
async def test_ingestion_stats(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/datasources/stats",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "total_sources" in data
    assert "total_documents" in data
    assert "total_chunks" in data
```

- [ ] **Step 7: Create backend/tests/test_documents.py**

```python
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_documents_empty(client: AsyncClient, admin_token: str):
    resp = await client.get(
        "/documents/",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_document_not_found(client: AsyncClient, admin_token: str):
    import uuid
    resp = await client.get(
        f"/documents/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/datasources/ backend/app/documents/ \
  backend/tests/test_datasources.py backend/tests/test_documents.py \
  backend/app/main.py
git commit -m "feat: data source CRUD, document listing, file upload, and ingestion trigger endpoints"
```

---

## Task 9: Frontend — Data Sources and Ingestion Dashboard

**Files:**
- Create: `frontend/src/pages/DataSources.tsx`
- Create: `frontend/src/pages/Ingestion.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Create frontend/src/pages/DataSources.tsx**

```tsx
import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface DataSource {
  id: string;
  name: string;
  source_type: string;
  connection_config: Record<string, string>;
  is_active: boolean;
  created_at: string;
  last_ingestion_at: string | null;
}

interface Props {
  token: string;
}

export default function DataSources({ token }: Props) {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [error, setError] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [path, setPath] = useState("");
  const [ingesting, setIngesting] = useState<string | null>(null);

  const loadSources = () => {
    apiFetch<DataSource[]>("/datasources/", { token })
      .then(setSources)
      .catch((e) => setError(e.message));
  };

  useEffect(loadSources, [token]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await apiFetch("/datasources/", {
        token,
        method: "POST",
        body: JSON.stringify({
          name,
          source_type: "directory",
          connection_config: { path },
        }),
      });
      setName("");
      setPath("");
      setShowForm(false);
      loadSources();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleIngest = async (sourceId: string) => {
    setIngesting(sourceId);
    try {
      await apiFetch(`/datasources/${sourceId}/ingest`, {
        token,
        method: "POST",
      });
    } catch (err: any) {
      setError(err.message);
    }
    setIngesting(null);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Data Sources</h2>
        <button
          onClick={() => setShowForm(!showForm)}
          className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700"
        >
          {showForm ? "Cancel" : "Add Source"}
        </button>
      </div>

      {error && <p className="text-red-600 mb-4">{error}</p>}

      {showForm && (
        <form onSubmit={handleCreate} className="bg-white p-4 rounded-lg border border-gray-200 mb-4 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Directory Path</label>
            <input
              value={path}
              onChange={(e) => setPath(e.target.value)}
              placeholder="/data/city-documents"
              className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
              required
            />
          </div>
          <button type="submit" className="bg-blue-600 text-white px-4 py-2 rounded-md text-sm font-medium hover:bg-blue-700">
            Create Source
          </button>
        </form>
      )}

      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="text-left px-4 py-3 font-medium text-gray-600">Name</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Last Ingestion</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((s) => (
              <tr key={s.id} className="border-b border-gray-100">
                <td className="px-4 py-3 text-gray-900">{s.name}</td>
                <td className="px-4 py-3 text-gray-600">{s.source_type}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs ${s.is_active ? "text-green-600" : "text-red-600"}`}>
                    {s.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500">
                  {s.last_ingestion_at ? new Date(s.last_ingestion_at).toLocaleString() : "Never"}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleIngest(s.id)}
                    disabled={ingesting === s.id}
                    className="text-blue-600 hover:text-blue-800 text-sm font-medium disabled:opacity-50"
                  >
                    {ingesting === s.id ? "Ingesting..." : "Ingest Now"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create frontend/src/pages/Ingestion.tsx**

```tsx
import { useState, useEffect } from "react";
import { apiFetch } from "@/lib/api";

interface Stats {
  total_sources: number;
  active_sources: number;
  total_documents: number;
  documents_by_status: Record<string, number>;
  total_chunks: number;
}

interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  ingestion_status: string;
  ingestion_error: string | null;
  chunk_count: number;
  ingested_at: string | null;
}

interface Props {
  token: string;
}

export default function Ingestion({ token }: Props) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch<Stats>("/datasources/stats", { token })
      .then(setStats)
      .catch((e) => setError(e.message));
    apiFetch<Document[]>("/documents/?limit=50", { token })
      .then(setDocs)
      .catch((e) => setError(e.message));
  }, [token]);

  const statusColors: Record<string, string> = {
    completed: "text-green-600",
    processing: "text-blue-600",
    pending: "text-yellow-600",
    failed: "text-red-600",
  };

  return (
    <div>
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Ingestion Dashboard</h2>
      {error && <p className="text-red-600 mb-4">{error}</p>}

      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Sources</p>
            <p className="text-2xl font-semibold text-gray-900">{stats.active_sources}/{stats.total_sources}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Documents</p>
            <p className="text-2xl font-semibold text-gray-900">{stats.total_documents}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Chunks</p>
            <p className="text-2xl font-semibold text-gray-900">{stats.total_chunks}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Completed</p>
            <p className="text-2xl font-semibold text-green-600">{stats.documents_by_status.completed || 0}</p>
          </div>
          <div className="bg-white p-4 rounded-lg border border-gray-200">
            <p className="text-sm text-gray-500">Failed</p>
            <p className="text-2xl font-semibold text-red-600">{stats.documents_by_status.failed || 0}</p>
          </div>
        </div>
      )}

      <h3 className="text-md font-semibold text-gray-900 mb-3">Recent Documents</h3>
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 bg-gray-50">
              <th className="text-left px-4 py-3 font-medium text-gray-600">Filename</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Type</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Size</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Status</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Chunks</th>
              <th className="text-left px-4 py-3 font-medium text-gray-600">Ingested</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((d) => (
              <tr key={d.id} className="border-b border-gray-100">
                <td className="px-4 py-3 text-gray-900">{d.filename}</td>
                <td className="px-4 py-3 text-gray-600">{d.file_type}</td>
                <td className="px-4 py-3 text-gray-600">{(d.file_size / 1024).toFixed(1)} KB</td>
                <td className="px-4 py-3">
                  <span className={`text-xs font-medium ${statusColors[d.ingestion_status] || "text-gray-600"}`}>
                    {d.ingestion_status}
                  </span>
                  {d.ingestion_error && (
                    <span className="block text-xs text-red-400 truncate max-w-xs" title={d.ingestion_error}>
                      {d.ingestion_error}
                    </span>
                  )}
                </td>
                <td className="px-4 py-3 text-gray-600">{d.chunk_count}</td>
                <td className="px-4 py-3 text-gray-500">
                  {d.ingested_at ? new Date(d.ingested_at).toLocaleString() : "—"}
                </td>
              </tr>
            ))}
            {docs.length === 0 && (
              <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400">No documents ingested yet</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update frontend/src/App.tsx — add new routes and nav links**

Add imports and routes for DataSources and Ingestion pages:

```tsx
import { useState, useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";
import DataSources from "./pages/DataSources";
import Ingestion from "./pages/Ingestion";

export default function App() {
  const [token, setToken] = useState<string | null>(
    localStorage.getItem("token")
  );

  useEffect(() => {
    if (token) localStorage.setItem("token", token);
    else localStorage.removeItem("token");
  }, [token]);

  if (!token) {
    return <Login onLogin={setToken} />;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <h1 className="text-lg font-semibold text-gray-900">CivicRecords AI</h1>
          <a href="/" className="text-sm text-gray-600 hover:text-gray-900">Dashboard</a>
          <a href="/sources" className="text-sm text-gray-600 hover:text-gray-900">Sources</a>
          <a href="/ingestion" className="text-sm text-gray-600 hover:text-gray-900">Ingestion</a>
          <a href="/users" className="text-sm text-gray-600 hover:text-gray-900">Users</a>
        </div>
        <button
          onClick={() => setToken(null)}
          className="text-sm text-gray-500 hover:text-gray-700"
        >
          Sign out
        </button>
      </nav>
      <main className="p-6 max-w-7xl mx-auto">
        <Routes>
          <Route path="/" element={<Dashboard token={token} />} />
          <Route path="/sources" element={<DataSources token={token} />} />
          <Route path="/ingestion" element={<Ingestion token={token} />} />
          <Route path="/users" element={<Users token={token} />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
    </div>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/DataSources.tsx frontend/src/pages/Ingestion.tsx \
  frontend/src/App.tsx
git commit -m "feat: data sources configuration and ingestion dashboard UI"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Data source configuration UI — Task 8 (API) + Task 9 (frontend)
- [x] Fast track parsers: PDF, DOCX, XLSX, CSV, email, HTML, text — Task 2
- [x] LLM track: Gemma 4 multimodal for scans/images, Tesseract fallback — Task 5
- [x] Chunking engine (configurable per source type) — Task 3
- [x] Embedding via nomic-embed-text through Ollama — Task 4
- [x] Celery workers for async processing — Task 7
- [x] Incremental ingestion (file hash dedup) — Task 6 (pipeline.py checks file_hash)
- [x] Ingestion dashboard (status, document count, errors) — Task 9
- [x] All ingestion actions audit-logged — Task 7 (tasks.py calls write_audit_log)
- [x] Exit criteria: Admin connects directory → system ingests → dashboard shows status

**Placeholder scan:** No TBDs or TODOs. All code blocks complete.

**Type consistency:**
- `IngestionStatus` enum used consistently in models, schemas, and API responses
- `SourceType` enum used consistently
- `ParseResult` and `ParsedPage` dataclasses used by all parsers
- `Chunk` dataclass flows from chunker → pipeline → database
- `embed_batch()` signature matches usage in pipeline.py
- Vector dimension 768 matches nomic-embed-text output

**Note:** The embedding dimension (768) is hardcoded for nomic-embed-text. If the user swaps to a different embedding model with a different dimension, the `Vector(768)` in the model and migration would need updating. This is acceptable for MVP — model swapping with dimension changes would be a schema migration in a future version.
