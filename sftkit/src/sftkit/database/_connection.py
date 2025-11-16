import json
from typing import Type, TypeVar

import asyncpg
from pydantic import BaseModel

from sftkit.error import NotFound

T = TypeVar("T", bound=BaseModel)


class Connection(asyncpg.Connection):
    async def fetch_one(self, model: Type[T], query: str, *args) -> T:
        result: asyncpg.Record | None = await self.fetchrow(query, *args)
        if result is None:
            raise NotFound(element_type=model.__name__)

        return model.model_validate(dict(result))

    async def fetch_maybe_one(self, model: Type[T], query: str, *args) -> T | None:
        result: asyncpg.Record | None = await self.fetchrow(query, *args)
        if result is None:
            return None

        return model.model_validate(dict(result))

    async def fetch_many(self, model: Type[T], query: str, *args) -> list[T]:
        # TODO: also allow async cursor
        results: list[asyncpg.Record] = await self.fetch(query, *args)
        return [model.model_validate(dict(r)) for r in results]


async def init_connection(conn: Connection):
    await conn.set_type_codec("json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")
