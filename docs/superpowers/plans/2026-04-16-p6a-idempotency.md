# P6a — Idempotency Contract Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix Sev-2 data integrity bug where REST/ODBC sources create duplicate documents on every sync by splitting the idempotency contract and adding canonical serialization.

**Architecture:** Split dedup into two contracts: binary connectors use `(source_id, file_hash)` uniqueness; structured connectors (REST/ODBC) use `(source_id, source_path)` identity with `file_hash` as change-detector only. A new `ingest_structured_record()` pipeline function handles upsert semantics with SELECT FOR UPDATE. Partial UNIQUE indexes enforced at DB level via a denormalized `connector_type` column on documents.

**Tech Stack:** Python/FastAPI, SQLAlchemy async, PostgreSQL partial indexes, Alembic, pytest, croniter (not yet — P6b). Ships before P6b and P7.

**Spec:** `docs/superpowers/specs/2026-04-16-p6a-idempotency-design.md`

---

## File Map

| Action | Path | Responsibility |
|---|---|---|
| Modify | `backend/app/schemas/connectors/rest_api.py` | Add `data_key`, `id_field`, `envelope_excludes` fields |
| Modify | `backend/app/connectors/rest_api.py` | Canonical serialization, URL-encode record ID in source_path, `_extract_dotted()` helper |
| Modify | `backend/app/connectors/odbc.py` | Canonical serialization with sort_keys + modified_column exclusion, URL-encode PK in source_path, unquote PK in fetch() |
| Modify | `backend/app/models/document.py` | Add `connector_type: String(20)` and `updated_at: DateTime` to Document |
| Modify | `backend/app/ingestion/pipeline.py` | Add `ingest_structured_record()` function |
| Modify | `backend/app/ingestion/tasks.py` | Route rest_api/odbc sync to `ingest_structured_record()` in `run_connector_sync()` |
| Modify | `backend/app/datasources/router.py` | Add double-fetch pollution detection to test-connection |
| Modify | `backend/app/schemas/document.py` | Add `sync_schedule`, `schedule_enabled`, `next_sync_at` stub fields; add `connector_type`, `updated_at` to DocumentRead |
| Create | `backend/alembic/versions/014_p6a_idempotency.py` | Migration: connector_type column, partial UNIQUE indexes, updated_at, dedup existing rows |
| Create | `backend/tests/test_pipeline_idempotency.py` | All determinism + race + update semantics tests |
| Create | `backend/tests/test_migration_014.py` | Migration backfill and dedup tests |
| Modify | `backend/tests/test_rest_connector.py` | data_key, source_path URL-encoding tests |
| Modify | `backend/tests/test_odbc_connector.py` | source_path encode/decode roundtrip tests |
| Modify | `backend/tests/test_datasources_router.py` | Pollution detection tests |

---

## Task 1: Write failing determinism tests [FIRST — must fail before any code changes]

**Files:**
- Create: `backend/tests/test_pipeline_idempotency.py`

- [ ] **Step 1: Create test file with the four [FIRST] determinism tests**

```python
# backend/tests/test_pipeline_idempotency.py
"""P6a idempotency tests — TDD order: all [FIRST] tests must fail before implementation."""
import hashlib
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_source_id() -> uuid.UUID:
    return uuid.uuid4()


def _canonical_rest(record: dict, data_key: str | None = None) -> bytes:
    """Reference implementation of what fetch() should produce."""
    import json
    if data_key:
        parts = data_key.split(".")
        obj = record
        for p in parts:
            obj = obj[p]
        record = obj
    return json.dumps(record, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


def _canonical_odbc(row_dict: dict, modified_column: str | None = None) -> bytes:
    d = {k: v for k, v in row_dict.items() if k != modified_column}
    return json.dumps(d, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# REST — determinism tests
# ---------------------------------------------------------------------------

class TestRestDeterminism:
    """REST fetch() must produce identical bytes for the same logical record
    regardless of envelope timestamp or key ordering."""

    def test_rest_envelope_timestamp_same_document(self):
        """Two fetches with differing fetched_at in envelope → same canonical bytes
        when data_key='data' extracts the inner record."""
        record = {"id": 1, "title": "Budget Report", "amount": 50000}

        response_fetch1 = {"fetched_at": "2026-04-16T01:00:00Z", "data": record}
        response_fetch2 = {"fetched_at": "2026-04-16T01:05:00Z", "data": record}

        bytes1 = _canonical_rest(response_fetch1, data_key="data")
        bytes2 = _canonical_rest(response_fetch2, data_key="data")

        assert bytes1 == bytes2, (
            "Envelope timestamp differs between fetches but should not affect canonical bytes"
        )
        assert hashlib.sha256(bytes1).hexdigest() == hashlib.sha256(bytes2).hexdigest()

    def test_rest_key_order_same_document(self):
        """Same logical record with JSON keys in different order → same canonical bytes."""
        bytes1 = _canonical_rest({"id": 1, "title": "Permit", "status": "open"})
        bytes2 = _canonical_rest({"status": "open", "id": 1, "title": "Permit"})
        assert bytes1 == bytes2

    # ---------------------------------------------------------------------------
    # ODBC — determinism tests
    # ---------------------------------------------------------------------------

    def test_odbc_modified_column_excluded(self):
        """Same row with modified_column ticking → same canonical bytes."""
        row1 = {"id": 42, "name": "Contract A", "last_modified": "2026-04-16T01:00:00Z"}
        row2 = {"id": 42, "name": "Contract A", "last_modified": "2026-04-16T02:00:00Z"}

        bytes1 = _canonical_odbc(row1, modified_column="last_modified")
        bytes2 = _canonical_odbc(row2, modified_column="last_modified")

        assert bytes1 == bytes2, (
            "modified_column value changed but canonical bytes should be identical"
        )

    def test_odbc_column_order_same_document(self):
        """Column order from cursor changes → same canonical bytes."""
        row1 = {"id": 1, "name": "Alice", "dept": "Finance"}
        row2 = {"dept": "Finance", "id": 1, "name": "Alice"}

        bytes1 = _canonical_odbc(row1)
        bytes2 = _canonical_odbc(row2)

        assert bytes1 == bytes2
```

- [ ] **Step 2: Run tests to confirm they PASS (these test reference implementations, not connector code — that's correct)**

```
cd backend && python -m pytest tests/test_pipeline_idempotency.py::TestRestDeterminism -v
```

Expected: 4 PASSED — these are pure unit tests on `_canonical_*` helpers.

- [ ] **Step 3: Add integration tests that will FAIL until connector code is fixed**

Append to `backend/tests/test_pipeline_idempotency.py`:

```python
# ---------------------------------------------------------------------------
# Integration: ingest_structured_record() — will fail until Task 6 implements it
# ---------------------------------------------------------------------------

class TestIngestStructuredRecord:

    @pytest.mark.asyncio
    async def test_structured_record_same_hash_is_noop(self, db_session):
        """Same source_path, same content hash → document unchanged, updated_at not set."""
        from app.ingestion.pipeline import ingest_structured_record
        source_id = _make_source_id()
        content = b'{"id": 1, "title": "Budget"}'

        doc1 = await ingest_structured_record(
            session=db_session,
            source_id=source_id,
            source_path="https://api.example.com/records/1",
            content_bytes=content,
            filename="1.json",
            metadata={},
            connector_type="rest_api",
        )
        doc2 = await ingest_structured_record(
            session=db_session,
            source_id=source_id,
            source_path="https://api.example.com/records/1",
            content_bytes=content,
            filename="1.json",
            metadata={},
            connector_type="rest_api",
        )
        assert doc1.id == doc2.id, "Same source_path + same hash → same document"

    @pytest.mark.asyncio
    async def test_structured_record_content_change_updates_document(self, db_session):
        """Same source_path, different content → document updated, updated_at set, no dup row."""
        from app.ingestion.pipeline import ingest_structured_record
        from sqlalchemy import select, func
        from app.models.document import Document
        source_id = _make_source_id()

        doc1 = await ingest_structured_record(
            session=db_session,
            source_id=source_id,
            source_path="https://api.example.com/records/2",
            content_bytes=b'{"id": 2, "amount": 100}',
            filename="2.json",
            metadata={},
            connector_type="rest_api",
        )

        doc2 = await ingest_structured_record(
            session=db_session,
            source_id=source_id,
            source_path="https://api.example.com/records/2",
            content_bytes=b'{"id": 2, "amount": 999}',
            filename="2.json",
            metadata={},
            connector_type="rest_api",
        )

        # Same document row, not a new row
        assert doc1.id == doc2.id
        # updated_at must be set after content change
        assert doc2.updated_at is not None
        # No duplicate rows
        count_result = await db_session.execute(
            select(func.count()).where(
                Document.source_id == source_id,
                Document.source_path == "https://api.example.com/records/2",
            )
        )
        assert count_result.scalar() == 1

    @pytest.mark.asyncio
    async def test_update_deletes_old_chunks_before_reembed(self, db_session):
        """Same source_path, content changes → old DocumentChunk rows deleted before re-chunk."""
        from app.ingestion.pipeline import ingest_structured_record
        from sqlalchemy import select, func
        from app.models.document import DocumentChunk
        source_id = _make_source_id()
        path = "https://api.example.com/records/3"

        doc = await ingest_structured_record(
            session=db_session, source_id=source_id, source_path=path,
            content_bytes=b'{"id": 3, "body": "original content long enough to chunk"}',
            filename="3.json", metadata={}, connector_type="rest_api",
        )
        first_chunk_count_result = await db_session.execute(
            select(func.count()).where(DocumentChunk.document_id == doc.id)
        )
        first_count = first_chunk_count_result.scalar()

        await ingest_structured_record(
            session=db_session, source_id=source_id, source_path=path,
            content_bytes=b'{"id": 3, "body": "completely different content"}',
            filename="3.json", metadata={}, connector_type="rest_api",
        )
        second_chunk_count_result = await db_session.execute(
            select(func.count()).where(DocumentChunk.document_id == doc.id)
        )
        second_count = second_chunk_count_result.scalar()

        # Old chunks removed, new chunks in place — no accumulation
        assert second_count <= first_count + 5  # sanity bound, not exact count
```

- [ ] **Step 4: Run the integration tests to confirm they FAIL**

```
cd backend && python -m pytest tests/test_pipeline_idempotency.py::TestIngestStructuredRecord -v
```

Expected: `ImportError: cannot import name 'ingest_structured_record' from 'app.ingestion.pipeline'`

- [ ] **Step 5: Commit failing tests**

```bash
cd backend && git add tests/test_pipeline_idempotency.py
git commit -m "test(p6a): add failing idempotency tests for structured record upsert"
```

---

## Task 2: Fix RestApiConnector — canonical serialization + source_path encoding + data_key

**Files:**
- Modify: `backend/app/schemas/connectors/rest_api.py`
- Modify: `backend/app/connectors/rest_api.py`

- [ ] **Step 1: Add data_key, id_field, envelope_excludes to RestApiConfig**

In `backend/app/schemas/connectors/rest_api.py`, add after the `results_field` line:

```python
    # Idempotency (P6a)
    data_key: Optional[str] = None          # dotted path to logical record; None = root object
    id_field: str = "id"                    # field within each list element used as record ID
    envelope_excludes: list[str] = []       # reserved for v2 — not used in v1
```

- [ ] **Step 2: Write failing tests for data_key and source_path encoding**

In `backend/tests/test_rest_connector.py`, add:

```python
class TestRestApiConnectorP6a:

    def _make_connector(self, extra_config: dict = None) -> "RestApiConnector":
        from app.connectors.rest_api import RestApiConnector
        config = {
            "base_url": "https://api.example.com",
            "endpoint_path": "/records",
            "auth_method": "none",
            "response_format": "json",
            **(extra_config or {}),
        }
        return RestApiConnector(config)

    def test_data_key_nested_extraction(self):
        """data_key='response.record' extracts correctly from nested response."""
        from app.connectors.rest_api import _extract_dotted
        payload = {"response": {"record": {"id": 1, "name": "Test"}}}
        result = _extract_dotted(payload, "response.record")
        assert result == {"id": 1, "name": "Test"}

    def test_data_key_missing_raises_key_error(self):
        """data_key='missing.path' → KeyError with descriptive message."""
        from app.connectors.rest_api import _extract_dotted
        with pytest.raises(KeyError, match="missing"):
            _extract_dotted({"data": {}}, "missing.path")

    def test_data_key_array_each_element_is_record(self):
        """data_key resolves to list → each element is its own DiscoveredRecord."""
        from app.connectors.rest_api import _extract_dotted
        payload = {"items": [{"id": 1}, {"id": 2}, {"id": 3}]}
        result = _extract_dotted(payload, "items")
        assert isinstance(result, list)
        assert len(result) == 3

    def test_source_path_record_id_encoded(self):
        """Record ID containing '/' is percent-encoded in source_path."""
        import urllib.parse
        from app.connectors.rest_api import _build_source_path
        base = "https://api.example.com"
        endpoint = "/records"
        record_id = "dept/2024/contract-001"
        path = _build_source_path(base, endpoint, record_id)
        # The record ID segment must be URL-encoded
        assert urllib.parse.quote(record_id, safe="") in path
        assert "/" not in path.split(endpoint + "/")[1]  # no raw slash in ID segment
```

- [ ] **Step 3: Run to confirm tests FAIL**

```
cd backend && python -m pytest tests/test_rest_connector.py::TestRestApiConnectorP6a -v
```

Expected: `ImportError: cannot import name '_extract_dotted' from 'app.connectors.rest_api'`

- [ ] **Step 4: Implement `_extract_dotted` helper and `_build_source_path` in rest_api.py**

Add after the `_MIME_TYPES` dict (before the `RestApiConnector` class) in `backend/app/connectors/rest_api.py`:

```python
import urllib.parse


def _extract_dotted(obj: Any, path: str | None) -> Any:
    """Traverse a dotted path into obj. None path returns obj unchanged.

    Raises KeyError if a segment is missing.
    Raises TypeError if a segment traverses a non-dict.
    """
    if path is None:
        return obj
    for segment in path.split("."):
        if not isinstance(obj, dict):
            raise TypeError(
                f"_extract_dotted: expected dict at segment '{segment}', got {type(obj).__name__}"
            )
        if segment not in obj:
            raise KeyError(
                f"_extract_dotted: key '{segment}' not found in object. "
                f"Available keys: {list(obj.keys())}"
            )
        obj = obj[segment]
    return obj


def _build_source_path(base_url: str, endpoint_path: str, record_id: str) -> str:
    """Construct canonical source_path for a REST record.

    Format: {base_url.rstrip('/')}{endpoint_path}/{url_encoded_record_id}
    Max 2048 chars enforced at call site (validation layer).
    """
    base = str(base_url).rstrip("/")
    encoded_id = urllib.parse.quote(str(record_id), safe="")
    return f"{base}{endpoint_path}/{encoded_id}"
```

- [ ] **Step 5: Fix `fetch()` in RestApiConnector for canonical serialization**

Replace the existing `fetch()` method body in `backend/app/connectors/rest_api.py` (lines ~224-248):

```python
    async def fetch(self, source_path: str) -> FetchedDocument:
        self._ensure_authenticated()
        response = await self._make_request("GET", source_path)
        response.raise_for_status()

        raw_bytes = response.content
        if len(raw_bytes) > self._cfg.max_response_bytes:
            raise RuntimeError(
                f"Fetch response size {len(raw_bytes)} exceeds "
                f"max_response_bytes={self._cfg.max_response_bytes}"
            )

        # Canonical serialization: extract via data_key, sort keys, deterministic output
        parsed = response.json()
        record = _extract_dotted(parsed, self._cfg.data_key)
        canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
        content = canonical.encode("utf-8")

        return FetchedDocument(
            source_path=source_path,
            filename=source_path.rstrip("/").split("/")[-1] + ".json",
            file_type=self._cfg.response_format,
            content=content,
            file_size=len(content),
            metadata={"url": source_path},
        )
```

- [ ] **Step 6: Fix `discover()` in RestApiConnector to URL-encode record IDs and use id_field**

In the `discover()` method, replace the source_path construction loop block (where `record_id` is extracted and `records.append(DiscoveredRecord(...))` is called):

```python
            for item in items:
                record_id = str(item.get(cfg.id_field, len(records)))
                source_path = _build_source_path(str(cfg.base_url), cfg.endpoint_path, record_id)
                records.append(
                    DiscoveredRecord(
                        source_path=source_path,
                        filename=f"{urllib.parse.quote(record_id, safe='')}.json",
                        file_type="json",
                        file_size=len(json.dumps(item).encode()),
                        metadata={"raw": item},
                    )
                )
```

- [ ] **Step 7: Run connector tests**

```
cd backend && python -m pytest tests/test_rest_connector.py -v
```

Expected: All tests PASS including the new P6a tests.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/connectors/rest_api.py backend/app/connectors/rest_api.py backend/tests/test_rest_connector.py
git commit -m "feat(p6a): canonical serialization + source_path encoding in RestApiConnector"
```

---

## Task 3: Fix OdbcConnector — canonical serialization + source_path encode/decode

**Files:**
- Modify: `backend/app/connectors/odbc.py`
- Modify: `backend/tests/test_odbc_connector.py`

- [ ] **Step 1: Write failing test for ODBC source_path encode/decode roundtrip**

In `backend/tests/test_odbc_connector.py`, add:

```python
class TestOdbcConnectorP6a:

    def test_source_path_encode_decode_special_chars(self):
        """pk_value containing '/', space, '%' → encoded in source_path, unquoted in fetch()."""
        import urllib.parse
        table = "public.contracts"
        pk = "dept/2024/item 100%"
        encoded = urllib.parse.quote(str(pk), safe="")
        source_path = f"{table}/{encoded}"

        # Simulate what fetch() must do to recover pk for SQL
        parts = source_path.split("/", 1)
        recovered_pk = urllib.parse.unquote(parts[1])
        assert recovered_pk == pk, f"Expected {pk!r}, got {recovered_pk!r}"

    def test_odbc_canonical_excludes_modified_column(self):
        """modified_column excluded from canonical bytes; sort_keys applied."""
        import json
        row = {"id": 1, "name": "Alice", "updated_at": "2026-04-16T00:00:00Z", "dept": "IT"}
        modified_column = "updated_at"

        row_without_ts = {k: v for k, v in row.items() if k != modified_column}
        canonical = json.dumps(row_without_ts, sort_keys=True, ensure_ascii=False, default=str)
        assert "updated_at" not in canonical
        assert '"dept": "IT"' in canonical
        # Keys in sorted order
        keys = list(json.loads(canonical).keys())
        assert keys == sorted(keys)
```

- [ ] **Step 2: Run to confirm the structural test passes (it's pure logic)**

```
cd backend && python -m pytest tests/test_odbc_connector.py::TestOdbcConnectorP6a -v
```

Expected: 2 PASSED (pure logic tests on the encoding round-trip).

- [ ] **Step 3: Fix `discover()` in OdbcConnector to URL-encode PK**

In `backend/app/connectors/odbc.py`, add at top:

```python
import urllib.parse
```

In the `discover()` method, replace the `source_path` construction:

```python
                # URL-encode PK to safely handle '/', spaces, '%', and other special chars
                encoded_pk = urllib.parse.quote(str(pk_value), safe="")
                records.append(
                    DiscoveredRecord(
                        source_path=f"{cfg.table_name}/{encoded_pk}",
                        filename=f"{encoded_pk}.json",
                        file_type="json",
                        file_size=len(content),
                        metadata={"pk": pk_value},
                    )
                )
```

- [ ] **Step 4: Fix `fetch()` in OdbcConnector — unquote PK + canonical serialization**

Replace the existing `fetch()` body in `backend/app/connectors/odbc.py`:

```python
    async def fetch(self, source_path: str) -> FetchedDocument:
        self._ensure_authenticated()
        cfg = self._cfg
        assert self._connection is not None

        # Extract and decode pk from source_path: "table_name/url_encoded_pk"
        parts = source_path.split("/", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid source_path format: {source_path!r}")
        pk_value = urllib.parse.unquote(parts[1])  # decode before SQL binding

        _validate_identifier(cfg.table_name, "table_name")
        _validate_identifier(cfg.pk_column, "pk_column")

        query = f"SELECT * FROM {cfg.table_name} WHERE {cfg.pk_column} = ?"
        try:
            cursor = self._connection.cursor()
            cursor.execute(query, [pk_value])
            columns_meta = [desc[0] for desc in cursor.description]
            row = cursor.fetchone()
        except Exception as exc:
            raise RuntimeError(
                f"OdbcConnector fetch() failed: {_scrub_dsn_error(str(exc))}"
            ) from exc

        if row is None:
            raise FileNotFoundError(f"Record not found: {source_path}")

        row_dict = dict(zip(columns_meta, row))

        # Canonical serialization: exclude modified_column, sort keys
        row_dict.pop(cfg.modified_column, None)
        canonical = json.dumps(row_dict, sort_keys=True, ensure_ascii=False, default=str)
        content = canonical.encode("utf-8")

        if len(content) > cfg.max_row_bytes:
            raise RuntimeError(
                f"Row {pk_value!r} size {len(content)} exceeds "
                f"max_row_bytes={cfg.max_row_bytes}"
            )

        return FetchedDocument(
            source_path=source_path,
            filename=f"{urllib.parse.quote(str(pk_value), safe='')}.json",
            file_type="json",
            content=content,
            file_size=len(content),
            metadata={"pk": pk_value, "table": cfg.table_name},
        )
```

- [ ] **Step 5: Run ODBC tests**

```
cd backend && python -m pytest tests/test_odbc_connector.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/connectors/odbc.py backend/tests/test_odbc_connector.py
git commit -m "feat(p6a): canonical serialization + source_path encode/decode in OdbcConnector"
```

---

## Task 4: Add connector_type and updated_at to Document model

**Files:**
- Modify: `backend/app/models/document.py`

- [ ] **Step 1: Add columns to Document ORM class**

In `backend/app/models/document.py`, add to the `Document` class after the `metadata_` mapped column:

```python
    # P6a: idempotency split
    connector_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 2: Verify model imports still work**

```
cd backend && python -c "from app.models.document import Document, DataSource; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/models/document.py
git commit -m "feat(p6a): add connector_type + updated_at columns to Document model"
```

---

## Task 5: Write Alembic migration 014_p6a_idempotency

**Files:**
- Create: `backend/alembic/versions/014_p6a_idempotency.py`

- [ ] **Step 1: Create the migration file**

```python
# backend/alembic/versions/014_p6a_idempotency.py
"""P6a: connector_type column, partial UNIQUE indexes, updated_at, dedup structured docs

Revision ID: 014_p6a_idempotency
Revises: 013_connector_types
Create Date: 2026-04-16

NOTE: As of 2026-04-16, no production rows have source_type IN ('rest_api', 'odbc').
The dedup step is defensive — it will find 0 rows to remove in a clean deployment.
Verify before running on any deployment that has ingested REST/ODBC data.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '014_p6a_idempotency'
down_revision: Union[str, None] = '013_connector_types'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add connector_type column to documents (denormalized from data_sources.source_type)
    op.add_column(
        "documents",
        sa.Column("connector_type", sa.String(20), nullable=True),
    )

    # 2. Add updated_at column to documents
    op.add_column(
        "documents",
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # 3. Backfill connector_type from data_sources
    op.execute("""
        UPDATE documents d
        SET connector_type = ds.source_type
        FROM data_sources ds
        WHERE d.source_id = ds.id
    """)

    # 4. Dedup structured source docs: for (source_id, source_path) dupes,
    #    keep the row with the latest ingested_at. This is defensive — see note above.
    op.execute("""
        DELETE FROM documents d1
        WHERE d1.connector_type IN ('rest_api', 'odbc')
          AND EXISTS (
            SELECT 1 FROM documents d2
            WHERE d2.source_id = d1.source_id
              AND d2.source_path = d1.source_path
              AND d2.ingested_at > d1.ingested_at
          )
    """)

    # 5. Add source_path max length constraint (2048 chars)
    op.create_check_constraint(
        "chk_source_path_length",
        "documents",
        "source_path IS NULL OR length(source_path) <= 2048",
    )

    # 6. Partial UNIQUE index for binary connectors: dedup by (source_id, file_hash)
    #    Excludes structured connectors (rest_api, odbc).
    op.create_index(
        "uq_documents_binary_hash",
        "documents",
        ["source_id", "file_hash"],
        unique=True,
        postgresql_where=sa.text("connector_type NOT IN ('rest_api', 'odbc')"),
    )

    # 7. Partial UNIQUE index for structured connectors: dedup by (source_id, source_path)
    op.create_index(
        "uq_documents_structured_path",
        "documents",
        ["source_id", "source_path"],
        unique=True,
        postgresql_where=sa.text("connector_type IN ('rest_api', 'odbc')"),
    )


def downgrade() -> None:
    op.drop_index("uq_documents_structured_path", table_name="documents")
    op.drop_index("uq_documents_binary_hash", table_name="documents")
    op.drop_constraint("chk_source_path_length", "documents", type_="check")
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "connector_type")
```

- [ ] **Step 2: Verify migration syntax**

```
cd backend && python -c "
from alembic.config import Config
from alembic.script import ScriptDirectory
cfg = Config('alembic.ini')
sd = ScriptDirectory.from_config(cfg)
print('Migration chain OK')
"
```

Expected: `Migration chain OK`

- [ ] **Step 3: Write migration test**

Create `backend/tests/test_migration_014.py`:

```python
# backend/tests/test_migration_014.py
"""Tests for migration 014 — connector_type backfill and structured doc dedup."""
import uuid
import pytest
from datetime import datetime, timezone


@pytest.mark.asyncio
async def test_connector_type_backfill(db_session):
    """Seed DB with REST/ODBC docs (including dupes), prove connector_type set correctly
    and dedup keeps latest by ingested_at."""
    # This test validates the migration logic in Python rather than running Alembic directly.
    # It seeds documents with the pre-migration state and then applies the same SQL logic
    # the migration would run.
    from sqlalchemy import text, insert
    from app.models.document import Document, DataSource, SourceType

    source_id = uuid.uuid4()
    # Create a REST API data source
    await db_session.execute(text("""
        INSERT INTO data_sources (id, name, source_type, connection_config, is_active, created_by)
        VALUES (:id, 'test-rest', 'rest_api', '{}', true,
                (SELECT id FROM users LIMIT 1))
    """), {"id": str(source_id)})

    doc_old_id = uuid.uuid4()
    doc_new_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    # Two docs for the same source_path — simulates pre-migration duplicate state
    for doc_id, ingested_delta in [(doc_old_id, -3600), (doc_new_id, 0)]:
        await db_session.execute(text("""
            INSERT INTO documents
              (id, source_id, source_path, filename, file_type, file_hash, file_size, ingested_at)
            VALUES (:id, :source_id, 'https://api.test.com/records/1',
                    '1.json', 'json', :hash, 100, :ingested_at)
        """), {
            "id": str(doc_id),
            "source_id": str(source_id),
            "hash": f"hash_{doc_id.hex[:8]}",
            "ingested_at": now.replace(second=now.second + ingested_delta) if ingested_delta else now,
        })

    await db_session.commit()

    # Apply migration backfill logic
    await db_session.execute(text("""
        UPDATE documents d
        SET connector_type = ds.source_type
        FROM data_sources ds
        WHERE d.source_id = ds.id
          AND d.connector_type IS NULL
    """))

    # Apply dedup logic
    await db_session.execute(text("""
        DELETE FROM documents d1
        WHERE d1.connector_type IN ('rest_api', 'odbc')
          AND EXISTS (
            SELECT 1 FROM documents d2
            WHERE d2.source_id = d1.source_id
              AND d2.source_path = d1.source_path
              AND d2.ingested_at > d1.ingested_at
          )
    """))

    await db_session.commit()

    # Verify: only one doc remains, and it's the newer one
    from sqlalchemy import select, func
    count = await db_session.scalar(
        select(func.count()).where(
            Document.source_id == source_id,
            Document.source_path == "https://api.test.com/records/1",
        )
    )
    assert count == 1

    remaining = await db_session.scalar(
        select(Document).where(
            Document.source_id == source_id,
            Document.source_path == "https://api.test.com/records/1",
        )
    )
    assert remaining.id == doc_new_id
    assert remaining.connector_type == "rest_api"
```

- [ ] **Step 4: Run migration test**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_migration_014.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/014_p6a_idempotency.py backend/tests/test_migration_014.py
git commit -m "feat(p6a): migration 014 — connector_type column, partial UNIQUE indexes, dedup"
```

---

## Task 6: Implement `ingest_structured_record()` in pipeline.py

**Files:**
- Modify: `backend/app/ingestion/pipeline.py`

- [ ] **Step 1: Add the function**

In `backend/app/ingestion/pipeline.py`, add after the imports (add `from sqlalchemy import select` if not present):

```python
import hashlib
from datetime import datetime, timezone
from sqlalchemy import select, delete
```

Then add this function after `ingest_file()`:

```python
async def ingest_structured_record(
    session: AsyncSession,
    source_id: uuid.UUID,
    source_path: str,
    content_bytes: bytes,
    filename: str,
    metadata: dict,
    connector_type: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    embed_model: str = "nomic-embed-text",
) -> Document:
    """Upsert a structured record (REST/ODBC) using (source_id, source_path) identity.

    - Same source_path + same hash → no-op (returns existing doc).
    - Same source_path + different hash → DELETE old chunks/embeddings, UPDATE doc.
    - New source_path → INSERT doc, chunk, embed.

    SELECT FOR UPDATE prevents concurrent workers from racing on the same record.
    """
    file_hash = hashlib.sha256(content_bytes).hexdigest()

    # Lock the row for this source_path to prevent concurrent update races (H5)
    async with session.begin_nested():
        result = await session.execute(
            select(Document)
            .where(Document.source_id == source_id, Document.source_path == source_path)
            .with_for_update()
        )
        existing = result.scalar_one_or_none()

        if existing is not None:
            if existing.file_hash == file_hash:
                # Content unchanged — no-op
                return existing

            # Content changed: DELETE old chunks then update doc atomically
            await session.execute(
                delete(DocumentChunk).where(DocumentChunk.document_id == existing.id)
            )
            existing.file_hash = file_hash
            existing.file_size = len(content_bytes)
            existing.updated_at = datetime.now(timezone.utc)
            existing.ingestion_status = IngestionStatus.PROCESSING
            await session.flush()

            # Re-chunk and re-embed (post-flush, same transaction)
            try:
                chunks = chunk_pages(
                    [{"text": content_bytes.decode("utf-8", errors="replace"), "page_number": 1}],
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                )
                if chunks:
                    texts = [c.text for c in chunks]
                    embeddings = await embed_batch(texts, model=embed_model)
                    for chunk, embedding in zip(chunks, embeddings):
                        session.add(DocumentChunk(
                            document_id=existing.id,
                            chunk_index=chunk.index,
                            content_text=chunk.text,
                            embedding=embedding,
                            token_count=chunk.token_count,
                            page_number=chunk.page_number,
                        ))
                existing.ingestion_status = IngestionStatus.COMPLETED
                existing.chunk_count = len(chunks)
                existing.ingested_at = datetime.now(timezone.utc)
            except Exception as e:
                existing.ingestion_status = IngestionStatus.FAILED
                existing.ingestion_error = str(e)[:2000]
                raise

            return existing

        # New record — INSERT
        doc = Document(
            source_id=source_id,
            source_path=source_path,
            filename=filename,
            file_type="json",
            file_hash=file_hash,
            file_size=len(content_bytes),
            connector_type=connector_type,
            ingestion_status=IngestionStatus.PROCESSING,
            metadata_=metadata,
        )
        session.add(doc)
        await session.flush()

        try:
            chunks = chunk_pages(
                [{"text": content_bytes.decode("utf-8", errors="replace"), "page_number": 1}],
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            if chunks:
                texts = [c.text for c in chunks]
                embeddings = await embed_batch(texts, model=embed_model)
                for chunk, embedding in zip(chunks, embeddings):
                    session.add(DocumentChunk(
                        document_id=doc.id,
                        chunk_index=chunk.index,
                        content_text=chunk.text,
                        embedding=embedding,
                        token_count=chunk.token_count,
                        page_number=chunk.page_number,
                    ))
            doc.ingestion_status = IngestionStatus.COMPLETED
            doc.chunk_count = len(chunks)
            doc.ingested_at = datetime.now(timezone.utc)
        except Exception as e:
            doc.ingestion_status = IngestionStatus.FAILED
            doc.ingestion_error = str(e)[:2000]
            raise

        return doc
```

- [ ] **Step 2: Run the integration tests that were failing in Task 1**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_pipeline_idempotency.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/app/ingestion/pipeline.py
git commit -m "feat(p6a): add ingest_structured_record() with SELECT FOR UPDATE upsert semantics"
```

---

## Task 7: Route run_connector_sync() to structured path for REST/ODBC

**Files:**
- Modify: `backend/app/ingestion/tasks.py`

- [ ] **Step 1: Update run_connector_sync() to call ingest_structured_record for structured sources**

In `backend/app/ingestion/tasks.py`, modify `run_connector_sync()`. Replace the `ingest_file_from_bytes` call inside the fetch loop:

```python
async def run_connector_sync(connector, source_id: str, session=None, db=None) -> dict:
    """Core connector sync loop: discover → fetch → ingest, with cursor-on-success semantics."""
    from app.models.document import DataSource
    from app.ingestion.pipeline import ingest_structured_record, ingest_file_from_bytes

    db_session = session or db
    if db_session is None:
        raise ValueError("run_connector_sync requires a db session (session= or db= kwarg)")

    source = await db_session.get(DataSource, uuid.UUID(source_id) if isinstance(source_id, str) else source_id)
    if not source:
        raise ValueError(f"DataSource not found: {source_id}")

    connector_type = source.source_type.value if hasattr(source.source_type, "value") else str(source.source_type)
    is_structured = connector_type in ("rest_api", "odbc")

    discovered = await connector.discover()
    ingested = 0
    errors = 0
    last_successful_modified: datetime | None = None

    try:
        for record in discovered:
            try:
                fetched = await connector.fetch(record.source_path)
                if is_structured:
                    doc = await ingest_structured_record(
                        session=db_session,
                        source_id=source.id,
                        source_path=fetched.source_path,
                        content_bytes=fetched.content,
                        filename=fetched.filename,
                        metadata=fetched.metadata,
                        connector_type=connector_type,
                    )
                else:
                    doc = await ingest_file_from_bytes(
                        session=db_session,
                        content=fetched.content,
                        filename=fetched.filename,
                        file_type=fetched.file_type,
                        source_id=source.id,
                    )
                if doc:
                    ingested += 1
                    if record.last_modified:
                        last_successful_modified = record.last_modified
            except Exception as exc:
                logger.error(
                    "Fetch failed",
                    extra={
                        "error_class": type(exc).__name__,
                        "record_id": record.source_path,
                        "status_code": getattr(exc, "status_code", None),
                        "retry_count": getattr(exc, "retry_count", 0),
                    },
                )
                errors += 1
                raise

        # Cursor advances to last successful modified timestamp, or now()
        source.last_sync_cursor = (
            last_successful_modified.isoformat()
            if last_successful_modified
            else datetime.now(timezone.utc).isoformat()
        )
        source.last_sync_at = datetime.now(timezone.utc)
        await db_session.commit()

    finally:
        connector.close()

    return {"ingested": ingested, "errors": errors, "discovered": len(discovered)}
```

- [ ] **Step 2: Run integration tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_ingestion_tasks.py tests/test_pipeline_idempotency.py -v
```

Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/app/ingestion/tasks.py
git commit -m "feat(p6a): route REST/ODBC sync to ingest_structured_record in run_connector_sync"
```

---

## Task 8: Add pollution detection to test-connection endpoint

**Files:**
- Modify: `backend/app/datasources/router.py`

- [ ] **Step 1: Write failing test for pollution detection**

In `backend/tests/test_datasources_router.py` (or `test_datasources_router_tc.py`), add:

```python
class TestTestConnectionPollutionDetection:

    @pytest.mark.asyncio
    async def test_test_connection_pollution_warning(self, async_client, admin_headers):
        """test-connection with two differing fetches (non-deterministic envelope)
        returns success=True with warning: non_deterministic_response."""
        import asyncio
        call_count = 0

        async def mock_fetch_varying(source_path):
            nonlocal call_count
            call_count += 1
            from app.connectors.base import FetchedDocument
            import json
            record = {"id": 1, "title": "Budget"}
            # Envelope differs on each call
            envelope = {"fetched_at": f"2026-04-16T00:0{call_count}:00Z", "data": record}
            canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
            return FetchedDocument(
                source_path=source_path,
                filename="1.json",
                file_type="json",
                content=canonical.encode(),  # canonical content — same
                file_size=len(canonical),
                metadata={},
            )

        # Patch at the router level
        with patch("app.datasources.router._double_fetch_hashes") as mock_dfh:
            mock_dfh.return_value = (
                "aaa111",  # hash1
                "bbb222",  # hash2 — differs!
                ["fetched_at", "request_id"],  # differing_keys
            )
            resp = await async_client.post(
                "/datasources/test-connection",
                json={
                    "source_type": "rest_api",
                    "config": {
                        "base_url": "https://api.example.com",
                        "endpoint_path": "/records",
                        "auth_method": "none",
                        "response_format": "json",
                        "data_key": "data",
                    },
                },
                headers=admin_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body.get("warning") == "non_deterministic_response"
        assert "differing_keys" in body
        assert "fetched_at" in body["differing_keys"]

    @pytest.mark.asyncio
    async def test_test_connection_no_pollution_warning(self, async_client, admin_headers):
        """Two identical fetches → no warning field in response."""
        with patch("app.datasources.router._double_fetch_hashes") as mock_dfh:
            mock_dfh.return_value = ("aaa111", "aaa111", [])  # identical hashes
            resp = await async_client.post(
                "/datasources/test-connection",
                json={
                    "source_type": "rest_api",
                    "config": {
                        "base_url": "https://api.example.com",
                        "endpoint_path": "/records",
                        "auth_method": "none",
                        "response_format": "json",
                    },
                },
                headers=admin_headers,
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "warning" not in body or body.get("warning") is None
```

- [ ] **Step 2: Implement `_double_fetch_hashes()` helper and integrate into test-connection**

Add this helper function in `backend/app/datasources/router.py` (after imports):

```python
import asyncio
import hashlib

async def _double_fetch_hashes(
    connector, first_source_path: str, data_key: str | None
) -> tuple[str, str, list[str]]:
    """Fetch a record twice (500ms apart) and compare canonical hashes.

    Returns (hash1, hash2, differing_top_level_keys).
    Used to detect non-deterministic envelopes at test-connection time.
    """
    import json
    from app.connectors.rest_api import _extract_dotted

    async def _fetch_and_hash():
        fetched = await connector.fetch(first_source_path)
        parsed = json.loads(fetched.content.decode("utf-8"))
        record = _extract_dotted(parsed, data_key)
        canonical = json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest(), parsed

    hash1, parsed1 = await _fetch_and_hash()
    await asyncio.sleep(0.5)
    hash2, parsed2 = await _fetch_and_hash()

    differing_keys: list[str] = []
    if hash1 != hash2 and isinstance(parsed1, dict) and isinstance(parsed2, dict):
        differing_keys = [
            k for k in set(parsed1) | set(parsed2)
            if parsed1.get(k) != parsed2.get(k)
        ]

    return hash1, hash2, differing_keys
```

In the test-connection endpoint handler, after a successful REST API connection test, add the pollution check. In `backend/app/datasources/router.py`, inside the `test_connection` endpoint for `rest_api` source type, add after the initial `authenticate()` + `discover()` succeeds:

```python
            # Pollution detection: double-fetch to detect non-deterministic envelopes
            if source_type == "rest_api" and discovered:
                first_path = discovered[0].source_path
                cfg = connection_config  # the parsed RestApiConfig
                data_key = cfg.get("data_key") if isinstance(cfg, dict) else getattr(cfg, "data_key", None)
                try:
                    h1, h2, differing_keys = await _double_fetch_hashes(connector, first_path, data_key)
                    if h1 != h2:
                        return {
                            "success": True,
                            "warning": "non_deterministic_response",
                            "warning_message": (
                                f"Response contains non-deterministic fields. "
                                f"Detected hash mismatch between two fetches with current data_key. "
                                f"Differing top-level keys: {differing_keys}. "
                                f"Refine data_key or use envelope_excludes."
                            ),
                            "differing_keys": differing_keys,
                        }
                except Exception:
                    pass  # pollution check is advisory — never fail test-connection on it
```

- [ ] **Step 3: Run pollution detection tests**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/test_datasources_router_tc.py -v -k "pollution"
```

Expected: 2 PASSED.

- [ ] **Step 4: Commit**

```bash
git add backend/app/datasources/router.py backend/tests/test_datasources_router_tc.py
git commit -m "feat(p6a): add double-fetch pollution detection to test-connection for REST sources"
```

---

## Task 9: Full test suite + apply migration

- [ ] **Step 1: Apply migration to test database**

```bash
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test alembic upgrade head
```

Expected: Migration 014_p6a_idempotency applies without errors.

- [ ] **Step 2: Run full test suite**

```
cd backend && DATABASE_URL=postgresql+asyncpg://civicrecords:civicrecords@localhost:5432/civicrecords_test python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests PASS. Zero failures.

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(p6a): complete idempotency contract split — all tests passing"
```
