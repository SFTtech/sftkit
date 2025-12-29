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
    """
    List all functions which are owned by the current database user and do not belong to any extension.
    """
    return await conn.fetch_many(
        PgFunctionDef,
        "select p.*, pg_get_function_identity_arguments(p.oid) as signature from pg_proc as p "
        "join pg_roles as a on p.proowner = a.oid "
        "where p.pronamespace = $1::regnamespace and a.rolname = CURRENT_USER "
        "  and not exists(select from pg_depend as d where d.objid = p.oid and d.deptype = 'e')",
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
