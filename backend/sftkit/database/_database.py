from pathlib import Path

from sftsdk.database._config import DatabaseConfig
from sftsdk.database._migrations import SchemaMigration, apply_migrations
from sftsdk.database._pool import Pool, create_db_pool


class Database:
    def __init__(self, config: DatabaseConfig, migrations_dir: Path, code_dir: Path):
        self.config = config
        self.migrations_dir = migrations_dir
        self.code_dir = code_dir

    async def create_pool(self, n_connections=10) -> Pool:
        return await create_db_pool(self.config, n_connections=n_connections)

    async def apply_migrations(self, until_migration: str | None = None) -> None:
        pool = await self.create_pool(n_connections=1)
        try:
            await apply_migrations(
                db_pool=pool,
                migration_path=self.migrations_dir,
                code_path=self.code_dir,
                until_migration=until_migration,
            )
        finally:
            await pool.close()

    async def list_migrations(self) -> list[SchemaMigration]:
        return SchemaMigration.migrations_from_dir(self.migrations_dir)
