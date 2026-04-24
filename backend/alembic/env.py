import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.models import Base

config = context.config
if config.config_file_name is not None:
    # Phase 1 Part B: programmatic alembic invocation (test_civiccore_migration_gates)
    # runs env.py in the pytest parent process. fileConfig's default
    # disable_existing_loggers=True sets .disabled=True on every pre-existing
    # app.* logger, which survives beyond the migration call. Subsequent tests
    # that rely on caplog (e.g. test_structured_log_on_fetch_failure) then see
    # empty caplog.records because pytest's caplog.at_level does NOT reset the
    # .disabled attribute — it only adjusts .level and logging.disable().
    # disable_existing_loggers=False is the correct posture for alembic invoked
    # from within a Python app that owns its own logger hierarchy.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    # Phase-1 (civiccore extraction): bring civiccore migrations to head BEFORE
    # records' own chain. See ADR-0003 §3.
    #
    # Civiccore is invoked in a subprocess rather than inline because alembic's
    # `context._proxy` is process-global, not stacked. Calling civiccore's
    # `command.upgrade` (even on a separate connection) would tear down records'
    # active context proxy on civiccore's __exit__, causing
    # `AttributeError: 'NoneType' object has no attribute 'configure'` on the
    # next records env.py line. A subprocess gives civiccore a clean alembic
    # process. Civiccore opens its own DB connection from DATABASE_URL.
    import subprocess
    import sys

    subprocess.run(
        [
            sys.executable,
            "-c",
            "from civiccore.migrations.runner import upgrade_to_head; upgrade_to_head()",
        ],
        check=True,
    )

    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.database_url)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
