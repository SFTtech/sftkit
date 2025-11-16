import asyncio
import logging
import ssl
from typing import Literal

import asyncpg

from sftkit.database._config import DatabaseConfig
from sftkit.database._connection import Connection, init_connection

logger = logging.getLogger(__name__)

Pool = asyncpg.Pool


async def create_db_pool(cfg: DatabaseConfig, n_connections: int) -> asyncpg.Pool:
    """
    get a connection pool to the database
    """
    pool = None

    retry_counter = 0
    next_log_at_retry = 0
    while pool is None:
        try:
            sslctx: ssl.SSLContext | Literal["verify-full", "prefer"] | None
            if cfg.sslrootcert and cfg.require_ssl:
                sslctx = ssl.create_default_context(
                    ssl.Purpose.SERVER_AUTH,
                    cafile=cfg.sslrootcert,
                )
                sslctx.check_hostname = True
            else:
                sslctx = "verify-full" if cfg.require_ssl else "prefer"

            pool = await asyncpg.create_pool(
                user=cfg.user,
                password=cfg.password,
                database=cfg.dbname,
                host=cfg.host,
                port=cfg.port,
                max_size=n_connections,
                connection_class=Connection,
                min_size=n_connections,
                ssl=sslctx,
                # the introspection query of asyncpg (defined as introspection.INTRO_LOOKUP_TYPES)
                # can take 1s with the jit.
                # the introspection is triggered to create converters for unknown types,
                # for example the integer[] (oid = 1007).
                # see https://github.com/MagicStack/asyncpg/issues/530
                server_settings={"jit": "off"},
                init=init_connection,
            )
        except Exception as e:  # pylint: disable=broad-except
            sleep_amount = 10
            if next_log_at_retry == retry_counter:
                logger.warning(
                    f"Failed to create database pool: {e}, waiting {sleep_amount} seconds and trying again..."
                )

            retry_counter += 1
            next_log_at_retry = min(retry_counter * 2, 2**9)
            await asyncio.sleep(sleep_amount)

    return pool
