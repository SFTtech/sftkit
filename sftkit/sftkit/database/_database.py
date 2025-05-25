from pathlib import Path

from ._attach import psql_attach
from ._config import DatabaseConfig
from ._migrations import MIGRATION_TABLE, SchemaMigration, apply_migrations, reload_db_code
from ._pool import Pool, create_db_pool


class Database:
    def __init__(self, config: DatabaseConfig, migrations_dir: Path, code_dir: Path):
        self.config = config
        self.migrations_dir = migrations_dir
        self.code_dir = code_dir

        self._pool: Pool | None = None

    async def create_pool(self, n_connections=10) -> Pool:
        self._pool = await create_db_pool(self.config, n_connections=n_connections)
        return self._pool

    async def apply_migrations(
        self,
        until_migration: str | None = None,
        function_blacklist: list[str] | None = None,
        function_blacklist_prefix: str | None = None,
    ) -> None:
        pool = await self.create_pool(n_connections=1)
        try:
            await apply_migrations(
                db_pool=pool,
                migration_path=self.migrations_dir,
                code_path=self.code_dir,
                until_migration=until_migration,
                function_blacklist=function_blacklist,
                function_blacklist_prefix=function_blacklist_prefix,
            )
        finally:
            await pool.close()

    async def attach(self):
        return await psql_attach(self.config)

    async def reload_code(
        self,
        function_blacklist: list[str] | None = None,
        function_blacklist_prefix: str | None = None,
    ):
        pool = await self.create_pool(n_connections=1)

        try:
            async with pool.acquire() as conn:
                async with conn.transaction(isolation="serializable"):
                    await reload_db_code(
                        conn,
                        code_path=self.code_dir,
                        function_blacklist=function_blacklist,
                        function_blacklist_prefix=function_blacklist_prefix,
                    )
        finally:
            await pool.close()

    def list_migrations(self) -> list[SchemaMigration]:
        return SchemaMigration.migrations_from_dir(self.migrations_dir)

    async def get_current_migration_version(self) -> str | None:
        assert self._pool is not None
        revision = await self._pool.fetchval(f"select version from {MIGRATION_TABLE} limit 1")
        return revision

    def get_desired_migration_version(self) -> str | None:
        desired_migration = SchemaMigration.latest_migration(self.migrations_dir)
        if desired_migration is None:
            return None
        return desired_migration.version
