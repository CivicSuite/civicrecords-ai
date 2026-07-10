"""CivicSunshine ingestion orchestration.

Parser, chunker, embedding, and pgvector storage primitives now live in
``civiccore.ingest``. This package keeps Records-specific Celery tasks,
scheduler, connector sync orchestration, and cron compatibility helpers.
"""
