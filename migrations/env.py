"""
Alembic environment configuration.

Reads DATABASE_URL from .env so we don't hardcode credentials in
alembic.ini. Imports the app's Base metadata so autogenerate can
detect schema changes.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# Add project root to sys.path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base  # noqa: E402
from app import models  # noqa: E402,F401


# --------------------------------------------------
# LOAD ENV
# --------------------------------------------------

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL not set in .env. "
        "Add: DATABASE_URL=postgresql://postgres:...@localhost:5432/atoma_dev"
    )


# --------------------------------------------------
# ALEMBIC CONFIG
# --------------------------------------------------

config = context.config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


target_metadata = Base.metadata


# --------------------------------------------------
# OFFLINE MODE
# --------------------------------------------------

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# --------------------------------------------------
# ONLINE MODE
# --------------------------------------------------

def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()