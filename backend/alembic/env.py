import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# Ensure the backend directory is on sys.path so `import db` / `import models` works.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load app's Base metadata (importing db first registers the engine/Base, then
# models registers all ORM classes against that Base).
import db  # noqa: E402  (side-effect: loads DATABASE_URL from .env)
import models  # noqa: E402  (side-effect: registers all ORM models)
from db import Base  # noqa: E402

# Alembic Config object — gives access to alembic.ini values.
config = context.config

# Override sqlalchemy.url with the value from the app's own DATABASE_URL env var
# so we never rely on the hardcoded placeholder in alembic.ini.
config.set_main_option("sqlalchemy.url", db.DATABASE_URL)

# Set up loggers as defined in alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout, no live connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect to the DB and apply)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
