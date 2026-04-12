import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ingestion.chunker import chunk_pages
from app.ingestion.embedder import embed_batch
from app.ingestion.parsers import detect_parser, is_image_file
from app.ingestion.llm_extractor import extract_text_from_image, extract_text_from_scanned_pdf
from app.models.document import Document, DocumentChunk, IngestionStatus


def compute_file_hash(file_path: Path) -> str:
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
    file_hash = compute_file_hash(file_path)
    file_size = file_path.stat().st_size

    existing = await session.execute(
        select(Document).where(Document.source_id == source_id, Document.file_hash == file_hash)
    )
    existing_doc = existing.scalar_one_or_none()
    if existing_doc:
        return existing_doc

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
        pages_data = []
        if is_image_file(file_path):
            text = await extract_text_from_image(file_path)
            pages_data = [{"text": text, "page_number": 1}]
        else:
            parser = detect_parser(file_path)
            if parser is None:
                raise ValueError(f"No parser for file type: {file_path.suffix}")
            result = parser.parse(file_path)
            if result.metadata.get("likely_scanned") and result.file_type == "pdf":
                pages_data = await extract_text_from_scanned_pdf(file_path)
            else:
                pages_data = [{"text": p.text, "page_number": p.page_number} for p in result.pages]
            doc.metadata_ = result.metadata

        chunks = chunk_pages(pages_data, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

        if not chunks:
            doc.ingestion_status = IngestionStatus.COMPLETED
            doc.chunk_count = 0
            doc.ingested_at = datetime.now(timezone.utc)
            await session.commit()
            return doc

        texts = [c.text for c in chunks]
        embeddings = await embed_batch(texts, model=embed_model)

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
    from app.ingestion.parsers import _PARSERS, IMAGE_EXTENSIONS

    supported_extensions = set()
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
            await ingest_file(session=session, file_path=file_path, source_id=source_id, chunk_size=chunk_size, chunk_overlap=chunk_overlap, embed_model=embed_model)
            stats["processed"] += 1
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append({"file": str(file_path), "error": str(e)})

    return stats
