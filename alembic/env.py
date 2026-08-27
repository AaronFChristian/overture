import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from overture.config import get_settings
from overture.db import models  # noqa: F401  -- populates Base.metadata, see db/base.py
from overture.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pull the URL from our own Settings rather than alembic.ini, so there's
# a single source of truth for the connection string (see D-0002).
#
# Percent signs must be escaped as %% before this call: Alembic's
# Config is backed by Python's configparser, whose default
# interpolation treats a bare % as the start of a %(name)s reference
# and raises ValueError on anything else. A URL-encoded password
# (e.g. Terraform's generated Postgres password, which contains
# %21, %23, etc. for special characters) looks exactly like malformed
# interpolation syntax to configparser. This never surfaced locally
# (docker-compose's password has no special characters) -- discovered
# via a real failed `alembic upgrade head` against Azure, the first
# time this project ever ran migrations against a
# Terraform-generated password. Reproduced and the fix verified
# directly (not assumed) before landing. See decisions.md D-0048.
config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
