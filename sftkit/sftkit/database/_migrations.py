import logging
import os
import re
from pathlib import Path
from typing import Iterable, Optional, Union

import asyncpg

logger = logging.getLogger(__name__)

MIGRATION_VERSION_RE = re.compile(r"^-- migration: (?P<version>\w+)$")
MIGRATION_REQURES_RE = re.compile(r"^-- requires: (?P<version>\w+)$")
MIGRATION_TABLE = "schema_revision"


async def _run_postgres_code(conn: asyncpg.Connection, code: str, file_name: Path):
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


async def _drop_all_views(conn: asyncpg.Connection, schema: str):
    # TODO: we might have to find out the dependency order of the views if drop cascade does not work
    result = await conn.fetch(
        "select table_name from information_schema.views where table_schema = $1 and table_name !~ '^pg_';",
        schema,
    )
    views = [row["table_name"] for row in result]
    if len(views) == 0:
        return

    # we use drop if exists here as the cascade dropping might lead the view to being already dropped
    # due to being a dependency of another view
    drop_statements = "\n".join([f"drop view if exists {view} cascade;" for view in views])
    await conn.execute(drop_statements)


async def _drop_all_triggers(conn: asyncpg.Connection, schema: str):
    result = await conn.fetch(
        "select distinct on (trigger_name, event_object_table) trigger_name, event_object_table "
        "from information_schema.triggers where trigger_schema = $1",
        schema,
    )
    statements = []
    for row in result:
        trigger_name = row["trigger_name"]
        table = row["event_object_table"]
        statements.append(f"drop trigger {trigger_name} on {table};")

    if len(statements) == 0:
        return

    drop_statements = "\n".join(statements)
    await conn.execute(drop_statements)


async def _drop_all_functions(conn: asyncpg.Connection, schema: str):
    result = await conn.fetch(
        "select proname, pg_get_function_identity_arguments(oid) as signature, prokind from pg_proc "
        "where pronamespace = $1::regnamespace;",
        schema,
    )
    drop_statements = []
    for row in result:
        kind = row["prokind"].decode("utf-8")
        name = row["proname"]
        signature = row["signature"]
        if kind in ("f", "w"):
            drop_type = "function"
        elif kind == "a":
            drop_type = "aggregate"
        elif kind == "p":
            drop_type = "procedure"
        else:
            raise RuntimeError(f'Unknown postgres function type "{kind}"')

        drop_statements.append(f"drop {drop_type} {name}({signature}) cascade;")

    if len(drop_statements) == 0:
        return

    drop_code = "\n".join(drop_statements)
    await conn.execute(drop_code)


async def _drop_all_constraints(conn: asyncpg.Connection, schema: str):
    """drop all constraints in the given schema which are not unique, primary or foreign key constraints"""
    result = await conn.fetch(
        "select con.conname as constraint_name, rel.relname as table_name, con.contype as constraint_type "
        "from pg_catalog.pg_constraint con "
        "   join pg_catalog.pg_namespace nsp on nsp.oid = con.connamespace "
        "   left join pg_catalog.pg_class rel on rel.oid = con.conrelid "
        "where nsp.nspname = $1 and con.conname !~ '^pg_' "
        "   and con.contype != 'p' and con.contype != 'f' and con.contype != 'u';",
        schema,
    )
    constraints = []
    for row in result:
        constraint_name = row["constraint_name"]
        constraint_type = row["constraint_type"].decode("utf-8")
        table_name = row["table_name"]
        if constraint_type == "c":
            constraints.append(f"alter table {table_name} drop constraint {constraint_name};")
        elif constraint_type == "t":
            constraints.append(f"drop constraint trigger {constraint_name};")
        else:
            raise RuntimeError(f'Unknown constraint type "{constraint_type}" for constraint "{constraint_name}"')

    if len(constraints) == 0:
        return

    drop_statements = "\n".join(constraints)
    await conn.execute(drop_statements)


async def _drop_db_code(conn: asyncpg.Connection, schema: str):
    await _drop_all_triggers(conn, schema=schema)
    await _drop_all_functions(conn, schema=schema)
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


async def reload_db_code(conn: asyncpg.Connection, code_path: Path):
    await _drop_db_code(conn, schema="public")
    await apply_db_code(conn, code_path)


async def apply_migrations(
    db_pool: asyncpg.Pool, migration_path: Path, code_path: Path, until_migration: str | None = None
):
    migrations = SchemaMigration.migrations_from_dir(migration_path)

    async with db_pool.acquire() as conn:
        async with conn.transaction(isolation="serializable"):
            await conn.execute(f"create table if not exists {MIGRATION_TABLE} (version text not null primary key)")

            curr_migration = await conn.fetchval(f"select version from {MIGRATION_TABLE} limit 1")

            await _drop_db_code(conn=conn, schema="public")
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
