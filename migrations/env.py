from alembic import context
from sqlalchemy import create_engine

from opspilot.core.config import Settings

config = context.config
engine = create_engine(Settings().database_url.get_secret_value())
with engine.connect() as connection:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
engine.dispose()
