import os
import random
import string
from pathlib import Path
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from pytest_asyncio import is_async_test

from sftkit.database import Connection, Database, DatabaseConfig, Pool, create_db_pool

ASSETS_DIR = Path(__file__).parent / "assets"


@pytest.fixture(scope="session")
def db_config() -> DatabaseConfig:
    return DatabaseConfig(
        host=os.environ.get("SFTKIT_TEST_DB_HOST"),
        port=os.environ.get("SFTKIT_TEST_DB_PORT", 5432),
        user=os.environ.get("SFTKIT_TEST_DB_USER"),
        password=os.environ.get("SFTKIT_TEST_DB_PASSWORD"),
        dbname=os.environ.get("SFTKIT_TEST_DB_DBNAME", "sftkit_test"),
    )


@pytest_asyncio.fixture(loop_scope="session", scope="session")
async def static_test_db_pool(db_config: DatabaseConfig) -> AsyncGenerator[Pool, None]:
    pool = await create_db_pool(cfg=db_config, n_connections=10)
    yield pool
    await pool.close()


@pytest_asyncio.fixture(loop_scope="session", scope="function")
async def test_db(
    db_config: DatabaseConfig, static_test_db_pool: Pool
) -> AsyncGenerator[Database, None]:
    dbname = "".join(random.choices(string.ascii_lowercase, k=20))
    cfg = db_config.model_copy()
    cfg.dbname = dbname
    await static_test_db_pool.execute(f'create database "{dbname}"')
    if db_config.user:
        await static_test_db_pool.execute(
            f'alter database "{dbname}" owner to "{db_config.user}"'
        )
    mininal_db_assets = ASSETS_DIR / "minimal_db"
    database = Database(
        config=cfg,
        migrations_dir=mininal_db_assets / "migrations",
        code_dir=mininal_db_assets / "code",
    )
    await database.apply_migrations()
    yield database
    await static_test_db_pool.execute(f'drop database "{dbname}"')


@pytest_asyncio.fixture(loop_scope="session", scope="function")
async def test_db_pool(test_db: Database) -> AsyncGenerator[Pool, None]:
    pool = await test_db.create_pool(n_connections=10)
    yield pool
    await pool.close()


@pytest_asyncio.fixture(loop_scope="session", scope="function")
async def test_db_conn(test_db_pool: Pool) -> AsyncGenerator[Connection, None]:
    async with test_db_pool.acquire() as conn:
        yield conn


def pytest_collection_modifyitems(items):
    pytest_asyncio_tests = (item for item in items if is_async_test(item))
    session_scope_marker = pytest.mark.asyncio(loop_scope="session")
    for async_test in pytest_asyncio_tests:
        async_test.add_marker(session_scope_marker, append=False)
