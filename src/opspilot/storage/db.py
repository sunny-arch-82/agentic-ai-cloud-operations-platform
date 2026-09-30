"""Short bounded SQL transactions. Never interpolate user SQL."""

from sqlalchemy import create_engine, text

from opspilot.core.config import Settings


class Database:
    def __init__(self, settings: Settings):
        self.engine = create_engine(
            settings.database_url.get_secret_value(),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=2,
            connect_args={"connect_timeout": 5, "prepare_threshold": None},
        )

    def read(self, sql: str, params: dict | None = None):
        with self.engine.begin() as conn:
            conn.execute(text("SET LOCAL statement_timeout = '5000ms'"))
            conn.execute(text("SET TRANSACTION READ ONLY"))
            return [dict(r) for r in conn.execute(text(sql), params or {}).mappings()]

    def close(self):
        self.engine.dispose()
