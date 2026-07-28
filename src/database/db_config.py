"""
Database connection settings, read from environment variables with sane
local-dev defaults. Never hardcode credentials in source — this is the
pattern a real production codebase uses (config injected via env/secret
manager, not committed to the repo).
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class DBConfig:
    host: str = os.getenv("CTR_DB_HOST", "localhost")
    port: int = int(os.getenv("CTR_DB_PORT", "5432"))
    dbname: str = os.getenv("CTR_DB_NAME", "ctr_platform")
    user: str = os.getenv("CTR_DB_USER", "postgres")
    password: str = os.getenv("CTR_DB_PASSWORD", "postgres")

    @property
    def dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.dbname} "
            f"user={self.user} password={self.password}"
        )

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.dbname}"
        )
