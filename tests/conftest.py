import asyncio
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from opspilot.core.config import Settings
from opspilot.rag.ingestion import ingest
from opspilot.storage.db import Database
from opspilot.storage.fixtures import seed_operational

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def settings():
    return Settings(_env_file=None, mode="demo", data_dir=ROOT / "data/sample")


@pytest.fixture(scope="session")
def integration_settings():
    url = os.environ.get("OPSPILOT_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "Set OPSPILOT_TEST_DATABASE_URL to an isolated PostgreSQL/pgvector test database"
        )
    return Settings(_env_file=None, mode="demo", database_url=url, data_dir=ROOT / "data/sample")


@pytest.fixture(scope="session")
def db(integration_settings):
    old_url = os.environ.get("OPSPILOT_DATABASE_URL")
    old_mode = os.environ.get("OPSPILOT_MODE")
    os.environ["OPSPILOT_DATABASE_URL"] = integration_settings.database_url.get_secret_value()
    os.environ["OPSPILOT_MODE"] = "demo"
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    database = Database(integration_settings)
    seed_operational(database, integration_settings.data_dir)
    asyncio.run(ingest(database, integration_settings))
    yield database
    database.close()
    for key, previous in [("OPSPILOT_DATABASE_URL", old_url), ("OPSPILOT_MODE", old_mode)]:
        if previous is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous
