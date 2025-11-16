from pydantic import BaseModel

from sftkit.database import Connection


class PgFunctionDef(BaseModel):
    proname: str
    pronamespace: int  # oid
    proowner: int  # oid
    prolang: int  # oid
    procost: float
    prorows: int
    provariadic: int  # oid
    prosupport: str
    prokind: str
    prosecdef: bool
    proleakproof: bool
    proisstrict: bool
    proretset: bool
    provolatile: str
    proparallel: str
    pronargs: int
    pronargdefaults: int
    prorettype: int  # oid
    proargtypes: list[int]  # oid
    proallargtypes: list[int] | None  # oid
    proargmodes: list[str] | None
    proargnames: list[str] | None
    # proargdefaults: pg_node_tree | None
    protrftypes: list[str] | None
    prosrc: str
    probin: str | None
    # prosqlbody: pg_node_tree | None
    proconfig: list[str] | None
    proacl: list[str] | None
    signature: str


async def list_functions(conn: Connection, schema: str) -> list[PgFunctionDef]:
    return await conn.fetch_many(
        PgFunctionDef,
        "select pg_proc.*, pg_get_function_identity_arguments(oid) as signature from pg_proc "
        "where pronamespace = $1::regnamespace and pg_proc.proname !~ '^pg_';",
        schema,
    )


class PgViewDef(BaseModel):
    table_name: str


async def list_views(conn: Connection, schema: str) -> list[PgViewDef]:
    return await conn.fetch_many(
        PgViewDef,
        "select table_name from information_schema.views where table_schema = $1 and table_name !~ '^pg_';",
        schema,
    )


class PgTriggerDef(BaseModel):
    trigger_name: str
    event_object_table: str


async def list_triggers(conn: Connection, schema: str) -> list[PgTriggerDef]:
    return await conn.fetch_many(
        PgTriggerDef,
        "select distinct on (trigger_name, event_object_table) trigger_name, event_object_table "
        "from information_schema.triggers where trigger_schema = $1",
        schema,
    )


class PgConstraintDef(BaseModel):
    conname: str
    relname: str
    contype: str


async def list_constraints(conn: Connection, schema: str) -> list[PgConstraintDef]:
    return await conn.fetch_many(
        PgConstraintDef,
        "select con.conname, rel.relname, con.contype "
        "from pg_catalog.pg_constraint con "
        "   join pg_catalog.pg_namespace nsp on nsp.oid = con.connamespace "
        "   left join pg_catalog.pg_class rel on rel.oid = con.conrelid "
        "where nsp.nspname = $1 and con.conname !~ '^pg_';",
        schema,
    )
