"""ADR-0003 §5 — Three migration gates for the civiccore Alembic baseline.

These tests gate Phase 1 PR merge. They verify the three deployment scenarios
described in ADR-0003 §4:

* **Gate 1 (fresh-install)** — empty Postgres → records env.py with civiccore
  wiring → all 16 shared tables + 15 records-only tables present, both
  ``alembic_version`` heads stamped at the expected revisions.
* **Gate 2 (upgrade-from-v1.2)** — Postgres seeded with records HEAD 019 but
  no civiccore version table → ``alembic upgrade head`` → records head
  unchanged, civiccore baseline stamped, schema unchanged.
* **Gate 3 (reapplication idempotent)** — fully migrated DB → ``alembic
  upgrade head`` again → no "running upgrade" lines, no errors, both heads
  unchanged.

Fixture strategy
----------------
Each test gets its own unique-named ephemeral Postgres database created on the
project's running ``postgres`` container. We invoke records' Alembic via
``subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], ...)``
with ``DATABASE_URL`` overridden to point at that ephemeral DB. This mirrors
the pattern already used by ``conftest.setup_db`` and avoids
docker-in-docker complexity.

For **Gate 2** we seed the v1.2.x state by stamping ``alembic_version`` to
``019_encrypt_connection_config`` on a freshly-created (but otherwise empty)
DB **without** the civiccore wiring active. This is semantically equivalent
to "ran records v1.2.x migrations to head" for the purpose of the gate
assertion (the gate proves: civiccore baseline runs against a DB whose
records head is already 019, no-ops the table creates, and stamps its own
version table). We intentionally do *not* run the records chain a second
time before the test action; doing so would require either a separate
records-only env.py or a pre-civiccore tag of the records source — both
materially more complex than a stamp, with no additional coverage. If the
guard pass in records 001–019 is incorrect, Gate 1 catches it.

These tests are marked ``@pytest.mark.integration`` per ADR-0003 §5 and the
records CLAUDE.md "Integration Tests" section. They require the running
``postgres`` container plus ``civiccore`` installed in the ``api`` image
(after Subagent B's ``pyproject.toml`` change).
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Final

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

# ---------------------------------------------------------------------------
# Constants — hard-coded so assertions are unambiguous and any drift between
# this test file and the live schema is loud and obvious. See ADR-0003
# "Context — Shared vs records-owned schema" tables.
# ---------------------------------------------------------------------------

SHARED_TABLES: Final[frozenset[str]] = frozenset({
    # 001
    "users", "service_accounts", "audit_log",
    # 002
    "data_sources", "documents", "document_chunks",
    # 003
    "model_registry",
    # 006 (only this one of the three from 006)
    "exemption_rules",
    # 787207afc66a (6 of 12)
    "connector_templates", "departments", "system_catalog",
    "city_profile", "notification_templates", "prompt_templates",
    # 016
    "sync_run_log", "sync_failures",
})  # 16 total — see ADR-0003 §Context shared list

RECORDS_TABLES: Final[frozenset[str]] = frozenset({
    # 004
    "search_sessions", "search_queries", "search_results",
    # 005
    "records_requests", "request_documents", "document_cache",
    # 006 (records-only portion)
    "exemption_flags", "disclosure_templates",
    # 009
    "fee_waivers",
    # 787207afc66a (6 of 12)
    "fee_schedules", "fee_line_items", "notification_log",
    "request_messages", "request_timeline", "response_letters",
})  # 15 total — see ADR-0003 §Context records list

CIVICCORE_BASELINE_REV: Final[str] = "civiccore_0001_baseline_v1"
RECORDS_HEAD_REV: Final[str] = "019_encrypt_connection_config"

# v1.2.0 tag's records-side alembic head as captured 2026-04-24 from the v1.2.0
# git worktree. Source of truth: ADR-0003 §Context — records HEAD at v1.2.0 was 019.
# Verified by the schema_v1_2_0.sql fixture capture: the alembic_version row in
# the live capture DB held this exact revision before pg_dump.
# Intentionally separate from RECORDS_HEAD_REV: this constant marks the operator's
# STARTING revision (v1.2.0); RECORDS_HEAD_REV marks the EXPECTED revision after
# upgrade. They happen to be equal today because v1.3.0 adds no new records-side
# migrations — but if v1.4.0 adds one, only RECORDS_HEAD_REV moves; this stays.
V1_2_0_HEAD_REVISION: Final[str] = "019_encrypt_connection_config"

V1_2_0_FIXTURE_PATH: Final[Path] = (
    Path(__file__).parent / "fixtures" / "schema_v1_2_0.sql"
)

BACKEND_DIR: Final[Path] = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers — ephemeral test-DB creation on the existing postgres container.
# Mirrors conftest.setup_db's pattern (DROP DATABASE WITH (FORCE), CREATE
# EXTENSION vector, subprocess alembic). Uses sync psycopg2 to avoid event-loop
# entanglement with pytest-asyncio.
# ---------------------------------------------------------------------------


def _admin_sync_url() -> str:
    """Return a sync psycopg2 URL pointed at the cluster admin DB ('postgres')."""
    from app.config import settings
    base = settings.database_url.rsplit("/", 1)[0]
    sync_base = base.replace("postgresql+asyncpg", "postgresql+psycopg2")
    return f"{sync_base}/postgres"


def _ephemeral_db_url(db_name: str) -> str:
    """Return the asyncpg-style URL records' Alembic env.py will consume."""
    from app.config import settings
    base = settings.database_url.rsplit("/", 1)[0]
    return f"{base}/{db_name}"


def _ephemeral_db_sync_url(db_name: str) -> str:
    """Return the psycopg2-style URL for direct schema introspection."""
    return _ephemeral_db_url(db_name).replace("postgresql+asyncpg", "postgresql+psycopg2")


def _create_test_db(name: str) -> None:
    """CREATE DATABASE <name> on the cluster + install pgvector."""
    admin = create_engine(_admin_sync_url(), echo=False)
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()

    db = create_engine(_ephemeral_db_sync_url(name), echo=False)
    try:
        with db.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
    finally:
        db.dispose()


def _drop_test_db(name: str) -> None:
    admin = create_engine(_admin_sync_url(), echo=False)
    try:
        with admin.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()


def _run_alembic_upgrade_head(database_url: str) -> subprocess.CompletedProcess[str]:
    """Invoke records' Alembic against ``database_url`` via the programmatic API.

    Implementation note: alembic 1.18 changed its CLI config-file detection so
    that the default ``Config()`` no longer auto-discovers ``alembic.ini`` from
    cwd (``config_file_name`` returns ``None``), and even ``alembic -c
    alembic.ini upgrade head`` fails with "No 'script_location' key found in
    configuration." Records does not use the alembic CLI in production — its
    application startup runs ``command.upgrade(Config(<explicit path>), "head")``
    directly — so this helper mirrors that pattern. ADR-0003 §5 cares about the
    behavior of records' env.py wiring, not the CLI surface.

    The CompletedProcess return shape is preserved so callers can keep their
    ``returncode``/``stdout``/``stderr`` assertions unchanged.
    """
    import contextlib
    import io

    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    old_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url

    # Records' env.py captures ``settings`` at module-load via
    # ``from app.config import settings``, so reassigning ``app.config.settings``
    # would not update the env.py module's local reference. Instead mutate the
    # original Settings instance in place — every holder sees the new value.
    # Pydantic v1 BaseSettings permits attribute assignment; Pydantic v2's default
    # config is also non-frozen.
    #
    # Test-harness state only — production sets DATABASE_URL before the Alembic
    # process starts, so the singleton binds to the intended DB on first import
    # and never needs mutation.
    import app.config as _app_config

    saved_database_url = _app_config.settings.database_url
    _app_config.settings.database_url = database_url

    try:
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            try:
                command.upgrade(cfg, "head")
                rc = 0
            except SystemExit as exc:
                rc = int(exc.code) if isinstance(exc.code, int) else 1
            except Exception as exc:  # noqa: BLE001 — preserve details for the assertion message
                stderr_buf.write(f"\nException: {type(exc).__name__}: {exc}")
                rc = 1
    finally:
        _app_config.settings.database_url = saved_database_url
        if old_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_db_url

    return subprocess.CompletedProcess(
        args=["python", "-m", "alembic", "upgrade", "head"],
        returncode=rc,
        stdout=stdout_buf.getvalue(),
        stderr=stderr_buf.getvalue(),
    )


def _table_names(engine: Engine) -> set[str]:
    inspector = sa.inspect(engine)
    return set(inspector.get_table_names(schema="public"))


def _alembic_version(engine: Engine, table: str) -> str | None:
    """Return the single ``version_num`` from an alembic version table, or None."""
    with engine.connect() as conn:
        if not sa.inspect(conn).has_table(table):
            return None
        row = conn.execute(sa.text(f"SELECT version_num FROM {table}")).fetchone()
        return row[0] if row else None


def _column_set(engine: Engine, table: str) -> set[str]:
    inspector = sa.inspect(engine)
    if table not in inspector.get_table_names(schema="public"):
        return set()
    return {c["name"] for c in inspector.get_columns(table, schema="public")}


def _load_sql_fixture(sync_url: str, sql_path: Path) -> None:
    """Load a pg_dump --schema-only output into the target DB.

    Strips psql meta-commands (lines beginning with backslash), executes the
    rest in autocommit so multi-statement DDL applies cleanly. Used by Gate 2
    to seed a real v1.2.x schema before the upgrade-path test runs.
    """
    raw_sql = sql_path.read_text(encoding="utf-8")
    cleaned = "\n".join(
        line for line in raw_sql.splitlines() if not line.lstrip().startswith("\\")
    )
    sync = create_engine(sync_url, echo=False)
    try:
        with sync.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            conn.exec_driver_sql(cleaned)
    finally:
        sync.dispose()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fresh_db() -> Iterator[str]:
    """Empty Postgres database. Yields the asyncpg-style DATABASE_URL."""
    name = f"gate1_{uuid.uuid4().hex[:12]}"
    _create_test_db(name)
    try:
        yield _ephemeral_db_url(name)
    finally:
        _drop_test_db(name)


@pytest.fixture
def v1_2_0_real_schema_db() -> Iterator[str]:
    """Database loaded with the actual v1.2.0 schema dump, stamped at v1.2.0 head.

    Replaces the prior stamped-019 approximation. The fixture file at
    ``backend/tests/fixtures/schema_v1_2_0.sql`` was captured 2026-04-24 from
    a clean Postgres running the v1.2.0 records-side alembic chain cold,
    with no civiccore involvement (v1.2.0 predates Phase 1).

    The fixture file is purely structural (``pg_dump --schema-only``). The
    ``alembic_version`` row is INSERTed here, after fixture load, to declare
    the operator's starting revision. This separation keeps the SQL file
    schema-only and self-documents the revision the test cares about.
    """
    name = f"gate2_{uuid.uuid4().hex[:12]}"
    _create_test_db(name)
    sync_url = _ephemeral_db_sync_url(name)
    try:
        _load_sql_fixture(sync_url, V1_2_0_FIXTURE_PATH)
        sync = create_engine(sync_url, echo=False)
        try:
            with sync.connect() as conn:
                # Schema dump created the table; stamp the row to declare v1.2.0 head.
                conn.execute(
                    sa.text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
                    {"v": V1_2_0_HEAD_REVISION},
                )
                conn.commit()
        finally:
            sync.dispose()
        yield _ephemeral_db_url(name)
    finally:
        _drop_test_db(name)


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_gate1_fresh_install(fresh_db: str) -> None:
    """ADR-0003 §5 Gate 1 — fresh install creates all shared + records tables.

    Empty DB → ``alembic upgrade head`` (records env.py invokes civiccore
    runner first) → all 31 expected tables present, both heads stamped.
    """
    result = _run_alembic_upgrade_head(fresh_db)
    assert result.returncode == 0, (
        f"alembic upgrade head failed (rc={result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    sync = create_engine(_ephemeral_db_sync_url(fresh_db.rsplit("/", 1)[1]), echo=False)
    try:
        tables = _table_names(sync)

        missing_shared = SHARED_TABLES - tables
        assert not missing_shared, (
            f"Gate 1: missing shared tables {sorted(missing_shared)}; "
            f"present={sorted(tables)}"
        )

        missing_records = RECORDS_TABLES - tables
        assert not missing_records, (
            f"Gate 1: missing records-only tables {sorted(missing_records)}; "
            f"present={sorted(tables)}"
        )

        records_head = _alembic_version(sync, "alembic_version")
        assert records_head == RECORDS_HEAD_REV, (
            f"Gate 1: alembic_version expected {RECORDS_HEAD_REV!r}, got {records_head!r}"
        )

        civiccore_head = _alembic_version(sync, "alembic_version_civiccore")
        assert civiccore_head == CIVICCORE_BASELINE_REV, (
            f"Gate 1: alembic_version_civiccore expected {CIVICCORE_BASELINE_REV!r}, "
            f"got {civiccore_head!r}"
        )
    finally:
        sync.dispose()


@pytest.mark.integration
def test_gate2_upgrade_from_v1_2(v1_2_0_real_schema_db: str) -> None:
    """ADR-0003 §5 Gate 2 — operator on v1.2.0 upgrades to v1.3.0 cleanly.

    Starting state: real v1.2.0 schema (33 tables, alembic_version=019, no
    civiccore_version table). Action: ``alembic upgrade head`` (records env.py
    invokes the civiccore runner first per Phase 1 wiring, then records' own
    chain runs through its idempotency guards). Expected end state:

      * No errors during upgrade (idempotency guards correctly no-op every
        shared-table create_*, the records chain doesn't try to re-create
        anything that already exists from the v1.2.0 dump).
      * Records head UNCHANGED — v1.3.0 adds no new records-side migrations,
        so 019 stays 019.
      * Civiccore baseline now stamped at civiccore_0001_baseline_v1 — proves
        the civiccore runner actually executed during the upgrade.
      * All 16 shared tables retain their pre-upgrade column sets — schema-diff
        fidelity check that the prior stamped-019 fixture could not provide.
    """
    db_name = v1_2_0_real_schema_db.rsplit("/", 1)[1]
    sync_url = _ephemeral_db_sync_url(db_name)

    # --- Pre-upgrade invariants --------------------------------------------
    pre = create_engine(sync_url, echo=False)
    try:
        before_records_head = _alembic_version(pre, "alembic_version")
        assert before_records_head == V1_2_0_HEAD_REVISION, (
            f"Gate 2 fixture: expected starting alembic_version "
            f"{V1_2_0_HEAD_REVISION!r}, got {before_records_head!r}"
        )
        before_civiccore_head = _alembic_version(pre, "alembic_version_civiccore")
        assert before_civiccore_head is None, (
            "Gate 2 fixture: alembic_version_civiccore must NOT exist pre-upgrade — "
            "the fixture represents a pre-Phase-1 v1.2.0 operator who has never "
            "seen civiccore."
        )
        pre_tables = _table_names(pre)
        assert SHARED_TABLES.issubset(pre_tables), (
            f"Gate 2 fixture: v1.2.0 dump should contain all 16 shared tables. "
            f"Missing: {sorted(SHARED_TABLES - pre_tables)}"
        )
        # Capture column sets for shared tables BEFORE upgrade — used post-upgrade
        # to assert no schema drift from the idempotency guard execution path.
        pre_columns = {tbl: _column_set(pre, tbl) for tbl in SHARED_TABLES}
    finally:
        pre.dispose()

    # --- Action: records env.py runs civiccore runner first, then records chain
    result = _run_alembic_upgrade_head(v1_2_0_real_schema_db)
    assert result.returncode == 0, (
        f"Gate 2: alembic upgrade head failed (rc={result.returncode}):\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

    # --- Post-upgrade assertions ------------------------------------------
    post = create_engine(sync_url, echo=False)
    try:
        records_head = _alembic_version(post, "alembic_version")
        assert records_head == RECORDS_HEAD_REV, (
            f"Gate 2: records head must be unchanged at {RECORDS_HEAD_REV!r} "
            f"(v1.3.0 adds no new records migrations); got {records_head!r}."
        )

        civiccore_head = _alembic_version(post, "alembic_version_civiccore")
        assert civiccore_head == CIVICCORE_BASELINE_REV, (
            f"Gate 2: civiccore baseline must be stamped at {CIVICCORE_BASELINE_REV!r} "
            f"after upgrade (proves civiccore runner ran); got {civiccore_head!r}."
        )

        post_tables = _table_names(post)
        missing_shared = SHARED_TABLES - post_tables
        assert not missing_shared, (
            f"Gate 2: shared tables disappeared during upgrade: "
            f"{sorted(missing_shared)}"
        )

        # Schema-diff fidelity — every shared table's column set must be unchanged.
        # If an idempotency guard misfired and re-created a table, we'd see drift here.
        for tbl in sorted(SHARED_TABLES):
            post_cols = _column_set(post, tbl)
            assert post_cols == pre_columns[tbl], (
                f"Gate 2: column set for shared table {tbl!r} drifted during "
                f"upgrade. pre={sorted(pre_columns[tbl])} post={sorted(post_cols)}"
            )
    finally:
        post.dispose()


@pytest.mark.integration
def test_gate3_reapplication_idempotent(fresh_db: str) -> None:
    """ADR-0003 §5 Gate 3 — second ``alembic upgrade head`` is a complete no-op.

    Run ``alembic upgrade head`` once to reach the end-state of Gate 1, then
    run it again. The second run must:
      * Exit zero with no errors.
      * Emit no "Running upgrade" lines (proves no migration body executed).
      * Leave both ``alembic_version`` heads at their expected values.
    """
    first = _run_alembic_upgrade_head(fresh_db)
    assert first.returncode == 0, (
        f"Gate 3 setup (first upgrade) failed:\n"
        f"--- stdout ---\n{first.stdout}\n"
        f"--- stderr ---\n{first.stderr}"
    )

    second = _run_alembic_upgrade_head(fresh_db)
    assert second.returncode == 0, (
        f"Gate 3: second upgrade must succeed, got rc={second.returncode}:\n"
        f"--- stdout ---\n{second.stdout}\n"
        f"--- stderr ---\n{second.stderr}"
    )

    combined = (second.stdout or "") + "\n" + (second.stderr or "")
    # Alembic emits "Running upgrade <from> -> <to>" for each applied revision.
    # Idempotent re-run must not print any such line.
    assert "Running upgrade" not in combined, (
        "Gate 3: second upgrade must be a no-op — no 'Running upgrade' lines.\n"
        f"--- stdout ---\n{second.stdout}\n"
        f"--- stderr ---\n{second.stderr}"
    )

    sync = create_engine(_ephemeral_db_sync_url(fresh_db.rsplit("/", 1)[1]), echo=False)
    try:
        records_head = _alembic_version(sync, "alembic_version")
        assert records_head == RECORDS_HEAD_REV, (
            f"Gate 3: records head changed across re-run. "
            f"Expected {RECORDS_HEAD_REV!r}, got {records_head!r}."
        )

        civiccore_head = _alembic_version(sync, "alembic_version_civiccore")
        assert civiccore_head == CIVICCORE_BASELINE_REV, (
            f"Gate 3: civiccore head changed across re-run. "
            f"Expected {CIVICCORE_BASELINE_REV!r}, got {civiccore_head!r}."
        )
    finally:
        sync.dispose()
