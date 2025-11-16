import logging
import os
import re
from pathlib import Path
from typing import Iterable, Optional, Union

import asyncpg

from sftkit.database import Connection
from sftkit.database.introspection import list_constraints, list_functions, list_triggers, list_views

logger = logging.getLogger(__name__)

MIGRATION_VERSION_RE = re.compile(r"^-- migration: (?P<version>\w+)$")
MIGRATION_REQURES_RE = re.compile(r"^-- requires: (?P<version>\w+)$")
MIGRATION_TABLE = "schema_revision"


async def _run_postgres_code(conn: Connection, code: str, file_name: Path):
    if all(line.startswith("--") for line in code.splitlines()):
        return
    try:
        await conn.execute(code)
    except asyncpg.exceptions.PostgresSyntaxError as exc:
        exc_dict = exc.as_dict()
        position = int(exc_dict["position"])
        message = exc_dict["message"]
        lineno = code.count("\n", 0, position) + 1
        raise ValueError(
            f"Syntax error when executing SQL code at character {position} ({file_name!s}:{lineno}): {message!r}"
        ) from exc
    except asyncpg.exceptions.SyntaxOrAccessError as exc:
        exc_dict = exc.as_dict()
        message = exc_dict["message"]
        raise ValueError(f"Syntax or Access error when executing SQL code ({file_name!s}): {message!r}") from exc


async def _drop_all_views(conn: Connection, schema: str):
    # TODO: we might have to find out the dependency order of the views if drop cascade does not work
    views = await list_views(conn, schema)
    if len(views) == 0:
        return

    # we use drop if exists here as the cascade dropping might lead the view to being already dropped
    # due to being a dependency of another view
    drop_statements = "\n".join([f"drop view if exists {view.table_name} cascade;" for view in views])
    await conn.execute(drop_statements)


async def _drop_all_triggers(conn: Connection, schema: str):
    triggers = await list_triggers(conn, schema)
    statements = []
    for trigger in triggers:
        statements.append(f'drop trigger "{trigger.trigger_name}" on "{trigger.event_object_table}";')

    if len(statements) == 0:
        return

    drop_statements = "\n".join(statements)
    await conn.execute(drop_statements)


async def _drop_all_functions(
    conn: Connection, schema: str, function_blacklist: list[str], function_blacklist_prefix: str | None
):
    blacklist = set(function_blacklist)
    funcs = await list_functions(conn, schema)
    drop_statements = []
    for func in funcs:
        if func.prokind in ("f", "w"):
            drop_type = "function"
        elif func.prokind == "a":
            drop_type = "aggregate"
        elif func.prokind == "p":
            drop_type = "procedure"
        else:
            raise RuntimeError(f'Unknown postgres function type "{func.prokind}"')

        if func.proname in blacklist:
            continue
        if function_blacklist_prefix is not None and func.proname.startswith(function_blacklist_prefix):
            continue

        drop_statements.append(f'drop {drop_type} "{func.proname}"({func.signature}) cascade;')

    if len(drop_statements) == 0:
        return

    drop_code = "\n".join(drop_statements)
    await conn.execute(drop_code)


async def _drop_all_constraints(conn: Connection, schema: str):
    """drop all constraints in the given schema which are not unique, primary or foreign key constraints"""
    constraints = await list_constraints(conn, schema)
    drop_statements = []
    for constraint in constraints:
        constraint_name = constraint.conname
        constraint_type = constraint.contype
        table_name = constraint.relname
        if constraint_type in ("p", "f", "u", "n"):
            continue
        if constraint_type == "c":
            drop_statements.append(f'alter table "{table_name}" drop constraint "{constraint_name}";')
        elif constraint_type == "t":
            drop_statements.append(f"drop constraint trigger {constraint_name};")
        else:
            raise RuntimeError(f'Unknown constraint type "{constraint_type}" for constraint "{constraint_name}"')

    if len(drop_statements) == 0:
        return

    drop_cmd = "\n".join(drop_statements)
    await conn.execute(drop_cmd)


async def _drop_db_code(
    conn: Connection, schema: str, function_blacklist: list[str], function_blacklist_prefix: str | None
):
    await _drop_all_triggers(conn, schema=schema)
    await _drop_all_functions(
        conn, schema=schema, function_blacklist=function_blacklist, function_blacklist_prefix=function_blacklist_prefix
    )
    await _drop_all_views(conn, schema=schema)
    await _drop_all_constraints(conn, schema=schema)


def _sql_is_empty(sql_code_lines: Iterable[str]):
    for line in sql_code_lines:
        stripped = line.strip()
        if stripped != "" and not stripped.startswith("--"):
            return False
    return True


class SchemaMigration:
    def __init__(self, file_name: Path, code: str, version: str, requires: Optional[str]):
        self.file_name = file_name
        self.code = code
        self.version = version
        self.requires = requires

    async def apply(self, conn):
        logger.info(f"Applying migration {self.file_name.name} with version {self.version}")
        if self.requires:
            version = await conn.fetchval(
                f"update {MIGRATION_TABLE} set version = $1 where version = $2 returning version",
                self.version,
                self.requires,
            )
            if version != self.version:
                raise ValueError(f"Found other migration present than {self.requires} which was required")
        else:
            n_table = await conn.fetchval(f"select count(*) from {MIGRATION_TABLE}")
            if n_table != 0:
                raise ValueError(
                    f"Could not apply migration {self.version} as there appears to be a migration present,"
                    f"none was expected"
                )
            await conn.execute(f"insert into {MIGRATION_TABLE} (version) values ($1)", self.version)

        # now we can actually apply the migration
        await _run_postgres_code(conn, self.code, self.file_name)

    @classmethod
    def latest_migration(cls, migrations_dir: Path) -> Union["SchemaMigration", None]:
        migrations = cls.migrations_from_dir(migrations_dir)
        if len(migrations) == 0:
            return None
        return migrations[-1]

    @classmethod
    def migrations_from_dir(cls, migrations_dir: Path) -> list["SchemaMigration"]:
        """
        returns an ordered list of migrations with their dependencies resolved
        """
        migrations = []
        for migration in sorted(migrations_dir.glob("*.sql")):
            migration_content = migration.read_text("utf-8")
            lines = migration_content.splitlines()
            if _sql_is_empty(lines):
                logger.debug(f"Migration {migration} is empty")

            if (version_match := MIGRATION_VERSION_RE.match(lines[0])) is None:
                raise ValueError(
                    f"Invalid version string in migration {migration}, " f"should be of form '-- migration: <name>'"
                )
            if (requires_match := MIGRATION_REQURES_RE.match(lines[1])) is None:
                raise ValueError(
                    f"Invalid requires string in migration {migration}, " f"should be of form '-- requires: <name>'"
                )

            version = version_match["version"]
            requires: Optional[str] = requires_match["version"]

            if requires == "null":
                requires = None

            migrations.append(
                cls(
                    migration,
                    migration_content,
                    version,
                    requires,
                )
            )

        if len(migrations) == 0:
            return migrations

        # now for the purpose of sorting the migrations according to their dependencies
        first_migration = next((x for x in migrations if x.requires is None), None)
        if first_migration is None:
            raise ValueError("Could not find a migration without any dependencies")

        # TODO: detect migration branches
        sorted_migrations = [first_migration]
        while len(sorted_migrations) < len(migrations):
            curr_migration = sorted_migrations[-1]
            next_migration = next((x for x in migrations if x.requires == curr_migration.version), None)
            if next_migration is None:
                raise ValueError(f"Could not find the successor to migration {curr_migration.version}")
            sorted_migrations.append(next_migration)

        return sorted_migrations


async def apply_db_code(conn: asyncpg.Connection, code_path: Path):
    for code_file in sorted(code_path.glob("*.sql")):
        logger.info(f"Applying database code file {code_file.name}")
        code = code_file.read_text("utf-8")
        await _run_postgres_code(conn, code, code_file)


async def reload_db_code(
    conn: asyncpg.Connection,
    code_path: Path,
    function_blacklist: list[str] | None = None,
    function_blacklist_prefix: str | None = None,
):
    _function_blacklist = function_blacklist or []
    await _drop_db_code(
        conn,
        schema="public",
        function_blacklist=_function_blacklist,
        function_blacklist_prefix=function_blacklist_prefix,
    )
    await apply_db_code(conn, code_path)


async def apply_migrations(
    db_pool: asyncpg.Pool,
    migration_path: Path,
    code_path: Path,
    until_migration: str | None = None,
    function_blacklist: list[str] | None = None,
    function_blacklist_prefix: str | None = None,
):
    migrations = SchemaMigration.migrations_from_dir(migration_path)

    async with db_pool.acquire() as conn:
        async with conn.transaction(isolation="serializable"):
            await conn.execute(f"create table if not exists {MIGRATION_TABLE} (version text not null primary key)")

            curr_migration = await conn.fetchval(f"select version from {MIGRATION_TABLE} limit 1")

            _function_blacklist = function_blacklist or []
            await _drop_db_code(
                conn=conn,
                schema="public",
                function_blacklist=_function_blacklist,
                function_blacklist_prefix=function_blacklist_prefix,
            )
            # TODO: perform a dry run to check all migrations before doing anything

            found = curr_migration is None
            for migration in migrations:
                if found:
                    await migration.apply(conn)

                if migration.version == curr_migration:
                    found = True

                if until_migration is not None and migration.version == until_migration:
                    return

            if not found:
                raise ValueError(f"Unknown migration {curr_migration} present in database")

            await apply_db_code(conn=conn, code_path=code_path)


def create_migration(migration_path: Path, name: str):
    migrations = SchemaMigration.migrations_from_dir(migration_path)
    filename = f"{str(len(migrations)).zfill(4)}-{name}.sql"
    new_revision_version = os.urandom(4).hex()
    file_path = migration_path / filename

    prev_migration_version = migrations[-1].version if len(migrations) > 0 else "null"
    migration_content = f"-- migration: {new_revision_version}\n-- requires: {prev_migration_version}\n"
    with file_path.open("w+") as f:
        f.write(migration_content)

    logger.info(f"Created new migration {file_path}")
